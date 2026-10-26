"""
Skill tool wrappers for Safe Local Computer Use and Desktop Automation.
Integrates with DesktopManager, DesktopSecurityManager, and SkillRegistry.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cie.desktop.manager import get_desktop_manager
from cie.desktop.schemas import (
    DesktopClickOutput,
    DesktopKeypressOutput,
    DesktopListWindowsOutput,
    DesktopScreenshotOutput,
    DesktopStateOutput,
    DesktopTypeTextOutput,
    DesktopWaitForStateOutput,
)


async def desktop_get_state() -> DesktopStateOutput:
    """
    Retrieves current desktop screen resolution, active foreground window,
    process name, rect bounds, and allowlist security status.
    """
    dm = get_desktop_manager()
    return dm.get_state()


async def desktop_list_windows(
    include_prohibited: bool = False,
) -> DesktopListWindowsOutput:
    """
    Enumerates visible top-level windows on the desktop, process names,
    and whether each window is permitted by the application security allowlist.
    """
    dm = get_desktop_manager()
    return dm.list_windows(include_prohibited=include_prohibited)


async def desktop_screenshot(
    target_window_only: bool = False,
    filename_prefix: str = "desktop_snap",
) -> DesktopScreenshotOutput:
    """
    Captures a PNG screenshot of the display or active window rectangle.
    Handles headless and detached sessions gracefully with diagnostic frames.
    """
    dm = get_desktop_manager()
    return dm.take_screenshot(
        target_window_only=target_window_only,
        filename_prefix=filename_prefix,
    )


async def desktop_click(
    x: int,
    y: int,
    button: str = "left",
    double_click: bool = False,
    consequential: bool = False,
    approval_token: Optional[str] = None,
) -> DesktopClickOutput:
    """
    Simulates a mouse click at screen coordinates (x, y).
    Enforces application allowlists and action-bound approval tokens for consequential actions.
    """
    dm = get_desktop_manager()
    return dm.click(
        x=x,
        y=y,
        button=button,
        double_click=double_click,
        consequential=consequential,
        approval_token=approval_token,
    )


async def desktop_type_text(
    text: str,
    press_enter: bool = False,
    consequential: bool = False,
    approval_token: Optional[str] = None,
) -> DesktopTypeTextOutput:
    """
    Types text into the active permitted window.
    Redacts credentials and requires action-bound approval tokens for consequential input.
    """
    dm = get_desktop_manager()
    return dm.type_text(
        text=text,
        press_enter=press_enter,
        consequential=consequential,
        approval_token=approval_token,
    )


async def desktop_keypress(
    key: str,
    modifiers: Optional[List[str]] = None,
    consequential: bool = False,
    approval_token: Optional[str] = None,
) -> DesktopKeypressOutput:
    """
    Sends a keypress or modifier combo (e.g. Enter, Esc, Ctrl+S) to the active window.
    Requires action-bound approval tokens for consequential keys.
    """
    dm = get_desktop_manager()
    return dm.keypress(
        key=key,
        modifiers=modifiers,
        consequential=consequential,
        approval_token=approval_token,
    )


async def desktop_wait_for_state(
    window_title: Optional[str] = None,
    process_name: Optional[str] = None,
    timeout_seconds: float = 10.0,
) -> DesktopWaitForStateOutput:
    """
    Polls until a window with matching title or process name appears within the timeout deadline.
    """
    dm = get_desktop_manager()
    return await dm.wait_for_state(
        window_title=window_title,
        process_name=process_name,
        timeout_seconds=timeout_seconds,
    )


class SWERexExecuteInput(BaseModel):
    command: List[str] = Field(..., description="Command to execute in isolated SWE-ReX workspace")
    workspace_root: str = Field(..., description="Workspace root directory")
    cwd: Optional[str] = Field(None, description="Working directory relative to workspace root")
    timeout_seconds: float = Field(30.0, description="Max execution time in seconds")


class SWERexExecuteOutput(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    upstream_runtime_used: bool


def swerex_execute(
    command: List[str],
    workspace_root: str,
    cwd: Optional[str] = None,
    timeout_seconds: float = 30.0,
) -> SWERexExecuteOutput:
    """
    Executes a command within an isolated workspace using SWE-ReX AbstractRuntime.
    Enforces strict path containment, environment variable sanitization, and timeout deadlines.
    """
    from cie.capabilities.agent.swerex import SWERexEnvironment, WorkspaceIsolationConfig
    config = WorkspaceIsolationConfig(
        workspace_root=workspace_root,
        max_execution_time_seconds=timeout_seconds,
    )
    env = SWERexEnvironment(config=config)
    res = env.run_isolated_command(command, cwd=cwd)

    if not res["success"] and res.get("exit_code") == 403:
        raise PermissionError(f"SecurityViolation: {res.get('stderr', 'Path traversal blocked')}")

    return SWERexExecuteOutput(
        success=res["success"],
        exit_code=res["exit_code"],
        stdout=res["stdout"],
        stderr=res["stderr"],
        upstream_runtime_used=env.upstream_active,
    )

