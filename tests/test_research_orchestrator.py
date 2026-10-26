"""
Integration tests for Research Subsystem in CIEOrchestrator using MockSearchProvider.
"""

import pytest
from cie.orchestrator import CIEOrchestrator
from cie.research.engine import ResearchEngine
from cie.research.provider import MockSearchProvider
from cie.research.schemas import SearchResult
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.mark.asyncio
async def test_orchestrator_research_success_with_mock():
    mock_data = {
        "python 3.14 alpha release": [
            SearchResult(
                title="Python 3.14 Alpha Notes",
                url="https://python.org/downloads/release/314",
                snippet="Python 3.14 alpha introduces deferred evaluation of annotations and JIT improvements.",
                date="2026-02-15",
            )
        ]
    }
    provider = MockSearchProvider(predefined_results=mock_data)
    engine = ResearchEngine(provider=provider)
    orchestrator = CIEOrchestrator(research_engine=engine)

    req = CIERequest(prompt="Search the web for python 3.14 alpha release")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.RESEARCH
    assert resp.metadata.get("sources_count") >= 1
    # Check that verified sources block was appended
    assert "### Verified Sources:" in resp.content
    assert "https://python.org/downloads/release/314" in resp.content


@pytest.mark.asyncio
async def test_orchestrator_research_empty_results():
    provider = MockSearchProvider(predefined_results={})  # 0 results
    engine = ResearchEngine(provider=provider)
    orchestrator = CIEOrchestrator(research_engine=engine)

    req = CIERequest(prompt="Search the web for non_existent_framework_xyz_99")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.RESEARCH
    # Must explicitly state 0 sources found and refuse to fabricate facts
    assert "unable to find accessible web sources" in resp.content
    assert "no unverified facts or citations were fabricated" in resp.content
