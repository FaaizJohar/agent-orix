"""
Deterministic Intent Classification and Routing Engine for CIE.
Uses rule-based precedence and regex scoring to eliminate small-model hallucination.
"""

import re
from typing import Dict, List, Tuple
from cie.schemas import IntentCategory, RouteDecision

# 1. CODE EXECUTION PATTERNS
CODE_EXEC_PATTERNS = [
    (re.compile(r"\b(run|execute|evaluate|eval)\s+(this|the|my)?\s*(?:[a-zA-Z0-9_+-]+\s+)?(code|script|program|snippet|function)\b", re.IGNORECASE), "explicit_execution_request"),
    (re.compile(r"\b(run|execute|eval)\s+.*?\b(tests?|pytest|unittest|jest|mocha)\b", re.IGNORECASE), "test_execution_request"),
    (re.compile(r"\b(execute\s+in\s+sandbox|run\s+in\s+sandbox|run\s+in\s+terminal)\b", re.IGNORECASE), "sandbox_execution_request"),
]

# 2. MULTILINGUAL PATTERNS (Hindi, Urdu, Devanagari, Romanized Hinglish)
# Devanagari Unicode Range: \u0900-\u097F
# Arabic / Perso-Arabic (Urdu) Unicode Range: \u0600-\u06FF
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]+")
ARABIC_URDU_REGEX = re.compile(r"[\u0600-\u06FF]+")

HINGLISH_KEYWORDS = [
    r"\bkya\b", r"\bhai\b", r"\bkaise\b", r"\bkarein\b", r"\bkaro\b", r"\bmujhe\b",
    r"\bbataiye\b", r"\bbatao\b", r"\byeh\b", r"\bkyu\b", r"\bkyun\b", r"\bchahiye\b",
    r"\bshukriya\b", r"\baap\b", r"\bhum\b", r"\bkarta\b", r"\bhoga\b"
]
HINGLISH_REGEX = re.compile(r"\b(" + "|".join(HINGLISH_KEYWORDS) + r")\b", re.IGNORECASE)

# 3. RESEARCH PATTERNS (Live web search, current facts, 2026 releases)
RESEARCH_PATTERNS = [
    (re.compile(r"\b(search\s+the\s+web|browse\s+the\s+internet|google\s+this|look\s+up\s+online)\b", re.IGNORECASE), "web_search_trigger"),
    (re.compile(r"\b(latest|current|recent|today'?s?|breaking)\s+(news|release|version|price|market|events?)\b", re.IGNORECASE), "temporal_recency_trigger"),
    (re.compile(r"\b(what\s+happened\s+in|who\s+won|stock\s+price\s+of)\b", re.IGNORECASE), "live_fact_query"),
    (re.compile(r"\b(2025|2026)\s+(updates?|trends?|releases?)\b", re.IGNORECASE), "contemporary_year_query"),
]

# 4. KNOWLEDGE PATTERNS (Cavrix Core corporate profile, founders, indexed docs)
KNOWLEDGE_PATTERNS = [
    (re.compile(r"\b(cavrix\s+core|about\s+cavrix|cavrixcore\.com)\b", re.IGNORECASE), "cavrix_core_mention"),
    (re.compile(r"\b(who\s+(founded|created|owns)\s+cavrix)\b", re.IGNORECASE), "cavrix_founders_query"),
    (re.compile(r"\b(faaiz\s+johar|mohd\s+fahad|fahad\s+multani)\b", re.IGNORECASE), "cavrix_founder_names"),
    (re.compile(r"\b(indexed\s+documents|local\s+knowledge\s+base|search\s+my\s+notes)\b", re.IGNORECASE), "local_knowledge_mention"),
]

