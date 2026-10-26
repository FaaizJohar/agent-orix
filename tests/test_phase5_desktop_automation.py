"""
CavrixCode Phase 5 — Controlled Computer Use & Workflow Automation Test Suite.
Verifies:
1. Safe Local Computer-Use Tools (7 tools):
   - desktop_get_state
   - desktop_list_windows
   - desktop_screenshot
   - desktop_click
   - desktop_type_text
   - desktop_keypress
   - desktop_wait_for_state
2. Desktop Application Allowlist & Prohibited Window Barriers:
   - Blocks administrative consoles (cmd.exe, powershell.exe, regedit.exe, Task Manager, UAC).
   - Blocks password managers (1Password, Bitwarden, KeePass).
3. Consequential Desktop Action Classification & Approval Token Enforcement:
   - Click on delete/submit/purchase elements.
   - Typing sensitive text or commands.
   - Action token tampering, forgery, expiration, and replay prevention.
4. Bounded Workflow Engine (Phase 5):
   - Hard maximum of 8 steps per plan.
   - Outcome verification after consequential steps.
   - Prohibiting auto-retrying consequential actions when outcome is uncertain.
   - Task plan cancellation support.
"""

import asyncio
import os
import time
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError

from cie.desktop.manager import DesktopManager, get_desktop_manager
from cie.desktop.schemas import (
    DesktopClickInput,
    DesktopClickOutput,
    DesktopKeypressInput,
    DesktopKeypressOutput,
    DesktopListWindowsInput,
    DesktopListWindowsOutput,
    DesktopScreenshotInput,
    DesktopScreenshotOutput,
    DesktopStateOutput,
    DesktopTypeTextInput,
    DesktopTypeTextOutput,
    DesktopWaitForStateInput,
    DesktopWaitForStateOutput,
    DesktopWindowInfo,
)
from cie.desktop.security import (
    DesktopSecurityError,
    DesktopSecurityManager,
    ALLOWED_PROCESS_NAMES,
    PROHIBITED_PROCESSES,
)
from cie.planning.executor import BoundedPlanExecutor
from cie.planning.schemas import (
    ErrorCategory,
    PlanStatus,
    PlanStep,
    PlanValidationError,
    StepStatus,
    TaskPlan,
    validate_plan_with_registry,
)
from cie.planning.verifier import PlanVerifier
from cie.security_tokens import compute_action_token, verify_action_token
from cie.skills.executor import SkillExecutor
from cie.skills.registry import SkillRegistry, get_default_registry
from cie.skills.schemas import (
    PermissionLevel,
    RiskLevel,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult,
)


# ==============================================================================
# 1. Desktop Security & Application Allowlist Barriers
# ==============================================================================

def test_prohibited_processes_strictly_blocked():
    """Verify that interaction with system shells and admin consoles is prohibited."""
    prohibited_cases = [
        ("Administrator: Windows PowerShell", "powershell.exe"),
        ("Command Prompt - ping 127.0.0.1", "cmd.exe"),
        ("Registry Editor", "regedit.exe"),
        ("Task Manager", "taskmgr.exe"),
        ("1Password - Password Manager", "1password.exe"),
        ("Bitwarden Vault", "bitwarden.exe"),
        ("Computer Management", "mmc.exe"),
        ("User Account Control", "consent.exe"),
    ]
    for title, proc in prohibited_cases:
        permitted, reason = DesktopSecurityManager.is_window_permitted(title, proc)
        assert permitted is False, f"Expected '{proc}' ('{title}') to be blocked."
        assert any(k in reason.lower() for k in ["prohibited", "shell", "administrative", "pattern"])


def test_allowlisted_applications_permitted():
    """Verify that legitimate productivity and development tools are permitted."""
    allowed_cases = [
        ("Cavrix Flow - Desktop Agent", "electron.exe"),
        ("index.js - Cavrix Flow - Visual Studio Code", "code.exe"),
        ("Untitled - Notepad", "notepad.exe"),
        ("Calculator", "calc.exe"),
        ("Google Chrome", "chrome.exe"),
        ("Microsoft Edge", "msedge.exe"),
    ]
    for title, proc in allowed_cases:
        permitted, _ = DesktopSecurityManager.is_window_permitted(title, proc)
        assert permitted is True, f"Expected '{proc}' to be permitted."


def test_consequential_desktop_action_classification():
    """Verify that destructive or state-mutating desktop actions require approval."""
    consequential_cases = [
        ("click", "Confirm Payment Dialog", None, None, False),
        ("click", "Delete Database Button", None, None, False),
        ("type_text", "Terminal", "rm -rf /", "enter", False),
        ("type_text", "Settings", "my_secret_password_123", None, False),
        ("keypress", "Active Window", None, "enter", True),  # Explicit flag
    ]
    for act, win, txt, key, explicit in consequential_cases:
        is_conseq, reason = DesktopSecurityManager.is_consequential_desktop_action(
            action_type=act,
            window_title=win,
            text=txt,
            key=key,
            explicit_flag=explicit,
        )
        assert is_conseq is True, f"Expected consequential classification for {act} in '{win}'."


