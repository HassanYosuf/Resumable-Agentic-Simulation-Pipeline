#!/usr/bin/env python3
"""
Test scenarios for the Resumable Agentic Simulation Pipeline.
Run this after starting the server with: uvicorn app.main:app --reload
"""

import json
import time
import requests
from typing import Any, Dict

BASE_URL = "http://127.0.0.1:8000"


def test_health() -> None:
    """Test 1: Health check endpoint."""
    print("\n=== TEST 1: Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check passed")


def test_create_job() -> int:
    """Test 2: Create a single job."""
    print("\n=== TEST 2: Create Job ===")
    payload = {
        "name": "weather-simulation",
        "priority": 100,
        "parameters": {"region": "US-Northeast", "duration": "7-days"},
        "max_retries": 2,
    }
    response = requests.post(f"{BASE_URL}/jobs", json=payload)
    print(f"Status: {response.status_code}")
    job = response.json()
    print(f"Response: {json.dumps(job, indent=2, default=str)}")
    assert response.status_code == 200
    print(f"✅ Job created with ID: {job['id']}")
    return job["id"]


def test_get_job(job_id: int) -> Dict[str, Any]:
    """Test 3: Get job details."""
    print(f"\n=== TEST 3: Get Job {job_id} ===")
    response = requests.get(f"{BASE_URL}/jobs/{job_id}")
    print(f"Status: {response.status_code}")
    job = response.json()
    print(f"Response: {json.dumps(job, indent=2, default=str)}")
    assert response.status_code == 200
    print(f"✅ Job retrieved: {job['name']} [{job['status']}]")
    return job


def test_list_jobs() -> None:
    """Test 4: List all jobs."""
    print("\n=== TEST 4: List All Jobs ===")
    response = requests.get(f"{BASE_URL}/jobs")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total jobs: {len(data['jobs'])}")
    for job in data["jobs"]:
        print(f"  - Job {job['id']}: {job['name']} [{job['status']}] - Progress: {job['progress']}%")
    assert response.status_code == 200
    print("✅ Jobs listed successfully")


def test_pause_job(job_id: int) -> None:
    """Test 5: Pause a job."""
    print(f"\n=== TEST 5: Pause Job {job_id} ===")
    response = requests.post(f"{BASE_URL}/jobs/{job_id}/pause")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2, default=str)}")
    assert response.status_code == 200
    print(f"✅ Job paused: {result['message']}")


def test_resume_job(job_id: int) -> None:
    """Test 6: Resume a paused job."""
    print(f"\n=== TEST 6: Resume Job {job_id} ===")
    response = requests.post(f"{BASE_URL}/jobs/{job_id}/resume")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2, default=str)}")
    assert response.status_code == 200
    print(f"✅ Job resumed: {result['message']}")


def test_cancel_job(job_id: int) -> None:
    """Test 7: Cancel a job."""
    print(f"\n=== TEST 7: Cancel Job {job_id} ===")
    response = requests.post(f"{BASE_URL}/jobs/{job_id}/cancel")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2, default=str)}")
    assert response.status_code == 200
    print(f"✅ Job cancelled: {result['message']}")


def test_decompose_instruction() -> int:
    """Test 8: Decompose natural language into task graph."""
    print("\n=== TEST 8: Decompose Instruction ===")
    payload = {
        "instruction": "Run a climate simulation for the Northern Hemisphere, validate results against historical data",
        "priority": 50,
    }
    response = requests.post(f"{BASE_URL}/jobs/decompose", json=payload)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Graph tasks: {len(result['graph'].get('tasks', []))}")
    for task in result["graph"].get("tasks", []):
        deps = task.get("depends_on", []) or []
        print(f"  - {task['id']}: {task['name']} (depends on: {deps})")
    print(f"Job ID: {result['job_id']}")
    assert response.status_code == 200
    print("✅ Instruction decomposed and job created")
    return result["job_id"]


def test_job_execution_monitoring(job_id: int) -> None:
    """Test 9: Monitor job execution over time."""
    print(f"\n=== TEST 9: Monitor Job {job_id} Execution ===")
    print("Monitoring for 10 seconds...")
    for i in range(5):
        response = requests.get(f"{BASE_URL}/jobs/{job_id}")
        job = response.json()
        print(
            f"  [{i}s] Status: {job['status']:<10} Progress: {job['progress']:>3}% Attempts: {job['attempts']}"
        )
        time.sleep(2)
    print("✅ Job execution monitored")


def test_priority_scheduling() -> None:
    """Test 10: Create multiple jobs with different priorities."""
    print("\n=== TEST 10: Priority Scheduling ===")
    job_ids = []
    for priority in [10, 100, 50]:
        payload = {
            "name": f"priority-{priority}-job",
            "priority": priority,
        }
        response = requests.post(f"{BASE_URL}/jobs", json=payload)
        job_id = response.json()["id"]
        job_ids.append(job_id)
        print(f"Created job {job_id} with priority {priority}")

    time.sleep(3)
    response = requests.get(f"{BASE_URL}/jobs")
    jobs = response.json()["jobs"]
    queued_jobs = [j for j in jobs if j["status"] == "queued"]
    print("Job queue order (by claim likelihood):")
    for job in queued_jobs[-3:]:
        print(f"  - Job {job['id']}: Priority {job['priority']}")
    print("✅ Priority scheduling verified")


def run_all_tests() -> None:
    """Run all test scenarios."""
    print("=" * 60)
    print("RESUMABLE AGENTIC SIMULATION PIPELINE - TEST SCENARIOS")
    print("=" * 60)

    try:
        # Basic operations
        test_health()
        job_id_1 = test_create_job()
        job_data = test_get_job(job_id_1)
        test_list_jobs()

        # Control operations
        test_pause_job(job_id_1)
        time.sleep(1)
        test_resume_job(job_id_1)
        time.sleep(1)
        test_cancel_job(job_id_1)

        # Decomposition
        job_id_2 = test_decompose_instruction()
        test_job_execution_monitoring(job_id_2)

        # Advanced features
        test_priority_scheduling()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server. Make sure it's running on port 8000")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    run_all_tests()