# 5. SKILL AND DEVELOPER TOOL PATTERNS
SKILL_PATTERNS = [
    (re.compile(r"\b(validate|check|lint)\s+(python\s+syntax|python\s+ast|ast)\b", re.IGNORECASE), "python_ast_validate"),
    (re.compile(r"\b(validate|check)\s+json\b", re.IGNORECASE), "json_validate"),
    (re.compile(r"\b(validate|check)\s+yaml\b", re.IGNORECASE), "yaml_validate"),
    (re.compile(r"\b(lint|check)\s+markdown\b", re.IGNORECASE), "markdown_check"),
    (re.compile(r"\b(convert\s+markdown\s+to\s+text|strip\s+markdown)\b", re.IGNORECASE), "markdown_to_text"),
    (re.compile(r"\b(git\s+status|check\s+git\s+repo\s+status)\b", re.IGNORECASE), "git_status"),
    (re.compile(r"\b(git\s+diff|git\s+diff\s+summary)\b", re.IGNORECASE), "git_diff_summary"),
    (re.compile(r"\b(inspect\s+file\s+tree|show\s+file\s+tree|inspect\s+directory\s+tree)\b", re.IGNORECASE), "file_tree_inspect"),
    (re.compile(r"\b(read\s+file|read\s+text\s+from\s+file|view\s+file\s+contents?)\b", re.IGNORECASE), "file_read_text"),
    (re.compile(r"\b(search\s+(in\s+)?files?|search\s+text\s+in|grep\s+files?|find\s+in\s+codebase)\b", re.IGNORECASE), "file_search_text"),
    (re.compile(r"\b(extract\s+readme|parse\s+readme)\b", re.IGNORECASE), "readme_extract"),
    (re.compile(r"\b(inspect\s+python\s+project|analyze\s+python\s+project)\b", re.IGNORECASE), "python_project_inspect"),
    (re.compile(r"\b(inspect\s+dependencies|check\s+requirements\.txt|check\s+package\.json)\b", re.IGNORECASE), "dependency_inspect"),
    (re.compile(r"\b(discover\s+tests|find\s+test\s+cases|scan\s+for\s+tests)\b", re.IGNORECASE), "test_discover"),
    (re.compile(r"\b(parse\s+log\s+errors|extract\s+errors\s+from\s+log)\b", re.IGNORECASE), "log_parse_errors"),
    (re.compile(r"\b(verify\s+file\s+integrity|calculate\s+sha256\s+of\s+file|checksum\s+of\s+file)\b", re.IGNORECASE), "file_integrity_verify"),
    (re.compile(r"\b(check\s+http\s+endpoint|check\s+url\s+status|ping\s+http)\b", re.IGNORECASE), "http_endpoint_check"),
    (re.compile(r"\b(inspect\s+github\s+repo|query\s+github\s+repo)\b", re.IGNORECASE), "github_repo_inspect"),
    (re.compile(r"\b(extract\s+document|parse\s+document|extract\s+text\s+from\s+document|read\s+pdf|read\s+docx|read\s+xlsx|read\s+csv)\b", re.IGNORECASE), "document_extract_text"),
    (re.compile(r"\b(ask\s+document|according\s+to\s+document|question\s+on\s+document|document\s+qa)\b", re.IGNORECASE), "document_qa"),
    (re.compile(r"\b(open\s+url|browse\s+to|navigate\s+to|open\s+website|visit\s+website|browser\s+open)\b", re.IGNORECASE), "browser_open"),
    (re.compile(r"\b(browser\s+back|go\s+back\s+in\s+browser)\b", re.IGNORECASE), "browser_back"),
    (re.compile(r"\b(page\s+snapshot|accessibility\s+tree|inspect\s+page|page\s+elements|browser\s+snapshot)\b", re.IGNORECASE), "browser_get_page_snapshot"),
    (re.compile(r"\b(find\s+text\s+on\s+page|search\s+on\s+page|browser\s+find)\b", re.IGNORECASE), "browser_find_text"),
    (re.compile(r"\b(click\s+element|click\s+button|click\s+link|browser\s+click)\b", re.IGNORECASE), "browser_click_element"),
    (re.compile(r"\b(fill\s+field|type\s+into|enter\s+text\s+into|browser\s+fill)\b", re.IGNORECASE), "browser_fill_field"),
    (re.compile(r"\b(select\s+option|select\s+dropdown|browser\s+select)\b", re.IGNORECASE), "browser_select_option"),
    (re.compile(r"\b(list\s+tabs|show\s+tabs|browser\s+tabs)\b", re.IGNORECASE), "browser_list_tabs"),
    (re.compile(r"\b(switch\s+tab|focus\s+tab)\b", re.IGNORECASE), "browser_switch_tab"),
    (re.compile(r"\b(close\s+tab)\b", re.IGNORECASE), "browser_close_tab"),
    (re.compile(r"\b(take\s+screenshot|capture\s+screenshot|browser\s+screenshot)\b", re.IGNORECASE), "browser_take_screenshot"),
    (re.compile(r"\b(wait\s+for\s+text|wait\s+for\s+element)\b", re.IGNORECASE), "browser_wait_for_text"),
    # Phase 15 & 16 Real Upstream Integrations
    (re.compile(r"\b(markitdown|convert\s+(?:file|document|html)\s+to\s+markdown|parse\s+markdown\s+stream)\b", re.IGNORECASE), "markitdown_convert"),
    (re.compile(r"\b(crawl4ai|crawl\s+webpage|extract\s+from\s+url|extract\s+structured\s+web\s+content)\b", re.IGNORECASE), "crawl4ai_extract"),
    (re.compile(r"\b(swerex|swerex_execute|execute\s+in\s+isolated\s+workspace|run\s+in\s+swe-rex)\b", re.IGNORECASE), "swerex_execute"),
    (re.compile(r"\b(dspy|compile\s+signature|dspy\s+prompt|compile\s+prompt\s+signature)\b", re.IGNORECASE), "dspy_compile_signature"),
    (re.compile(r"\b(inspect_ai|inspect\s+ai|evaluate\s+benchmark|run\s+inspect\s+eval)\b", re.IGNORECASE), "inspect_ai_eval"),
    # Phase 17 Upstream Integrations
    (re.compile(r"\b(hermes|hermes_format|format\s+tool\s+call|parse\s+hermes\s+tool\s+call)\b", re.IGNORECASE), "hermes_format_tool_call"),
    (re.compile(r"\b(lightrag|lightrag_query|query\s+knowledge\s+graph|dual\s+level\s+graph\s+retrieval)\b", re.IGNORECASE), "lightrag_query_graph"),
]