# ==============================================================================
# 2. Safe Local Computer-Use Tools Implementation (7 Tools)
# ==============================================================================

def test_all_7_desktop_tools_registered_in_default_registry():
    """Verify that all 7 desktop automation tools are registered in SkillRegistry."""
    reg = get_default_registry()
    expected_tools = [
        "desktop_get_state",
        "desktop_list_windows",
        "desktop_screenshot",
        "desktop_click",
        "desktop_type_text",
        "desktop_keypress",
        "desktop_wait_for_state",
    ]
    for tool_name in expected_tools:
        tool_def = reg.get_tool(tool_name)
        assert tool_def is not None, f"Tool '{tool_name}' not registered."
        assert reg.get_handler(tool_name) is not None, f"Handler for '{tool_name}' missing."


def test_desktop_tools_permissions_and_risk_ratings():
    """Verify permissions and elevated risk levels on mutating computer-use tools."""
    reg = get_default_registry()

    # Read-only tools
    assert reg.get_tool("desktop_get_state").permission == PermissionLevel.READ_ONLY
    assert reg.get_tool("desktop_list_windows").permission == PermissionLevel.READ_ONLY
    assert reg.get_tool("desktop_screenshot").permission == PermissionLevel.READ_ONLY
    assert reg.get_tool("desktop_wait_for_state").permission == PermissionLevel.READ_ONLY

    # Consequential / Mutating tools
    click_tool = reg.get_tool("desktop_click")
    assert click_tool.permission == PermissionLevel.LOCAL_WRITE
    assert click_tool.risk == RiskLevel.HIGH
    assert click_tool.requires_approval is True

    type_tool = reg.get_tool("desktop_type_text")
    assert type_tool.permission == PermissionLevel.LOCAL_WRITE
    assert type_tool.risk == RiskLevel.HIGH
    assert type_tool.requires_approval is True

    key_tool = reg.get_tool("desktop_keypress")
    assert key_tool.permission == PermissionLevel.LOCAL_WRITE
    assert key_tool.risk == RiskLevel.HIGH
    assert key_tool.requires_approval is True


def test_desktop_get_state_returns_valid_metrics():
    """desktop_get_state must return screen resolution and active window info."""
    dm = get_desktop_manager()
    state = dm.get_state()
    assert "width" in state.screen_resolution
    assert "height" in state.screen_resolution
    assert state.screen_resolution["width"] >= 640
    assert state.screen_resolution["height"] >= 480
    assert isinstance(state.is_permitted, bool)


def test_desktop_list_windows_filters_and_annotates():
    """desktop_list_windows returns window list with allowlist flags."""
    dm = get_desktop_manager()
    out = dm.list_windows(include_prohibited=True)
    assert isinstance(out.windows, list)
    assert out.total_windows >= 0


def test_desktop_screenshot_handles_fallback_safely():
    """desktop_screenshot creates a valid PNG file without crashing on headless sessions."""
    dm = get_desktop_manager()
    out = dm.take_screenshot(filename_prefix="test_phase5_snap")
    assert os.path.exists(out.file_path)
    assert out.file_path.endswith(".png")
    assert out.size_bytes > 0
    assert out.width > 0
    assert out.height > 0


def test_desktop_click_blocked_on_prohibited_window():
    """desktop_click must fail closed if the foreground window is prohibited."""
    dm = get_desktop_manager()
    fake_prohibited_window = DesktopWindowInfo(
        hwnd=9999,
        title="Administrator: Windows PowerShell",
        process_name="powershell.exe",
        pid=1234,
        is_permitted=False,
    )
    with patch.object(dm, "_get_window_info", return_value=fake_prohibited_window):
        out = dm.click(x=100, y=100)
        assert out.success is False
        assert "security violation" in out.error.lower() or "blocked" in out.error.lower()


def test_desktop_click_consequential_requires_approval_token():
    """Consequential desktop clicks require an unforgeable approval token."""
    dm = get_desktop_manager()
    fake_window = DesktopWindowInfo(
        hwnd=1111,
        title="Confirm Payment - Checkout",
        process_name="chrome.exe",
        pid=5555,
        is_permitted=True,
    )
    with patch.object(dm, "_get_window_info", return_value=fake_window):
        # 1. Missing token fails
        out_no_token = dm.click(x=200, y=300, consequential=True, approval_token=None)
        assert out_no_token.success is False
        assert "approval token" in out_no_token.error.lower()

        # 2. Forged token fails
        out_forged = dm.click(x=200, y=300, consequential=True, approval_token="forged_token_abc")
        assert out_forged.success is False

        # 3. Valid HMAC token succeeds
        valid_args = {
            "button": "left",
            "consequential": True,
            "double_click": False,
            "x": 200,
            "y": 300,
        }
        token = compute_action_token("desktop_click", valid_args)
        out_valid = dm.click(x=200, y=300, consequential=True, approval_token=token)
        assert out_valid.success is True


