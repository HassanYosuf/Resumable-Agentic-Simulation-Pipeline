from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    cancelled = "cancelled"
    completed = "completed"
    failed = "failed"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    recipe: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = Field(default=JobStatus.queued, index=True)
    priority: int = Field(default=100, index=True)
    progress: int = Field(default=0)
    max_progress: int = Field(default=100)
    attempts: int = Field(default=0)
    max_retries: int = Field(default=3)
    last_error: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    checkpoint: Optional[str] = None
    parameters: Optional[str] = None
    is_paused: bool = Field(default=False)
    is_cancelled: bool = Field(default=False)
    run_after: Optional[datetime] = None
    graph: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
