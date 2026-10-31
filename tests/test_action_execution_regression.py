"""
Regression Test Suite for Natural-Language Action Execution & Contextual Follow-ups.
Verifies:
1. Deterministic intent routing for application and browser launches.
2. Real tool execution (desktop_launch_app) instead of raw conversational text.
3. Multi-turn follow-ups ("open", "do it", "yes", "bro you have to open it") using pending/prior context.
4. Error reporting when target application or browser is missing.
5. Security policy enforcement blocking prohibited shells and SSRF URLs.
6. No false success claims without tool verification.
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from cie.cli.agent import ConversationalAgent
from cie.desktop.schemas import DesktopLaunchAppOutput
from cie.desktop.manager import get_desktop_manager
from cie.skills.registry import get_default_registry


@pytest.fixture
def agent():
    return ConversationalAgent(workspace="E:/agent-orix")


@pytest.mark.asyncio
async def test_open_youtube_in_chrome_invokes_real_tool(agent):
    """Verify that 'open youtube in chrome' invokes desktop_launch_app with the right parameters."""
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=1234,
        )

        reply = await agent.handle_message("open youtube in chrome")

        assert mock_launch.call_count == 1
        args, kwargs = mock_launch.call_args
        assert kwargs["app_name"] == "chrome"
        assert kwargs["args"] == ["https://www.youtube.com"]
        assert "Successfully opened YouTube (https://www.youtube.com) using Google Chrome (Process ID: 1234)." in reply
        # Verify it did not just chat back telling the user to open it
        assert "please go ahead and open" not in reply.lower()


@pytest.mark.asyncio
async def test_followup_bro_you_have_to_open_it_executes_action(agent):
    """Verify multi-turn follow-ups execute the pending action instead of debating."""
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="chrome",
            process_name="chrome.exe",
            pid=2345,
        )

        # Turn 1
        await agent.handle_message("open youtube in chrome")
        assert mock_launch.call_count == 1

        # Turn 2: User says "open"
        reply2 = await agent.handle_message("open")
        assert mock_launch.call_count == 2
        assert "Successfully opened" in reply2

        # Turn 3: User says "bro you have to open it"
        reply3 = await agent.handle_message("bro you have to open it")
        assert mock_launch.call_count == 3
        assert "Successfully opened" in reply3

        # Turn 4: User says "yes"
        reply4 = await agent.handle_message("yes")
        assert mock_launch.call_count == 4
        assert "Successfully opened" in reply4


@pytest.mark.asyncio
async def test_open_notepad_and_calculator(agent):
    """Verify direct natural-language actions for standard desktop tools."""
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="notepad",
            process_name="notepad.exe",
            pid=3456,
        )
        r_np = await agent.handle_message("open notepad")
        assert "Successfully opened Notepad using Notepad" in r_np
        assert mock_launch.call_args[1]["app_name"] == "notepad"

        mock_launch.return_value = DesktopLaunchAppOutput(
            success=True,
            app_name="calc",
            process_name="calc.exe",
            pid=3457,
        )
        r_calc = await agent.handle_message("open calculator")
        assert "Successfully opened Calculator using Calculator" in r_calc
        assert mock_launch.call_args[1]["app_name"] == "calc"


@pytest.mark.asyncio
async def test_chrome_missing_reports_actionable_error(agent):
    """Verify that when Chrome is missing, the exact actionable error is reported, not false success."""
    with patch("cie.skills.tools.desktop_tools.desktop_launch_app", new_callable=AsyncMock) as mock_launch:
        mock_launch.return_value = DesktopLaunchAppOutput(
            success=False,
            app_name="chrome",
            process_name="chrome.exe",
            error="Application 'chrome' was not found on this system.",
        )
        reply = await agent.handle_message("open youtube in chrome")
        assert "Unable to open YouTube (https://www.youtube.com): Application 'chrome' was not found on this system." in reply
        # Must never claim success when tool fails
        assert "successfully" not in reply.lower()


@pytest.mark.asyncio
async def test_prohibited_application_blocked_by_policy(agent):
    """Verify that system shells and administrative consoles are rejected by policy."""
    reply = await agent.handle_message("open powershell")
    assert "Unable to open Powershell: Access to system shell or administrative process 'powershell.exe' is strictly prohibited" in reply


@pytest.mark.asyncio
async def test_ssrf_url_blocked_during_app_launch(agent):
    """Verify that launching a browser with an SSRF cloud metadata URL is blocked."""
    reply = await agent.handle_message("open http://169.254.169.254 in chrome")
    assert "Unable to open" in reply
    assert any(term in reply.lower() for term in ["ssrf", "validation failed", "prohibited"])


def test_tool_is_registered_in_skill_registry():
    """Verify that desktop_launch_app is formally registered in the Skills Registry."""
    registry = get_default_registry()
    tool = registry.get_tool("desktop_launch_app")
    assert tool is not None
    assert tool.name == "desktop_launch_app"
    assert tool.permission.name == "LOCAL_WRITE" or tool.permission.value == "LOCAL_WRITE"
    handler = registry.get_handler("desktop_launch_app")
    assert callable(handler)


def test_real_windows_launch_app_security_and_resolution():
    """Smoke test DesktopManager.launch_app parameter validation on Windows without spawning windows."""
    dm = get_desktop_manager()
    # 1. Empty app name
    res_empty = dm.launch_app("")
    assert res_empty.success is False
    assert "empty" in res_empty.error.lower()

    # 2. Prohibited app (cmd.exe)
    res_proh = dm.launch_app("cmd.exe")
    assert res_proh.success is False
    assert "prohibited" in res_proh.error.lower()

    # 3. Non-allowlisted app
    res_unknown = dm.launch_app("random_malware.exe")
    assert res_unknown.success is False
    assert "not permitted" in res_unknown.error.lower()

    # 4. SSRF URL rejection
    res_ssrf = dm.launch_app("chrome", args=["http://127.0.0.1:8080/admin"])
    assert res_ssrf.success is False
    assert "ssrf" in res_ssrf.error.lower() or "validation failed" in res_ssrf.error.lower()
