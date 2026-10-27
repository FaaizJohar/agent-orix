"""
Phase 4 Browser Automation & Controlled Computer Use Test Suite.
Tests SSRF security boundaries, private IP and cloud metadata blocking,
consequential action classification and gating, accessibility tree snapshots,
element interaction (click, fill, select), tab management, screenshot capture,
and integration with CIE SkillRegistry, Planner, and Verifier.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
pytest.importorskip("playwright")

from cie.browser.manager import BrowserManager, get_browser_manager
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
    InteractiveElement,
)
from cie.browser.security import BrowserSecurityError, BrowserSecurityManager
from cie.planning.planner import AdaptivePlanner
from cie.planning.schemas import PlanStatus, PlanStep, StepStatus, TaskPlan
from cie.planning.verifier import PlanVerifier
from cie.router import DeterministicRouter
from cie.schemas import IntentCategory
from cie.skills.executor import SkillExecutor
from cie.skills.registry import get_default_registry
from cie.skills.schemas import (
    PermissionLevel,
    RiskLevel,
    ToolExecutionRequest,
    ToolExecutionResult,
    compute_action_token,
)


# ==============================================================================
# 1. SSRF & Security Boundary Tests
# ==============================================================================

def test_ssrf_blocks_private_and_loopback_destinations():
    """Verify that private subnets, loopback, and localhost destinations are blocked."""
    forbidden_urls = [
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1/admin",
        "http://10.0.0.5/api",
        "http://172.16.0.1/dashboard",
        "http://192.168.1.1/router",
        "http://0.0.0.0",
        "https://myhost.local",
    ]
    for url in forbidden_urls:
        with pytest.raises(BrowserSecurityError) as exc_info:
            BrowserSecurityManager.validate_destination_url(url)
        assert any(term in str(exc_info.value).lower() for term in ["prohibited", "ssrf", "forbidden", "private", "local"])


def test_ssrf_blocks_cloud_metadata():
    """Verify that AWS/GCP/Azure link-local cloud metadata endpoints (169.254.169.254) are rejected."""
    metadata_url = "http://169.254.169.254/latest/meta-data"
    with pytest.raises(BrowserSecurityError) as exc_info:
        BrowserSecurityManager.validate_destination_url(metadata_url)
    assert "ssrf violation" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_ssrf_blocks_non_http_schemes():
    """Verify that file://, ftp://, javascript:, gopher:// schemes are rejected."""
    schemes = [
        "file:///etc/passwd",
        "file://C:/Windows/System32/drivers/etc/hosts",
        "ftp://ftp.example.com",
        "javascript:alert(1)",
        "gopher://gopher.example.com",
    ]
    for s_url in schemes:
        with pytest.raises(BrowserSecurityError) as exc_info:
            BrowserSecurityManager.validate_destination_url(s_url)
        assert "forbidden navigation scheme" in str(exc_info.value).lower()


def test_ssrf_rejects_empty_and_malformed_urls():
    """Verify that empty, blank, or invalid URLs raise BrowserSecurityError."""
    for bad_url in ["", "   ", "not-a-url"]:
        with pytest.raises(BrowserSecurityError):
            BrowserSecurityManager.validate_destination_url(bad_url)


def test_consequential_action_classification():
    """Verify that buttons/inputs with consequential verbs or submit types are classified correctly."""
    # Consequential cases
    is_conseq, reason = BrowserSecurityManager.is_consequential_action(
        tag="button", text="Submit Payment"
    )
    assert is_conseq
    assert "consequential action pattern" in reason

    is_conseq, reason = BrowserSecurityManager.is_consequential_action(
        tag="input", input_type="submit"
    )
    assert is_conseq
    assert "mutates state" in reason

    is_conseq, reason = BrowserSecurityManager.is_consequential_action(
        tag="input", input_type="password"
    )
    assert is_conseq
    assert "credentials" in reason

    is_conseq, reason = BrowserSecurityManager.is_consequential_action(
        tag="button", text="Delete Repository"
    )
    assert is_conseq

    # Safe / non-consequential cases
    is_conseq, _ = BrowserSecurityManager.is_consequential_action(
        tag="a", role="link", text="Next Page"
    )
    assert not is_conseq

    is_conseq, _ = BrowserSecurityManager.is_consequential_action(
        tag="button", text="Expand Accordion"
    )
    assert not is_conseq

    # Explicit flag override
    is_conseq, _ = BrowserSecurityManager.is_consequential_action(
        tag="div", text="custom", explicit_flag=True
    )
    assert is_conseq


