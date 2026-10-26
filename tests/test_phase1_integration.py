"""
Integration tests for Phase 1 Security Hardening & CIE Streaming Compatibility.
Verifies /v1/chat/stream across DIRECT, RESEARCH, and KNOWLEDGE routes,
citation preservation, and empty retrieval handling.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from cie.server import app
from cie.research.schemas import EvidencePackage, SourceRecord
from cie.knowledge.schemas import KnowledgeEvidencePackage, KnowledgeSearchResult


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_endpoint(client):
    """Verify health check endpoint returns 200 with local process metrics."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("HEALTHY", "DEGRADED")
    assert "process_ram_mb" in data
    assert "total_visible_ram_mb" in data


def test_chat_stream_rejects_empty_prompt(client):
    """Verify streaming endpoint rejects empty or whitespace prompt."""
    res = client.post("/v1/chat/stream", json={"prompt": "   "})
    assert res.status_code == 200
    assert "Request rejected" in res.text
    assert "[DONE]" in res.text


def test_chat_stream_direct_coding(client):
    """Verify streaming endpoint handles DIRECT coding routes cleanly."""
    mock_chunks = ["def ", "fib(n):", "\n    return n"]

    async def mock_gen(*args, **kwargs):
        for c in mock_chunks:
            yield c

    with patch("cie.server._orchestrator.ollama_client.generate_stream", side_effect=mock_gen):
        res = client.post("/v1/chat/stream", json={"prompt": "Write a python function to compute fibonacci"})
        assert res.status_code == 200
        text = res.text
        assert "data: def " in text
        assert "data: fib(n):" in text
        assert "data: [DONE]" in text


def test_chat_stream_research_route_with_citations(client):
    """Verify research route gathers evidence, preserves citations, and appends sources."""
    fake_sources = [
        SourceRecord(
            source_id="source_1",
            title="Python 3.13 Release Notes",
            url="https://docs.python.org/3.13/",
            excerpt="Python 3.13 introduces experimental free-threading and JIT compilation.",
            raw_text="Python 3.13 introduces experimental free-threading and JIT compilation.",
        )
    ]
    fake_evidence = EvidencePackage(
        query="latest python 3.13 features",
        sources=fake_sources,
    )

    async def mock_evidence(*args, **kwargs):
        return fake_evidence

    async def mock_gen(*args, **kwargs):
        yield "Python 3.13 includes a JIT compiler [Source 1]."

    with patch("cie.server._orchestrator.research_engine.gather_evidence", side_effect=mock_evidence):
        with patch("cie.server._orchestrator.ollama_client.generate_stream", side_effect=mock_gen):
            res = client.post("/v1/chat/stream", json={"prompt": "Search the web: latest python 3.13 features"})
            assert res.status_code == 200
            text = res.text
            assert "Python 3.13 includes a JIT compiler [Source 1]" in text
            assert "**Sources:**" in text
            assert "https://docs.python.org/3.13/" in text
            assert "[DONE]" in text


def test_chat_stream_research_empty_evidence(client):
    """Verify empty research retrieval does not hallucinate facts."""
    empty_evidence = EvidencePackage(query="unknown query xyz", sources=[])

    async def mock_evidence(*args, **kwargs):
        return empty_evidence

    with patch("cie.server._orchestrator.research_engine.gather_evidence", side_effect=mock_evidence):
        res = client.post("/v1/chat/stream", json={"prompt": "Search the web for unknown query xyz"})
        assert res.status_code == 200
        text = res.text
        assert "No unverified facts were fabricated" in text
        assert "[DONE]" in text


def test_chat_stream_knowledge_route_with_references(client):
    """Verify knowledge route retrieves local document chunks and appends references."""
    fake_chunks = [
        KnowledgeSearchResult(
            chunk_identifier="chunk_1",
            title="Cavrix Specifications",
            source_path="cavrix_core/cavrix_code_specifications.md",
            collection="cavrix_core",
            content="Cavrix Code is optimized for local CPU execution via Ollama.",
            score=4.5,
        )
    ]
    fake_bundle = KnowledgeEvidencePackage(query="What are Cavrix Core specifications?", chunks=fake_chunks)

    def mock_retrieve(*args, **kwargs):
        return fake_bundle

    async def mock_gen(*args, **kwargs):
        yield "Cavrix Code is locally runnable [Doc 1]."

    with patch("cie.server._orchestrator.knowledge_retriever.retrieve", side_effect=mock_retrieve):
        with patch("cie.server._orchestrator.ollama_client.generate_stream", side_effect=mock_gen):
            res = client.post("/v1/chat/stream", json={"prompt": "What are Cavrix Core specifications?"})
            assert res.status_code == 200
            text = res.text
            assert "Cavrix Code is locally runnable [Doc 1]." in text
            assert "**Verified References:**" in text
            assert "Cavrix Specifications" in text
            assert "[DONE]" in text


def test_chat_stream_knowledge_empty_retrieval(client):
    """Verify empty knowledge retrieval does not invent corporate facts."""
    empty_bundle = KnowledgeEvidencePackage(query="Who is the founder of Cavrix Core?", chunks=[])

    def mock_retrieve(*args, **kwargs):
        return empty_bundle

    with patch("cie.server._orchestrator.knowledge_retriever.retrieve", side_effect=mock_retrieve):
        res = client.post("/v1/chat/stream", json={"prompt": "Who is the founder of Cavrix Core?"})
        assert res.status_code == 200
        text = res.text
        assert "No unverified claims were fabricated" in text
        assert "[DONE]" in text
