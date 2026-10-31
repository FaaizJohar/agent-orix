"""
Phase 21 Comprehensive Test Suite: Full Harness Activation, Universal Task Execution & Conversational Intelligence.
Covers all 18 required scenarios:
1. Open Chrome
2. Navigate to YouTube
3. Search for a specified song
4. Create a single-file HTML website
5. Create and execute a Python script
6. Inspect a project
7. Fix a failing test
8. Install project dependencies
9. Run a development server
10. Diagnose a build failure
11. Explain Cavrix Core using authoritative knowledge source
12. Explain Cavrix Code without confusing with Cavrix Core
13. Handle missing tools
14. Handle failed commands
15. Handle approval-denied operations
16. Preserve context across follow-up messages
17. Prevent unauthorized file modifications
18. Report actual results without false success claims
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest

from cie.cli.agent import ConversationalAgent


@pytest.fixture
def clean_workspace():
    tmp_dir = tempfile.mkdtemp(prefix="phase21_test_")
    ws = Path(tmp_dir)
    # Populate minimal workspace structure
    (ws / "main.py").write_text("print('Hello from Agent Orix')", encoding="utf-8")
    (ws / "README.md").write_text("# Project Alpha\nSample test repository.", encoding="utf-8")
    yield ws
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_scenario_01_open_chrome(clean_workspace):
    """Scenario 1: Open Chrome."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Open Chrome")
    assert "google chrome" in resp.lower() or "opened" in resp.lower()
    assert "i can't assist with that" not in resp.lower()


@pytest.mark.asyncio
async def test_scenario_02_navigate_to_youtube(clean_workspace):
    """Scenario 2: Navigate to YouTube."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Navigate to YouTube")
    assert "youtube" in resp.lower()
    assert "google chrome" in resp.lower() or "opened" in resp.lower()
    assert "i can't assist with that" not in resp.lower()


@pytest.mark.asyncio
async def test_scenario_03_search_for_specified_song(clean_workspace):
    """Scenario 3: Search for a specified song vs ambiguous search."""
    agent = ConversationalAgent(workspace=str(clean_workspace))

    # 3a. Ambiguous query -> NEEDS CLARIFICATION
    resp_ambiguous = await agent.handle_message("Search YouTube for this song")
    assert "which song" in resp_ambiguous.lower() or "clarif" in resp_ambiguous.lower() or "artist" in resp_ambiguous.lower()

    # 3b. Follow-up with song name -> EXECUTED
    resp_followup = await agent.handle_message("Bohemian Rhapsody")
    assert "bohemian rhapsody" in resp_followup.lower()
    assert "youtube" in resp_followup.lower()

    # 3c. Direct specified search -> EXECUTED
    resp_direct = await agent.handle_message("Search YouTube for Shape of You")
    assert "shape of you" in resp_direct.lower()
    assert "youtube" in resp_direct.lower()


@pytest.mark.asyncio
async def test_scenario_04_create_html_website(clean_workspace):
    """Scenario 4: Create a single-file HTML website."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Build me a website")
    assert "index.html" in resp
    assert (clean_workspace / "index.html").exists()
    content = (clean_workspace / "index.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<script>" in content


@pytest.mark.asyncio
async def test_scenario_05_create_and_execute_python_script(clean_workspace):
    """Scenario 5: Create and execute a Python script."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Create and execute a Python script")
    assert "orix_task_script.py" in resp or "script" in resp.lower()
    assert "Exit Code `0`" in resp or "PASSED" in resp
    assert (clean_workspace / "orix_task_script.py").exists()


@pytest.mark.asyncio
async def test_scenario_06_inspect_project(clean_workspace):
    """Scenario 6: Inspect a project."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Inspect this project")
    assert clean_workspace.name in resp
    assert "Architecture" in resp or "Overview" in resp
    assert len(agent.context["proposed_improvements"]) > 0


@pytest.mark.asyncio
async def test_scenario_07_fix_failing_test(clean_workspace):
    """Scenario 7: Fix a failing test."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    # Step 1: Deliberately failing test diagnosis & repair
    diag = await agent.handle_message("Diagnose deliberately failing test")
    assert "orix_calc.py" in diag
    assert "calculate_sum" in diag or "Root Cause:" in diag
    assert "PASSED" in diag

    # Step 2: Follow-up verification
    fix = await agent.handle_message("Fix it")
    assert "passed" in fix.lower() or "verified" in fix.lower()


@pytest.mark.asyncio
async def test_scenario_08_install_project_dependencies(clean_workspace):
    """Scenario 8: Install project dependencies."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Install project dependencies")
    assert "requirements.txt" in resp
    assert (clean_workspace / "requirements.txt").exists()


