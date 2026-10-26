"""
README Extraction Tool.
Extracts project title, sections, badges, and documentation structure from README files.
"""

import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field


class ReadmeExtractInput(BaseModel):
    file_path_or_content: str = Field(..., description="File path to README or direct markdown string")
    is_path: bool = Field(default=False, description="Whether input is a file path")


class ReadmeExtractOutput(BaseModel):
    title: Optional[str] = None
    sections: List[str] = Field(default_factory=list)
    badge_count: int = 0
    code_languages: List[str] = Field(default_factory=list)
    total_lines: int = 0
    summary: str = ""
    error: Optional[str] = None


from cie.skills.path_guard import validate_safe_path, is_sensitive_filename, PathSecurityError


def readme_extract(file_path_or_content: str, is_path: bool = False) -> ReadmeExtractOutput:
    """
    Safely parses README contents to extract high-level architectural and documentation metadata.
    Enforces path security and disallows reading sensitive files.
    """
    content = ""
    if is_path:
        try:
            path_obj = validate_safe_path(file_path_or_content, must_exist=True, must_be_file=True)
            path = str(path_obj)
        except PathSecurityError as pse:
            return ReadmeExtractOutput(error=f"Security restriction: {str(pse)}")
        except Exception as e:
            return ReadmeExtractOutput(error=f"File '{file_path_or_content}' is invalid or does not exist: {str(e)}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(250_000)  # Bound file read to 250 KB
        except Exception as e:
            return ReadmeExtractOutput(error=f"Failed to read file: {str(e)}")
    else:
        content = file_path_or_content

    lines = content.splitlines()
    title = None
    sections: List[str] = []
    badge_pattern = re.compile(r"\[!\[.*?\]\(.*?\)\]\(.*?\)|!\[.*?\]\(.*?\)")
    badge_count = len(badge_pattern.findall(content))

    code_fence_pattern = re.compile(r"^```([a-zA-Z0-9_-]+)?")
    code_languages: List[str] = []

    for line in lines:
        sline = line.strip()
        if sline.startswith("# ") and title is None:
            title = sline[2:].strip()
        elif sline.startswith("## ") or sline.startswith("### "):
            sec_name = sline.lstrip("#").strip()
            sections.append(sec_name)

        cmatch = code_fence_pattern.match(sline)
        if cmatch:
            lang = cmatch.group(1)
            if lang and lang.strip():
                code_languages.append(lang.strip().lower())

    summary_parts = []
    if title:
        summary_parts.append(f"Project: {title}")
    if sections:
        summary_parts.append(f"Sections ({len(sections)}): {', '.join(sections[:8])}")
    if code_languages:
        unique_langs = sorted(list(set(code_languages)))
        summary_parts.append(f"Languages: {', '.join(unique_langs)}")

    summary = " | ".join(summary_parts) if summary_parts else "Empty or unformatted README."

    return ReadmeExtractOutput(
        title=title,
        sections=sections,
        badge_count=badge_count,
        code_languages=sorted(list(set(code_languages))),
        total_lines=len(lines),
        summary=summary,
        error=None,
    )