# 6. DIRECT CODING PATTERNS
DIRECT_CODING_PATTERNS = [
    (re.compile(r"\b(write|create|implement|build|generate)\s+.*?\b(python|javascript|js|ts|typescript|c\+\+|rust|function|class|algorithm|script|code)\b", re.IGNORECASE), "code_generation_intent"),
    (re.compile(r"\b(quicksort|mergesort|binary\s+search|linked\s+list|lru\s+cache|dynamic\s+programming|dijkstra|two\s+pointer|palindrome)\b", re.IGNORECASE), "known_algorithm_data_structure"),
    (re.compile(r"\b(debug|fix|troubleshoot|solve|refactor)\s+.*?\b(bug|error|issue|exception|code|traceback)\b", re.IGNORECASE), "code_debugging_intent"),
    (re.compile(r"\b(explain|break\s+down|walk\s+through)\s+.*?\b(code|algorithm|function|logic)\b", re.IGNORECASE), "code_explanation_intent"),
    (re.compile(r"\b(def\s+[a-zA-Z_]|function\s+[a-zA-Z_]|class\s+[a-zA-Z_]|const\s+[a-zA-Z_]|let\s+[a-zA-Z_])\b", re.IGNORECASE), "code_syntax_snippet"),
    (re.compile(r"```(python|javascript|js|ts|typescript|json|html|css)?", re.IGNORECASE), "markdown_code_block"),
]


