"""
Test Suite for Agent Orix Executing Agent Architecture.
Covers FIX 1 through FIX 6:
- TEST A: play fairy tale in chrome via youtube
- TEST B: build an html css website about yourself
- Create a Python file
- Create a single-file HTML website
- Explain existing code
- Edit an existing file
- Run a script
- Open Chrome
- Search YouTube
- Handle an ambiguous song
- Handle a missing browser / hardware tool
- Recover from tool errors truthfully
- Avoid repetitive and truncated generated content
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from cie.cli.agent import ConversationalAgent, deduplicate_loops
from cie.desktop.schemas import DesktopLaunchAppOutput


@pytest.fixture
def workspace_env():
    tmp_dir = tempfile.mkdtemp(prefix="orix_exec_agent_")
    ws = Path(tmp_dir)
    (ws / "main.py").write_text("print('Agent Orix Test Workspace')", encoding="utf-8")
    (ws / "README.md").write_text("# Test Project\nSample repository for verification.", encoding="utf-8")
    yield ws
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ─── TEST A: PLAY FAIRY TALE IN CHROME VIA YOUTUBE ─────────────────────────
@pytest.mark.asyncio
async def test_reproduction_a_play_fairy_tale_in_chrome_via_youtube(workspace_env):
    """
    TEST A Reproduction:
    User: 'play fairy tale in chrome via youtube'
    Must recognize song ('fairy tale'), destination (YouTube in Chrome),
    dispatch to desktop_launch_app with correct parameters, and report real verified launch.
    """
    agent = ConversationalAgent(workspace=str(workspace_env))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=24156,
        )

        resp = await agent.handle_message("play fairy tale in chrome via youtube")

        # 1. Verify tool invocation
        assert mock_launch.call_count == 1
        _, kwargs = mock_launch.call_args
        assert kwargs["app_name"] == "chrome"
        assert len(kwargs["args"]) == 1
        assert "youtube.com" in kwargs["args"][0]
        assert "fairy+tale" in kwargs["args"][0] or "fairy%20tale" in kwargs["args"][0]

        # 2. Verify response content
        assert "Successfully opened" in resp or "navigated" in resp.lower()
        assert "fairy tale" in resp.lower()
        assert "24156" in resp
        # Must NOT demand user to specify exact command
        assert "please specify the exact command" not in resp.lower()


# ─── TEST B: BUILD AN HTML CSS WEBSITE ABOUT YOURSELF ──────────────────────
@pytest.mark.asyncio
async def test_reproduction_b_build_website_about_yourself(workspace_env):
    """
    TEST B Reproduction:
    User: 'build an html css website about yourself'
    Must create a complete, valid index.html in the workspace,
    embed modern styling and interactivity, report real path, and avoid looping text.
    """
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("build an html css website about yourself")

    # 1. Verify file was created in workspace
    index_file = workspace_env / "index.html"
    assert index_file.exists(), "index.html was not created on disk"

    # 2. Verify file content integrity
    content = index_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<html" in content and "</html>" in content
    assert "<head>" in content and "</head>" in content
    assert "<body" in content and "</body>" in content
    assert "<style>" in content and "</style>" in content
    assert "<script>" in content and "</script>" in content
    assert "Agent Orix" in content

    # 3. Verify no degenerate repetition loop
    assert content.count("evidence-driven and systematic") <= 1

    # 4. Verify response mentions target file, path, and unified diff
    assert "Website Built Successfully" in resp
    assert "index.html" in resp
    assert str(index_file.resolve()) in resp or str(workspace_env.name) in resp
    assert "diff" in resp.lower()


# ─── CREATE A PYTHON FILE ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_python_file(workspace_env):
    """Verify creating an actual Python file with AST syntax check."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("create a python file fibonacci.py")

    fib_file = workspace_env / "fibonacci.py"
    assert fib_file.exists()
    content = fib_file.read_text(encoding="utf-8")
    assert "compute_fibonacci" in content
    assert "Python File Created & Verified" in resp
    assert "100% valid Python AST" in resp


