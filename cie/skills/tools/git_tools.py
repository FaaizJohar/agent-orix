"""
Safe, read-only Git developer tools.
Executes git status and git diff inspection with shell=False and strict argument validation.
"""

import os
import shutil
import subprocess
from typing import List, Optional
from pydantic import BaseModel, Field


from cie.skills.path_guard import validate_safe_path, is_sensitive_filename, PathSecurityError


class GitStatusInput(BaseModel):
    repo_path: str = Field(default=".", description="Path to git repository directory")


class GitStatusOutput(BaseModel):
    is_git_repo: bool
    branch: Optional[str] = None
    clean: bool = True
    staged_count: int = 0
    unstaged_count: int = 0
    untracked_count: int = 0
    summary: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class GitDiffSummaryInput(BaseModel):
    repo_path: str = Field(default=".", description="Path to git repository directory")
    cached: bool = Field(default=False, description="Whether to inspect staged/cached diff")


class GitDiffSummaryOutput(BaseModel):
    is_git_repo: bool
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    stat_lines: List[str] = Field(default_factory=list)
    error: Optional[str] = None


def git_status(repo_path: str = ".") -> GitStatusOutput:
    """
    Safely inspect git repository status without performing any mutations.
    Enforces path boundaries and argument injection safeguards.
    """
    if repo_path.strip().startswith("-"):
        return GitStatusOutput(is_git_repo=False, clean=False, error="Argument injection rejected: Path cannot start with a hyphen.")

    if not shutil.which("git"):
        return GitStatusOutput(is_git_repo=False, clean=False, error="Git executable not found in PATH.")

    try:
        abs_path_obj = validate_safe_path(repo_path, must_exist=True, must_be_dir=True)
        abs_path = str(abs_path_obj)
    except PathSecurityError as pse:
        return GitStatusOutput(is_git_repo=False, clean=False, error=f"Security restriction: {str(pse)}")
    except Exception as e:
        return GitStatusOutput(is_git_repo=False, clean=False, error=f"Directory '{repo_path}' is invalid: {str(e)}")

    cmd = ["git", "-C", abs_path, "status", "--porcelain", "-b"]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=10,
        )
    except Exception as e:
        return GitStatusOutput(is_git_repo=False, clean=False, error=f"Git command failed: {str(e)}")

    if proc.returncode != 0:
        return GitStatusOutput(
            is_git_repo=False,
            clean=False,
            error=proc.stderr.strip() or "Not a git repository.",
        )

    lines = proc.stdout.splitlines()
    branch = None
    staged = 0
    unstaged = 0
    untracked = 0
    summary = []

    for line in lines:
        if line.startswith("##"):
            branch = line[3:].split("...")[0].strip()
            continue
        path_part = line[3:].strip() if len(line) > 3 else line
        if is_sensitive_filename(path_part):
            continue
        summary.append(line)
        if len(line) >= 2:
            x, y = line[0], line[1]
            if x in "MADRC":
                staged += 1
            if y in "MADRC":
                unstaged += 1
            if x == "?" and y == "?":
                untracked += 1

    clean = (len(summary) == 0)

    return GitStatusOutput(
        is_git_repo=True,
        branch=branch,
        clean=clean,
        staged_count=staged,
        unstaged_count=unstaged,
        untracked_count=untracked,
        summary=summary[:50],  # Bounded to 50 entries
        error=None,
    )


def git_diff_summary(repo_path: str = ".", cached: bool = False) -> GitDiffSummaryOutput:
    """
    Safely inspect git diff summary (--stat) without performing any mutations.
    Enforces path boundaries and argument injection safeguards.
    """
    if repo_path.strip().startswith("-"):
        return GitDiffSummaryOutput(is_git_repo=False, error="Argument injection rejected: Path cannot start with a hyphen.")

    if not shutil.which("git"):
        return GitDiffSummaryOutput(is_git_repo=False, error="Git executable not found in PATH.")

    try:
        abs_path_obj = validate_safe_path(repo_path, must_exist=True, must_be_dir=True)
        abs_path = str(abs_path_obj)
    except PathSecurityError as pse:
        return GitDiffSummaryOutput(is_git_repo=False, error=f"Security restriction: {str(pse)}")
    except Exception as e:
        return GitDiffSummaryOutput(is_git_repo=False, error=f"Directory '{repo_path}' is invalid: {str(e)}")

    cmd = ["git", "-C", abs_path, "diff", "--stat"]
    if cached:
        cmd.append("--cached")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=10,
        )
    except Exception as e:
        return GitDiffSummaryOutput(is_git_repo=False, error=f"Git diff command failed: {str(e)}")

    if proc.returncode != 0:
        return GitDiffSummaryOutput(
            is_git_repo=False,
            error=proc.stderr.strip() or "Failed to run git diff.",
        )

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    files_changed = 0
    insertions = 0
    deletions = 0

    if lines:
        summary_line = lines[-1]
        import re
        m_files = re.search(r"(\d+)\s+file", summary_line)
        m_ins = re.search(r"(\d+)\s+insertion", summary_line)
        m_del = re.search(r"(\d+)\s+deletion", summary_line)

        if m_files:
            files_changed = int(m_files.group(1))
        if m_ins:
            insertions = int(m_ins.group(1))
        if m_del:
            deletions = int(m_del.group(1))

    return GitDiffSummaryOutput(
        is_git_repo=True,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        stat_lines=lines[:30],
        error=None,
    )
