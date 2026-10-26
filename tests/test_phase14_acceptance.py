"""
Phase 14 Comprehensive Acceptance Test Suite.
Verifies concrete capability behavior for all 30 open-source ecosystem entries.
Exercises end-to-end functionality including persistence, AST parsing,
HTML conversion, budget compression, and evaluation assertions.
"""

import ast
import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure CIE is on path
CIE_ROOT = Path("E:/cavrix_cie")
if str(CIE_ROOT) not in sys.path:
    sys.path.insert(0, str(CIE_ROOT))

# Capability imports
from cie.capabilities.agent.hermes import HermesAgentAdapter, HermesToolCall, HermesToolResponse
from cie.capabilities.agent.open_interpreter import OpenInterpreterAdapter, CodeExecutionRequest
from cie.capabilities.agent.letta import LettaMemoryManager
from cie.capabilities.agent.mem0 import Mem0MemoryStore
from cie.capabilities.agent.computer_use import OpenInterpreterComputerUseAdapter, ComputerActionRequest
from cie.capabilities.agent.openhands import OpenHandsAgentSession, OpenHandsAction, OpenHandsObservation, AgentState
from cie.capabilities.agent.swerex import SWERexEnvironment, WorkspaceIsolationConfig
from cie.capabilities.agent.agent_s import AgentSPlanner, UIElementBoundingBox

from cie.capabilities.browser.playwright_mcp import PlaywrightMCPAdapter
from cie.capabilities.browser.browser_use import BrowserUseAgent
from cie.capabilities.browser.devtools_mcp import ChromeDevToolsMCPAdapter, DevToolsNetworkRequest
from cie.capabilities.browser.context7 import Context7Adapter, LibraryDocQuery
from cie.capabilities.browser.crawl4ai import Crawl4AIAdapter
from cie.capabilities.browser.obscura import ObscuraAdapter
from cie.capabilities.browser.n8n import N8nWorkflowAdapter, WorkflowDefinition, WorkflowNode

from cie.capabilities.knowledge.openviking import OpenVikingAdapter, VikingResourceNode
from cie.capabilities.knowledge.graphiti import GraphitiAdapter
from cie.capabilities.knowledge.ragflow import RAGFlowAdapter
from cie.capabilities.knowledge.lightrag import LightRAGAdapter, EntityNode, CommunitySummary
from cie.capabilities.knowledge.cognee import CogneeAdapter
from cie.capabilities.knowledge.codebase_memory import CodebaseMemoryMCPAdapter
from cie.capabilities.knowledge.amem import AMEMAdapter

from cie.capabilities.documents.paddleocr import PaddleOCRAdapter
from cie.capabilities.documents.markitdown import MarkItDownAdapter
from cie.capabilities.documents.llmlingua import LLMLinguaAdapter
from cie.capabilities.documents.dspy import DSPyAdapter, DSPySignature, SignatureField
from cie.capabilities.documents.promptfoo import PromptfooAdapter, PromptfooAssertion
from cie.capabilities.documents.inspect_ai import InspectAIAdapter, BenchmarkSample
from cie.capabilities.documents.langfuse import LangfuseAdapter

from cie.capabilities.vision.frigate import FrigateAdapter


# =========================================================================
# BATCH 1: AGENT INTELLIGENCE & EXECUTION (Entries 1 - 8)
# =========================================================================

def test_p14_entry1_hermes_upstream_validation():
    adapter = HermesAgentAdapter()
    adapter.register_tool({"name": "execute_sql", "description": "Execute a safe SQL query"})
    prompt = adapter.render_system_prompt_tools()
    assert "<tool_call>" in prompt
    assert "execute_sql" in prompt

    raw_output = '<tool_call>\n{"name": "execute_sql", "arguments": {"query": "SELECT count(*) FROM users"}}\n</tool_call>'
    calls = adapter.parse_tool_calls(raw_output)
    assert len(calls) == 1
    assert calls[0].name == "execute_sql"
    assert calls[0].arguments["query"] == "SELECT count(*) FROM users"

    resp = adapter.format_tool_response(HermesToolResponse(name="execute_sql", content={"count": 42}))
    assert "<tool_response>" in resp
    assert "42" in resp


def test_p14_entry2_open_interpreter_sandboxed_exec():
    adapter = OpenInterpreterAdapter()
    req = CodeExecutionRequest(language="python", code="print(2 ** 10)")
    res = adapter.execute(req)
    assert res.success is True
    assert "1024" in res.stdout.strip()


def test_p14_entry3_letta_tiered_memory():
    letta = LettaMemoryManager(db_path=":memory:")
    assert "CavrixCode" in letta.core.persona
    assert letta.core_memory_append("human", "Loves Python and Rust.") is True
    assert "Rust" in letta.core.human

    # Archival
    pid = letta.archival_memory_insert("User is configuring Fastify server on port 3001.", {"topic": "server"})
    assert pid > 0
    search_res = letta.archival_memory_search("Fastify")
    assert len(search_res) == 1
    assert "3001" in search_res[0]["content"]

    # Recall
    rid = letta.recall_memory_log("user", "Start server")
    assert rid > 0


def test_p14_entry4_mem0_structured_entity_indexing():
    store = Mem0MemoryStore()
    item = store.add(
        user_id="user_123",
        entity="editor",
        attribute="theme",
        value="dark_plus",
    )
    assert item.value == "dark_plus"

    retrieved = store.get("user_123", "editor", "theme")
    assert retrieved is not None
    assert retrieved.value == "dark_plus"

    search_res = store.search("user_123", "dark")
    assert len(search_res) == 1
    assert search_res[0].entity == "editor"


def test_p14_entry5_computer_use_safety_bounds():
    adapter = OpenInterpreterComputerUseAdapter(screen_width=1920, screen_height=1080)
    # Valid bounded coordinate
    res_valid = adapter.execute_action(ComputerActionRequest(action="click", x=500, y=300))
    assert res_valid.success is True
    assert res_valid.details["x"] == 500

    # Out of bounds coordinate
    res_invalid = adapter.execute_action(ComputerActionRequest(action="click", x=2500, y=300))
    assert res_invalid.success is False
    assert "outside screen bounds" in res_invalid.error


def test_p14_entry6_openhands_event_stream_fsm():
    session = OpenHandsAgentSession(session_id="p14_test_session")
    assert session.state == AgentState.INIT

    session.start()
    assert session.state == AgentState.RUNNING

    session.add_action(OpenHandsAction(id="act_1", action_type="CmdRunAction", payload={"command": "dir"}))
    session.add_observation(OpenHandsObservation(action_id="act_1", observation_type="CmdOutputObservation", content="drive E"))

    events = session.get_event_stream()
    assert len(events) == 2

    session.complete()
    assert session.state == AgentState.COMPLETED


def test_p14_entry7_swerex_path_traversal_barrier():
    with tempfile.TemporaryDirectory() as tmp_ws:
        config = WorkspaceIsolationConfig(workspace_root=tmp_ws, max_execution_time_seconds=5.0)
        env = SWERexEnvironment(config=config)

        # In-bounds execution
        res_ok = env.run_isolated_command(["python", "-c", "print('SWE-ReX isolated OK')"])
        assert res_ok["success"] is True
        assert "SWE-ReX isolated OK" in res_ok["stdout"]

        # Out-of-bounds traversal attack blocked
        res_blocked = env.run_isolated_command(["cmd.exe", "/c", "dir"], cwd="C:/Windows/System32")
        assert res_blocked["success"] is False
        assert res_blocked["exit_code"] == 403


def test_p14_entry8_agent_s_hierarchical_planner():
    planner = AgentSPlanner()
    planner.register_element(UIElementBoundingBox(label="SubmitButton", x_min=100, y_min=200, x_max=150, y_max=220))
    coords = planner.resolve_element_coordinates("SubmitButton")
    assert coords == (125, 210)

    steps = planner.plan_gui_task("Click Submit Button")
    assert len(steps) >= 2
    assert steps[0].action_type == "focus_window"


# =========================================================================
# BATCH 2: BROWSER AUTOMATION & MCP INTERFACES (Entries 9 - 15)
# =========================================================================

def test_p14_entry9_playwright_mcp_tool_schemas():
    adapter = PlaywrightMCPAdapter()
    tools = adapter.list_tools()
    assert len(tools) >= 4
    tool_names = [t.name for t in tools]
    assert "browser_navigate" in tool_names
    assert "browser_click" in tool_names

    res = adapter.execute_mcp_call("browser_navigate", {"url": "https://example.com"})
    assert res["isError"] is False
    assert "successfully" in res["content"][0]["text"]


def test_p14_entry10_browser_use():
    agent = BrowserUseAgent(max_steps=5)
    plan = agent.create_plan_for_goal("Look up Fastify documentation", "https://fastify.dev")
    assert len(plan.steps) >= 2
    assert plan.steps[0].action_name == "browser_open"
    assert agent.evaluate_step_outcome(plan.steps[0], {"success": True}) is True


def test_p14_entry11_chrome_devtools_mcp():
    adapter = ChromeDevToolsMCPAdapter()
    adapter.record_console_log("info", "Page initialized")
    adapter.record_console_log("error", "Uncaught TypeError: Cannot read properties of undefined")
    errors = adapter.get_console_errors()
    assert len(errors) == 1
    assert "TypeError" in errors[0].message

    adapter.record_network_request(DevToolsNetworkRequest(request_id="req_1", url="https://api.test/data", method="GET", status=200))
    adapter.record_network_request(DevToolsNetworkRequest(request_id="req_2", url="https://api.test/missing", method="GET", status=404))
    summary = adapter.get_network_summary()
    assert summary["total_requests"] == 2
    assert summary["failed_requests"] == 1


def test_p14_entry12_context7():
    adapter = Context7Adapter()
    res = adapter.fetch_docs(LibraryDocQuery(library="pydantic", version="2.0", query="BaseModel"))
    assert res.version == "2.10.0"
    assert len(res.matched_sections) > 0
    assert "BaseModel" in res.matched_sections[0]


def test_p14_entry13_crawl4ai_structured_markdown_extraction():
    adapter = Crawl4AIAdapter()
    raw_html = """
    <html>
      <head><title>Test Page</title></head>
      <body>
        <script>var x = 10;</script>
        <h1>Article Heading</h1>
        <p>This is paragraph content extracted by Crawl4AI.</p>
        <a href="https://example.com/link1">Link 1</a>
        <img src="https://example.com/img.png" />
      </body>
    </html>
    """
    res = adapter.extract_from_html("https://example.com/test", raw_html, title="Test Page")
    assert res.title == "Test Page"
    assert "Article Heading" in res.markdown
    assert "var x = 10;" not in res.markdown
    assert "https://example.com/link1" in res.links
    assert "https://example.com/img.png" in res.images


def test_p14_entry14_obscura_stealth_profile():
    adapter = ObscuraAdapter()
    profile = adapter.create_stealth_profile()
    assert "Windows" in profile.user_agent or "Macintosh" in profile.user_agent
    assert profile.disable_webrtc is True
    assert profile.mask_canvas_noise is True
    assert "Sec-Ch-Ua" in profile.headers


def test_p14_entry15_n8n_workflow():
    adapter = N8nWorkflowAdapter()
    workflow = WorkflowDefinition(
        name="Phase14_Alert_Pipeline",
        nodes=[
            WorkflowNode(id="node_1", name="Set Config", type="n8n-nodes-base.set", parameters={"env": "production"}),
            WorkflowNode(id="node_2", name="Webhook Call", type="n8n-nodes-base.httpRequest"),
        ]
    )
    res = adapter.execute_workflow(workflow)
    assert res.success is True
    assert len(res.executed_nodes) == 2
    assert res.outputs["env"] == "production"
    assert res.outputs["last_http_status"] == 200


