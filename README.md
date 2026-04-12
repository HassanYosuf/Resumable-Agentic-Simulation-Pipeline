# Resumable Agentic Simulation Pipeline

A FastAPI-based job execution engine for long-running scientific simulation work. This project implements a persistent async queue, job state recovery, pause/resume/cancel controls, priority-aware scheduling, retry handling, and a natural-language decomposition endpoint for graph-based workflows.

## Features Implemented

### Core (✅ Complete)
- **Job Queue**: Async background workers pull and execute jobs from a persistent queue
- **Persistent State**: SQLite database stores job metadata, progress, checkpoints, and retry attempts
- **Status API**: RESTful endpoints for submitting, monitoring, and controlling jobs
- **Cancellation**: Clean cancellation with immediate status updates and heartbeat tracking
- **Pause/Resume**: Flag-based pause/resume with checkpoint restoration on resume

### Level 2: Reliability (✅ Complete)
- **Stale Job Recovery**: Workers detect and requeue jobs that haven't sent heartbeats within 30 seconds
- **Retry Backoff**: Failed jobs retry up to `max_retries` times with exponential backoff (5s × attempt count)
- **Priority Scheduling**: Jobs ordered by priority score, with age-based fairness (priority decreases by 1 per 5 minutes of wait)
- **Worker Heartbeats**: Running jobs update `last_heartbeat` timestamp to signal liveness
- **Graceful Degradation**: Worker errors are caught and logged; recovery is automatic on next cycle

### Level 3: Intelligence (✅ Complete)
- **Natural Language Decomposition**: `POST /jobs/decompose` accepts plain-English instructions and decomposes them into a task DAG
- **Task Dependency Graph**: Executed tasks respect `depends_on` lists; cycles are detected
- **Graph Execution**: Workflow executor processes tasks in order, respecting dependencies
- **LLM Integration**: OpenAI GPT integration (with fallback stub decomposer) for instruction parsing
- **Checkpoint Progress**: Task graphs track completed tasks and resume from checkpoints

## Known Limitations
- Single-process workers use in-memory locks; distributed deployments would require Redis or similar
- The decomposer fallback uses a stub if no API key is configured; production should require real LLM
- Job payloads stored as JSON text rather than normalized tables; limits querying
- No result storage beyond checkpoint progress; full job output history not retained
- Worker scaling is manual; no auto-scaling or load balancing

## Setup

### Prerequisites
- Python 3.10+
- `pip` package manager

### Installation & Configuration

1. **Create a Python virtual environment**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Install dependencies**

```powershell
pip install -r requirements.txt
```

3. **Configure environment variables (optional)**

Create a `.env` file in the project root:

```env
# Optional: OpenAI API key for natural-language decomposition
OPENAI_API_KEY=sk-your-key-here

# Database configuration (defaults to SQLite)
# DATABASE_URL=sqlite:///./jobs.db
```

If `OPENAI_API_KEY` is not set, the decomposer will use a fallback stub that generates basic task graphs without LLM assistance.

4. **Run the application**

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

The server will start at `http://127.0.0.1:8000`.

### API Documentation

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

Both provide interactive documentation and allow testing endpoints directly in the browser.
## API Endpoints

### Job Lifecycle
- `POST /jobs` — Submit a single simulation job
- `GET /jobs` — List all jobs with status and progress
- `GET /jobs/{job_id}` — Inspect a specific job
- `POST /jobs/{job_id}/pause` — Request pause (queued jobs pause immediately; running jobs pause after current step)
- `POST /jobs/{job_id}/resume` — Request resume (moves paused jobs back to queued)
- `POST /jobs/{job_id}/cancel` — Request cancellation (marks job as cancelled)

### Decomposition & Workflows
- `POST /jobs/decompose` — Decompose a natural-language instruction into a task DAG and enqueue as a job
  - **Request**: `{"instruction": "Run a weather simulation", "priority": 100}`
  - **Response**: Returns the generated task graph and the created job ID

### Health Check
- `GET /health` — Verify server is running

## Architectural Decisions

### 1. FastAPI for the Web Framework
FastAPI was chosen for its modern async-first design, built-in OpenAPI documentation, and easy integration with background tasks. The framework's automatic request validation via Pydantic reduces boilerplate and catches errors early. Uvicorn as the ASGI server provides high throughput and seamless async/await support, which is critical for handling worker coordination and job polling without blocking.

### 2. SQLite for Persistence
SQLite offers simplicity and portability without requiring external services—crucial for a self-contained challenge submission. While not suitable for massive scale, SQLite's transaction support and queryability make it ideal for correctness guarantees. Jobs, checkpoints, and retry state are all queryable, enabling recovery logic like stale-job detection. For production at scale, this would swap to PostgreSQL with a connection pool.