# ==============================================================================
# 2. Skills Registry Integration & Schema Validation
# ==============================================================================

def test_all_12_browser_tools_registered():
    """Verify that all 12 browser tools are registered in the SkillRegistry."""
    registry = get_default_registry()
    expected_tools = [
        "browser_open",
        "browser_back",
        "browser_get_page_snapshot",
        "browser_find_text",
        "browser_click_element",
        "browser_fill_field",
        "browser_select_option",
        "browser_list_tabs",
        "browser_switch_tab",
        "browser_close_tab",
        "browser_take_screenshot",
        "browser_wait_for_text",
    ]
    for tool_name in expected_tools:
        tool_def = registry.get_tool(tool_name)
        assert tool_def is not None, f"Tool '{tool_name}' must be registered."
        assert tool_def.enabled is True
        assert tool_def.input_model is not None
        assert tool_def.output_model is not None
        assert registry.get_handler(tool_name) is not None


def test_browser_tools_permissions_and_risk():
    """Verify permissions and risk ratings conform to safety policy."""
    registry = get_default_registry()

    # Read/inspection tools
    for tool_name in ["browser_open", "browser_get_page_snapshot", "browser_find_text", "browser_list_tabs"]:
        t = registry.get_tool(tool_name)
        assert t.permission == PermissionLevel.NETWORK_READ

    # Screenshot tool
    screenshot_tool = registry.get_tool("browser_take_screenshot")
    assert screenshot_tool.permission == PermissionLevel.READ_ONLY
    assert screenshot_tool.risk == RiskLevel.LOW


# ==============================================================================
# 3. Headless Browser Lifecycle & Element Interaction
# ==============================================================================

