"""
Regression Test Suite for Knowledge Grounding, Response Quality & Identity Separation.
Verifies:
1. "tell me about cavrix core" returns authoritative company profile (software company, founders, mission).
2. "what is cavrix code" returns the AI coding assistant product.
3. Queries with absent evidence state lack of documentation and never fabricate facts.
4. Total suppression of internal filesystem paths and raw chunk metadata.
5. Strict identity distinction between parent tech company and AI assistant product.
"""

import re
import pytest
from cie.cli.client import LocalAgentClient
from cie.cli.agent import ConversationalAgent
from cie.knowledge.retriever import KnowledgeRetriever
from cie.knowledge.grounding import KnowledgeGrounding
from cie.knowledge.store import KnowledgeStore
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.fixture
def local_client():
    return LocalAgentClient()


@pytest.mark.asyncio
async def test_cavrix_core_company_profile(orchestrator):
    """
    Query: 'tell me about cavrix core'
    Must identify Cavrix Core as the parent software company, name founders,
    and NOT describe it as an AI coding assistant/model.
    """
    req = CIERequest(prompt="tell me about cavrix core")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.KNOWLEDGE

    content = resp.content
    content_lower = content.lower()

    # Must describe company/technology identity
    assert any(term in content_lower for term in [
        "technology", "software development", "company", "digital ecosystem"
    ]), f"Response did not describe company identity: {content}"

    # Must identify founders
    assert ("faaiz johar" in content_lower or "mohd fahad" in content_lower or "fahad multani" in content_lower), \
        f"Response did not mention founders: {content}"

    # Must NOT transfer AI model specs to the parent company
    assert "24-layer" not in content_lower
    assert "494,032,768" not in content_lower
    assert "transformer model" not in content_lower
    # Must NOT claim Cavrix Core itself is a coding assistant
    assert not re.search(r"cavrix core is an? (?:lightweight )?(?:bilingual )?ai coding assistant", content_lower)

    # Must suppress internal paths and raw chunk identifiers
    assert not re.search(r"[a-zA-Z]:\\[^\s\)\`\]\>]+", content)
    assert not re.search(r"\[(?:Doc\s*\d+[_\s-]*)?Chunk\s*\d+\]", content)
    assert "Doc_2_Chunk" not in content


@pytest.mark.asyncio
async def test_what_is_cavrix_code(orchestrator):
    """
    Query: 'what is cavrix code'
    Must identify Cavrix Code as the local AI coding assistant developed by Cavrix Core.
    """
    req = CIERequest(prompt="what is cavrix code")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.KNOWLEDGE

    content = resp.content
    content_lower = content.lower()

    # Must identify coding assistant product
    assert any(term in content_lower for term in [
        "coding assistant", "ai coding", "python", "javascript", "model", "developer tool"
    ]), f"Response did not describe Cavrix Code product: {content}"

    # Must suppress internal paths and raw chunk IDs
    assert not re.search(r"[a-zA-Z]:\\[^\s\)\`\]\>]+", content)
    assert not re.search(r"\[(?:Doc\s*\d+[_\s-]*)?Chunk\s*\d+\]", content)
    assert "Doc_" not in content


@pytest.mark.asyncio
async def test_query_absent_from_knowledge_base(orchestrator):
    """
    Query whose answer is absent from local documentation.
    Must state that available documentation does not establish the answer,
    and must NOT fabricate answers.
    """
    req = CIERequest(prompt="who is the CFO of cavrix core")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.KNOWLEDGE

    content = resp.content
    assert "does not establish" in content
    assert "no unverified facts" in content


@pytest.mark.asyncio
async def test_quantum_query_absent_from_knowledge_base(orchestrator):
    """
    Query about topic absent from knowledge base.
    """
    req = CIERequest(prompt="tell me about quantum computing architecture in cavrix core")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    content = resp.content
    assert "does not establish" in content


def test_retriever_reranks_company_profile_over_model_specs():
    """
    Verifies that KnowledgeRetriever prioritizes official company profile
    over Cavrix Code model specs for Cavrix Core company queries.
    """
    retriever = KnowledgeRetriever()
    pkg = retriever.retrieve("tell me about cavrix core")

    assert len(pkg.chunks) > 0
    top_chunk = pkg.chunks[0]
    # Top chunk must be from company profile (Doc_2_Chunk_0), not model specifications (Doc_3_Chunk_0/1)
    assert "company profile" in top_chunk.title.lower() or "cavrix_core_profile" in top_chunk.source_path.lower()
    assert "model specifications" not in top_chunk.title.lower()


def test_knowledge_grounding_suppresses_paths_and_raw_chunks():
    """
    Unit test verifying that validate_citations strips raw chunk tags
    and absolute paths from generated output.
    """
    store = KnowledgeStore()
    raw = store.search_fts("cavrix core", limit=1)
    pkg = KnowledgeRetriever().retrieve("cavrix core")

    raw_llm_output = (
        "According to [Chunk 1] and Doc_2_Chunk_0 located at E:\\cavrix_cie\\data\\knowledge_sources\\cavrix_core\\cavrix_core_profile.md, "
        "Cavrix Core was founded by Faaiz Johar."
    )

    verified, unverified, enriched = KnowledgeGrounding.validate_citations(raw_llm_output, pkg)

    assert "[Chunk 1]" not in enriched
    assert "Doc_2_Chunk_0" not in enriched
    assert "E:\\cavrix_cie" not in enriched
    assert "Faaiz Johar" in enriched
    assert "### Verified Local Documentation Sources:" in enriched


@pytest.mark.asyncio
async def test_conversational_agent_terminal_interaction(local_client):
    """
    Verifies full end-to-end terminal interaction through ConversationalAgent.
    """
    agent = ConversationalAgent(client=local_client)
    answer = await agent.handle_message("tell me about cavrix core")

    answer_lower = answer.lower()
    assert "cavrix core" in answer_lower
    assert ("faaiz johar" in answer_lower or "mohd fahad" in answer_lower or "fahad multani" in answer_lower)
    # Must NOT contain raw paths or chunk tokens in terminal output
    assert not re.search(r"[a-zA-Z]:\\[^\s\)\`\]\>]+", answer)
    assert not re.search(r"\[(?:Doc\s*\d+[_\s-]*)?Chunk\s*\d+\]", answer)
    assert "Doc_" not in answer