### 3. SQLModel for ORM
SQLModel provides a lightweight typed abstraction over SQLAlchemy, enabling declarative models that double as Pydantic validators. This reduces duplication between database schemas and API request/response types. The Job model is simultaneously a database table definition and a serializable API response, keeping the codebase DRY.

### 4. In-Process Workers with Async Polling
Background workers run as async tasks in the same process as the FastAPI app. Each worker polls the job queue every 1 second, claims a single queued job with a status transition, and executes it. A shared `asyncio.Lock` prevents race conditions between workers claiming the same job. While this approach doesn't scale to distributed deployments, it's deterministic and easy to reason about—crucial for a correctness-focused system. Stale-job recovery by heartbeat timeout handles process crashes gracefully.

### 5. Flag-Based Pause/Resume and Cancellation
Rather than signal handlers or middleware, pause and cancellation are communicated via database flags (`is_paused`, `is_cancelled`). The simulation loop periodically checks these flags and yields control. This keeps the pause/resume logic explicit and traceable in code, and avoids race conditions between signal delivery and state mutation. The tradeoff is that pause/cancellation aren't instantaneous—they take effect after the current simulation step completes.

### 6. Task DAG Execution with Checkpoint Resumption
The graph executor maintains a set of completed task IDs in a checkpoint JSON blob stored in the job record. On resume, it loads the checkpoint, skips already-completed tasks, and continues. This design ensures that if a worker crashes mid-task-graph, the job can resume from the last completed task without re-executing earlier work. The checkpoint is small and human-readable, aiding debugging.

### 7. Priority + Aging for Fairness
The job scheduler scores candidates by `priority - (age_minutes // 5)`, ensuring older jobs eventually get selected even if newer high-priority jobs arrive. This prevents starvation of low-priority work and ensures the system makes forward progress on all jobs over time.
## Example LLM Conversation

I used Claude to work through the graph execution and checkpoint resumption logic. The key problem was: *How do I ensure a task graph resumes from exactly where it left off if a worker crashes mid-execution?*

**Problem**: If a worker crashes while executing task "run-simulation", when the job is recovered and restarted, should it:
1. Re-run "run-simulation" (wasting work)?
2. Skip it and move on (assuming it completed)?
3. Somehow know it was partially done?

**Claude's suggestion**: Store a checkpoint that tracks which task IDs have *completely* finished. Before executing a task, check if it's in the completed set. After a task finishes successfully, add its ID to the set and persist the checkpoint.

**Implementation**: The checkpoint is a JSON blob `{"completed": ["setup", "run-simulation"]}` stored in the job record. On each worker loop, the graph executor loads the checkpoint, loops through tasks, and skips any whose ID is already in `completed`. This is simple, idempotent, and survives crashes.

**Code snippet** from [app/simulation.py](app/simulation.py#L48-L90):
```python
completed = set()
if job.checkpoint:
    try:
        checkpoint = json.loads(job.checkpoint)
        completed = set(checkpoint.get("completed", []))
    except Exception:
        completed = set()
```

This conversation clarified that correctness requires explicit state tracking, and that checkpoints should be *data*, not code.

## What I Would Do Differently with More Time

1. **Distributed Locking**: Replace the in-memory `asyncio.Lock` with a Redis-backed distributed lock, enabling multiple independent worker processes and true horizontal scaling.

2. **Result Storage & Audit Trail**: Store the full output and side effects of each job step, not just progress. This would enable rich post-mortem analysis and allow users to inspect intermediate results from long-running workflows.

3. **Task Retry Policies**: Allow per-task retry limits and exponential backoff strategies defined in the decomposition output, so complex workflows can tolerate transient failures on specific steps.

4. **Worker Pool Management**: Implement a configurable pool of workers with dynamic scaling based on queue depth, rather than a fixed count.

5. **Observability**: Add structured logging (JSON formatted), OpenTelemetry tracing, and Prometheus metrics for job latency, worker utilization, and retry rates.

6. **Graph Validation**: Pre-validate the task DAG for cycles, dangling dependencies, and missing task definitions before execution begins.

7. **Sub-Task Logging**: Each simulated step could emit structured events (started, progressed, completed) that are queryable via a `/jobs/{id}/events` endpoint.

## Testing

Run the test suite:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

Tests cover:
- Health endpoint availability
- Job creation and retrieval
- Decomposition graph generation

## File Structure

```
.
├── app/
│   ├── main.py           # FastAPI app, route handlers
│   ├── worker.py         # Background worker loop, job claiming, stale recovery
│   ├── simulation.py     # Graph executor, simulation task runner
│   ├── llm_client.py     # OpenAI integration, decomposition fallback stub
│   ├── models.py         # SQLModel Job definition
│   ├── db.py             # SQLite engine and session management
│   ├── schemas.py        # Pydantic request/response schemas
│   └── __init__.py
├── tests/
│   └── test_jobs.py      # Integration tests
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
└── README.md             # This file
```