class DeterministicRouter:
    """
    Evaluates prompts against layered regex rules to produce a confident,
    explainable routing decision.
    """

    def route(self, prompt: str) -> RouteDecision:
        stripped = prompt.strip()
        matched: List[str] = []

        # Rule 1: Code Execution Precedence
        for pattern, label in CODE_EXEC_PATTERNS:
            if pattern.search(stripped):
                matched.append(label)
        if matched:
            return RouteDecision(
                category=IntentCategory.CODE_EXECUTION,
                confidence=0.95,
                reason="Explicit instruction requesting code or test execution.",
                matched_patterns=matched,
                fallback_applied=False,
            )

        # Rule 2: Multilingual Precedence
        if DEVANAGARI_REGEX.search(stripped):
            return RouteDecision(
                category=IntentCategory.MULTILINGUAL,
                confidence=0.99,
                reason="Devanagari script detected in prompt.",
                matched_patterns=["devanagari_script_detected"],
                fallback_applied=False,
            )
        if ARABIC_URDU_REGEX.search(stripped):
            return RouteDecision(
                category=IntentCategory.MULTILINGUAL,
                confidence=0.99,
                reason="Arabic / Perso-Arabic (Urdu) script detected in prompt.",
                matched_patterns=["arabic_urdu_script_detected"],
                fallback_applied=False,
            )
        hinglish_matches = HINGLISH_REGEX.findall(stripped)
        if len(hinglish_matches) >= 2:
            return RouteDecision(
                category=IntentCategory.MULTILINGUAL,
                confidence=0.90,
                reason=f"Multiple Romanized Hindi/Hinglish vocabulary tokens identified: {set(hinglish_matches)}.",
                matched_patterns=[f"hinglish_tokens:{len(hinglish_matches)}"],
                fallback_applied=False,
            )

        # Rule 3: Live Research Precedence
        for pattern, label in RESEARCH_PATTERNS:
            if pattern.search(stripped):
                matched.append(label)
        if matched:
            return RouteDecision(
                category=IntentCategory.RESEARCH,
                confidence=0.90,
                reason="Request requires live web search or contemporary time-sensitive data.",
                matched_patterns=matched,
                fallback_applied=False,
            )

        # Rule 4: Cavrix Knowledge / Local Docs Precedence
        for pattern, label in KNOWLEDGE_PATTERNS:
            if pattern.search(stripped):
                matched.append(label)
        if matched:
            return RouteDecision(
                category=IntentCategory.KNOWLEDGE,
                confidence=0.92,
                reason="Request references Cavrix Core corporate identity or indexed local documentation.",
                matched_patterns=matched,
                fallback_applied=False,
            )

        # Rule 5: Skill and Developer Tools Precedence
        for pattern, label in SKILL_PATTERNS:
            if pattern.search(stripped):
                matched.append(label)
        if matched:
            return RouteDecision(
                category=IntentCategory.SKILL,
                confidence=0.95,
                reason="Request matches registered developer skill / inspection tool.",
                matched_patterns=matched,
                fallback_applied=False,
            )

        # Rule 6: Direct Coding & Technical Implementation
        for pattern, label in DIRECT_CODING_PATTERNS:
            if pattern.search(stripped):
                matched.append(label)
        if matched:
            return RouteDecision(
                category=IntentCategory.DIRECT,
                confidence=0.95,
                reason="Direct software engineering, code generation, debugging, or explanation task.",
                matched_patterns=matched,
                fallback_applied=False,
            )

        # Rule 6: General Fallback for conversational or ambiguous queries
        return RouteDecision(
            category=IntentCategory.GENERAL,
            confidence=0.60,
            reason="Ambiguous or general conversational query. Routed to standard model path with safety boundaries.",
            matched_patterns=["general_unmatched_fallback"],
            fallback_applied=True,
        )