@pytest.mark.asyncio
async def test_browser_manager_lifecycle_and_content_interaction():
    """
    Tests BrowserManager page rendering, accessibility tree snapshot generation,
    stable @ref_N mapping, find_text, form fill, and screenshot.
    """
    bm = BrowserManager()
    await bm.ensure_initialized()
    assert bm._active_page is not None

    try:
        # Load synthetic HTML page with interactive form elements
        test_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Cavrix Test Portal</title></head>
        <body>
            <h1>Welcome to Cavrix Test Portal</h1>
            <p>This is a synthetic test document for Playwright automation.</p>
            <nav>
                <a href="#about" role="link">About Us</a>
                <a href="#docs" role="link">Documentation</a>
            </nav>
            <main>
                <input id="search-input" name="search" type="text" placeholder="Search keywords..." />
                <button id="search-btn" type="button">Search Docs</button>
                <select id="env-select" name="environment">
                    <option value="dev">Development</option>
                    <option value="staging">Staging</option>
                    <option value="prod">Production</option>
                </select>
                <form id="pay-form" onsubmit="event.preventDefault()">
                    <input id="pwd" type="password" name="auth_token" />
                    <button id="submit-btn" type="submit">Submit Payment</button>
                </form>
            </main>
        </body>
        </html>
        """
        await bm._active_page.set_content(test_html)

        # 1. Snapshot and accessibility tree
        snapshot = await bm.get_page_snapshot()
        assert snapshot.title == "Cavrix Test Portal"
        assert snapshot.total_elements >= 5
        assert len(snapshot.interactive_elements) >= 5
        assert "Welcome to Cavrix Test Portal" in snapshot.text_content
        assert "@ref_1" in snapshot.accessibility_tree

        # Check consequential detection on Submit Payment button
        conseq_elements = [el for el in snapshot.interactive_elements if el.is_consequential]
        assert len(conseq_elements) >= 1
        assert any("submit" in el.text.lower() or el.input_type == "password" for el in conseq_elements)

        # 2. Text Search
        find_res = await bm.find_text("synthetic test document")
        assert find_res.found is True
        assert find_res.matches_count >= 1
        assert len(find_res.matched_snippets) >= 1

        not_found = await bm.find_text("nonexistent phrase 12345")
        assert not_found.found is False
        assert not_found.matches_count == 0

        # 3. Fill field
        fill_res = await bm.fill_field(selector="#search-input", value="deep learning")
        assert fill_res.success is True
        assert fill_res.value_length == len("deep learning")

        # 4. Select option
        select_res = await bm.select_option(selector="#env-select", option_value="staging")
        assert select_res.success is True
        assert select_res.selected_option == "staging"

        # 5. Non-consequential click (Search Docs button)
        click_res = await bm.click_element(selector="#search-btn")
        assert click_res.success is True

        # 6. Consequential action blocking: Attempt to click Submit Payment without token
        blocked_click = await bm.click_element(
            selector="#submit-btn",
            consequential=True,
            approval_token=None,
        )
        assert blocked_click.success is False
        assert "consequential action blocked" in blocked_click.error.lower()

        # 7. Consequential action allowed with valid action-bound approval token
        action_args = {
            "consequential": True,
            "ref_id": None,
            "selector": "#submit-btn",
            "text": None,
        }
        valid_token = compute_action_token("browser_click_element", action_args)
        approved_click = await bm.click_element(
            selector="#submit-btn",
            consequential=True,
            approval_token=valid_token,
        )
        assert approved_click.success is True

        # 8. Screenshot capture
        screenshot_res = await bm.take_screenshot(filename_prefix="test_snap")
        assert screenshot_res.error is None
        assert os.path.exists(screenshot_res.file_path)
        assert screenshot_res.size_bytes > 0
        # Clean up temporary screenshot
        try:
            os.remove(screenshot_res.file_path)
        except OSError:
            pass

        # 9. Tab management
        tabs = await bm.list_tabs()
        assert tabs.tabs_count >= 1
        assert tabs.active_tab_index == 0

        # 10. Wait for text
        wait_res = await bm.wait_for_text(text="Welcome to Cavrix Test Portal", timeout_seconds=3.0)
        assert wait_res.appeared is True

    finally:
        await bm.close()


# ==============================================================================
# 4. Plan Verifier Tests for Browser Operations
# ==============================================================================

def test_plan_verifier_browser_open_checks():
    """Verify PlanVerifier validates browser_open responses."""
    verifier = PlanVerifier()
    step = PlanStep(
        step_id="step_1",
        skill_id="browser_open",
        purpose="Open site",
        expected_outcome="Status 200 and URL loaded",
    )

    # Success case
    ok_res = ToolExecutionResult(
        success=True,
        tool_name="browser_open",
        result={"current_url": "https://python.org", "status_code": 200, "title": "Python"},
        permission_used=PermissionLevel.NETWORK_READ,
    )
    is_ok, err = verifier.verify_step_outcome(step, ok_res)
    assert is_ok is True
    assert err is None

    # HTTP 404 failure case
    fail_res = ToolExecutionResult(
        success=True,
        tool_name="browser_open",
        result={"current_url": "https://example.com/bad", "status_code": 404, "title": "Not Found"},
        permission_used=PermissionLevel.NETWORK_READ,
    )
    is_ok, err = verifier.verify_step_outcome(step, fail_res)
    assert is_ok is False
    assert "404" in err


def test_plan_verifier_browser_click_checks():
    """Verify PlanVerifier validates browser_click_element outcomes."""
    verifier = PlanVerifier()
    step = PlanStep(
        step_id="step_2",
        skill_id="browser_click_element",
        purpose="Click search",
        expected_outcome="Button clicked and DOM updated",
    )

    # Success case
    ok_res = ToolExecutionResult(
        success=True,
        tool_name="browser_click_element",
        result={"action": "click", "target": "#search-btn", "success": True},
        permission_used=PermissionLevel.NETWORK_READ,
    )
    is_ok, _ = verifier.verify_step_outcome(step, ok_res)
    assert is_ok is True

    # Internal failure case
    fail_res = ToolExecutionResult(
        success=True,
        tool_name="browser_click_element",
        result={"action": "click", "target": "#bad-btn", "success": False, "error": "Element not visible"},
        permission_used=PermissionLevel.NETWORK_READ,
    )
    is_ok, err = verifier.verify_step_outcome(step, fail_res)
    assert is_ok is False
    assert "Element not visible" in err or "click element failed" in err.lower()


# ==============================================================================
# 5. Router & Planner Selection Tests
# ==============================================================================

def test_router_classifies_browser_intents():
    """Verify DeterministicRouter classifies browser commands to SKILL intent."""
    router = DeterministicRouter()
    prompts = [
        "open website https://python.org in the browser",
        "inspect page elements and capture page snapshot",
        "take screenshot of current page",
        "click element @ref_3 on the page",
        "fill field @ref_2 with 'test query'",
        "list tabs in browser",
    ]
    for p in prompts:
        route = router.route(p)
        assert route.category == IntentCategory.SKILL
        assert route.confidence >= 0.85


def test_intelligent_skill_selector_browser_skills():
    """Verify IntelligentSkillSelector maps browser goals to proper skills without hallucination."""
    planner = AdaptivePlanner()
    matches = planner.selector.match_skills_for_prompt("open website https://example.com and inspect page elements")
    skill_ids = [m.skill_id for m in matches]
    assert "browser_open" in skill_ids or "browser_get_page_snapshot" in skill_ids


def test_adaptive_planner_creates_browser_plan():
    """Verify AdaptivePlanner generates an executable TaskPlan for browser goals."""
    planner = AdaptivePlanner()
    plan = planner.create_plan("open website https://python.org and take screenshot")
    assert plan.status == PlanStatus.PENDING
    assert len(plan.steps) >= 1
    assert any("browser" in s.skill_id for s in plan.steps)


# ==============================================================================
# 6. Ref-ID Interaction, Tab Switching, and SkillExecutor Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_ref_id_interaction_and_tab_operations():
    """Verify interaction using @ref_N identifiers and tab operations."""
    bm = BrowserManager()
    await bm.ensure_initialized()
    try:
        html = """
        <html><body>
            <input id="user-field" name="username" type="text" value="" />
            <button id="next-btn" type="button">Next Step</button>
        </body></html>
        """
        await bm._active_page.set_content(html)
        snapshot = await bm.get_page_snapshot()

        # Find ref_id for the input
        input_ref = None
        btn_ref = None
        for el in snapshot.interactive_elements:
            if el.is_input:
                input_ref = el.ref_id
            elif el.is_clickable:
                btn_ref = el.ref_id

        assert input_ref is not None
        assert btn_ref is not None

        # Fill using ref_id
        fill_res = await bm.fill_field(ref_id=input_ref, value="cavrix_agent")
        assert fill_res.success is True
        assert fill_res.target == input_ref

        # Click using ref_id
        click_res = await bm.click_element(ref_id=btn_ref)
        assert click_res.success is True
        assert click_res.target == btn_ref

        # Tab management
        tabs = await bm.list_tabs()
        assert tabs.tabs_count >= 1

        # Tab close (safe fallback ensures at least 1 remains open)
        close_res = await bm.close_tab(tab_index=0)
        assert close_res.success is True
        assert close_res.remaining_tabs_count >= 1
    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_skill_executor_browser_tools_execution():
    """Verify SkillExecutor can execute browser tools safely with audit trails."""
    executor = SkillExecutor()
    bm = get_browser_manager()
    await bm.ensure_initialized()

    try:
        await bm._active_page.set_content("<html><body><h1>CIE Agent</h1><button id='b1'>Action</button></body></html>")

        # Execute browser_get_page_snapshot via SkillExecutor
        req = ToolExecutionRequest(
            tool_name="browser_get_page_snapshot",
            arguments={"include_interactive_only": False},
        )
        res = await executor.execute(req)
        assert res.success is True
        assert "accessibility_tree" in res.result
        assert res.permission_used == PermissionLevel.NETWORK_READ

        # Execute browser_find_text via SkillExecutor
        find_req = ToolExecutionRequest(
            tool_name="browser_find_text",
            arguments={"query": "CIE Agent"},
        )
        find_res = await executor.execute(find_req)
        assert find_res.success is True
        assert find_res.result["found"] is True
    finally:
        await bm.close()

