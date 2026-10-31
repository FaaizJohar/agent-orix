"""
Centralized Path Traversal and Sensitive File Protection Guard for CIE.
Enforces filesystem boundaries, symlink safety, and blocks access to credentials, private keys, and environment files.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Set, Tuple

# Sensitive filename patterns and extensions that must never be exposed or read
SENSITIVE_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),                         # .env, .env.local, .env.production, etc.
    re.compile(r".*\.env$", re.IGNORECASE),                               # any file ending in .env
    re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)(\..*)?$", re.IGNORECASE),    # SSH private keys
    re.compile(r".*\.(pem|key|pkcs12|pfx|p12|crt)$", re.IGNORECASE),     # Certificates / keys
    re.compile(r".*(credential|client_secret|service_account|secret|password|passwd|shadow).*", re.IGNORECASE),
    re.compile(r"^(\.git|\.hg|\.svn)(\/|\\|$)", re.IGNORECASE),          # VCS internal folders
]

# System directories that are strictly forbidden from inspection
FORBIDDEN_SYSTEM_PATHS = [
    re.compile(r"^[a-zA-Z]:\\windows", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\program files", re.IGNORECASE),
    re.compile(r"^/etc", re.IGNORECASE),
    re.compile(r"^/var", re.IGNORECASE),
    re.compile(r"^/sys", re.IGNORECASE),
    re.compile(r"^/proc", re.IGNORECASE),
]


class PathSecurityError(Exception):
    pass


def is_sensitive_filename(name: str) -> bool:
    """Check if a single filename or directory name matches sensitive patterns."""
    basename = os.path.basename(name).strip()
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(basename):
            return True
    return False


def is_sensitive_path(path_str: str) -> Tuple[bool, str]:
    """
    Checks if a full or relative path touches or targets sensitive files or directories.
    Returns: (is_sensitive, reason)
    """
    if not path_str:
        return False, ""

    # Check for null bytes
    if "\x00" in path_str:
        return True, "Null bytes are strictly forbidden in file paths."

    norm_path = os.path.normpath(path_str)

    # Check for system paths
    for sys_pat in FORBIDDEN_SYSTEM_PATHS:
        if sys_pat.search(norm_path):
            return True, f"Access to system path '{norm_path}' is strictly prohibited."

    # Split into path components and check each
    parts = Path(norm_path).parts
    for part in parts:
        if is_sensitive_filename(part):
            return True, f"Path component '{part}' matches sensitive or protected credential pattern."

    return False, ""


def get_default_allowed_roots() -> List[Path]:
    """Returns canonical permitted filesystem roots for CIE operations."""
    roots = [
        Path(r"E:\agent-orix").resolve() if Path(r"E:\agent-orix").exists() else None,
        Path(r"E:\cavrix_cie").resolve() if Path(r"E:\cavrix_cie").exists() else None,
        Path(r"E:\cavrix_code").resolve() if Path(r"E:\cavrix_code").exists() else None,
        Path(r"E:\nox ai").resolve() if Path(r"E:\nox ai").exists() else None,
        Path(r"E:\CavrixCode-latest").resolve() if Path(r"E:\CavrixCode-latest").exists() else None,
        Path(os.getcwd()).resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    return [r for r in roots if r is not None and r.exists()]


def validate_safe_path(
    path_str: str,
    allowed_roots: Optional[List[Path]] = None,
    must_exist: bool = True,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Path:
    """
    Canonicalizes path, resolves symlinks, checks boundary confinement and sensitive patterns.
    """
    if not path_str:
        raise PathSecurityError("Path cannot be empty.")

    if "\x00" in path_str:
        raise PathSecurityError("Null bytes in path are strictly forbidden.")

    # Check if raw path contains sensitive patterns
    sensitive, reason = is_sensitive_path(path_str)
    if sensitive:
        raise PathSecurityError(f"Security restriction: {reason}")

    # Resolve canonical absolute path including symlinks
    raw_path = Path(path_str)
    try:
        resolved = raw_path.resolve(strict=must_exist)
    except FileNotFoundError:
        if must_exist:
            raise FileNotFoundError(f"Path does not exist: {path_str}")
        resolved = raw_path.resolve(strict=False)

    # Re-check resolved path for sensitive targets (e.g. symlink pointing to .env)
    sensitive, reason = is_sensitive_path(str(resolved))
    if sensitive:
        raise PathSecurityError(f"Security restriction: Resolved target '{resolved.name}' is sensitive: {reason}")

    # Verify type
    if must_exist:
        if must_be_file and not resolved.is_file():
            raise PathSecurityError(f"Expected a regular file, but found directory or special file: {resolved}")
        if must_be_dir and not resolved.is_dir():
            raise PathSecurityError(f"Expected a directory, but found: {resolved}")

    # Enforce allowed root boundary confinement
    roots = allowed_roots or get_default_allowed_roots()
    in_bounds = False
    for root in roots:
        try:
            resolved.relative_to(root)
            in_bounds = True
            break
        except ValueError:
            # Check drive letter equivalence on Windows
            if os.name == "nt" and resolved.drive and root.drive:
                if resolved.drive.upper() == root.drive.upper():
                    try:
                        resolved.relative_to(root)
                        in_bounds = True
                        break
                    except ValueError:
                        pass

    if not in_bounds:
        raise PathSecurityError(
            f"Path traversal blocked: '{path_str}' resolves outside permitted roots: {resolved}"
        )

    return resolved
