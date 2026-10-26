"""
Intelligent Skill Selector and Intent Decomposition Engine.
Distinguishes informational/direct questions from tool tasks, selects registered skills,
explains capability matches, and detects missing parameters or unsupported requests.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from cie.skills.registry import SkillRegistry, get_default_registry
from cie.skills.schemas import ToolDefinition


class SelectionMatch:
    def __init__(
        self,
        skill_id: str,
        display_name: str,
        reason: str,
        confidence: float,
        extracted_arguments: Dict[str, Any],
        missing_parameters: List[str] = None,
        clarification_prompt: Optional[str] = None,
    ):
        self.skill_id = skill_id
        self.display_name = display_name
        self.reason = reason
        self.confidence = confidence
        self.extracted_arguments = extracted_arguments
        self.missing_parameters = missing_parameters or []
        self.clarification_prompt = clarification_prompt


class IntelligentSkillSelector:
    """
    Intelligently maps user objectives to registered skills without hallucinations.
    """

    # Pure informational / conceptual queries that do NOT need tool invocation
    INFORMATIONAL_PATTERNS = [
        re.compile(r"^(what|who|when|where|why|how)\s+(is|are|was|were|do|does|can)\b", re.IGNORECASE),
        re.compile(r"\b(explain|describe|tell me about|summarize the concept of)\b", re.IGNORECASE),
        re.compile(r"^(write|implement|create|give me|show me)\s+(a\s+)?(?:[a-zA-Z0-9_+-]+\s+)?(function|script|example|code|algorithm)\s+(to|that|for)\b", re.IGNORECASE),
        re.compile(r"\b(difference between|compare)\s+.*?\s+and\b", re.IGNORECASE),
    ]

    # Explicit requests for capabilities that do NOT exist in the Skills Registry
    UNSUPPORTED_CAPABILITY_PATTERNS = [
        (re.compile(r"\b(docker|container|kubernetes|k8s|pod)\b", re.IGNORECASE), "Container/Kubernetes operations are not supported."),
        (re.compile(r"\b(send\s+(an?\s+)?(email|sms|text)|push\s+notification)\b", re.IGNORECASE), "Messaging and email dispatching are not supported."),
        (re.compile(r"\b(deploy\s+(to|on)\s+(aws|gcp|azure|heroku|vercel))\b", re.IGNORECASE), "Cloud deployment is not supported."),
        (re.compile(r"\b(bash|sh|cmd|powershell|terminal|shell)\s+(command|script|exec)\b", re.IGNORECASE), "Arbitrary shell execution is strictly disallowed."),
    ]

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or get_default_registry()

    def is_informational_or_direct(self, prompt: str) -> bool:
        """
        Determines if the prompt is an informational question or pure code generation
        that should receive a direct response rather than invoking tools.
        """
        stripped = prompt.strip()

        # If user explicitly asks to run, check, inspect, validate, or verify, it is NOT purely informational
        action_verbs = [
            "validate", "check", "inspect", "lint", "verify", "discover",
            "git status", "git diff", "sha256", "checksum", "extract readme",
            "check endpoint", "http", "read file", "read text", "search files",
            "search text", "grep", "extract document", "parse document",
            "read pdf", "read docx", "read excel", "read xlsx", "read csv",
            "document qa", "ask document"
        ]
        if any(verb in stripped.lower() for verb in action_verbs):
            return False

        for pattern in self.INFORMATIONAL_PATTERNS:
            if pattern.search(stripped):
                return True

        return False

    def detect_unsupported_capability(self, prompt: str) -> Optional[str]:
        """
        Detects if user is asking for capabilities outside the registered tools.
        """
        for pattern, reason in self.UNSUPPORTED_CAPABILITY_PATTERNS:
            if pattern.search(prompt):
                return reason
        return None

    def match_skills_for_prompt(self, prompt: str) -> List[SelectionMatch]:
        """
        Analyzes prompt and matches registered skills with extracted arguments
        and capability explanations.
        """
        matches: List[SelectionMatch] = []
        p_lower = prompt.lower()

        # 1. python_ast_validate
        if any(k in p_lower for k in ["python syntax", "python ast", "ast validate", "validate syntax"]):
            code_match = re.search(r"```(?:python)?\n([\s\S]*?)```", prompt)
            code = code_match.group(1) if code_match else ""
            if not code:
                # Check for explicit code snippet assignment or def/class keyword
                m = re.search(r"(?:code|snippet|syntax|python):\s*([\s\S]+)$", prompt, re.IGNORECASE)
                if m:
                    code = m.group(1).strip()
                elif "def " in prompt:
                    code = prompt[prompt.find("def "):].strip()
                elif "class " in prompt:
                    code = prompt[prompt.find("class "):].strip()

            missing = ["code"] if not code else []
            clarification = "Please provide the Python code snippet to validate." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="python_ast_validate",
                    display_name="Python AST Validator",
                    reason="Request asks to validate Python syntax/AST structure without execution.",
                    confidence=0.95,
                    extracted_arguments={"code": code} if code else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 2. json_validate
        if "json" in p_lower and any(k in p_lower for k in ["validate", "check", "parse", "lint", "verify"]):
            json_str = ""
            code_match = re.search(r"```(?:json)?\n([\s\S]*?)```", prompt)
            if code_match:
                json_str = code_match.group(1)
            else:
                start = prompt.find("{")
                if start == -1:
                    start = prompt.find("[")
                if start != -1:
                    closing = "}" if prompt[start] == "{" else "]"
                    end = prompt.rfind(closing)
                    json_str = prompt[start:end+1] if end > start else prompt[start:]

            missing = ["content"] if not json_str else []
            clarification = "Please provide the JSON string to validate." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="json_validate",
                    display_name="JSON Validator",
                    reason="Request asks to parse and validate JSON data structure.",
                    confidence=0.95,
                    extracted_arguments={"content": json_str} if json_str else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 3. yaml_validate
        if "yaml" in p_lower and any(k in p_lower for k in ["validate", "check", "parse", "lint"]):
            yaml_match = re.search(r"```(?:yaml)?\n([\s\S]*?)```", prompt)
            yaml_str = yaml_match.group(1) if yaml_match else ""
            matches.append(
                SelectionMatch(
                    skill_id="yaml_validate",
                    display_name="YAML Validator",
                    reason="Request asks to safely validate YAML syntax.",
                    confidence=0.95,
                    extracted_arguments={"content": yaml_str} if yaml_str else {"content": prompt},
                )
            )

        # 4. git_status
        if "git status" in p_lower or "git repo status" in p_lower:
            repo_path = "."
            # Extract path if provided
            path_m = re.search(r"(?:in|at|for|repo_path)\s+([a-zA-Z0-9_\-./\\]+)", prompt)
            if path_m and path_m.group(1).lower() not in ("repo", "git", "status"):
                repo_path = path_m.group(1)

            matches.append(
                SelectionMatch(
                    skill_id="git_status",
                    display_name="Git Status Inspector",
                    reason="Request asks to inspect current working tree and git branch status.",
                    confidence=0.95,
                    extracted_arguments={"repo_path": repo_path},
                )
            )

        # 5. git_diff_summary
        if "git diff" in p_lower:
            repo_path = "."
            matches.append(
                SelectionMatch(
                    skill_id="git_diff_summary",
                    display_name="Git Diff Summary",
                    reason="Request asks for summary of unstaged or staged git changes.",
                    confidence=0.95,
                    extracted_arguments={"repo_path": repo_path},
                )
            )

        # 6. file_tree_inspect
        if any(k in p_lower for k in ["file tree", "directory tree", "inspect files", "list files in tree"]):
            dir_path = "."
            path_m = re.search(r"(?:dir|directory|folder|in|at)\s+([a-zA-Z0-9_\-./\\]+)", prompt)
            if path_m and path_m.group(1).lower() not in ("tree", "files", "folder"):
                dir_path = path_m.group(1)

            matches.append(
                SelectionMatch(
                    skill_id="file_tree_inspect",
                    display_name="File Tree Inspector",
                    reason="Request asks to traverse directory and report file tree hierarchy.",
                    confidence=0.90,
                    extracted_arguments={"directory_path": dir_path, "max_depth": 3},
                )
            )

        # 7. readme_extract
        if "readme" in p_lower and any(k in p_lower for k in ["extract", "parse", "read", "summarize"]):
            matches.append(
                SelectionMatch(
                    skill_id="readme_extract",
                    display_name="README Extractor",
                    reason="Request asks to parse structured sections and headings from README.",
                    confidence=0.90,
                    extracted_arguments={"file_path_or_content": "README.md", "is_path": True},
                )
            )

        # 8. python_project_inspect
        if any(k in p_lower for k in ["inspect python project", "analyze python project", "python project structure"]):
            matches.append(
                SelectionMatch(
                    skill_id="python_project_inspect",
                    display_name="Python Project Inspector",
                    reason="Request asks to inspect Python package configuration, entry points, and modules.",
                    confidence=0.90,
                    extracted_arguments={"project_dir": "."},
                )
            )

        # 9. dependency_inspect
        if any(k in p_lower for k in ["dependency", "dependencies", "requirements.txt", "package.json"]):
            dep_file = "requirements.txt"
            if "package.json" in p_lower:
                dep_file = "package.json"
            elif "pyproject.toml" in p_lower:
                dep_file = "pyproject.toml"

            matches.append(
                SelectionMatch(
                    skill_id="dependency_inspect",
                    display_name="Dependency Inspector",
                    reason="Request asks to parse declared dependencies and version constraints.",
                    confidence=0.90,
                    extracted_arguments={"file_path": dep_file},
                )
            )

        # 10. test_discover
        if any(k in p_lower for k in ["discover tests", "find tests", "scan for tests", "test discovery"]):
            matches.append(
                SelectionMatch(
                    skill_id="test_discover",
                    display_name="Test Suite Discoverer",
                    reason="Request asks to find pytest/unittest test files without executing them.",
                    confidence=0.90,
                    extracted_arguments={"directory_path": "."},
                )
            )

        # 11. log_parse_errors
        if any(k in p_lower for k in ["parse log", "log errors", "extract errors from log", "error log"]):
            matches.append(
                SelectionMatch(
                    skill_id="log_parse_errors",
                    display_name="Log Error Parser",
                    reason="Request asks to extract structured stack traces and error messages from log.",
                    confidence=0.90,
                    extracted_arguments={"log_content_or_path": prompt, "is_path": False},
                )
            )

        # 12. file_integrity_verify
        if any(k in p_lower for k in ["file integrity", "sha256", "checksum", "verify file"]):
            path_m = re.search(r"(?:file|path|hash)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", prompt)
            f_path = path_m.group(1) if path_m else ""
            missing = ["file_path"] if not f_path else []
            clarification = "Please specify the file path to verify SHA-256 integrity." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="file_integrity_verify",
                    display_name="File Integrity Verifier",
                    reason="Request asks to calculate and verify cryptographic SHA-256 checksum.",
                    confidence=0.95,
                    extracted_arguments={"file_path": f_path} if f_path else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 13. http_endpoint_check
        if any(k in p_lower for k in ["check http", "check url", "endpoint status", "ping url", "http check"]):
            url_m = re.search(r"https?://[^\s]+", prompt)
            url = url_m.group(0) if url_m else ""
            missing = ["url"] if not url else []
            clarification = "Please specify the HTTP/HTTPS URL to check." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="http_endpoint_check",
                    display_name="HTTP Endpoint Inspector",
                    reason="Request asks to verify HTTP connectivity and response status code.",
                    confidence=0.95,
                    extracted_arguments={"url": url} if url else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 14. github_repo_inspect
        if any(k in p_lower for k in ["github repo", "inspect github", "query github"]):
            owner, repo = "", ""
            gh_m = re.search(r"github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)", prompt)
            if gh_m:
                owner, repo = gh_m.group(1), gh_m.group(2)
            else:
                # check for owner/repo pattern
                slash_m = re.search(r"\b([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)\b", prompt)
                if slash_m and "github" not in slash_m.group(0).lower():
                    owner, repo = slash_m.group(1), slash_m.group(2)

            missing = []
            if not owner or not repo:
                missing = ["owner", "repo"]
                clarification = "Please specify the GitHub repository in 'owner/repo' format."
            else:
                clarification = None

            matches.append(
                SelectionMatch(
                    skill_id="github_repo_inspect",
                    display_name="GitHub Repository Inspector",
                    reason="Request asks to fetch metadata for a public GitHub repository.",
                    confidence=0.95,
                    extracted_arguments={"owner": owner, "repo": repo} if not missing else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 15. markdown_check
        if "markdown" in p_lower and any(k in p_lower for k in ["lint", "check", "structure", "headings"]):
            matches.append(
                SelectionMatch(
                    skill_id="markdown_check",
                    display_name="Markdown Structural Checker",
                    reason="Request asks to check Markdown headings hierarchy and unclosed code blocks.",
                    confidence=0.90,
                    extracted_arguments={"content": prompt},
                )
            )

        # 16. file_read_text
        if any(k in p_lower for k in ["read file", "view file", "file content", "read text from file", "read lines from"]):
            path_m = re.search(r"(?:file|path|from)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", prompt)
            f_path = path_m.group(1) if path_m else ""
            missing = ["file_path"] if not f_path else []
            clarification = "Please specify the file path to read." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="file_read_text",
                    display_name="Safe File Text Reader",
                    reason="Request asks to safely read file content lines.",
                    confidence=0.95,
                    extracted_arguments={"file_path": f_path} if f_path else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 17. file_search_text
        if any(k in p_lower for k in ["search in files", "search text", "find in files", "grep", "search codebase"]):
            q_m = re.search(r"(?:for|query|search)\s+['\"]([^'\"]+)['\"]", prompt)
            query_val = q_m.group(1) if q_m else ""
            matches.append(
                SelectionMatch(
                    skill_id="file_search_text",
                    display_name="Safe File Text Searcher",
                    reason="Request asks to search for text patterns across project files.",
                    confidence=0.90,
                    extracted_arguments={"query": query_val or prompt, "directory_path": "."},
                )
            )

        # 18. document_extract_text
        if any(k in p_lower for k in ["extract document", "parse document", "extract text from document", "read pdf", "read docx", "read excel", "read xlsx", "read csv", "parse spreadsheet"]):
            path_m = re.search(r"(?:from|file|document|path)\s+([a-zA-Z0-9_\-./\\]+\.(?:pdf|docx|xlsx|csv|md|txt))", prompt, re.IGNORECASE)
            f_path = path_m.group(1) if path_m else ""
            missing = ["file_path"] if not f_path else []
            clarification = "Please specify the document file path to extract." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="document_extract_text",
                    display_name="Document Text Extractor",
                    reason="Request asks to extract structured content from document file.",
                    confidence=0.95,
                    extracted_arguments={"file_path": f_path} if f_path else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 19. document_qa
        if any(k in p_lower for k in ["ask document", "according to document", "question on document", "in document", "from document", "document qa"]):
            path_m = re.search(r"(?:in|from|document|file)\s+([a-zA-Z0-9_\-./\\]+\.(?:pdf|docx|xlsx|csv|md|txt))", prompt, re.IGNORECASE)
            f_path = path_m.group(1) if path_m else ""
            missing = ["file_path"] if not f_path else []
            clarification = "Please specify the document file path to query." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="document_qa",
                    display_name="Grounded Document QA",
                    reason="Request asks a grounded question against a local document file.",
                    confidence=0.95,
                    extracted_arguments={"file_path": f_path, "question": prompt} if f_path else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 20. browser_open
        if any(k in p_lower for k in ["open url", "browse to", "navigate to", "open website", "visit website", "browser open", "browse url"]):
            url_m = re.search(r"https?://[^\s]+", prompt)
            u_val = url_m.group(0) if url_m else ""
            missing = ["url"] if not u_val else []
            clarification = "Please provide the target HTTP/HTTPS URL to open." if missing else None

            matches.append(
                SelectionMatch(
                    skill_id="browser_open",
                    display_name="Browser Open URL",
                    reason="Request asks to open and navigate to a website in the browser.",
                    confidence=0.95,
                    extracted_arguments={"url": u_val} if u_val else {},
                    missing_parameters=missing,
                    clarification_prompt=clarification,
                )
            )

        # 21. browser_get_page_snapshot
        if any(k in p_lower for k in ["page snapshot", "accessibility tree", "inspect page", "page elements", "browser snapshot"]):
            matches.append(
                SelectionMatch(
                    skill_id="browser_get_page_snapshot",
                    display_name="Browser Page Accessibility Snapshot",
                    reason="Request asks to inspect current browser page and extract accessibility tree.",
                    confidence=0.90,
                    extracted_arguments={},
                )
            )

        # 22. browser_find_text
        if any(k in p_lower for k in ["find text on page", "search on page", "browser find", "look for text on page"]):
            q_m = re.search(r"(?:for|text|find)\s+['\"]([^'\"]+)['\"]", prompt)
            q_val = q_m.group(1) if q_m else ""
            missing = ["query"] if not q_val else []
            matches.append(
                SelectionMatch(
                    skill_id="browser_find_text",
                    display_name="Browser Find Text",
                    reason="Request asks to search for specific text on the active browser page.",
                    confidence=0.90,
                    extracted_arguments={"query": q_val} if q_val else {},
                    missing_parameters=missing,
                )
            )

        # 23. browser_click_element
        if any(k in p_lower for k in ["click element", "click button", "click link", "browser click"]):
            ref_m = re.search(r"(@ref_\d+)", prompt)
            ref_val = ref_m.group(1) if ref_m else None
            matches.append(
                SelectionMatch(
                    skill_id="browser_click_element",
                    display_name="Browser Click Element",
                    reason="Request asks to click an interactive element in the browser.",
                    confidence=0.90,
                    extracted_arguments={"ref_id": ref_val} if ref_val else {},
                )
            )

        # 24. browser_fill_field
        if any(k in p_lower for k in ["fill field", "type into", "enter text into", "browser fill"]):
            ref_m = re.search(r"(@ref_\d+)", prompt)
            ref_val = ref_m.group(1) if ref_m else None
            val_m = re.search(r"(?:with|value)\s+['\"]([^'\"]+)['\"]", prompt)
            val_text = val_m.group(1) if val_m else ""
            matches.append(
                SelectionMatch(
                    skill_id="browser_fill_field",
                    display_name="Browser Fill Field",
                    reason="Request asks to fill text into an input field or textarea.",
                    confidence=0.90,
                    extracted_arguments={"ref_id": ref_val, "value": val_text} if ref_val and val_text else {},
                )
            )

        # 25. browser_take_screenshot
        if any(k in p_lower for k in ["take screenshot", "capture screenshot", "browser screenshot", "screenshot page"]):
            matches.append(
                SelectionMatch(
                    skill_id="browser_take_screenshot",
                    display_name="Browser Take Screenshot",
                    reason="Request asks to capture a visual screenshot of the browser page.",
                    confidence=0.95,
                    extracted_arguments={"filename_prefix": "screenshot"},
                )
            )

        # 26. browser_list_tabs / switch / close
        if any(k in p_lower for k in ["list tabs", "show tabs", "browser tabs"]):
            matches.append(
                SelectionMatch(
                    skill_id="browser_list_tabs",
                    display_name="Browser List Open Tabs",
                    reason="Request asks to list open browser tabs.",
                    confidence=0.90,
                    extracted_arguments={},
                )
            )

        # 27. browser_back
        if any(k in p_lower for k in ["browser back", "go back in browser", "navigate back in browser"]):
            matches.append(
                SelectionMatch(
                    skill_id="browser_back",
                    display_name="Browser Navigate Back",
                    reason="Request asks to navigate back to previous browser page.",
                    confidence=0.90,
                    extracted_arguments={},
                )
            )

        return matches