# =========================================================================
# BATCH 3: KNOWLEDGE GRAPHS & CONTEXT ENGINES (Entries 16 - 22)
# =========================================================================

def test_p14_entry16_openviking_tiered_filesystem_delivery():
    adapter = OpenVikingAdapter()
    adapter.add_resource(
        VikingResourceNode(
            uri="viking://models/cavrix_code",
            title="CavrixCode GGUF Model",
            l0_abstract="Fine-tuned code intelligence GGUF model.",
            l1_overview="CavrixCode Q4_K_M quantized model deployed in Ollama runtime.",
            l2_detail="Full configuration: context 16384, rope freq 1.0, sha256 4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1",
        )
    )

    l0 = adapter.get_resource("viking://models/cavrix_code", tier="L0")
    l1 = adapter.get_resource("viking://models/cavrix_code", tier="L1")
    l2 = adapter.get_resource("viking://models/cavrix_code", tier="L2")

    assert "Fine-tuned" in l0
    assert "Q4_K_M" in l1
    assert "4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1" in l2


def test_p14_entry17_graphiti_temporal_edges():
    adapter = GraphitiAdapter()
    adapter.add_edge("User", "works_at", "AcmeCorp")
    rels = adapter.query_relationships("User")
    assert len(rels) == 1
    assert rels[0].target == "AcmeCorp"

    # Invalidate edge
    adapter.invalidate_edge("User", "works_at", "AcmeCorp")
    rels_after = adapter.query_relationships("User")
    assert len(rels_after) == 0


def test_p14_entry18_ragflow_document_chunking():
    adapter = RAGFlowAdapter()
    doc_text = "Fastify is a high performance node.js web framework. Python FastAPI is another asynchronous web server."
    chunks = adapter.ingest_document("doc_web", doc_text, chunk_size=5)
    assert len(chunks) >= 2

    search_res = adapter.hybrid_search("Fastify performance")
    assert len(search_res) > 0
    assert "Fastify" in search_res[0].content


def test_p14_entry19_lightrag_dual_level_query():
    adapter = LightRAGAdapter()
    adapter.add_entity(EntityNode(name="Ollama", entity_type="tool", description="Local LLM runner"))
    adapter.add_community(CommunitySummary(
        community_id="c1",
        theme="Inference Engines",
        entities=["Ollama"],
        summary="Local execution runtimes",
    ))

    res = adapter.dual_level_query("Ollama inference")
    assert len(res["low_level_entities"]) == 1
    assert len(res["high_level_themes"]) == 1


def test_p14_entry20_cognee():
    adapter = CogneeAdapter()
    res = adapter.process_text_ecl("Alice founded WonderCorp in Oxford.")
    assert len(res.extracted_entities) >= 2
    assert len(res.cognified_triplets) >= 1
    assert res.loaded_status is True


def test_p14_entry21_codebase_memory_mcp():
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


def test_p14_entry22_amem():
    adapter = AMEMAdapter()
    node = adapter.insert("mem_1", "User prefers dark mode.")
    assert node.compute_strength() == 1.0

    # Recall strengthens memory
    recalled = adapter.recall("mem_1")
    assert recalled.access_count == 2
    assert recalled.compute_strength() == 2.0


# =========================================================================
# BATCH 4: DOCUMENTS, EVALUATION, OBSERVABILITY & VISION (Entries 23 - 30)
# =========================================================================

def test_p14_entry23_paddleocr():
    adapter = PaddleOCRAdapter()
    res = adapter.process_image_simulated("data/sample_receipt.png", ["Order #42", "Total: $12.50"])
    assert "Order #42" in res.full_text
    assert len(res.elements) == 2
    assert res.elements[0].confidence >= 0.95


