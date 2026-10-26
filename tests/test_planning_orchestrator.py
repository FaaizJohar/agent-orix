"""
Integration tests for CIEOrchestrator with Adaptive Planning (plan_mode=True).
"""

import pytest
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.mark.asyncio
async def test_orchestrator_plan_mode_execution(orchestrator):
    prompt = 'Validate json syntax: {"engine": "Cavrix", "phase": 5}'
    req = CIERequest(
        prompt=prompt,
        metadata={"plan_mode": True},
    )
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert len(resp.steps_taken) == 3
    assert resp.steps_taken[2].action == "AdaptivePlanExecution"
    assert "Task Plan Report" in resp.content
    assert "Verified" in resp.content
    assert "plan" in resp.metadata
    assert resp.metadata["plan"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_orchestrator_plan_mode_clarification(orchestrator):
    prompt = "Check file integrity of file"  # Missing file path
    req = CIERequest(
        prompt=prompt,
        metadata={"plan_mode": True},
    )
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.REJECTED  # BLOCKED maps to REJECTED for direct response
    assert "Clarification Required" in resp.content
    assert "file path" in resp.content.lower()


@pytest.mark.asyncio
async def test_orchestrator_plan_mode_unsupported(orchestrator):
    prompt = "Deploy this application on Kubernetes"
    req = CIERequest(
        prompt=prompt,
        metadata={"plan_mode": True},
    )
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.ERROR
    assert "unsupported" in resp.content.lower()
