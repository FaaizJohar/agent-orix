"""
Tests for CavrixCode Phase 12/13 - Batch 2: Browser Automation, Research, and Web Access (Entries 9-15).
Playwright MCP, Browser Use, Chrome DevTools MCP, Context7, Crawl4AI, Obscura, n8n.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cie.capabilities.browser.playwright_mcp import PlaywrightMCPAdapter
from cie.capabilities.browser.browser_use import BrowserUseAgent
from cie.capabilities.browser.devtools_mcp import ChromeDevToolsMCPAdapter, DevToolsNetworkRequest
from cie.capabilities.browser.context7 import Context7Adapter, LibraryDocQuery
from cie.capabilities.browser.crawl4ai import Crawl4AIAdapter
from cie.capabilities.browser.obscura import ObscuraAdapter
from cie.capabilities.browser.n8n import N8nWorkflowAdapter, WorkflowDefinition, WorkflowNode


def test_entry9_playwright_mcp():
    adapter = PlaywrightMCPAdapter()
    tools = adapter.list_tools()
    assert len(tools) >= 4
    tool_names = [t.name for t in tools]
    assert "browser_navigate" in tool_names
    assert "browser_click" in tool_names

    res = adapter.execute_mcp_call("browser_navigate", {"url": "https://example.com"})
    assert res["isError"] is False
    assert "successfully" in res["content"][0]["text"]


def test_entry10_browser_use():
    agent = BrowserUseAgent(max_steps=5)
    plan = agent.create_plan_for_goal("Look up Fastify documentation", "https://fastify.dev")
    assert len(plan.steps) >= 2
    assert plan.steps[0].action_name == "browser_open"
    assert agent.evaluate_step_outcome(plan.steps[0], {"success": True}) is True


def test_entry11_chrome_devtools_mcp():
    adapter = ChromeDevToolsMCPAdapter()
    adapter.record_console_log("info", "Page initialized")
    adapter.record_console_log("error", "Uncaught TypeError: Cannot read properties of undefined")
    errors = adapter.get_console_errors()
    assert len(errors) == 1
    assert "TypeError" in errors[0].message

    adapter.record_network_request(DevToolsNetworkRequest(request_id="req_1", url="https://api.test/data", method="GET", status=200))
    adapter.record_network_request(DevToolsNetworkRequest(request_id="req_2", url="https://api.test/missing", method="GET", status=404))
    summary = adapter.get_network_summary()
    assert summary["total_requests"] == 2
    assert summary["failed_requests"] == 1


def test_entry12_context7():
    adapter = Context7Adapter()
    res = adapter.fetch_docs(LibraryDocQuery(library="pydantic", version="2.0", query="BaseModel"))
    assert res.version == "2.10.0"
    assert len(res.matched_sections) > 0
    assert "BaseModel" in res.matched_sections[0]


def test_entry13_crawl4ai():
    adapter = Crawl4AIAdapter()
    html = """
    <html>
      <head><title>Test Article</title></head>
      <body>
        <h1>Main Heading</h1>
        <p>This is a paragraph with <a href="https://example.com/learn">Link</a>.</p>
        <img src="https://example.com/banner.png" alt="banner" />
      </body>
    </html>
    """
    res = adapter.extract_from_html("https://example.com", html, title="Test Article")
    assert res.title == "Test Article"
    assert "Main Heading" in res.markdown
    assert "https://example.com/learn" in res.links
    assert "https://example.com/banner.png" in res.images
    assert res.word_count > 0


def test_entry14_obscura():
    adapter = ObscuraAdapter()
    profile = adapter.create_stealth_profile()
    assert "Windows" in profile.user_agent or "Macintosh" in profile.user_agent
    assert profile.disable_webrtc is True
    assert profile.mask_canvas_noise is True
    assert "Sec-Ch-Ua" in profile.headers


def test_entry15_n8n():
    adapter = N8nWorkflowAdapter()
    workflow = WorkflowDefinition(
        name="Test Deploy Workflow",
        nodes=[
            WorkflowNode(id="node_1", name="Set Config", type="n8n-nodes-base.set", parameters={"env": "production"}),
            WorkflowNode(id="node_2", name="Webhook Call", type="n8n-nodes-base.httpRequest"),
        ]
    )
    res = adapter.execute_workflow(workflow)
    assert res.success is True
    assert len(res.executed_nodes) == 2
    assert res.outputs["env"] == "production"
    assert res.outputs["last_http_status"] == 200