@pytest.mark.asyncio
async def test_scenario_09_run_development_server(clean_workspace):
    """Scenario 9: Run a development server."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Run a development server")
    assert "8000" in resp or "http://" in resp
    assert "Development Server Ready" in resp or "bound" in resp.lower()


@pytest.mark.asyncio
async def test_scenario_10_diagnose_build_failure(clean_workspace):
    """Scenario 10: Diagnose a build failure."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    # Introduce syntax error
    bad_file = clean_workspace / "broken.py"
    bad_file.write_text("def faulty(\n", encoding="utf-8")

    resp = await agent.handle_message("Find why my application crashes")
    assert "broken.py" in resp
    assert "Line" in resp or "Syntax" in resp or "faulty" in resp


@pytest.mark.asyncio
async def test_scenario_11_explain_cavrix_core(clean_workspace):
    """Scenario 11: Explain Cavrix Core using authoritative knowledge source."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Tell me about Cavrix Core")
    assert "Cavrix Core" in resp
    assert "Faaiz Johar" in resp
    # Must NOT confuse with Cavrix Code coding assistant
    assert "lightweight bilingual ai coding assistant" not in resp.lower()
    # Must NOT leak internal chunk tokens or paths
    assert "[Doc" not in resp
    assert "Chunk" not in resp


@pytest.mark.asyncio
async def test_scenario_12_explain_cavrix_code(clean_workspace):
    """Scenario 12: Explain Cavrix Code without confusing with Cavrix Core."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("What is Cavrix Code?")
    assert "Cavrix Code" in resp
    assert "assistant" in resp.lower() or "pair programming" in resp.lower()


@pytest.mark.asyncio
async def test_scenario_13_handle_missing_tools(clean_workspace):
    """Scenario 13: Handle missing / unsupported tools."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Deploy to Kubernetes cluster on AWS")
    assert "unsupported" in resp.lower()
    assert "kubernetes" in resp.lower()
    assert "alternative" in resp.lower()


@pytest.mark.asyncio
async def test_scenario_14_handle_failed_commands(clean_workspace):
    """Scenario 14: Handle failed commands truthfully without false success."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("run command: python -c \"import sys; sys.exit(42)\"")
    assert "Failed" in resp or "Exit Code: `42`" in resp
    assert "Succeeded" not in resp


@pytest.mark.asyncio
async def test_scenario_15_handle_approval_denied_operations(clean_workspace):
    """Scenario 15: Handle approval-denied operations safely."""
    agent = ConversationalAgent(workspace=str(clean_workspace))

    def deny_approval(action, details):
        return False, None

    resp = await agent.handle_message("Build me a website", on_approval=deny_approval)
    assert "cancelled" in resp.lower() or "authorization" in resp.lower()
    assert not (clean_workspace / "index.html").exists()


@pytest.mark.asyncio
async def test_scenario_16_preserve_context_across_followups(clean_workspace):
    """Scenario 16: Preserve context across follow-up messages."""
    agent = ConversationalAgent(workspace=str(clean_workspace))

    # Turn 1: Open Chrome
    t1 = await agent.handle_message("Open Chrome")
    assert "google chrome" in t1.lower()

    # Turn 2: Now open YouTube
    t2 = await agent.handle_message("Now open YouTube")
    assert "youtube" in t2.lower()

    # Turn 3: Contextual confirmation
    t3 = await agent.handle_message("Do it")
    assert "youtube" in t3.lower() or "opened" in t3.lower()


@pytest.mark.asyncio
async def test_scenario_17_prevent_unauthorized_file_modifications(clean_workspace):
    """Scenario 17: Prevent unauthorized file modifications and path traversal."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    resp = await agent.handle_message("Read file ../../../windows/system32/cmd.exe")
    assert "Security violation" in resp or "prohibited" in resp.lower()


@pytest.mark.asyncio
async def test_scenario_18_report_actual_results(clean_workspace):
    """Scenario 18: Report actual results without false success claims."""
    agent = ConversationalAgent(workspace=str(clean_workspace))
    # Execute valid command
    resp = await agent.handle_message("run command: python -c \"print('REAL_OUTPUT_4821')\"")
    assert "REAL_OUTPUT_4821" in resp
    assert "Exit Code:" in resp
    assert "`0`" in resp
