"""
File Integrity Verification Tool.
Calculates cryptographic checksums (SHA-256, MD5) and byte metrics in bounded memory.
"""

import hashlib
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FileIntegrityInput(BaseModel):
    file_path: str = Field(..., description="Path to file to hash and inspect")
    algorithms: List[str] = Field(default=["sha256", "md5"], description="Hash algorithms: 'sha256', 'md5', 'sha1'")


class FileIntegrityOutput(BaseModel):
    file_path: str
    exists: bool
    size_bytes: int = 0
    hashes: Dict[str, str] = Field(default_factory=dict)
    is_readable: bool = False
    error: Optional[str] = None


from cie.skills.path_guard import validate_safe_path, PathSecurityError


def file_integrity_verify(
    file_path: str,
    algorithms: Optional[List[str]] = None,
) -> FileIntegrityOutput:
    """
    Computes cryptographic hashes in 64KB stream chunks to avoid memory pressure on low-RAM hosts.
    Enforces filesystem boundary validation.
    """
    if algorithms is None:
        algorithms = ["sha256", "md5"]

    try:
        abs_path_obj = validate_safe_path(file_path, must_exist=True, must_be_file=True)
        abs_path = str(abs_path_obj)
    except PathSecurityError as pse:
        return FileIntegrityOutput(
            file_path=file_path,
            exists=False,
            error=f"Security restriction: {str(pse)}",
        )
    except Exception as e:
        return FileIntegrityOutput(
            file_path=file_path,
            exists=False,
            error=f"File '{file_path}' does not exist or is invalid: {str(e)}",
        )

    hashers = {}
    for alg in algorithms:
        alg_lower = alg.lower()
        if hasattr(hashlib, alg_lower):
            hashers[alg_lower] = getattr(hashlib, alg_lower)()

    size = 0
    try:
        size = os.path.getsize(abs_path)
        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):
                for h in hashers.values():
                    h.update(chunk)
    except PermissionError:
        return FileIntegrityOutput(
            file_path=file_path,
            exists=True,
            size_bytes=size,
            is_readable=False,
            error="Permission denied when reading file.",
        )
    except Exception as e:
        return FileIntegrityOutput(
            file_path=file_path,
            exists=True,
            size_bytes=size,
            is_readable=False,
            error=f"Failed to read file: {str(e)}",
        )

    return FileIntegrityOutput(
        file_path=abs_path,
        exists=True,
        size_bytes=size,
        hashes={name: h.hexdigest() for name, h in hashers.items()},
        is_readable=True,
        error=None,
    )
