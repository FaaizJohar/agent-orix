"""
Desktop Automation & Computer Use subsystem for Cavrix Intelligence Engine.
"""

from cie.desktop.schemas import (
    DesktopStateOutput,
    DesktopListWindowsInput,
    DesktopListWindowsOutput,
    DesktopScreenshotInput,
    DesktopScreenshotOutput,
    DesktopClickInput,
    DesktopClickOutput,
    DesktopTypeTextInput,
    DesktopTypeTextOutput,
    DesktopKeypressInput,
    DesktopKeypressOutput,
    DesktopWaitForStateInput,
    DesktopWaitForStateOutput,
    DesktopWindowInfo,
)
from cie.desktop.security import (
    DesktopSecurityManager,
    DesktopSecurityError,
    ALLOWED_PROCESS_NAMES,
    PROHIBITED_PROCESSES,
)
from cie.desktop.manager import DesktopManager, get_desktop_manager

__all__ = [
    "DesktopManager",
    "get_desktop_manager",
    "DesktopSecurityManager",
    "DesktopSecurityError",
    "DesktopStateOutput",
    "DesktopListWindowsInput",
    "DesktopListWindowsOutput",
    "DesktopScreenshotInput",
    "DesktopScreenshotOutput",
    "DesktopClickInput",
    "DesktopClickOutput",
    "DesktopTypeTextInput",
    "DesktopTypeTextOutput",
    "DesktopKeypressInput",
    "DesktopKeypressOutput",
    "DesktopWaitForStateInput",
    "DesktopWaitForStateOutput",
    "DesktopWindowInfo",
    "ALLOWED_PROCESS_NAMES",
    "PROHIBITED_PROCESSES",
]
