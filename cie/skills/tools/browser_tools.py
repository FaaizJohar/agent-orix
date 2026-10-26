"""
Developer & Agent Tools for Browser Automation & Controlled Computer Use.
Integrates isolated, SSRF-guarded Playwright operations into the Skills Registry.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cie.browser.manager import get_browser_manager
from cie.browser.schemas import (
    BrowserBackInput,
    BrowserBackOutput,
    BrowserClickInput,
    BrowserClickOutput,
    BrowserFillInput,
    BrowserFillOutput,
    BrowserFindTextInput,
    BrowserFindTextOutput,
    BrowserOpenInput,
    BrowserOpenOutput,
    BrowserScreenshotInput,
    BrowserScreenshotOutput,
    BrowserSelectInput,
    BrowserSelectOutput,
    BrowserSnapshotInput,
    BrowserSnapshotOutput,
    BrowserTabCloseInput,
    BrowserTabCloseOutput,
    BrowserTabListInput,
    BrowserTabListOutput,
    BrowserTabSwitchInput,
    BrowserTabSwitchOutput,
    BrowserWaitTextInput,
    BrowserWaitTextOutput,
)


async def browser_open(
    url: str,
    timeout_seconds: float = 15.0,
) -> BrowserOpenOutput:
    """
    Safely opens an HTTP/HTTPS URL in the headless browser after SSRF validation.
    """
    bm = get_browser_manager()
    return await bm.open_url(url=url, timeout_seconds=timeout_seconds)


async def browser_back(
    session_id: Optional[str] = None,
) -> BrowserBackOutput:
    """
    Navigates to the previous page in session history.
    """
    bm = get_browser_manager()
    return await bm.go_back(session_id=session_id)


async def browser_get_page_snapshot(
    include_interactive_only: bool = False,
) -> BrowserSnapshotOutput:
    """
    Captures text hierarchy, accessibility tree, and stable interactive @ref_N elements.
    """
    bm = get_browser_manager()
    return await bm.get_page_snapshot(include_interactive_only=include_interactive_only)


async def browser_find_text(
    query: str,
) -> BrowserFindTextOutput:
    """
    Searches visible page content for a query text and returns matching snippets.
    """
    bm = get_browser_manager()
    return await bm.find_text(query=query)


async def browser_click_element(
    selector: Optional[str] = None,
    ref_id: Optional[str] = None,
    text: Optional[str] = None,
    consequential: bool = False,
    approval_token: Optional[str] = None,
) -> BrowserClickOutput:
    """
    Clicks an interactive element using ref_id (@ref_1), CSS selector, or text.
    Enforces action-bound approval tokens for consequential actions (submits, payments, deletes).
    """
    bm = get_browser_manager()
    return await bm.click_element(
        selector=selector,
        ref_id=ref_id,
        text=text,
        consequential=consequential,
        approval_token=approval_token,
    )


async def browser_fill_field(
    value: str,
    selector: Optional[str] = None,
    ref_id: Optional[str] = None,
    press_enter: bool = False,
    consequential: bool = False,
    approval_token: Optional[str] = None,
) -> BrowserFillOutput:
    """
    Fills an input or textarea with text value and optionally presses Enter.
    Enforces action-bound approval tokens for consequential fields (passwords, sensitive forms).
    """
    bm = get_browser_manager()
    return await bm.fill_field(
        selector=selector,
        ref_id=ref_id,
        value=value,
        press_enter=press_enter,
        consequential=consequential,
        approval_token=approval_token,
    )


async def browser_select_option(
    option_value: str,
    selector: Optional[str] = None,
    ref_id: Optional[str] = None,
) -> BrowserSelectOutput:
    """
    Selects an option from a <select> dropdown by value or visible label.
    """
    bm = get_browser_manager()
    return await bm.select_option(
        selector=selector,
        ref_id=ref_id,
        option_value=option_value,
    )


async def browser_list_tabs() -> BrowserTabListOutput:
    """
    Lists open browser tabs, titles, and indicates the active tab index.
    """
    bm = get_browser_manager()
    return await bm.list_tabs()


async def browser_switch_tab(
    tab_index: int,
) -> BrowserTabSwitchOutput:
    """
    Switches active tab context to the given zero-based index.
    """
    bm = get_browser_manager()
    return await bm.switch_tab(tab_index=tab_index)


async def browser_close_tab(
    tab_index: Optional[int] = None,
) -> BrowserTabCloseOutput:
    """
    Closes the tab at tab_index (or currently active tab).
    """
    bm = get_browser_manager()
    return await bm.close_tab(tab_index=tab_index)


async def browser_take_screenshot(
    filename_prefix: str = "screenshot",
    full_page: bool = False,
) -> BrowserScreenshotOutput:
    """
    Captures a PNG screenshot of the current page and stores it in the data directory.
    """
    bm = get_browser_manager()
    return await bm.take_screenshot(
        filename_prefix=filename_prefix,
        full_page=full_page,
    )


async def browser_wait_for_text(
    text: str,
    timeout_seconds: float = 10.0,
) -> BrowserWaitTextOutput:
    """
    Waits for expected text string to become visible on the page.
    """
    bm = get_browser_manager()
    return await bm.wait_for_text(
        text=text,
        timeout_seconds=timeout_seconds,
    )


class Crawl4AIExtractInput(BaseModel):
    url: str = Field(..., description="Target web URL to extract")
    html: Optional[str] = Field(None, description="Optional raw HTML content if already retrieved")
    title: str = Field("", description="Optional page title")


class Crawl4AIExtractOutput(BaseModel):
    url: str
    title: str
    markdown: str
    links: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    word_count: int = 0
    upstream_used: bool = True


async def crawl4ai_extract(
    url: str,
    html: Optional[str] = None,
    title: str = "",
) -> Crawl4AIExtractOutput:
    """
    Extracts structured markdown, links, and media from HTML or target web URL using Crawl4AI.
    """
    from cie.capabilities.browser.crawl4ai import Crawl4AIAdapter
    adapter = Crawl4AIAdapter()

    if html is None:
        # Fetch page via headless browser manager
        bm = get_browser_manager()
        res_open = await bm.open_url(url)
        if not res_open.success:
            return Crawl4AIExtractOutput(
                url=url,
                title=title or "Failed to Open",
                markdown=f"Failed to open URL: {res_open.error}",
                upstream_used=adapter.upstream_active,
            )
        html = await bm.get_page_content()
        title = res_open.title or title

    res = adapter.extract_from_html(url=url, html=html, title=title)
    return Crawl4AIExtractOutput(
        url=res.url,
        title=res.title,
        markdown=res.markdown,
        links=res.links,
        images=res.images,
        word_count=res.word_count,
        upstream_used=adapter.upstream_active,
    )

