import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from .db import create_session
from .models import Job, JobStatus

logger = logging.getLogger("simulation")


def refresh_job_record(job_id: int) -> Optional[Job]:
    with create_session() as session:
        return session.get(Job, job_id)


def update_job_record(job_id: int, **kwargs) -> Optional[Job]:
    with create_session() as session:
        job = session.get(Job, job_id)
        if not job:
            return None
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def _check_control(job_id: int) -> Optional[str]:
    job = refresh_job_record(job_id)
    if not job:
        return "cancel"
    if job.is_cancelled:
        return "cancel"
    if job.is_paused:
        return "pause"
    return None


async def run_simulation_task(job_id: int, task_name: str, total_steps: int = 6, start_step: int = 0) -> str:
    for step in range(start_step, total_steps):
        control = await asyncio.to_thread(_check_control, job_id)
        if control:
            return control

        progress = int((step + 1) / total_steps * 100)
        update_job_record(job_id, progress=progress, last_heartbeat=datetime.utcnow(), checkpoint=json.dumps({"task": task_name, "step": step + 1}))
        logger.info("Job %s running task %s step %d/%d", job_id, task_name, step + 1, total_steps)
        await asyncio.sleep(1)

    update_job_record(job_id, progress=100, last_heartbeat=datetime.utcnow(), checkpoint=json.dumps({"task": task_name, "step": total_steps}))
    return "done"


async def execute_graph_job(job: Job) -> str:
    graph = job.graph or {}
    tasks = graph.get("tasks", [])
    completed = set()
    if job.checkpoint:
        try:
            checkpoint = json.loads(job.checkpoint)
            completed = set(checkpoint.get("completed", []))
        except Exception:
            completed = set()

    remaining = {task["id"]: task for task in tasks}
    while remaining:
        progress_made = False
        for task_id, task in list(remaining.items()):
            if task_id in completed:
                remaining.pop(task_id)
                progress_made = True
                continue
            dependencies = task.get("depends_on", []) or []
            if not all(dep in completed for dep in dependencies):
                continue

            update_job_record(
                job.id,
                checkpoint=json.dumps({"current_task": task_id, "completed": list(completed)}),
                last_heartbeat=datetime.utcnow(),
            )
            step_status = await run_simulation_task(job.id, task["name"], total_steps=6)
            if step_status != "done":
                return step_status

            completed.add(task_id)
            remaining.pop(task_id)
            progress = int(len(completed) / max(1, len(tasks)) * 100)
            update_job_record(
                job.id,
                progress=progress,
                checkpoint=json.dumps({"completed": list(completed)}),
                last_heartbeat=datetime.utcnow(),
            )
            progress_made = True
            break

        if not progress_made:
            logger.error("Graph for job %s contains a dependency cycle or missing task reference", job.id)
            return "failed"

    return "done"
