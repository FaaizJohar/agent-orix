"""
Tests for CavrixCode Phase 12/13 - Batch 3: Knowledge, Memory & Retrieval (Entries 16-22).
OpenViking, Graphiti, RAGFlow, LightRAG, Cognee, Codebase Memory MCP, A-MEM.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cie.capabilities.knowledge.openviking import OpenVikingAdapter, VikingResourceNode
from cie.capabilities.knowledge.graphiti import GraphitiAdapter
from cie.capabilities.knowledge.ragflow import RAGFlowAdapter
from cie.capabilities.knowledge.lightrag import LightRAGAdapter, EntityNode, CommunitySummary
from cie.capabilities.knowledge.cognee import CogneeAdapter
from cie.capabilities.knowledge.codebase_memory import CodebaseMemoryMCPAdapter
from cie.capabilities.knowledge.amem import AMEMAdapter


def test_entry16_openviking():
    adapter = OpenVikingAdapter()
    node = VikingResourceNode(
        uri="viking://resources/auth",
        title="Authentication Module",
        l0_abstract="JWT and HMAC token verification module.",
        l1_overview="Exports verify_token and generate_token functions with 300s default TTL.",
        l2_detail="def verify_token(token):\n    # Full source code\n    return True\n",
    )
    adapter.add_resource(node)
    assert adapter.get_resource("viking://resources/auth", "L0") == node.l0_abstract
    assert adapter.get_resource("viking://resources/auth", "L1") == node.l1_overview
    assert adapter.get_resource("viking://resources/auth", "L2") == node.l2_detail
    assert len(adapter.list_subtree("viking://resources/")) == 1


def test_entry17_graphiti():
    adapter = GraphitiAdapter()
    adapter.add_edge("User", "works_at", "AcmeCorp")
    rels = adapter.query_relationships("User")
    assert len(rels) == 1
    assert rels[0].target == "AcmeCorp"

    # Invalidate edge
    adapter.invalidate_edge("User", "works_at", "AcmeCorp")
    rels_after = adapter.query_relationships("User")
    assert len(rels_after) == 0


def test_entry18_ragflow():
    adapter = RAGFlowAdapter()
    doc_text = "Fastify is a high performance node.js web framework. Python FastAPI is another asynchronous web server."
    chunks = adapter.ingest_document("doc_web", doc_text, chunk_size=5)
    assert len(chunks) >= 2

    search_res = adapter.hybrid_search("Fastify performance")
    assert len(search_res) > 0
    assert "Fastify" in search_res[0].content


def test_entry19_lightrag():
    adapter = LightRAGAdapter()
    adapter.add_entity(EntityNode(name="Ollama", entity_type="tool", description="Local LLM runner"))
    adapter.add_community(CommunitySummary(community_id="c1", theme="Inference Engines", entities=["Ollama"], summary="Local execution runtimes"))

    res = adapter.dual_level_query("Ollama inference")
    assert len(res["low_level_entities"]) == 1
    assert len(res["high_level_themes"]) == 1


def test_entry20_cognee():
    adapter = CogneeAdapter()
    res = adapter.process_text_ecl("Alice founded WonderCorp in Oxford.")
    assert len(res.extracted_entities) >= 2
    assert len(res.cognified_triplets) >= 1
    assert res.loaded_status is True


def test_entry21_codebase_memory_mcp():
    adapter = CodebaseMemoryMCPAdapter()
    code = """
class AgentRunner:
    '''Runs agent tasks.'''
    def start_task(self, task_id: str):
        pass

def global_helper():
    pass
"""
    symbols = adapter.index_python_source("server/runner.py", code)
    assert len(symbols) == 3
    found_class = adapter.find_symbol("AgentRunner")
    assert len(found_class) == 1
    assert found_class[0].symbol_type == "class"


def test_entry22_amem():
    adapter = AMEMAdapter()
    node = adapter.insert("mem_1", "User prefers dark mode.")
    assert node.compute_strength() == 1.0

    # Recall strengthens memory
    recalled = adapter.recall("mem_1")
    assert recalled.access_count == 2
    assert recalled.compute_strength() == 2.0
