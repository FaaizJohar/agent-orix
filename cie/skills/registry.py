"""
Modular Typed Skills Registry for CIE.
Maintains tool definitions, permissions, risk ratings, and handler functions.
"""

from typing import Any, Callable, Dict, List, Optional
from cie.skills.schemas import PermissionLevel, RiskLevel, ToolDefinition


class SkillRegistryError(Exception):
    pass


class SkillRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable,
    ) -> None:
        """
        Registers a tool definition and its execution handler.
        """
        if definition.name in self._tools:
            raise SkillRegistryError(f"Tool '{definition.name}' is already registered.")

        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name)

    def list_tools(
        self,
        permission: Optional[PermissionLevel] = None,
        enabled_only: bool = True,
    ) -> List[ToolDefinition]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        if permission:
            tools = [t for t in tools if t.permission == permission]
        return tools

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name not in self._tools:
            raise SkillRegistryError(f"Tool '{name}' not found.")
        self._tools[name].enabled = enabled


def build_default_registry() -> SkillRegistry:
    """Constructs and populates the default registry with all 16 built-in tools."""
    from cie.skills.tools.python_ast import PythonAstInput, PythonAstOutput, python_ast_validate
    from cie.skills.tools.json_validator import JsonValidateInput, JsonValidateOutput, json_validate
    from cie.skills.tools.yaml_validator import YamlValidateInput, YamlValidateOutput, yaml_validate
    from cie.skills.tools.markdown_tools import (
        MarkdownCheckInput,
        MarkdownCheckOutput,
        MarkdownToTextInput,
        MarkdownToTextOutput,
        markdown_check,
        markdown_to_text,
    )
    from cie.skills.tools.git_tools import (
        GitStatusInput,
        GitStatusOutput,
        GitDiffSummaryInput,
        GitDiffSummaryOutput,
        git_status,
        git_diff_summary,
    )
    from cie.skills.tools.file_tools import (
        FileTreeInspectInput,
        FileTreeInspectOutput,
        file_tree_inspect,
        FileReadTextInput,
        FileReadTextOutput,
        file_read_text,
        FileSearchTextInput,
        FileSearchTextOutput,
        file_search_text,
    )
    from cie.skills.tools.document_tools import (
        DocumentExtractTextInput,
        DocumentExtractTextOutput,
        document_extract_text,
        DocumentQAInput,
        DocumentQAOutput,
        document_qa,
    )
    from cie.skills.tools.readme_tools import ReadmeExtractInput, ReadmeExtractOutput, readme_extract
    from cie.skills.tools.project_inspect import (
        PythonProjectInspectInput,
        PythonProjectInspectOutput,
        python_project_inspect,
    )
    from cie.skills.tools.dependency_inspect import (
        DependencyInspectInput,
        DependencyInspectOutput,
        dependency_inspect,
    )
    from cie.skills.tools.test_discover import TestDiscoverInput, TestDiscoverOutput, test_discover
    from cie.skills.tools.log_tools import LogParseErrorsInput, LogParseErrorsOutput, log_parse_errors
    from cie.skills.tools.file_integrity import (
        FileIntegrityInput,
        FileIntegrityOutput,
        file_integrity_verify,
    )
    from cie.skills.tools.http_tools import (
        HttpEndpointCheckInput,
        HttpEndpointCheckOutput,
        http_endpoint_check,
    )
    from cie.skills.tools.github_tools import (
        GithubRepoInspectInput,
        GithubRepoInspectOutput,
        github_repo_inspect,
    )

    registry = SkillRegistry()

    # 1. python_ast_validate
    registry.register(
        ToolDefinition(
            name="python_ast_validate",
            display_name="Python AST Validator",
            description="Validates Python syntax and extracts classes, functions, and imports safely without execution.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=PythonAstInput,
            output_model=PythonAstOutput,
            input_schema=PythonAstInput.model_json_schema(),
            output_schema=PythonAstOutput.model_json_schema(),
        ),
        python_ast_validate,
    )

    # 2. json_validate
    registry.register(
        ToolDefinition(
            name="json_validate",
            display_name="JSON Validator",
            description="Parses and validates JSON strings, returning data type and element counts.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=JsonValidateInput,
            output_model=JsonValidateOutput,
            input_schema=JsonValidateInput.model_json_schema(),
            output_schema=JsonValidateOutput.model_json_schema(),
        ),
        json_validate,
    )

    # 3. yaml_validate
    registry.register(
        ToolDefinition(
            name="yaml_validate",
            display_name="YAML Validator",
            description="Safely validates YAML syntax using PyYAML safe_load.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=YamlValidateInput,
            output_model=YamlValidateOutput,
            input_schema=YamlValidateInput.model_json_schema(),
            output_schema=YamlValidateOutput.model_json_schema(),
        ),
        yaml_validate,
    )

    # 4. markdown_check
    registry.register(
        ToolDefinition(
            name="markdown_check",
            display_name="Markdown Structural Checker",
            description="Checks Markdown headings hierarchy, unclosed code blocks, and link integrity.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=MarkdownCheckInput,
            output_model=MarkdownCheckOutput,
            input_schema=MarkdownCheckInput.model_json_schema(),
            output_schema=MarkdownCheckOutput.model_json_schema(),
        ),
        markdown_check,
    )

    # 5. markdown_to_text
    registry.register(
        ToolDefinition(
            name="markdown_to_text",
            display_name="Markdown to Plaintext Converter",
            description="Strips markdown formatting tags and produces clean, unformatted plaintext.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=MarkdownToTextInput,
            output_model=MarkdownToTextOutput,
            input_schema=MarkdownToTextInput.model_json_schema(),
            output_schema=MarkdownToTextOutput.model_json_schema(),
        ),
        markdown_to_text,
    )

    # 6. git_status
    registry.register(
        ToolDefinition(
            name="git_status",
            display_name="Git Status Inspector",
            description="Inspects working directory git status and modified files safely without shell invocation.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=GitStatusInput,
            output_model=GitStatusOutput,
            input_schema=GitStatusInput.model_json_schema(),
            output_schema=GitStatusOutput.model_json_schema(),
        ),
        git_status,
    )

    # 7. git_diff_summary
    registry.register(
        ToolDefinition(
            name="git_diff_summary",
            display_name="Git Diff Summary Inspector",
            description="Inspects git diff summary statistics (--stat) without mutations.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=GitDiffSummaryInput,
            output_model=GitDiffSummaryOutput,
            input_schema=GitDiffSummaryInput.model_json_schema(),
            output_schema=GitDiffSummaryOutput.model_json_schema(),
        ),
        git_diff_summary,
    )

    # 8. file_tree_inspect
    registry.register(
        ToolDefinition(
            name="file_tree_inspect",
            display_name="File Tree Inspector",
            description="Safely inspects directory trees with depth limits and automated privacy exclusions (.env, .git).",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=FileTreeInspectInput,
            output_model=FileTreeInspectOutput,
            input_schema=FileTreeInspectInput.model_json_schema(),
            output_schema=FileTreeInspectOutput.model_json_schema(),
        ),
        file_tree_inspect,
    )

    # 8a. file_read_text
    registry.register(
        ToolDefinition(
            name="file_read_text",
            display_name="Safe File Text Reader",
            description="Safely reads lines of text from files within allowed workspace roots with size and boundary enforcement.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=FileReadTextInput,
            output_model=FileReadTextOutput,
            input_schema=FileReadTextInput.model_json_schema(),
            output_schema=FileReadTextOutput.model_json_schema(),
        ),
        file_read_text,
    )

    # 8b. file_search_text
    registry.register(
        ToolDefinition(
            name="file_search_text",
            display_name="Safe File Text Searcher",
            description="Searches for text matches across files within permitted roots ignoring sensitive files and caches.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=FileSearchTextInput,
            output_model=FileSearchTextOutput,
            input_schema=FileSearchTextInput.model_json_schema(),
            output_schema=FileSearchTextOutput.model_json_schema(),
        ),
        file_search_text,
    )

    # 9. readme_extract
    registry.register(
        ToolDefinition(
            name="readme_extract",
            display_name="README Metadata Extractor",
            description="Extracts title, badges, sections, and code snippet languages from README files.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=ReadmeExtractInput,
            output_model=ReadmeExtractOutput,
            input_schema=ReadmeExtractInput.model_json_schema(),
            output_schema=ReadmeExtractOutput.model_json_schema(),
        ),
        readme_extract,
    )

    # 10. python_project_inspect
    registry.register(
        ToolDefinition(
            name="python_project_inspect",
            display_name="Python Project Inspector",
            description="Inspects project build configurations, virtualenv presence, and test folder presence.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=PythonProjectInspectInput,
            output_model=PythonProjectInspectOutput,
            input_schema=PythonProjectInspectInput.model_json_schema(),
            output_schema=PythonProjectInspectOutput.model_json_schema(),
        ),
        python_project_inspect,
    )

    # 11. dependency_inspect
    registry.register(
        ToolDefinition(
            name="dependency_inspect",
            display_name="Dependency Manifest Inspector",
            description="Parses declared dependencies from requirements.txt, package.json, or pyproject.toml.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=120,
            input_model=DependencyInspectInput,
            output_model=DependencyInspectOutput,
            input_schema=DependencyInspectInput.model_json_schema(),
            output_schema=DependencyInspectOutput.model_json_schema(),
        ),
        dependency_inspect,
    )

    # 12. test_discover
    registry.register(
        ToolDefinition(
            name="test_discover",
            display_name="Test Case Discoverer",
            description="Statically discovers test files, test classes, and test functions without running tests.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=TestDiscoverInput,
            output_model=TestDiscoverOutput,
            input_schema=TestDiscoverInput.model_json_schema(),
            output_schema=TestDiscoverOutput.model_json_schema(),
        ),
        test_discover,
    )

    # 13. log_parse_errors
    registry.register(
        ToolDefinition(
            name="log_parse_errors",
            display_name="Log Error and Traceback Parser",
            description="Parses log text or files to extract errors, warnings, and stack traces with secret redaction.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=LogParseErrorsInput,
            output_model=LogParseErrorsOutput,
            input_schema=LogParseErrorsInput.model_json_schema(),
            output_schema=LogParseErrorsOutput.model_json_schema(),
        ),
        log_parse_errors,
    )

    # 14. file_integrity_verify
    registry.register(
        ToolDefinition(
            name="file_integrity_verify",
            display_name="File Checksum and Integrity Verifier",
            description="Computes SHA-256 and MD5 cryptographic hashes and byte sizes in bounded 64KB memory chunks.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=FileIntegrityInput,
            output_model=FileIntegrityOutput,
            input_schema=FileIntegrityInput.model_json_schema(),
            output_schema=FileIntegrityOutput.model_json_schema(),
        ),
        file_integrity_verify,
    )

    # 15. http_endpoint_check
    registry.register(
        ToolDefinition(
            name="http_endpoint_check",
            display_name="HTTP Endpoint Health Checker",
            description="Checks remote HTTP status codes and latency with SSRF firewall blocking private IP ranges.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.MEDIUM,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=HttpEndpointCheckInput,
            output_model=HttpEndpointCheckOutput,
            input_schema=HttpEndpointCheckInput.model_json_schema(),
            output_schema=HttpEndpointCheckOutput.model_json_schema(),
        ),
        http_endpoint_check,
    )

    # 16. github_repo_inspect
    registry.register(
        ToolDefinition(
            name="github_repo_inspect",
            display_name="GitHub Repository Inspector",
            description="Queries public GitHub repository metadata, stars, forks, and README.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.MEDIUM,
            timeout_seconds=15.0,
            rate_limit_per_minute=30,
            input_model=GithubRepoInspectInput,
            output_model=GithubRepoInspectOutput,
            input_schema=GithubRepoInspectInput.model_json_schema(),
            output_schema=GithubRepoInspectOutput.model_json_schema(),
        ),
        github_repo_inspect,
    )

    # 17. document_extract_text
    registry.register(
        ToolDefinition(
            name="document_extract_text",
            display_name="Document Text Extractor",
            description="Safely extracts structured text, headings, pages, and tables from PDF, Word, Excel, CSV, or text documents.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=DocumentExtractTextInput,
            output_model=DocumentExtractTextOutput,
            input_schema=DocumentExtractTextInput.model_json_schema(),
            output_schema=DocumentExtractTextOutput.model_json_schema(),
        ),
        document_extract_text,
    )

    # 18. document_qa
    registry.register(
        ToolDefinition(
            name="document_qa",
            display_name="Grounded Document Question Answering",
            description="Answers questions grounded in local document evidence using FTS5 retrieval and verified citations.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=30,
            input_model=DocumentQAInput,
            output_model=DocumentQAOutput,
            input_schema=DocumentQAInput.model_json_schema(),
            output_schema=DocumentQAOutput.model_json_schema(),
        ),
        document_qa,
    )

    # Browser Automation & Controlled Computer Use Tools (19 - 30)
    from cie.skills.tools.browser_tools import (
        browser_open,
        browser_back,
        browser_get_page_snapshot,
        browser_find_text,
        browser_click_element,
        browser_fill_field,
        browser_select_option,
        browser_list_tabs,
        browser_switch_tab,
        browser_close_tab,
        browser_take_screenshot,
        browser_wait_for_text,
    )
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

    # 19. browser_open
    registry.register(
        ToolDefinition(
            name="browser_open",
            display_name="Browser Open URL",
            description="Safely opens an HTTP/HTTPS URL in the headless browser after SSRF validation.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.MEDIUM,
            timeout_seconds=20.0,
            rate_limit_per_minute=30,
            input_model=BrowserOpenInput,
            output_model=BrowserOpenOutput,
            input_schema=BrowserOpenInput.model_json_schema(),
            output_schema=BrowserOpenOutput.model_json_schema(),
        ),
        browser_open,
    )

    # 20. browser_back
    registry.register(
        ToolDefinition(
            name="browser_back",
            display_name="Browser Navigate Back",
            description="Navigates back to previous page in browser history.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=BrowserBackInput,
            output_model=BrowserBackOutput,
            input_schema=BrowserBackInput.model_json_schema(),
            output_schema=BrowserBackOutput.model_json_schema(),
        ),
        browser_back,
    )

    # 21. browser_get_page_snapshot
    registry.register(
        ToolDefinition(
            name="browser_get_page_snapshot",
            display_name="Browser Page Accessibility Snapshot",
            description="Captures visible text, accessibility tree, and stable interactive @ref_N elements.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=40,
            input_model=BrowserSnapshotInput,
            output_model=BrowserSnapshotOutput,
            input_schema=BrowserSnapshotInput.model_json_schema(),
            output_schema=BrowserSnapshotOutput.model_json_schema(),
        ),
        browser_get_page_snapshot,
    )

    # 22. browser_find_text
    registry.register(
        ToolDefinition(
            name="browser_find_text",
            display_name="Browser Find Text",
            description="Searches visible page content for a query string and returns matching context snippets.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=BrowserFindTextInput,
            output_model=BrowserFindTextOutput,
            input_schema=BrowserFindTextInput.model_json_schema(),
            output_schema=BrowserFindTextOutput.model_json_schema(),
        ),
        browser_find_text,
    )

    # 23. browser_click_element
    registry.register(
        ToolDefinition(
            name="browser_click_element",
            display_name="Browser Click Element",
            description="Clicks an interactive element by @ref_N ID, CSS selector, or visible text with consequential action checks.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.MEDIUM,
            timeout_seconds=15.0,
            rate_limit_per_minute=30,
            input_model=BrowserClickInput,
            output_model=BrowserClickOutput,
            input_schema=BrowserClickInput.model_json_schema(),
            output_schema=BrowserClickOutput.model_json_schema(),
        ),
        browser_click_element,
    )

    # 24. browser_fill_field
    registry.register(
        ToolDefinition(
            name="browser_fill_field",
            display_name="Browser Fill Field",
            description="Fills text into an input field or textarea and optionally submits with Enter.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.MEDIUM,
            timeout_seconds=15.0,
            rate_limit_per_minute=30,
            input_model=BrowserFillInput,
            output_model=BrowserFillOutput,
            input_schema=BrowserFillInput.model_json_schema(),
            output_schema=BrowserFillOutput.model_json_schema(),
        ),
        browser_fill_field,
    )

    # 25. browser_select_option
    registry.register(
        ToolDefinition(
            name="browser_select_option",
            display_name="Browser Select Dropdown Option",
            description="Selects an option from a select dropdown element by option value or visible label.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=BrowserSelectInput,
            output_model=BrowserSelectOutput,
            input_schema=BrowserSelectInput.model_json_schema(),
            output_schema=BrowserSelectOutput.model_json_schema(),
        ),
        browser_select_option,
    )

    # 26. browser_list_tabs
    registry.register(
        ToolDefinition(
            name="browser_list_tabs",
            display_name="Browser List Open Tabs",
            description="Lists all open tabs, URLs, titles, and active tab index in current browser session.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=60,
            input_model=BrowserTabListInput,
            output_model=BrowserTabListOutput,
            input_schema=BrowserTabListInput.model_json_schema(),
            output_schema=BrowserTabListOutput.model_json_schema(),
        ),
        browser_list_tabs,
    )

    # 27. browser_switch_tab
    registry.register(
        ToolDefinition(
            name="browser_switch_tab",
            display_name="Browser Switch Active Tab",
            description="Switches focus and active context to the specified tab index.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=BrowserTabSwitchInput,
            output_model=BrowserTabSwitchOutput,
            input_schema=BrowserTabSwitchInput.model_json_schema(),
            output_schema=BrowserTabSwitchOutput.model_json_schema(),
        ),
        browser_switch_tab,
    )

    # 28. browser_close_tab
    registry.register(
        ToolDefinition(
            name="browser_close_tab",
            display_name="Browser Close Tab",
            description="Closes the specified tab index and maintains at least one operational tab.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=BrowserTabCloseInput,
            output_model=BrowserTabCloseOutput,
            input_schema=BrowserTabCloseInput.model_json_schema(),
            output_schema=BrowserTabCloseOutput.model_json_schema(),
        ),
        browser_close_tab,
    )

    # 29. browser_take_screenshot
    registry.register(
        ToolDefinition(
            name="browser_take_screenshot",
            display_name="Browser Take Screenshot",
            description="Captures a PNG screenshot of the current viewport or full page and saves to local disk.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=20,
            input_model=BrowserScreenshotInput,
            output_model=BrowserScreenshotOutput,
            input_schema=BrowserScreenshotInput.model_json_schema(),
            output_schema=BrowserScreenshotOutput.model_json_schema(),
        ),
        browser_take_screenshot,
    )

    # 30. browser_wait_for_text
    registry.register(
        ToolDefinition(
            name="browser_wait_for_text",
            display_name="Browser Wait For Text",
            description="Waits for a specific text string or element to appear on the page before proceeding.",
            permission=PermissionLevel.NETWORK_READ,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=30,
            input_model=BrowserWaitTextInput,
            output_model=BrowserWaitTextOutput,
            input_schema=BrowserWaitTextInput.model_json_schema(),
            output_schema=BrowserWaitTextOutput.model_json_schema(),
        ),
        browser_wait_for_text,
    )

    # ==============================================================================
    # Desktop Automation & Controlled Computer Use Tools (Phase 5)
    # ==============================================================================
    from cie.desktop.schemas import (
        DesktopClickInput,
        DesktopClickOutput,
        DesktopKeypressInput,
        DesktopKeypressOutput,
        DesktopListWindowsInput,
        DesktopListWindowsOutput,
        DesktopScreenshotInput,
        DesktopScreenshotOutput,
        DesktopStateOutput,
        DesktopTypeTextInput,
        DesktopTypeTextOutput,
        DesktopWaitForStateInput,
        DesktopWaitForStateOutput,
    )
    from cie.skills.tools.desktop_tools import (
        desktop_click,
        desktop_get_state,
        desktop_keypress,
        desktop_list_windows,
        desktop_screenshot,
        desktop_type_text,
        desktop_wait_for_state,
    )

    # 31. desktop_get_state
    registry.register(
        ToolDefinition(
            name="desktop_get_state",
            display_name="Desktop Get State",
            description="Retrieves primary monitor resolution, active foreground window, and allowlist security status.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=60,
            output_model=DesktopStateOutput,
            output_schema=DesktopStateOutput.model_json_schema(),
        ),
        desktop_get_state,
    )

    # 32. desktop_list_windows
    registry.register(
        ToolDefinition(
            name="desktop_list_windows",
            display_name="Desktop List Visible Windows",
            description="Lists all visible top-level windows, process names, and whether they are permitted by allowlist.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=5.0,
            rate_limit_per_minute=60,
            input_model=DesktopListWindowsInput,
            output_model=DesktopListWindowsOutput,
            input_schema=DesktopListWindowsInput.model_json_schema(),
            output_schema=DesktopListWindowsOutput.model_json_schema(),
        ),
        desktop_list_windows,
    )

    # 33. desktop_screenshot
    registry.register(
        ToolDefinition(
            name="desktop_screenshot",
            display_name="Desktop Take Screenshot",
            description="Captures a PNG screenshot of the display or target window rectangle.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=DesktopScreenshotInput,
            output_model=DesktopScreenshotOutput,
            input_schema=DesktopScreenshotInput.model_json_schema(),
            output_schema=DesktopScreenshotOutput.model_json_schema(),
        ),
        desktop_screenshot,
    )

    # 34. desktop_click
    registry.register(
        ToolDefinition(
            name="desktop_click",
            display_name="Desktop Mouse Click",
            description="Simulates mouse click at coordinates (x, y) on permitted windows with action-bound approval tokens.",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_approval=True,
            timeout_seconds=5.0,
            rate_limit_per_minute=30,
            input_model=DesktopClickInput,
            output_model=DesktopClickOutput,
            input_schema=DesktopClickInput.model_json_schema(),
            output_schema=DesktopClickOutput.model_json_schema(),
        ),
        desktop_click,
    )

    # 35. desktop_type_text
    registry.register(
        ToolDefinition(
            name="desktop_type_text",
            display_name="Desktop Type Text",
            description="Types text into the active permitted window with credential redaction and action approval tokens.",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_approval=True,
            timeout_seconds=10.0,
            rate_limit_per_minute=30,
            input_model=DesktopTypeTextInput,
            output_model=DesktopTypeTextOutput,
            input_schema=DesktopTypeTextInput.model_json_schema(),
            output_schema=DesktopTypeTextInput.model_json_schema(),
        ),
        desktop_type_text,
    )

    # 36. desktop_keypress
    registry.register(
        ToolDefinition(
            name="desktop_keypress",
            display_name="Desktop Send Keypress",
            description="Sends key or modifier combo (Enter, Tab, Esc, Ctrl+S) with action approval tokens for consequential keys.",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_approval=True,
            timeout_seconds=5.0,
            rate_limit_per_minute=30,
            input_model=DesktopKeypressInput,
            output_model=DesktopKeypressOutput,
            input_schema=DesktopKeypressInput.model_json_schema(),
            output_schema=DesktopKeypressOutput.model_json_schema(),
        ),
        desktop_keypress,
    )

    # 37. desktop_wait_for_state
    registry.register(
        ToolDefinition(
            name="desktop_wait_for_state",
            display_name="Desktop Wait For State",
            description="Polls until a window with matching title or process name appears within deadline.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=30.0,
            rate_limit_per_minute=30,
            input_model=DesktopWaitForStateInput,
            output_model=DesktopWaitForStateOutput,
            input_schema=DesktopWaitForStateInput.model_json_schema(),
            output_schema=DesktopWaitForStateOutput.model_json_schema(),
        ),
        desktop_wait_for_state,
    )

    # 38. markitdown_convert (Phase 15 Upstream Microsoft MarkItDown Integration)
    from cie.skills.tools.document_tools import (
        MarkItDownConvertInput,
        MarkItDownConvertOutput,
        markitdown_convert,
    )
    registry.register(
        ToolDefinition(
            name="markitdown_convert",
            display_name="Microsoft MarkItDown Document Converter",
            description="Converts documents, spreadsheets, presentations, and HTML into clean Markdown using Microsoft MarkItDown.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=30.0,
            rate_limit_per_minute=60,
            input_model=MarkItDownConvertInput,
            output_model=MarkItDownConvertOutput,
            input_schema=MarkItDownConvertInput.model_json_schema(),
            output_schema=MarkItDownConvertOutput.model_json_schema(),
        ),
        markitdown_convert,
    )

    # 39. crawl4ai_extract (Phase 15 Upstream Crawl4AI Integration)
    from cie.skills.tools.browser_tools import (
        Crawl4AIExtractInput,
        Crawl4AIExtractOutput,
        crawl4ai_extract,
    )
    registry.register(
        ToolDefinition(
            name="crawl4ai_extract",
            display_name="Crawl4AI Structured Web Content Extractor",
            description="Extracts structured markdown, links, and media from HTML or URLs using Crawl4AI.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=20.0,
            rate_limit_per_minute=60,
            input_model=Crawl4AIExtractInput,
            output_model=Crawl4AIExtractOutput,
            input_schema=Crawl4AIExtractInput.model_json_schema(),
            output_schema=Crawl4AIExtractOutput.model_json_schema(),
        ),
        crawl4ai_extract,
    )

    # 40. swerex_execute (Phase 15 Upstream SWE-ReX AbstractRuntime Integration)
    from cie.skills.tools.desktop_tools import (
        SWERexExecuteInput,
        SWERexExecuteOutput,
        swerex_execute,
    )
    registry.register(
        ToolDefinition(
            name="swerex_execute",
            display_name="SWE-ReX Isolated Workspace Executor",
            description="Executes commands within a contained workspace enforcing path boundaries and sanitized environments.",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_consequential_approval=True,
            timeout_seconds=30.0,
            rate_limit_per_minute=30,
            input_model=SWERexExecuteInput,
            output_model=SWERexExecuteOutput,
            input_schema=SWERexExecuteInput.model_json_schema(),
            output_schema=SWERexExecuteOutput.model_json_schema(),
        ),
        swerex_execute,
    )

    # 41. dspy_compile_signature (Phase 16 Upstream Stanford DSPy Integration)
    from cie.skills.tools.document_tools import (
        DSPyCompileSignatureInput,
        DSPyCompileSignatureOutput,
        dspy_compile_signature,
    )
    registry.register(
        ToolDefinition(
            name="dspy_compile_signature",
            display_name="DSPy Declarative Signature Compiler",
            description="Compiles declarative prompt signatures into structured instructions using Stanford DSPy primitives.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=60,
            input_model=DSPyCompileSignatureInput,
            output_model=DSPyCompileSignatureOutput,
            input_schema=DSPyCompileSignatureInput.model_json_schema(),
            output_schema=DSPyCompileSignatureOutput.model_json_schema(),
        ),
        dspy_compile_signature,
    )

    # 42. inspect_ai_eval (Phase 16 Upstream UK AISI Inspect AI Integration)
    from cie.skills.tools.document_tools import (
        InspectAIEvalInput,
        InspectAIEvalOutput,
        inspect_ai_eval,
    )
    registry.register(
        ToolDefinition(
            name="inspect_ai_eval",
            display_name="Inspect AI Benchmark Evaluation Runner",
            description="Evaluates benchmark samples and calculates accuracy metrics conforming to UK AISI Inspect AI.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=30.0,
            rate_limit_per_minute=60,
            input_model=InspectAIEvalInput,
            output_model=InspectAIEvalOutput,
            input_schema=InspectAIEvalInput.model_json_schema(),
            output_schema=InspectAIEvalOutput.model_json_schema(),
        ),
        inspect_ai_eval,
    )

    # 43. hermes_format_tool_call (Phase 17 Upstream NousResearch Hermes Integration)
    from cie.skills.tools.document_tools import (
        HermesFormatToolCallInput,
        HermesFormatToolCallOutput,
        hermes_format_tool_call,
    )
    registry.register(
        ToolDefinition(
            name="hermes_format_tool_call",
            display_name="Hermes Tool Call Formatter & Validator",
            description="Formats and parses structured XML/JSON tool calls conforming to upstream NousResearch Hermes protocol.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=15.0,
            rate_limit_per_minute=60,
            input_model=HermesFormatToolCallInput,
            output_model=HermesFormatToolCallOutput,
            input_schema=HermesFormatToolCallInput.model_json_schema(),
            output_schema=HermesFormatToolCallOutput.model_json_schema(),
        ),
        hermes_format_tool_call,
    )

    # 44. lightrag_query_graph (Phase 17 Upstream HKUDS LightRAG Integration)
    from cie.skills.tools.document_tools import (
        LightRAGQueryInput,
        LightRAGQueryOutput,
        lightrag_query_graph,
    )
    registry.register(
        ToolDefinition(
            name="lightrag_query_graph",
            display_name="LightRAG Dual-Level Knowledge Graph Retriever",
            description="Retrieves low-level entities and high-level community themes using upstream HKUDS LightRAG primitives.",
            permission=PermissionLevel.READ_ONLY,
            risk=RiskLevel.LOW,
            timeout_seconds=30.0,
            rate_limit_per_minute=60,
            input_model=LightRAGQueryInput,
            output_model=LightRAGQueryOutput,
            input_schema=LightRAGQueryInput.model_json_schema(),
            output_schema=LightRAGQueryOutput.model_json_schema(),
        ),
        lightrag_query_graph,
    )

    return registry


_default_registry: Optional[SkillRegistry] = None


def get_default_registry() -> SkillRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry
