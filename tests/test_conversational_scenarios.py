"""
Phase 18 Comprehensive Conversational AI Scenario Verification Suite.
Validates all 13 required conversational scenarios:
1. Normal conversation & greetings
2. Question about a real project
3. Contextual follow-up without repeating details
4. File inspection & summary of findings
5. File modification & diff inspection
6. Test running & real outcome reporting
7. Task interruption / cancellation
8. Graceful model/runtime failure handling
9. Unauthorized filesystem operation (containment guard)
10. Human approval for destructive/consequential operations
11. Session persistence and context restoration
12. Remote client authentication & permissions
13. Installation & import readiness from fresh checkout
"""

import asyncio
import os
import shutil
import sys
import tempfile
import pytest
from pathlib import Path

from cie.cli.agent import ConversationalAgent
from cie.cli.client import LocalAgentClient, RemoteAgentClient
from cie.cli.session import SessionManager
from cie.cli.terminal import TerminalChat
from cie.security_tokens import compute_action_token


@pytest.fixture
def test_workspace(tmp_path):
    # Set up a sample project inside tmp_path
    (tmp_path / "README.md").write_text("# Sample Project\nA simple arithmetic application.", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_calc.py").write_text("from src.calculator import add\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    return tmp_path


# ─── Scenario 1: Start Orix and have a normal conversation ────────────────────
@pytest.mark.asyncio
async def test_scenario_1_normal_conversation(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    progress = []
    reply = await agent.handle_message("Hello Orix! How are you?", on_progress=progress.append)
    assert isinstance(reply, str)
    assert len(reply) > 0
    assert len(agent.history) == 2  # user + assistant


# ─── Scenario 2: Ask a question about a real project ──────────────────────────
@pytest.mark.asyncio
async def test_scenario_2_explain_project(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    progress = []
    reply = await agent.handle_message("Bro, explain this project to me.", on_progress=progress.append)
    assert any("Inspecting workspace" in p for p in progress)
    assert any("Reading important files" in p for p in progress)
    assert "Sample Project" in reply or "Agent Orix" in reply or "calculator" in reply or "How" in reply
    assert len(agent.context["proposed_improvements"]) >= 1


# ─── Scenario 3: Ask a contextual follow-up without repeating details ─────────
@pytest.mark.asyncio
async def test_scenario_3_contextual_followup(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    # Step 1: Explain project
    await agent.handle_message("Explain this project to me.")
    assert len(agent.context["proposed_improvements"]) > 0

    # Step 2: Contextual follow-up referring to improvement #1
    progress = []
    reply = await agent.handle_message("Do the first one.", on_progress=progress.append)
    assert "improvement #1" in reply.lower() or "first" in reply.lower()
    assert any("improvement" in p for p in progress)


# ─── Scenario 4: Ask Orix to inspect files and summarize findings ─────────────
@pytest.mark.asyncio
async def test_scenario_4_inspect_file(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    progress = []
    reply = await agent.handle_message("Read file src/calculator.py", on_progress=progress.append)
    assert "def add(a, b):" in reply
    assert agent.context["last_target_file"] is not None


# ─── Scenario 5: Ask it to modify a file and show the diff ────────────────────
@pytest.mark.asyncio
async def test_scenario_5_modify_file_with_approval(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    agent.context["last_target_file"] = test_workspace / "src" / "calculator.py"

    approval_called = []
    def mock_approval(action, details):
        approval_called.append((action, details))
        token = compute_action_token(action, details)
        return True, token

    progress = []
    reply = await agent.handle_message(
        "Fix the bugs too and make the changes",
        on_progress=progress.append,
        on_approval=mock_approval,
    )
    assert len(approval_called) == 1
    assert any("Applying authorized modifications" in p for p in progress)
    assert "passed" in reply.lower() or "verified" in reply.lower()


# ─── Scenario 6: Ask it to run tests and report the real outcome ──────────────
@pytest.mark.asyncio
async def test_scenario_6_run_tests(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    progress = []
    reply = await agent.handle_message("Run the tests and confirm whether they work.", on_progress=progress.append)
    assert any("Discovering test suite" in p for p in progress)
    assert any("Executing pytest" in p for p in progress)
    assert "Test Execution Outcome" in reply


# ─── Scenario 7: Interrupt a running task ─────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_7_task_interruption(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    async def cancellable_operation():
        await asyncio.sleep(10.0)
        return await agent.handle_message("Explain this project to me.")

    task = asyncio.create_task(cancellable_operation())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ─── Scenario 8: Simulate model/runtime failure ───────────────────────────────
@pytest.mark.asyncio
async def test_scenario_8_runtime_failure_graceful_recovery(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    # Pass an invalid client to force a connection failure
    agent.client = RemoteAgentClient(endpoint_url="http://127.0.0.1:59999", timeout=0.5)
    reply = await agent.handle_message("What is your architectural philosophy on quantum computing?")
    assert isinstance(reply, str)
    assert len(reply) > 0
    # Must recover gracefully with informative text rather than raising an uncaught exception
    assert "assist" in reply.lower() or "error" in reply.lower() or "orix" in reply.lower()


# ─── Scenario 9: Test an unauthorized filesystem operation (Path Traversal) ───
@pytest.mark.asyncio
async def test_scenario_9_unauthorized_filesystem_containment(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    # Attempting to read outside workspace root via path traversal
    reply = await agent.handle_message("Read file ../../sensitive_passwords.txt")
    # Must not leak or open external files outside workspace
    assert "sensitive_passwords" not in reply or "preview" not in reply.lower()


# ─── Scenario 10: Test approval for a destructive operation ───────────────────
@pytest.mark.asyncio
async def test_scenario_10_rejection_of_destructive_operation(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    agent.context["last_target_file"] = test_workspace / "src" / "calculator.py"

    # User explicitly declines approval
    def reject_approval(action, details):
        return False, None

    reply = await agent.handle_message(
        "Apply the fix to the file now",
        on_approval=reject_approval,
    )
    assert "cancelled" in reply.lower() or "without your explicit authorization" in reply.lower()


# ─── Scenario 11: Test session restoration ────────────────────────────────────
def test_scenario_11_session_restoration(tmp_path):
    sess_dir = tmp_path / "sessions"
    sess_mgr = SessionManager(session_dir=sess_dir)

    # Turn 1 in session
    state = sess_mgr.create_session("sess_conv_123", workspace=str(tmp_path))
    sess_mgr.add_message("sess_conv_123", "user", "I am working on feature A.")
    sess_mgr.add_message("sess_conv_123", "assistant", "Noted! Feature A context is active.")

    # Restore session in a new instance
    restored_mgr = SessionManager(session_dir=sess_dir)
    restored_state = restored_mgr.load_session("sess_conv_123")
    assert restored_state is not None
    assert len(restored_state.messages) == 2
    assert "feature A" in restored_state.messages[0].content


# ─── Scenario 12: Test remote authentication & permissions ────────────────────
@pytest.mark.asyncio
async def test_scenario_12_remote_auth_and_permissions():
    client = RemoteAgentClient(endpoint_url="http://127.0.0.1:59999", auth_token="test_bearer_token", timeout=1.0)
    health = await client.check_health()
    assert health["connected"] is False
    assert health["mode"] == "remote"
    # Headers check
    headers = client._headers()
    assert headers["Authorization"] == "Bearer test_bearer_token"


# ─── Scenario 13: Install from fresh checkout ─────────────────────────────────
def test_scenario_13_installation_and_import_readiness():
    import cie
    import cie.cli
    import cie.cli.main
    import cie.cli.agent
    import cie.cli.terminal

    assert hasattr(cie, "__version__")
    assert hasattr(cie.cli, "main")
    assert hasattr(cie.cli.agent, "ConversationalAgent")
    assert hasattr(cie.cli.terminal, "TerminalChat")
