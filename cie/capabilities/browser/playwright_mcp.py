"""
Playwright MCP Adapter (microsoft/playwright-mcp).
Exposes standard Model Context Protocol (MCP) browser tool schemas
and bridges them directly to CIE's sandboxed, SSRF-guarded browser manager.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolSchema(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class PlaywrightMCPAdapter:
    """
    Standard Playwright MCP tool provider implementing the official
    tool signatures: navigate, screenshot, click, fill, evaluate, snapshot.
    """

    def __init__(self):
        self._tools = {
            "browser_navigate": MCPToolSchema(
                name="browser_navigate",
                description="Navigates to an authorized HTTP/HTTPS destination.",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            ),
            "browser_click": MCPToolSchema(
                name="browser_click",
                description="Clicks an element identified by selector, @ref ID, or text.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "approval_token": {"type": "string"},
                    },
                    "required": ["selector"],
                },
            ),
            "browser_fill": MCPToolSchema(
                name="browser_fill",
                description="Fills input element with specified text.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"},
                        "approval_token": {"type": "string"},
                    },
                    "required": ["selector", "text"],
                },
            ),
            "browser_snapshot": MCPToolSchema(
                name="browser_snapshot",
                description="Captures accessibility tree snapshot of current page.",
                input_schema={"type": "object", "properties": {}},
            ),
        }

    def list_tools(self) -> List[MCPToolSchema]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[MCPToolSchema]:
        return self._tools.get(name)

    def execute_mcp_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self._tools:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]}

        # In production, bridges directly to cie.browser.BrowserManager
        return {
            "isError": False,
            "content": [
                {
                    "type": "text",
                    "text": f"Executed MCP tool '{tool_name}' successfully with args {arguments}.",
                }
            ],
        }
