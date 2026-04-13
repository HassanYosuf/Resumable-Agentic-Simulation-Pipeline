import asyncio
import json
import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from sqlmodel import select

from .db import init_db, create_session
from .llm_client import decompose_instruction
from .models import Job, JobStatus
from .schemas import ActionResponse, DecomposeRequest, DecomposeResult, JobCreate, JobListResponse, JobResponse
from .worker import create_workers

logger = logging.getLogger("uvicorn")
app = FastAPI(title="Resumable Agentic Simulation Pipeline")


@app.on_event("startup")
async def startup_event() -> None:
    init_db()
    app.state.worker_tasks = await create_workers()
    logger.info("Started %d background workers", len(app.state.worker_tasks))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in getattr(app.state, "worker_tasks", []):
        task.cancel()
    await asyncio.gather(*getattr(app.state, "worker_tasks", []), return_exceptions=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/jobs/decompose", response_model=DecomposeResult)
def decompose_job(payload: DecomposeRequest) -> DecomposeResult:
    """Decompose natural-language instruction into a task graph and enqueue."""
    graph = decompose_instruction(payload.instruction)
    job = Job(
        name=f"decomposed: {payload.instruction[:64]}",
        priority=payload.priority,
        graph=graph,
        checkpoint=json.dumps({"completed": []}),
        status=JobStatus.queued,
    )
    with create_session() as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    return DecomposeResult(instruction=payload.instruction, graph=graph, job_id=job.id)


@app.post("/jobs", response_model=JobResponse)
def create_job(payload: JobCreate) -> JobResponse:
    """Submit a single simulation job."""
    job = Job(
        name=payload.name,
        priority=payload.priority,
        parameters=json.dumps(payload.parameters if payload.parameters is not None else {}),
        max_retries=payload.max_retries,
        status=JobStatus.queued,
    )
    with create_session() as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    return job


@app.get("/jobs", response_model=JobListResponse)
def list_jobs() -> JobListResponse:
    """List all jobs with status and progress."""
    with create_session() as session:
        jobs = session.exec(select(Job).order_by(Job.status, Job.priority, Job.created_at)).all()
    return JobListResponse(jobs=jobs)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int) -> JobResponse:
    with create_session() as session:
        job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs/{job_id}/pause", response_model=ActionResponse)
def pause_job(job_id: int) -> ActionResponse:
    with create_session() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job.is_paused = True
        if job.status == JobStatus.queued:
            job.status = JobStatus.paused
        session.add(job)
        session.commit()
        session.refresh(job)
    return ActionResponse(id=job.id, status=job.status, message="Pause requested")


@app.post("/jobs/{job_id}/resume", response_model=ActionResponse)
def resume_job(job_id: int) -> ActionResponse:
    with create_session() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.is_cancelled:
            raise HTTPException(status_code=400, detail="Job has been cancelled")
        job.is_paused = False
        job.status = JobStatus.queued
        session.add(job)
        session.commit()
        session.refresh(job)
    return ActionResponse(id=job.id, status=job.status, message="Resume requested")


@app.post("/jobs/{job_id}/cancel", response_model=ActionResponse)
def cancel_job(job_id: int) -> ActionResponse:
    with create_session() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job.is_cancelled = True
        job.status = JobStatus.cancelled
        session.add(job)
        session.commit()
        session.refresh(job)
    return ActionResponse(id=job.id, status=job.status, message="Cancel requested")
