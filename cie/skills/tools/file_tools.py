"""
File Tree Inspection Tool.
Safely inspects directory hierarchy with depth, count boundaries, and automated privacy exclusion.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cie.skills.path_guard import is_sensitive_filename, validate_safe_path, PathSecurityError

DEFAULT_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".env",
    ".env.local",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
}


class FileTreeInspectInput(BaseModel):
    directory_path: str = Field(default=".", description="Path to root directory to inspect")
    max_depth: int = Field(default=3, description="Maximum directory traversal depth (1-5)")
    max_files: int = Field(default=200, description="Maximum number of files/folders to return")


class FileTreeInspectOutput(BaseModel):
    root: str
    total_directories: int
    total_files: int
    tree: Dict[str, Any]
    truncated: bool = False
    error: Optional[str] = None


def file_tree_inspect(
    directory_path: str = ".",
    max_depth: int = 3,
    max_files: int = 200,
) -> FileTreeInspectOutput:
    """
    Produces a safe, bounded JSON tree representation of a directory.
    Excludes sensitive files like .env and heavy caches like .git / node_modules.
    Enforces path boundaries and blocks access to system or sensitive folders.
    """
    try:
        abs_root_path = validate_safe_path(directory_path, must_exist=True, must_be_dir=True)
        abs_root = str(abs_root_path)
    except PathSecurityError as pse:
        return FileTreeInspectOutput(
            root=directory_path,
            total_directories=0,
            total_files=0,
            tree={},
            error=f"Security restriction: {str(pse)}",
        )
    except Exception as e:
        return FileTreeInspectOutput(
            root=directory_path,
            total_directories=0,
            total_files=0,
            tree={},
            error=f"Directory '{directory_path}' does not exist or is not a directory: {str(e)}",
        )

    bounded_depth = max(1, min(max_depth, 5))
    bounded_max_files = max(10, min(max_files, 500))

    dir_count = 0
    file_count = 0
    total_visited = 0
    truncated = False

    def build_tree(current_dir: str, current_depth: int) -> Dict[str, Any]:
        nonlocal dir_count, file_count, total_visited, truncated

        node: Dict[str, Any] = {
            "name": os.path.basename(current_dir) or current_dir,
            "type": "directory",
            "children": [],
        }

        if current_depth > bounded_depth or total_visited >= bounded_max_files:
            if total_visited >= bounded_max_files:
                truncated = True
            return node

        try:
            entries = sorted(os.scandir(current_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            node["error"] = "Access denied"
            return node

        for entry in entries:
            if entry.name in DEFAULT_EXCLUDES or is_sensitive_filename(entry.name):
                continue

            if total_visited >= bounded_max_files:
                truncated = True
                break

            total_visited += 1

            try:
                if entry.is_dir(follow_symlinks=False):
                    dir_count += 1
                    child_node = build_tree(entry.path, current_depth + 1)
                    node["children"].append(child_node)
                else:
                    file_count += 1
                    size = 0
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        pass
                    node["children"].append({
                        "name": entry.name,
                        "type": "file",
                        "size": size,
                    })
            except OSError:
                continue

        return node

    tree = build_tree(abs_root, 1)

    return FileTreeInspectOutput(
        root=abs_root,
        total_directories=dir_count,
        total_files=file_count,
        tree=tree,
        truncated=truncated,
        error=None,
    )


class FileReadTextInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to read (must be within allowed project roots)")
    start_line: int = Field(default=1, ge=1, description="Line number to start reading from (1-based)")
    max_lines: int = Field(default=200, ge=1, le=500, description="Maximum number of lines to return (1-500)")


class FileReadTextOutput(BaseModel):
    file_path: str
    total_lines: int
    start_line: int
    lines_returned: int
    content: str
    truncated: bool = False
    error: Optional[str] = None


def file_read_text(
    file_path: str,
    start_line: int = 1,
    max_lines: int = 200,
) -> FileReadTextOutput:
    """
    Safely reads text content from a local file within permitted project roots.
    Enforces path traversal protection, sensitive pattern exclusions, and 2MB max file size.
    """
    try:
        abs_path = validate_safe_path(file_path, must_exist=True, must_be_file=True)
    except (PathSecurityError, FileNotFoundError) as pse:
        return FileReadTextOutput(
            file_path=file_path,
            total_lines=0,
            start_line=start_line,
            lines_returned=0,
            content="",
            error=f"Security/Path error: {str(pse)}",
        )
    except Exception as e:
        return FileReadTextOutput(
            file_path=file_path,
            total_lines=0,
            start_line=start_line,
            lines_returned=0,
            content="",
            error=f"Error accessing file: {str(e)}",
        )

    MAX_FILE_BYTES = 2 * 1024 * 1024
    try:
        st_size = abs_path.stat().st_size
        if st_size > MAX_FILE_BYTES:
            return FileReadTextOutput(
                file_path=str(abs_path),
                total_lines=0,
                start_line=start_line,
                lines_returned=0,
                content="",
                truncated=True,
                error=f"File exceeds maximum allowed size of 2MB (actual: {st_size} bytes)",
            )
    except OSError as e:
        return FileReadTextOutput(
            file_path=str(abs_path),
            total_lines=0,
            start_line=start_line,
            lines_returned=0,
            content="",
            error=f"Cannot stat file: {str(e)}",
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return FileReadTextOutput(
            file_path=str(abs_path),
            total_lines=0,
            start_line=start_line,
            lines_returned=0,
            content="",
            error=f"Failed to read file: {str(e)}",
        )

    total_lines = len(all_lines)
    bounded_max_lines = max(1, min(max_lines, 500))
    start_idx = max(0, start_line - 1)
    end_idx = min(start_idx + bounded_max_lines, total_lines)

    selected_lines = all_lines[start_idx:end_idx]
    truncated = end_idx < total_lines or start_idx > 0

    return FileReadTextOutput(
        file_path=str(abs_path),
        total_lines=total_lines,
        start_line=start_line,
        lines_returned=len(selected_lines),
        content="".join(selected_lines),
        truncated=truncated,
        error=None,
    )


class FileSearchTextInput(BaseModel):
    directory_path: str = Field(default=".", description="Root directory to search within")
    query: str = Field(..., description="Text query to search for (case-insensitive)")
    file_extension: Optional[str] = Field(default=None, description="Optional extension filter, e.g. '.py', '.js'")
    max_results: int = Field(default=30, ge=1, le=50, description="Maximum number of matching lines to return (1-50)")


class FileSearchMatch(BaseModel):
    file: str
    line_number: int
    line_text: str


class FileSearchTextOutput(BaseModel):
    directory_path: str
    query: str
    matches_count: int
    matches: List[FileSearchMatch]
    truncated: bool = False
    error: Optional[str] = None


def file_search_text(
    query: str,
    directory_path: str = ".",
    file_extension: Optional[str] = None,
    max_results: int = 30,
) -> FileSearchTextOutput:
    """
    Safely searches for text across files within permitted project roots.
    Skips sensitive directories/files, ignores symlinks, and respects bounded results.
    """
    if not query or not query.strip():
        return FileSearchTextOutput(
            directory_path=directory_path,
            query=query,
            matches_count=0,
            matches=[],
            error="Search query cannot be empty",
        )

    try:
        abs_root_path = validate_safe_path(directory_path, must_exist=True, must_be_dir=True)
        abs_root = str(abs_root_path)
    except Exception as e:
        return FileSearchTextOutput(
            directory_path=directory_path,
            query=query,
            matches_count=0,
            matches=[],
            error=f"Security/Path error: {str(e)}",
        )

    bounded_max = max(1, min(max_results, 50))
    matches: List[FileSearchMatch] = []
    truncated = False
    lower_query = query.lower()

    ext_filter = file_extension.strip().lower() if file_extension else None
    if ext_filter and not ext_filter.startswith("."):
        ext_filter = "." + ext_filter

    MAX_FILE_BYTES = 2 * 1024 * 1024

    for root_dir, dirs, files in os.walk(abs_root):
        # Filter directories in-place to avoid descending into ignored or sensitive paths
        dirs[:] = [
            d for d in dirs
            if d not in DEFAULT_EXCLUDES and not is_sensitive_filename(d)
        ]

        for fname in sorted(files):
            if is_sensitive_filename(fname) or fname in DEFAULT_EXCLUDES:
                continue

            if ext_filter and not fname.lower().endswith(ext_filter):
                continue

            full_fpath = os.path.join(root_dir, fname)
            try:
                if os.path.islink(full_fpath):
                    continue
                if os.path.getsize(full_fpath) > MAX_FILE_BYTES:
                    continue

                rel_path = os.path.relpath(full_fpath, abs_root)

                with open(full_fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line_no, line in enumerate(f, start=1):
                        if lower_query in line.lower():
                            matches.append(
                                FileSearchMatch(
                                    file=rel_path,
                                    line_number=line_no,
                                    line_text=line.strip()[:300],
                                )
                            )
                            if len(matches) >= bounded_max:
                                truncated = True
                                break
            except (OSError, PermissionError):
                continue

            if truncated:
                break
        if truncated:
            break

    return FileSearchTextOutput(
        directory_path=abs_root,
        query=query,
        matches_count=len(matches),
        matches=matches,
        truncated=truncated,
        error=None,
    )
