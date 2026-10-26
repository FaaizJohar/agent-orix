"""
MarkItDown Document to Markdown Converter Adapter (microsoft/markitdown).
Converts PDF, DOCX, XLSX, HTML, and CSV files into clean, readable Markdown.
"""

from pathlib import Path
import sys
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

# Directly leverage upstream markitdown from E:\CavrixCode-ecosystem\upstream\markitdown\packages\markitdown\src
MARKITDOWN_SRC = Path(r"E:\CavrixCode-ecosystem\upstream\markitdown\packages\markitdown\src")

_GLOBAL_MARKITDOWN_INSTANCE = None
_UPSTREAM_AVAILABLE = None

def _is_upstream_available() -> bool:
    global _UPSTREAM_AVAILABLE
    if _UPSTREAM_AVAILABLE is None:
        _UPSTREAM_AVAILABLE = MARKITDOWN_SRC.exists()
    return _UPSTREAM_AVAILABLE

def _get_markitdown_instance():
    global _GLOBAL_MARKITDOWN_INSTANCE
    if _GLOBAL_MARKITDOWN_INSTANCE is None and _is_upstream_available():
        try:
            if str(MARKITDOWN_SRC) not in sys.path:
                sys.path.insert(0, str(MARKITDOWN_SRC))
            from markitdown import MarkItDown
            _GLOBAL_MARKITDOWN_INSTANCE = MarkItDown()
        except Exception:
            _GLOBAL_MARKITDOWN_INSTANCE = None
    return _GLOBAL_MARKITDOWN_INSTANCE


class MarkItDownResult(BaseModel):
    markdown: str
    source_file: str
    file_type: str
    success: bool = True
    error: Optional[str] = None


class MarkItDownAdapter:
    """
    Adapter interfacing Microsoft's MarkItDown library for CavrixCode.
    Directly invokes upstream MarkItDown.convert_stream and MarkItDown.convert.
    """

    def __init__(self):
        self._md = None
        self.upstream_active = _is_upstream_available()

    def _ensure_md(self):
        if self._md is None:
            self._md = _get_markitdown_instance()
        return self._md

    def convert_text_or_html(self, content: str, extension: str = ".html") -> MarkItDownResult:
        """
        Converts text/HTML content to Markdown using upstream MarkItDown.convert_stream.
        """
        md_inst = self._ensure_md()
        if md_inst is not None:
            try:
                import io
                stream = io.BytesIO(content.encode("utf-8"))
                res = md_inst.convert_stream(stream, file_extension=extension)
                return MarkItDownResult(
                    markdown=res.text_content,
                    source_file="inline_stream",
                    file_type=extension,
                    success=True,
                )
            except Exception as e:
                pass

        # Native fallback if upstream is unavailable
        import re
        clean = re.sub(r"<[^>]+>", " ", content)
        md_text = "\n".join(l.strip() for l in clean.splitlines() if l.strip())
        return MarkItDownResult(
            markdown=md_text,
            source_file="inline_content",
            file_type=extension,
            success=True,
        )

    def convert_file(self, file_path: str) -> MarkItDownResult:
        """
        Converts a document on disk (PDF, DOCX, XLSX, HTML, etc.) to Markdown.
        """
        path = Path(file_path)
        if not path.exists():
            return MarkItDownResult(
                markdown="",
                source_file=file_path,
                file_type=path.suffix,
                success=False,
                error=f"File not found: {file_path}",
            )

        # Fast-path for direct markdown, text, code, and config files (instant)
        if path.suffix.lower() in (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".rst"):
            try:
                return MarkItDownResult(
                    markdown=path.read_text(encoding="utf-8", errors="ignore"),
                    source_file=str(path),
                    file_type=path.suffix,
                    success=True,
                )
            except Exception:
                pass

        md_inst = self._ensure_md()
        if md_inst is not None:
            try:
                res = md_inst.convert(str(path))
                return MarkItDownResult(
                    markdown=res.text_content,
                    source_file=str(path),
                    file_type=path.suffix,
                    success=True,
                )
            except Exception as e:
                return MarkItDownResult(
                    markdown="",
                    source_file=str(path),
                    file_type=path.suffix,
                    success=False,
                    error=f"Upstream MarkItDown error: {e}",
                )

        return MarkItDownResult(
            markdown=path.read_text(encoding="utf-8", errors="ignore"),
            source_file=str(path),
            file_type=path.suffix,
            success=True,
        )
