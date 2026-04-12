import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_job() -> None:
    payload = {"name": "sim-1", "priority": 10}
    create_response = client.post("/jobs", json=payload)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "sim-1"
    assert created["status"] in ["queued", "running"]

    details = client.get(f"/jobs/{created['id']}")
    assert details.status_code == 200
    job = details.json()
    assert job["id"] == created["id"]
    assert job["name"] == "sim-1"


def test_decompose_job_returns_graph() -> None:
    payload = {"instruction": "Run a weather simulation and verify results", "priority": 5}
    response = client.post("/jobs/decompose", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "graph" in body
    assert isinstance(body["graph"], dict)
    assert body["job_id"] > 0
