"""
Browser automation, research, and web access capabilities (Entries 9-15).
"""

from cie.capabilities.browser.playwright_mcp import PlaywrightMCPAdapter, MCPToolSchema
from cie.capabilities.browser.browser_use import BrowserUseAgent, BrowserUsePlan, BrowserActionStep
from cie.capabilities.browser.devtools_mcp import ChromeDevToolsMCPAdapter, DevToolsConsoleLog, DevToolsNetworkRequest
from cie.capabilities.browser.context7 import Context7Adapter, LibraryDocQuery, LibraryDocResult
from cie.capabilities.browser.crawl4ai import Crawl4AIAdapter, CrawlResult
from cie.capabilities.browser.obscura import ObscuraAdapter, BrowserProfileConfig
from cie.capabilities.browser.n8n import N8nWorkflowAdapter, WorkflowDefinition, WorkflowNode, WorkflowExecutionResult

__all__ = [
    "PlaywrightMCPAdapter",
    "MCPToolSchema",
    "BrowserUseAgent",
    "BrowserUsePlan",
    "BrowserActionStep",
    "ChromeDevToolsMCPAdapter",
    "DevToolsConsoleLog",
    "DevToolsNetworkRequest",
    "Context7Adapter",
    "LibraryDocQuery",
    "LibraryDocResult",
    "Crawl4AIAdapter",
    "CrawlResult",
    "ObscuraAdapter",
    "BrowserProfileConfig",
    "N8nWorkflowAdapter",
    "WorkflowDefinition",
    "WorkflowNode",
    "WorkflowExecutionResult",
]
