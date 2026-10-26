"""
Browser Automation & Controlled Computer Use Subsystem for CIE.
Provides isolated, SSRF-guarded Playwright Chromium interaction,
accessibility tree snapshots, element locators, and outcome verification.
"""

from cie.browser.schemas import (
    BrowserOpenInput,
    BrowserOpenOutput,
    BrowserBackInput,
    BrowserBackOutput,
    BrowserSnapshotInput,
    BrowserSnapshotOutput,
    BrowserFindTextInput,
    BrowserFindTextOutput,
    BrowserClickInput,
    BrowserClickOutput,
    BrowserFillInput,
    BrowserFillOutput,
    BrowserSelectInput,
    BrowserSelectOutput,
    BrowserTabListInput,
    BrowserTabListOutput,
    BrowserTabSwitchInput,
    BrowserTabSwitchOutput,
    BrowserTabCloseInput,
    BrowserTabCloseOutput,
    BrowserScreenshotInput,
    BrowserScreenshotOutput,
    BrowserWaitTextInput,
    BrowserWaitTextOutput,
)
from cie.browser.manager import BrowserManager, get_browser_manager
from cie.browser.security import BrowserSecurityManager

__all__ = [
    "BrowserOpenInput",
    "BrowserOpenOutput",
    "BrowserBackInput",
    "BrowserBackOutput",
    "BrowserSnapshotInput",
    "BrowserSnapshotOutput",
    "BrowserFindTextInput",
    "BrowserFindTextOutput",
    "BrowserClickInput",
    "BrowserClickOutput",
    "BrowserFillInput",
    "BrowserFillOutput",
    "BrowserSelectInput",
    "BrowserSelectOutput",
    "BrowserTabListInput",
    "BrowserTabListOutput",
    "BrowserTabSwitchInput",
    "BrowserTabSwitchOutput",
    "BrowserTabCloseInput",
    "BrowserTabCloseOutput",
    "BrowserScreenshotInput",
    "BrowserScreenshotOutput",
    "BrowserWaitTextInput",
    "BrowserWaitTextOutput",
    "BrowserManager",
    "get_browser_manager",
    "BrowserSecurityManager",
]
