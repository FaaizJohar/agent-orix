"""
Markdown Tools: Inspection, Structural Linting, and Clean Text Conversion.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MarkdownCheckInput(BaseModel):
    content: str = Field(..., description="Markdown text content to inspect")


class MarkdownCheckOutput(BaseModel):
    valid: bool
    headers: List[Dict[str, Any]] = Field(default_factory=list)
    code_blocks_count: int = 0
    unclosed_code_blocks: bool = False
    link_count: int = 0
    broken_links: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class MarkdownToTextInput(BaseModel):
    content: str = Field(..., description="Markdown content to convert to plain text")


class MarkdownToTextOutput(BaseModel):
    text: str
    word_count: int
    char_count: int


def markdown_check(content: str) -> MarkdownCheckOutput:
    """
    Checks markdown structure, code fence termination, headers hierarchy, and link formatting.
    """
    warnings: List[str] = []
    headers: List[Dict[str, Any]] = []
    code_fences_open = False
    fence_pattern = re.compile(r"^```")
    header_pattern = re.compile(r"^(#{1,6})\s+(.*)$")
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")

    lines = content.splitlines()
    code_block_count = 0
    last_header_level = 0

    for i, line in enumerate(lines, 1):
        # Code fence check
        if fence_pattern.match(line.strip()):
            if not code_fences_open:
                code_fences_open = True
                code_block_count += 1
            else:
                code_fences_open = False
            continue

        if code_fences_open:
            continue

        # Header check
        h_match = header_pattern.match(line.strip())
        if h_match:
            level = len(h_match.group(1))
            title = h_match.group(2).strip()
            headers.append({"level": level, "title": title, "line": i})
            if last_header_level > 0 and level > last_header_level + 1:
                warnings.append(
                    f"Header hierarchy skipped at line {i}: H{last_header_level} directly followed by H{level} ('{title}')"
                )
            last_header_level = level

    if code_fences_open:
        warnings.append("Unclosed code block (```) detected at the end of document.")

    # Link check
    links = link_pattern.findall(content)
    broken_links: List[str] = []
    for text, url in links:
        if not url.strip():
            broken_links.append(f"Empty link destination for text '{text}'")

    valid = len(warnings) == 0 and len(broken_links) == 0 and not code_fences_open

    return MarkdownCheckOutput(
        valid=valid,
        headers=headers,
        code_blocks_count=code_block_count,
        unclosed_code_blocks=code_fences_open,
        link_count=len(links),
        broken_links=broken_links,
        warnings=warnings,
    )


def markdown_to_text(content: str) -> MarkdownToTextOutput:
    """
    Strips Markdown formatting syntax to generate clean, legible plaintext.
    """
    # Remove code blocks fences
    text = re.sub(r"```[a-zA-Z0-9_-]*\n([\s\S]*?)```", r"\1", content)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Replace markdown links [text](url) with "text (url)"
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    # Remove header markers (# Header)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold / italic markers
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    # Remove blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Normalize excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    words = text.split()
    return MarkdownToTextOutput(
        text=text,
        word_count=len(words),
        char_count=len(text),
    )
