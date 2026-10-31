"""
Agent Orix - Phase G: Competitive Coding Agent Verification Suite
Tests all 12 non-negotiable scenarios:
1. Open YouTube in Chrome (real action execution and output).
2. Open supported desktop application (Notepad/Calculator).
3. Explain repository using actual file evidence (README/pyproject).
4. Explain Cavrix Core vs Cavrix Code (truthful separation, zero model specs on company).
5. Implement multi-file code change and run tests (unified diffs, pytest exit code 0).
6. Diagnose deliberately failing test (pinpoint root cause from trace, patch, rerun test).
7. Handle missing tool/app without false success (truthful error message).
8. Continue multi-turn task without losing pending action (follow-up 'do it' / 'yes').
9. Respect approval requirements for protected modifications (cancellation on denial).
10. Reject workspace escape attempts and redact secrets (../../windows blocked, secrets masked).
11. Avoid exposing internal paths and raw retrieval metadata (no Doc_, no [Chunk 1], no E:\\).
12. Recover safely from a failed command (truthful non-zero exit code reporting, recovery steps).
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cie.cli.agent import ConversationalAgent
from cie.desktop.schemas import DesktopLaunchAppOutput
from cie.knowledge.grounding import KnowledgeGrounding


@pytest.fixture
def test_workspace(tmp_path):
    """Initializes a clean, realistic isolated workspace."""
    (tmp_path / "README.md").write_text("# Project Alpha\nA high-performance data processing service.", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "project-alpha"\nversion = "0.1.0"\n', encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "service.py").write_text("def process(data):\n    return [x * 2 for x in data]\n", encoding="utf-8")
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_service.py").write_text("from src.service import process\ndef test_process():\n    assert process([1, 2]) == [2, 4]\n", encoding="utf-8")
    return tmp_path


# ─── 1. Open YouTube in Chrome ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_01_open_youtube_in_chrome(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=1234,
        )

        progress = []
        resp = await agent.handle_message("open youtube in chrome", on_progress=progress.append)

        assert mock_launch.call_count == 1
        args, kwargs = mock_launch.call_args
        assert kwargs["app_name"] == "chrome"
        assert kwargs["args"] == ["https://www.youtube.com"]
        assert "Successfully opened YouTube (https://www.youtube.com) using Google Chrome (Process ID: 1234)." in resp
        assert "please go ahead and open" not in resp.lower()


# ─── 2. Open Supported Desktop Application ──────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_02_open_desktop_application(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="notepad",
            process_name="notepad.exe",
            pid=5678,
        )

        resp = await agent.handle_message("open notepad")
        assert mock_launch.call_count == 1
        assert "Successfully opened Notepad using Notepad (Process ID: 5678)." in resp


# ─── 3. Explain Repository Using Actual File Evidence ───────────────────────
@pytest.mark.asyncio
async def test_scenario_03_explain_repository_using_file_evidence(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    resp = await agent.handle_message("explain this project")

    assert "Project Alpha" in resp
    assert "data processing service" in resp
    assert "Proposed Next Improvements" in resp


# ─── 4. Explain Cavrix Core vs Cavrix Code ──────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_04_cavrix_core_vs_code_identity(test_workspace):
    grounding = KnowledgeGrounding()
    cleaned = grounding.format_grounded_response(
        query="tell me about cavrix core",
        raw_text="Cavrix Core is the parent technology company founded by Faaiz Johar and Mohd Fahad. Cavrix Code is the local AI assistant product.",
        sources=[{"title": "Cavrix Core — Official Profile", "path": "E:\\docs\\profile.md"}]
    )

    assert "Cavrix Core" in cleaned
    assert "Faaiz Johar" in cleaned
    assert "Mohd Fahad" in cleaned
    # Never expose internal filesystem path
    assert "E:\\" not in cleaned
    assert "profile.md" not in cleaned


# ─── 5. Implement Multi-File Code Change & Run Tests ─────────────────────────
@pytest.mark.asyncio
async def test_scenario_05_multi_file_code_change_and_tests(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    resp = await agent.handle_message("implement multi-file code change and run tests")

    assert "Multi-File Changes Implemented & Verified" in resp
    assert "Exit Code: `0`" in resp
    assert "PASSED" in resp
    assert (test_workspace / "orix_sample_module.py").exists()
    assert (test_workspace / "test_orix_sample_module.py").exists()


# ─── 6. Diagnose Deliberately Failing Test ───────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_06_diagnose_and_repair_failing_test(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    resp = await agent.handle_message("diagnose deliberately failing test")

    assert "Failure Diagnosis & Automated Resolution" in resp
    assert "Root Cause:" in resp
    assert "orix_calc.py" in resp
    assert "Exit Code" in resp
    assert "PASSED" in resp


# ─── 7. Handle Missing Tool/App Without False Success ────────────────────────
@pytest.mark.asyncio
async def test_scenario_07_handle_missing_tool_without_false_success(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    resp = await agent.handle_message("open nonexistent_fake_app_9999")

    # Truthful reporting: must report unable to open and not claim success
    assert "unable to open" in resp.lower() or "not allowed" in resp.lower() or "unrecognized" in resp.lower()
    assert "successfully opened" not in resp.lower()


# ─── 8. Continue Multi-Turn Task Without Losing Pending Action ───────────────
@pytest.mark.asyncio
async def test_scenario_08_multi_turn_continuation(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=2345,
        )

        # Set pending action with full display context
        agent.context["pending_action"] = {
            "tool_name": "desktop_launch_app",
            "app_name": "chrome",
            "display_name": "Google Chrome",
            "display_target": "YouTube (https://www.youtube.com)",
            "args": ["https://www.youtube.com"],
            "url": "https://www.youtube.com",
        }

        # Follow-up trigger
        resp = await agent.handle_message("bro you have to open it")
        assert mock_launch.call_count == 1
        assert "Successfully opened YouTube (https://www.youtube.com) using Google Chrome (Process ID: 2345)." in resp
        assert agent.context.get("pending_action") is None


# ─── 9. Respect Approval Requirements for Protected Modifications ────────────
@pytest.mark.asyncio
async def test_scenario_09_respect_approval_requirements(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))

    def deny_approval(action_type, params):
        return False, None

    resp = await agent.handle_message(
        "implement multi-file code change and run tests",
        on_approval=deny_approval
    )

    assert "Action cancelled" in resp
    assert "authorization" in resp.lower()
    # Confirm files were NOT created when denied
    assert not (test_workspace / "orix_sample_module.py").exists()


# ─── 10. Reject Workspace Escape Attempts & Redact Secrets ───────────────────
@pytest.mark.asyncio
async def test_scenario_10_workspace_escape_and_secret_redaction(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))

    # Test 10a: Workspace containment
    resp = await agent.handle_message("read file ../../windows/system.ini")
    assert "security violation" in resp.lower() or "workspace boundary" in resp.lower()

    # Test 10b: Secret redaction in command execution
    resp_cmd = await agent.handle_message("run command: python -c \"print('Secret: ghp_1234567890abcdef1234567890abcdef')\"")
    assert "ghp_1234567890abcdef1234567890abcdef" not in resp_cmd
    assert "[REDACTED_SECRET]" in resp_cmd or "REDACTED" in resp_cmd


# ─── 11. Avoid Exposing Internal Paths and Raw Retrieval Metadata ────────────
@pytest.mark.asyncio
async def test_scenario_11_suppress_internal_paths_and_raw_chunks(test_workspace):
    grounding = KnowledgeGrounding()
    raw = (
        "Document: Doc_9999\n"
        "[Chunk 1] Source: E:\\agent-orix\\cie\\data\\profile.json\n"
        "Score: 0.9998\n"
        "Cavrix Core is a developer-focused technology company."
    )
    cleaned = grounding.format_grounded_response(
        query="tell me about cavrix core",
        raw_text=raw,
        sources=[{"title": "Cavrix Core Profile", "path": "E:\\agent-orix\\cie\\data\\profile.json"}]
    )

    assert "Doc_9999" not in cleaned
    assert "[Chunk 1]" not in cleaned
    assert "E:\\agent-orix" not in cleaned
    assert "Cavrix Core is a developer-focused technology company." in cleaned


# ─── 12. Recover Safely from a Failed Command ────────────────────────────────
@pytest.mark.asyncio
async def test_scenario_12_recover_safely_from_failed_command(test_workspace):
    agent = ConversationalAgent(workspace=str(test_workspace))
    resp = await agent.handle_message("run command: python -c \"import sys; sys.exit(42)\"")

    assert "Command Execution Failed" in resp
    assert "42" in resp
    assert "NON-ZERO FAILURE" in resp
    assert "Actionable recovery" in resp
