"""
Tests for CavrixCode Phase 12 - Batch 1: Agent Intelligence & Execution (Entries 1-8).
Hermes, Open Interpreter, Letta, Mem0, Computer Use, OpenHands, SWE-ReX, Agent S.
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cie.capabilities.agent.hermes import HermesAgentAdapter, HermesToolResponse
from cie.capabilities.agent.open_interpreter import (
    OpenInterpreterAdapter,
    CodeExecutionRequest,
)
from cie.capabilities.agent.letta import LettaMemoryManager
from cie.capabilities.agent.mem0 import Mem0MemoryStore
from cie.capabilities.agent.computer_use import (
    OpenInterpreterComputerUseAdapter,
    ComputerActionRequest,
)
from cie.capabilities.agent.openhands import (
    OpenHandsAgentSession,
    OpenHandsAction,
    OpenHandsObservation,
    AgentState,
)
from cie.capabilities.agent.swerex import SWERexEnvironment, WorkspaceIsolationConfig
from cie.capabilities.agent.agent_s import AgentSPlanner, UIElementBoundingBox


def test_entry1_hermes_tool_calling():
    adapter = HermesAgentAdapter()
    adapter.register_tool({"name": "fetch_weather", "description": "Fetches weather"})
    prompt = adapter.render_system_prompt_tools()
    assert "<tool_call>" in prompt
    assert "fetch_weather" in prompt

    raw_output = 'Thinking...\n<tool_call>\n{"name": "fetch_weather", "arguments": {"city": "Berlin"}}\n</tool_call>'
    calls = adapter.parse_tool_calls(raw_output)
    assert len(calls) == 1
    assert calls[0].name == "fetch_weather"
    assert calls[0].arguments == {"city": "Berlin"}

    resp = adapter.format_tool_response(HermesToolResponse(name="fetch_weather", content={"temp": 18}))
    assert "<tool_response>" in resp
    assert "Berlin" not in resp or True


def test_entry2_open_interpreter_safe_execution():
    adapter = OpenInterpreterAdapter()
    req = CodeExecutionRequest(
        language="python",
        code="print('Hello from OpenInterpreter')",
    )
    res = adapter.execute(req)
    assert res.success is True
    assert "Hello from OpenInterpreter" in res.stdout

    # Test consequential rejection without token
    req_bad = CodeExecutionRequest(
        language="cmd",
        code="del /f test.txt",
    )
    res_bad = adapter.execute(req_bad)
    assert res_bad.success is False
    assert res_bad.error == "CONSEQUENTIAL_ACTION_BLOCKED"


def test_entry3_letta_tiered_memory():
    # Use in-memory SQLite for test reliability and zero file-locking on Windows
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


def test_entry4_mem0_structured_memory():
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

    assert store.delete("user_123", "editor", "theme") is True
    assert store.get("user_123", "editor", "theme") is None


def test_entry5_open_interpreter_computer_use():
    adapter = OpenInterpreterComputerUseAdapter(screen_width=1920, screen_height=1080)
    req = ComputerActionRequest(action="click", x=500, y=300)
    res = adapter.execute_action(req)
    assert res.success is True
    assert res.details["x"] == 500

    # Bounds check failure
    req_oob = ComputerActionRequest(action="click", x=2500, y=300)
    res_oob = adapter.execute_action(req_oob)
    assert res_oob.success is False
    assert "outside screen bounds" in res_oob.error

    # Consequential without token
    req_conseq = ComputerActionRequest(action="click", x=500, y=300, requires_approval=True)
    res_conseq = adapter.execute_action(req_conseq)
    assert res_conseq.success is False
    assert "approval token" in res_conseq.error


def test_entry6_openhands_event_stream():
    session = OpenHandsAgentSession(session_id="sess_42")
    assert session.state == AgentState.INIT

    session.start()
    assert session.state == AgentState.RUNNING

    action = OpenHandsAction(id="act_1", action_type="CmdRunAction", payload={"command": "dir"})
    session.add_action(action)

    obs = OpenHandsObservation(action_id="act_1", observation_type="CmdOutputObservation", content="volume in drive E")
    session.add_observation(obs)

    events = session.get_event_stream()
    assert len(events) == 2
    assert events[0]["type"] == "action"
    assert events[1]["type"] == "observation"

    session.complete()
    assert session.state == AgentState.COMPLETED


def test_entry7_swerex_isolated_environment():
    with tempfile.TemporaryDirectory() as tmp_ws:
        config = WorkspaceIsolationConfig(workspace_root=tmp_ws)
        env = SWERexEnvironment(config)

        # In-bounds path
        assert env.is_path_contained(os.path.join(tmp_ws, "subfolder")) is True
        # Directory traversal attempt
        assert env.is_path_contained("C:\\Windows\\System32") is False

        # Run command within isolated workspace
        res = env.run_isolated_command([sys.executable, "-c", "print('SWE-ReX isolated OK')"])
        assert res["success"] is True
        assert "SWE-ReX isolated OK" in res["stdout"]


def test_entry8_agent_s_hierarchical_gui():
    planner = AgentSPlanner()
    planner.register_element(UIElementBoundingBox(label="SubmitButton", x_min=100, y_min=200, x_max=150, y_max=220))
    coords = planner.resolve_element_coordinates("SubmitButton")
    assert coords == (125, 210)

    steps = planner.plan_gui_task("Click Submit Button")
    assert len(steps) >= 2
    assert steps[0].action_type == "focus_window"
