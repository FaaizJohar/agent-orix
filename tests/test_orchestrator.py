"""
Tests for CIE Orchestrator step-boundedness, dispatching, and concurrency.
"""

import asyncio
import pytest
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.mark.asyncio
async def test_step_boundedness(orchestrator):
    # Every request must be strictly <= 3 steps
    req = CIERequest(prompt="Write a Python function to check palindrome.")
    resp = await orchestrator.process_request(req)
    assert len(resp.steps_taken) <= orchestrator.max_steps
    assert len(resp.steps_taken) >= 2


@pytest.mark.asyncio
async def test_not_implemented_routes(orchestrator):

    # Code execution route
    e_resp = await orchestrator.process_request(CIERequest(prompt="Run this python code in sandbox"))
    assert e_resp.status == ExecutionStatus.NOT_IMPLEMENTED
    assert e_resp.route.category == IntentCategory.CODE_EXECUTION
    assert "Phase 5" in e_resp.content

    # Multilingual route
    m_resp = await orchestrator.process_request(CIERequest(prompt="यह कोड कैसे काम करता है बताइए"))
    assert m_resp.status == ExecutionStatus.NOT_IMPLEMENTED
    assert m_resp.route.category == IntentCategory.MULTILINGUAL
    assert "Phase 6" in m_resp.content


@pytest.mark.asyncio
async def test_rejection_of_empty_prompt(orchestrator):
    req = CIERequest(prompt="   ")
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.REJECTED
    assert "empty" in resp.content.lower()


@pytest.mark.asyncio
async def test_concurrency_semaphore(orchestrator):
    # Verify that the semaphore limits concurrent inference to max_concurrent_inferences
    assert orchestrator._inference_semaphore._value == 1