def test_p14_entry24_markitdown_upstream_conversion():
    adapter = MarkItDownAdapter()
    res = adapter.convert_text_or_html("<h1>Document Title</h1><p>Sample paragraph.</p>")
    assert res.success is True
    assert "Document Title" in res.markdown
    assert "Sample paragraph." in res.markdown


def test_p14_entry25_llmlingua_budget_compression():
    adapter = LLMLinguaAdapter()
    prompt = (
        "This is basically a really long prompt with lots of filler words that should actually be pruned. "
        "```python\ndef critical_code():\n    return 42\n``` "
        "The critical code inside the markdown fence must be strictly preserved."
    )
    res = adapter.compress_prompt(prompt, target_ratio=0.5)
    assert res.compressed_tokens <= res.original_tokens
    assert "def critical_code():" in res.compressed_text
    assert "return 42" in res.compressed_text


def test_p14_entry26_dspy_upstream_signatures():
    adapter = DSPyAdapter()
    sig = DSPySignature(
        name="SummarizeDoc",
        instructions="Summarize the given document concisely.",
        inputs=[SignatureField(name="document", desc="Input document", prefix="Document:")],
        outputs=[SignatureField(name="summary", desc="Summary output", prefix="Summary:")],
    )
    prompt = adapter.compile_signature_prompt(sig, {"document": "Fastify is fast."})
    assert "Instruction:" in prompt
    assert "Document: Fastify is fast." in prompt
    assert "Summary:" in prompt


def test_p14_entry27_promptfoo_redteam_assertions():
    adapter = PromptfooAdapter()
    assertions = [
        PromptfooAssertion(type="contains", value="CavrixCode"),
        PromptfooAssertion(type="not-contains", value="forbidden_key"),
        PromptfooAssertion(type="regex", value=r"v\d+\.\d+"),
    ]
    res_pass = adapter.evaluate_response("Welcome to CavrixCode v1.0.0 official build.", assertions)
    assert res_pass.passed is True
    assert res_pass.score == 1.0

    res_fail = adapter.evaluate_response("Welcome to BadCode without version.", assertions)
    assert res_fail.passed is False
    assert "missing" in res_fail.reason or "regex" in res_fail.reason


def test_p14_entry28_inspect_ai_evaluation_runner():
    adapter = InspectAIAdapter()
    samples = [
        BenchmarkSample(id="s1", input="2 + 2", target="4"),
        BenchmarkSample(id="s2", input="10 * 10", target="100"),
    ]
    def simple_eval_solver(inp: str) -> str:
        if "2 + 2" in inp:
            return "4"
        return "100"

    res = adapter.evaluate_task(samples, simple_eval_solver)
    assert res["total_samples"] == 2
    assert res["mean_accuracy"] == 1.0


def test_p14_entry29_langfuse_telemetry_trace():
    adapter = LangfuseAdapter()
    trace = adapter.create_trace(trace_id="tr_100", name="ChatSession", user_id="usr_1")
    assert trace.trace_id == "tr_100"

    span = adapter.start_span("tr_100", "sp_1", "ToolExecution", {"tool": "python_ast_validate"})
    assert span is not None
    assert span.status == "running"

    adapter.end_span("tr_100", "sp_1", {"valid": True})
    assert span.status == "completed"
    assert span.end_time is not None


def test_p14_entry30_frigate_camera_events():
    # Test disabled by default
    adapter_disabled = FrigateAdapter(enabled=False)
    res_disabled = adapter_disabled.handle_webhook_event({"id": "evt_1", "label": "person"})
    assert res_disabled["success"] is False
    assert "disabled" in res_disabled["error"]

    # Test opt-in enabled
    adapter_enabled = FrigateAdapter(enabled=True)
    res_enabled = adapter_enabled.handle_webhook_event({"id": "evt_1", "camera": "front_door", "label": "person", "score": 0.92, "start_time": 1000.0})
    assert res_enabled["success"] is True
    assert res_enabled["label"] == "person"
    events = adapter_enabled.list_recent_events("front_door")
    assert len(events) == 1
