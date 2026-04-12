import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlmodel import Session

from .db import create_session
from .models import Job, JobStatus
from .simulation import execute_graph_job, run_simulation_task, update_job_record, refresh_job_record

logger = logging.getLogger("worker")
WORKER_COUNT = 2
WORKER_SLEEP = 1.0
STALLED_THRESHOLD_SECONDS = 30
CLAIM_LOCK = asyncio.Lock()


def _score_job(job: Job) -> int:
    age_minutes = max(0, int((datetime.utcnow() - job.created_at).total_seconds() / 60))
    age_bonus = age_minutes // 5
    return max(0, job.priority - age_bonus)


def claim_next_job() -> Optional[Job]:
    with create_session() as session:
        now = datetime.utcnow()
        statement = select(Job).where(
            Job.status == JobStatus.queued,
            Job.is_cancelled == False,
            (Job.run_after == None) | (Job.run_after <= now),
        )
        candidates = list(session.exec(statement).unique().all())
        if not candidates:
            return None
        candidates.sort(key=_score_job)
        job = candidates[0]
        job.status = JobStatus.running
        job.last_heartbeat = now
        job.attempts += 1
        job.updated_at = now
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def recover_stale_jobs() -> None:
    with create_session() as session:
        stale_at = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD_SECONDS)
        statement = select(Job).where(Job.status == JobStatus.running, Job.last_heartbeat != None, Job.last_heartbeat < stale_at)
        stale_jobs = session.exec(statement).all()
        for job in stale_jobs:
            logger.warning("Recovering stale job %s (last heartbeat %s)", job.id, job.last_heartbeat)
            if job.is_cancelled:
                job.status = JobStatus.cancelled
            elif job.is_paused:
                job.status = JobStatus.paused
            else:
                job.status = JobStatus.queued
            job.updated_at = datetime.utcnow()
            session.add(job)
        session.commit()


async def execute_job(job_id: int) -> None:
    job = refresh_job_record(job_id)
    if not job:
        return

    try:
        if job.graph:
            result = await execute_graph_job(job)
        else:
            result = await run_simulation_task(job.id, job.name)

        if result == "pause":
            update_job_record(job.id, status=JobStatus.paused, is_paused=True, last_heartbeat=datetime.utcnow())
        elif result == "cancel":
            update_job_record(job.id, status=JobStatus.cancelled, is_cancelled=True, last_heartbeat=datetime.utcnow())
        else:
            update_job_record(job.id, status=JobStatus.completed, progress=100, last_heartbeat=datetime.utcnow())
    except Exception as exc:
        job = refresh_job_record(job_id)
        if not job:
            return
        message = str(exc)
        next_status = JobStatus.failed
        run_after = None
        if job.attempts < job.max_retries:
            next_status = JobStatus.queued
            run_after = datetime.utcnow() + timedelta(seconds=5 * job.attempts)
            logger.warning("Retrying job %s after error: %s", job.id, message)
        update_job_record(job.id, status=next_status, last_error=message, run_after=run_after, last_heartbeat=datetime.utcnow())


async def worker_loop(worker_id: int) -> None:
    logger.info("Starting worker %d", worker_id)
    while True:
        try:
            recover_stale_jobs()
            async with CLAIM_LOCK:
                job = await asyncio.to_thread(claim_next_job)
            if job:
                logger.info("Worker %d claimed job %s", worker_id, job.id)
                await execute_job(job.id)
                continue
            await asyncio.sleep(WORKER_SLEEP)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Worker %d encountered an error", worker_id)
            await asyncio.sleep(WORKER_SLEEP)


async def create_workers() -> list[asyncio.Task]:
    return [asyncio.create_task(worker_loop(i)) for i in range(WORKER_COUNT)]
