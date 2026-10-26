"""
Data schemas and models for Browser Automation tools.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BrowserActionType(str, Enum):
    OPEN = "open"
    BACK = "back"
    SNAPSHOT = "snapshot"
    FIND_TEXT = "find_text"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    TABS = "tabs"
    SWITCH_TAB = "switch_tab"
    CLOSE_TAB = "close_tab"
    SCREENSHOT = "screenshot"
    WAIT_FOR_TEXT = "wait_for_text"


class InteractiveElement(BaseModel):
    ref_id: str
    tag: str
    role: Optional[str] = None
    name: Optional[str] = None
    selector: str
    text: str = ""
    is_clickable: bool = False
    is_input: bool = False
    input_type: Optional[str] = None
    is_consequential: bool = False


# 1. browser_open
class BrowserOpenInput(BaseModel):
    url: str = Field(..., description="Target HTTP or HTTPS URL to navigate to")
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=45.0, description="Max navigation timeout in seconds")


class BrowserOpenOutput(BaseModel):
    current_url: str
    title: str
    status_code: int = 200
    page_summary: str = ""
    interactive_elements_count: int = 0
    error: Optional[str] = None


# 2. browser_back
class BrowserBackInput(BaseModel):
    session_id: Optional[str] = None


class BrowserBackOutput(BaseModel):
    current_url: str
    title: str
    success: bool
    error: Optional[str] = None


# 3. browser_get_page_snapshot
class BrowserSnapshotInput(BaseModel):
    include_interactive_only: bool = Field(default=False, description="Filter for interactive elements only")


class BrowserSnapshotOutput(BaseModel):
    current_url: str
    title: str
    text_content: str
    accessibility_tree: str
    interactive_elements: List[InteractiveElement] = Field(default_factory=list)
    total_elements: int = 0
    error: Optional[str] = None


# 4. browser_find_text
class BrowserFindTextInput(BaseModel):
    query: str = Field(..., min_length=1, description="Text string to find on page")


class BrowserFindTextOutput(BaseModel):
    query: str
    matches_count: int
    matched_snippets: List[str] = Field(default_factory=list)
    found: bool = False
    error: Optional[str] = None


# 5. browser_click_element
class BrowserClickInput(BaseModel):
    selector: Optional[str] = Field(default=None, description="CSS selector or Playwright locator")
    ref_id: Optional[str] = Field(default=None, description="Element reference ID from snapshot (@ref_1)")
    text: Optional[str] = Field(default=None, description="Exact or partial text of element to click")
    consequential: bool = Field(default=False, description="Flag indicating action submits form or mutates state")
    approval_token: Optional[str] = Field(default=None, description="Action-bound cryptographic token required for consequential actions")


class BrowserClickOutput(BaseModel):
    action: str = "click"
    target: str
    success: bool
    new_url: Optional[str] = None
    navigation_occurred: bool = False
    verification_message: str = ""
    error: Optional[str] = None


# 6. browser_fill_field
class BrowserFillInput(BaseModel):
    selector: Optional[str] = Field(default=None, description="CSS selector or Playwright locator")
    ref_id: Optional[str] = Field(default=None, description="Element reference ID from snapshot")
    value: str = Field(..., description="Text value to enter into field")
    press_enter: bool = Field(default=False, description="Whether to press Enter after filling")
    consequential: bool = Field(default=False, description="Flag indicating action affects credentials or sensitive state")
    approval_token: Optional[str] = Field(default=None, description="Action-bound cryptographic token required for consequential actions")


class BrowserFillOutput(BaseModel):
    action: str = "fill"
    target: str
    value_length: int
    success: bool
    verification_message: str = ""
    error: Optional[str] = None


# 7. browser_select_option
class BrowserSelectInput(BaseModel):
    selector: Optional[str] = None
    ref_id: Optional[str] = None
    option_value: str = Field(..., description="Option value or label to select")


class BrowserSelectOutput(BaseModel):
    action: str = "select"
    target: str
    selected_option: str
    success: bool
    error: Optional[str] = None


# 8. browser_list_tabs
class BrowserTabListInput(BaseModel):
    pass


class TabInfo(BaseModel):
    index: int
    title: str
    url: str
    is_active: bool


class BrowserTabListOutput(BaseModel):
    tabs_count: int
    active_tab_index: int
    tabs: List[TabInfo] = Field(default_factory=list)
    error: Optional[str] = None


# 9. browser_switch_tab
class BrowserTabSwitchInput(BaseModel):
    tab_index: int = Field(..., ge=0, description="Zero-based index of tab to switch to")


class BrowserTabSwitchOutput(BaseModel):
    active_tab_index: int
    current_url: str
    title: str
    success: bool
    error: Optional[str] = None


# 10. browser_close_tab
class BrowserTabCloseInput(BaseModel):
    tab_index: Optional[int] = Field(default=None, description="Tab index to close; defaults to active tab")


class BrowserTabCloseOutput(BaseModel):
    closed_tab_index: int
    remaining_tabs_count: int
    success: bool
    error: Optional[str] = None


# 11. browser_take_screenshot
class BrowserScreenshotInput(BaseModel):
    filename_prefix: Optional[str] = Field(default="screenshot", description="Prefix for screenshot filename")
    full_page: bool = Field(default=False, description="Capture full scrollable page")


class BrowserScreenshotOutput(BaseModel):
    file_path: str
    format: str = "png"
    size_bytes: int
    dimensions: str
    error: Optional[str] = None


# 12. browser_wait_for_text
class BrowserWaitTextInput(BaseModel):
    text: str = Field(..., min_length=1, description="Text string to wait for on page")
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=30.0, description="Max wait timeout in seconds")


class BrowserWaitTextOutput(BaseModel):
    text: str
    appeared: bool
    elapsed_seconds: float
    error: Optional[str] = None
