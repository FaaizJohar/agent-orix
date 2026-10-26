"""
Hermes Agent Adapter (NousResearch/Hermes-Function-Calling).
Provides structured XML/JSON function-calling prompt framing,
parser for <tool_call> blocks, and dynamic skill injection.
Directly integrates upstream NousResearch Hermes validation utilities.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_HERMES_DIR = Path("E:/CavrixCode-ecosystem/upstream/hermes-function-calling")
_UPSTREAM_AVAILABLE = False
_upstream_validate_and_extract = None

if UPSTREAM_HERMES_DIR.exists():
    try:
        sys.path.insert(0, str(UPSTREAM_HERMES_DIR))
        from utils import validate_and_extract_tool_calls
        _upstream_validate_and_extract = validate_and_extract_tool_calls
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class HermesToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]


class HermesToolResponse(BaseModel):
    name: str
    content: Any


class HermesAgentAdapter:
    """
    Implements the Hermes-style function calling protocol:
    Formats tool schemas into system prompts, parses <tool_call> tags,
    and formats <tool_response> tags using upstream NousResearch utilities.
    """

    TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*({.*?})\s*</tool_call>", re.DOTALL)

    def __init__(self, tools: Optional[List[Dict[str, Any]]] = None):
        self.tools: List[Dict[str, Any]] = tools or []
        self.upstream_active = _UPSTREAM_AVAILABLE

    def register_tool(self, tool_schema: Dict[str, Any]) -> None:
        self.tools.append(tool_schema)

    def render_system_prompt_tools(self) -> str:
        """
        Renders the standard Hermes function-calling prompt instructions.
        """
        tool_json = json.dumps(self.tools, indent=2)
        return (
            "You are a helpful assistant with access to the following tools.\n"
            "To use a tool, respond with a JSON object wrapped in <tool_call></tool_call> tags:\n"
            "<tool_call>\n"
            '{"name": "<tool_name>", "arguments": {<args>}}\n'
            "</tool_call>\n\n"
            f"Tools Available:\n{tool_json}\n"
        )

    def parse_tool_calls(self, text: str) -> List[HermesToolCall]:
        """
        Extracts all <tool_call> blocks from raw model output using upstream
        NousResearch validate_and_extract_tool_calls if available.
        """
        results: List[HermesToolCall] = []

        if _upstream_validate_and_extract is not None:
            try:
                valid, tool_calls, _ = _upstream_validate_and_extract(text)
                if valid and tool_calls:
                    for tc in tool_calls:
                        if isinstance(tc, dict) and "name" in tc:
                            results.append(
                                HermesToolCall(
                                    name=str(tc["name"]),
                                    arguments=tc.get("arguments", {}),
                                )
                            )
                    return results
            except Exception:
                pass

        # Native fallback regex parser
        matches = self.TOOL_CALL_REGEX.findall(text)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict) and "name" in parsed:
                    results.append(
                        HermesToolCall(
                            name=str(parsed["name"]),
                            arguments=parsed.get("arguments", {}),
                        )
                    )
            except Exception:
                continue
        return results

    def format_tool_response(self, response: HermesToolResponse) -> str:
        """
        Formats a tool execution outcome for feeding back into the prompt.
        """
        content_str = (
            json.dumps(response.content)
            if not isinstance(response.content, str)
            else response.content
        )
        return f"<tool_response>\n{{\"name\": \"{response.name}\", \"content\": {content_str}}}\n</tool_response>"

