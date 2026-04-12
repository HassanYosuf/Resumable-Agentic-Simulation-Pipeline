from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    cancelled = "cancelled"
    completed = "completed"
    failed = "failed"


class JobCreate(BaseModel):
    name: str
    priority: Optional[int] = 100
    parameters: Optional[Dict[str, str]] = None
    max_retries: Optional[int] = 3


class JobResponse(BaseModel):
    id: int
    name: str
    status: JobStatus
    priority: int
    progress: int
    max_progress: int
    attempts: int
    max_retries: int
    last_error: Optional[str]
    checkpoint: Optional[str]
    graph: Optional[Dict]
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    jobs: List[JobResponse]


class ActionResponse(BaseModel):
    id: int
    status: JobStatus
    message: str


class DecomposeRequest(BaseModel):
    instruction: str
    priority: Optional[int] = 100


class DecomposeResult(BaseModel):
    instruction: str
    graph: Dict
    job_id: int
