"""
Pydantic schemas and data models for Safe Local Computer Use & Desktop Automation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DesktopWindowInfo(BaseModel):
    hwnd: int = Field(..., description="Window handle ID")
    title: str = Field(..., description="Window title bar text (sanitized)")
    process_name: str = Field(default="unknown", description="Executable name, e.g. 'Code.exe'")
    pid: int = Field(default=0, description="Process ID")
    is_visible: bool = Field(default=True)
    is_minimized: bool = Field(default=False)
    is_permitted: bool = Field(default=True, description="Whether window is permitted by application allowlist")
    bounds: Dict[str, int] = Field(
        default_factory=lambda: {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}
    )


class DesktopStateOutput(BaseModel):
    screen_resolution: Dict[str, int] = Field(default_factory=lambda: {"width": 1920, "height": 1080})
    active_window: Optional[DesktopWindowInfo] = None
    is_permitted: bool = Field(default=True, description="Whether the active window is permitted by security allowlist")
    total_visible_windows: int = 0
    os_interactive_session: bool = Field(default=True, description="Whether active display DC is available")
    diagnostic_note: Optional[str] = None


class DesktopListWindowsInput(BaseModel):
    include_prohibited: bool = Field(default=False, description="Whether to include prohibited windows (flagged as non-permitted)")


class DesktopListWindowsOutput(BaseModel):
    windows: List[DesktopWindowInfo] = Field(default_factory=list)
    total_windows: int = 0
    permitted_windows: int = 0


class DesktopScreenshotInput(BaseModel):
    target_window_only: bool = Field(default=False, description="Capture only the active window rectangle")
    filename_prefix: str = Field(default="desktop_snap", max_length=50)


class DesktopScreenshotOutput(BaseModel):
    file_path: str = Field(..., description="Artifact path to the saved PNG screenshot")
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    window_captured: Optional[str] = None
    is_synthetic: bool = Field(default=False, description="True if captured via fallback in headless environment")


class DesktopClickInput(BaseModel):
    x: int = Field(..., ge=0, description="X coordinate on screen")
    y: int = Field(..., ge=0, description="Y coordinate on screen")
    button: str = Field(default="left", description="Mouse button: 'left', 'right', 'middle'")
    double_click: bool = Field(default=False)
    consequential: bool = Field(default=False, description="Flags this interaction as consequential (requires approval token)")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic action-bound approval token")


class DesktopClickOutput(BaseModel):
    action: str = "click"
    x: int
    y: int
    button: str
    success: bool
    verified_target: Optional[str] = None
    error: Optional[str] = None


class DesktopTypeTextInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Text string to type")
    press_enter: bool = Field(default=False, description="Press Enter after typing")
    consequential: bool = Field(default=False, description="Flags typing sensitive text as consequential")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic action-bound approval token")


class DesktopTypeTextOutput(BaseModel):
    action: str = "type_text"
    characters_typed: int = 0
    success: bool
    target_window: Optional[str] = None
    error: Optional[str] = None


class DesktopKeypressInput(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, description="Key name, e.g. 'Enter', 'Tab', 'Escape', 'F5'")
    modifiers: List[str] = Field(default_factory=list, description="Modifier keys: 'ctrl', 'alt', 'shift', 'win'")
    consequential: bool = Field(default=False, description="Flags keypress as consequential")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic action-bound approval token")


class DesktopKeypressOutput(BaseModel):
    action: str = "keypress"
    key_sent: str
    modifiers_sent: List[str] = Field(default_factory=list)
    success: bool
    target_window: Optional[str] = None
    error: Optional[str] = None


class DesktopWaitForStateInput(BaseModel):
    window_title: Optional[str] = Field(default=None, description="Target window title substring to await")
    process_name: Optional[str] = Field(default=None, description="Target process name to await, e.g. 'notepad.exe'")
    timeout_seconds: float = Field(default=10.0, ge=0.5, le=30.0)


class DesktopWaitForStateOutput(BaseModel):
    matched: bool
    window_found: Optional[DesktopWindowInfo] = None
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
