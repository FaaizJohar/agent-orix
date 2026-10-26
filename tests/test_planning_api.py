"""
Integration tests for Phase 5 FastAPI Planning and Execution endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from cie.server import app
from cie.planning.schemas import PlanStatus, StepStatus


@pytest.fixture
def client():
    return TestClient(app)


def test_api_create_task_plan(client):
    res = client.post(
        "/v1/tasks/plan",
        json={"goal": "Validate python syntax: def add(x, y): return x + y"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "task_id" in data
    assert data["goal"] == "Validate python syntax: def add(x, y): return x + y"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["skill_id"] == "python_ast_validate"


def test_api_execute_task_plan(client):
    # 1. Create plan
    res_plan = client.post(
        "/v1/tasks/plan",
        json={"goal": 'Validate json syntax: {"hello": "world"}'},
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    task_id = plan_data["task_id"]

    # 2. Execute plan by task_id
    res_exec = client.post(
        "/v1/tasks/execute",
        json={"task_id": task_id},
    )
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["status"] == PlanStatus.COMPLETED.value
    assert exec_data["steps"][0]["status"] == StepStatus.SUCCEEDED.value
    assert exec_data["steps"][0]["result"]["valid"] is True


def test_api_get_task_status(client):
    # 1. Create plan
    res_plan = client.post(
        "/v1/tasks/plan",
        json={"goal": "What is an algorithm?"},
    )
    plan_data = res_plan.json()
    task_id = plan_data["task_id"]

    # 2. Get task
    res_get = client.get(f"/v1/tasks/{task_id}")
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["task_id"] == task_id
    assert get_data["status"] == PlanStatus.COMPLETED.value
    assert "direct" in get_data["direct_answer"].lower() or "no tool" in get_data["direct_answer"].lower()


def test_api_get_nonexistent_task_404(client):
    res = client.get("/v1/tasks/nonexistent_task_id_12345")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_cancel_task(client):
    res = client.post("/v1/tasks/test_task_cancel/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