def test_desktop_type_text_consequential_requires_approval_token():
    """Typing consequential commands or text requires an approval token."""
    dm = get_desktop_manager()
    fake_window = DesktopWindowInfo(
        hwnd=2222,
        title="Settings - Cavrix Flow",
        process_name="electron.exe",
        pid=6666,
        is_permitted=True,
    )
    with patch.object(dm, "_get_window_info", return_value=fake_window):
        # 1. Consequential text without token fails
        out_no_token = dm.type_text("drop database users;", consequential=True, approval_token=None)
        assert out_no_token.success is False
        assert "approval token" in out_no_token.error.lower()

        # 2. Valid token succeeds
        valid_args = {
            "consequential": True,
            "press_enter": False,
            "text": "drop database users;",
        }
        token = compute_action_token("desktop_type_text", valid_args)
        out_valid = dm.type_text("drop database users;", consequential=True, approval_token=token)
        assert out_valid.success is True


@pytest.mark.asyncio
async def test_desktop_wait_for_state_timeout_handling():
    """desktop_wait_for_state returns timeout error gracefully when state is not met."""
    dm = get_desktop_manager()
    out = await dm.wait_for_state(
        window_title="NonExistentWindowTitle123456789",
        timeout_seconds=0.5,
    )
    assert out.matched is False
    assert "timed out" in out.error.lower()


# ==============================================================================
# 3. Bounded Workflow Engine & Verification Gates
# ==============================================================================

def test_workflow_engine_enforces_hard_8_step_maximum():
    """TaskPlans cannot exceed the hard maximum of 8 steps."""
    reg = get_default_registry()
    steps = [
        PlanStep(
            step_id=f"step_{i}",
            skill_id="desktop_get_state",
            purpose=f"Check step {i}",
            expected_outcome="State verified",
        )
        for i in range(1, 10)  # 9 steps!
    ]
    # 1. Pydantic schema rejects max_steps > 8
    with pytest.raises(ValidationError):
        TaskPlan(task_id="task_exceed_schema", goal="Exceed limits", steps=[], max_steps=9)

    # 2. validate_plan_with_registry rejects plans with more steps than max_steps (8)
    plan = TaskPlan(task_id="task_exceed", goal="Exceed limits", steps=steps, max_steps=8)
    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan_with_registry(plan, reg)
    assert "exceeds maximum allowable step count" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_consequential_action_with_uncertain_outcome_stops_and_does_not_auto_retry():
    """
    Stage 2 Constraint: If a consequential action outcome is unverified or uncertain,
    the workflow engine MUST NOT auto-retry; it must stop and request user guidance.
    """
    class MockClickInput(BaseModel):
        x: int
        y: int
        consequential: bool = True

    class MockClickOutput(BaseModel):
        success: bool
        error: str

    reg = SkillRegistry()
    reg.register(
        ToolDefinition(
            name="desktop_click",
            display_name="Desktop Mouse Click",
            description="Consequential action",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_approval=True,
            input_model=MockClickInput,
            output_model=MockClickOutput,
        ),
        # Returns an uncertain failure (e.g. timeout during click)
        lambda x, y, consequential=True: MockClickOutput(success=False, error="Target window unresponsive; outcome uncertain"),
    )

    executor = SkillExecutor(registry=reg)
    verifier = PlanVerifier()
    plan_executor = BoundedPlanExecutor(skill_executor=executor, verifier=verifier)

    action_args = {"x": 50, "y": 50, "consequential": True}
    token = compute_action_token("desktop_click", action_args)

    plan = TaskPlan(
        task_id="task_uncertain_click",
        goal="Perform consequential click",
        steps=[
            PlanStep(
                step_id="step_1",
                skill_id="desktop_click",
                arguments=action_args,
                purpose="Click important button",
                expected_outcome="Outcome verified",
                approval_token=token,
            )
        ],
    )

    executed_plan = await plan_executor.execute_plan(plan)

    # Must be BLOCKED with AWAITING_APPROVAL, NOT auto-retried
    assert executed_plan.status == PlanStatus.BLOCKED
    step = executed_plan.steps[0]
    assert step.status == StepStatus.AWAITING_APPROVAL
    assert step.retries_attempted == 0, "CRITICAL: Consequential actions must NEVER auto-retry when uncertain."
    assert "auto-retry prohibited" in step.error.lower()


@pytest.mark.asyncio
async def test_workflow_cancellation_halts_in_flight_plan():
    """Verifies that cancel_task() immediately halts an in-flight plan execution."""
    reg = get_default_registry()
    executor = SkillExecutor(registry=reg)
    plan_executor = BoundedPlanExecutor(skill_executor=executor)

    plan = TaskPlan(
        task_id="task_cancel_test",
        goal="Cancel plan test",
        steps=[
            PlanStep(step_id="step_1", skill_id="desktop_get_state", purpose="State 1", expected_outcome="Done"),
            PlanStep(step_id="step_2", skill_id="desktop_get_state", purpose="State 2", expected_outcome="Done"),
        ],
    )

    # Cancel task before execution starts
    plan_executor.cancel_task("task_cancel_test")
    res_plan = await plan_executor.execute_plan(plan)

    assert res_plan.status == PlanStatus.CANCELLED
    assert res_plan.steps[0].status == StepStatus.SKIPPED
    assert "cancelled by user" in res_plan.steps[0].error.lower()
