"""
Chrome DevTools MCP Adapter (ChromeDevTools/chrome-devtools-mcp).
Provides Chrome DevTools Protocol inspection, console logging,
network request tracking, and DOM evaluation.
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DevToolsConsoleLog(BaseModel):
    level: str
    message: str
    source: str = "console-api"
    timestamp: float = Field(default_factory=time.time)


class DevToolsNetworkRequest(BaseModel):
    request_id: str
    url: str
    method: str
    status: Optional[int] = None
    response_headers: Dict[str, str] = Field(default_factory=dict)
    duration_ms: Optional[float] = None


class ChromeDevToolsMCPAdapter:
    """
    Connects to CDP (Chrome DevTools Protocol) sessions to inspect
    runtime console logs, network timing, and DOM nodes.
    """

    def __init__(self):
        self.console_logs: List[DevToolsConsoleLog] = []
        self.network_requests: List[DevToolsNetworkRequest] = []

    def record_console_log(self, level: str, message: str, source: str = "console-api") -> None:
        self.console_logs.append(DevToolsConsoleLog(level=level, message=message, source=source))

    def record_network_request(self, req: DevToolsNetworkRequest) -> None:
        self.network_requests.append(req)

    def get_console_errors(self) -> List[DevToolsConsoleLog]:
        return [l for l in self.console_logs if l.level.lower() in ("error", "fatal")]

    def get_network_summary(self) -> Dict[str, Any]:
        total = len(self.network_requests)
        failed = sum(1 for r in self.network_requests if r.status and r.status >= 400)
        return {"total_requests": total, "failed_requests": failed}
