"""
Integration tests for Knowledge & Memory Subsystem in CIEOrchestrator.
"""

import pytest
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.mark.asyncio
async def test_knowledge_orchestrator_success(orchestrator):
    req = CIERequest(prompt="Who are the founders of Cavrix Core?")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.KNOWLEDGE
    assert resp.metadata.get("chunks_count", 0) >= 1
    # Verify that the response includes verified local documentation references
    assert "### Verified Local Documentation Sources:" in resp.content
    # Verified founders from ingested documentation
    assert ("Faaiz Johar" in resp.content or "Mohd Fahad" in resp.content or "Fahad Multani" in resp.content)


@pytest.mark.asyncio
async def test_knowledge_orchestrator_no_match(orchestrator):
    # Query completely unrelated to Cavrix Core or local docs
    req = CIERequest(prompt="What is the internal architecture of project nonexistent_quantum_hyperdrive_99?")
    resp = await orchestrator.process_request(req)

    # If routed to KNOWLEDGE or GENERAL
    if resp.route.category == IntentCategory.KNOWLEDGE:
        assert resp.status == ExecutionStatus.COMPLETED
        assert "does not establish an answer" in resp.content
        assert "no unverified facts" in resp.content