# ─── CREATE A SINGLE-FILE HTML WEBSITE ─────────────────────────────────────
@pytest.mark.asyncio
async def test_create_single_file_html_website(workspace_env):
    """Verify standard single-file HTML website creation."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("build a website for my portfolio")

    index_file = workspace_env / "index.html"
    assert index_file.exists()
    assert "Website Built Successfully" in resp
    assert "index.html" in resp


# ─── EXPLAIN EXISTING CODE ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_explain_existing_code(workspace_env):
    """Verify codebase inspection and explanation."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("explain this codebase")

    assert "How" in resp and "Works" in resp
    assert workspace_env.name in resp
    assert len(agent.context["proposed_improvements"]) > 0


# ─── EDIT AN EXISTING FILE ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_edit_existing_file(workspace_env):
    """Verify focused editing of an existing file in workspace."""
    sample_file = workspace_env / "module.py"
    sample_file.write_text("def base_func():\n    return 42\n", encoding="utf-8")

    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("edit file module.py")

    assert "File Modified & Verified" in resp
    assert "module.py" in resp
    assert (workspace_env / "module.py").exists()
    new_content = sample_file.read_text(encoding="utf-8")
    assert "health_check" in new_content


# ─── RUN A SCRIPT ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_script(workspace_env):
    """Verify running a script via bounded project command execution."""
    test_script = workspace_env / "test_run.py"
    test_script.write_text("print('SCRIPT_EXECUTION_SUCCESS_9182')", encoding="utf-8")

    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("run script test_run.py")

    assert "SCRIPT_EXECUTION_SUCCESS_9182" in resp
    assert "Exit Code: `0`" in resp or "Exit Code" in resp


# ─── OPEN CHROME ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_open_chrome(workspace_env):
    """Verify application launch for Chrome."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=1122,
        )
        resp = await agent.handle_message("Open Chrome")
        assert mock_launch.call_count == 1
        assert "Google Chrome" in resp
        assert "1122" in resp


# ─── SEARCH YOUTUBE ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_youtube(workspace_env):
    """Verify direct YouTube search query."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=3344,
        )
        resp = await agent.handle_message("search youtube for Bohemian Rhapsody")
        assert mock_launch.call_count == 1
        _, kwargs = mock_launch.call_args
        assert "Bohemian" in kwargs["args"][0]
        assert "YouTube search for 'Bohemian Rhapsody'" in resp


# ─── HANDLE AN AMBIGUOUS SONG ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_handle_ambiguous_song(workspace_env):
    """Verify specific clarification request when song query is unspecified."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("play this song in chrome via youtube")

    assert "which song" in resp.lower() or "artist" in resp.lower()
    assert agent.context.get("pending_action") is not None

    # Follow-up with song name
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=5566,
        )
        followup_resp = await agent.handle_message("Coldplay - Yellow")
        assert mock_launch.call_count == 1
        assert "Coldplay" in followup_resp or "yellow" in followup_resp.lower()


# ─── HANDLE A MISSING BROWSER / HARDWARE TOOL ──────────────────────────────
@pytest.mark.asyncio
async def test_handle_missing_browser_tool(workspace_env):
    """Verify graceful rejection with alternative for unsupported capability."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    resp = await agent.handle_message("flash firmware to esp32 microcontroller")

    assert "unsupported" in resp.lower()
    assert "firmware_flashing" in resp.lower() or "alternative" in resp.lower()


# ─── RECOVER FROM TOOL ERRORS ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_recover_from_tool_errors(workspace_env):
    """Verify truthful error reporting when tool launch fails."""
    agent = ConversationalAgent(workspace=str(workspace_env))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=False,
            app_name="chrome",
            error="Chrome binary not found on PATH or registry",
        )
        resp = await agent.handle_message("open chrome")
        assert "Unable to open" in resp
        assert "Chrome binary not found" in resp


# ─── AVOID REPETITIVE AND TRUNCATED GENERATED CONTENT ──────────────────────
def test_avoid_repetitive_content():
    """Verify deduplicate_loops trims degenerate Markov repetition."""
    looping_text = (
        "Welcome! I am an AI assistant. "
        "I am evidence-driven and systematic. "
        "I am evidence-driven and systematic. "
        "I am evidence-driven and systematic. "
        "I am evidence-driven and systematic. "
    )
    trimmed = deduplicate_loops(looping_text)
    assert trimmed.count("I am evidence-driven and systematic.") <= 2
    assert "trimmed" in trimmed.lower()
