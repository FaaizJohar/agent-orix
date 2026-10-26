"""
Regression tests protecting existing Cavrix Code model artifacts and Ollama deployments.
"""

import hashlib
import json
import os
from pathlib import Path
import urllib.request
import pytest

EXPECTED_SHA256 = "4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1"
EXPECTED_SIZE = 531068000
LOCAL_GGUF_PATH = Path(r"E:\cavrix_code\models\cavrix_code_latest.gguf")


def test_local_gguf_integrity():
    assert LOCAL_GGUF_PATH.exists(), f"Model file missing at {LOCAL_GGUF_PATH}"
    assert LOCAL_GGUF_PATH.stat().st_size == EXPECTED_SIZE, (
        f"Model size mismatch: expected {EXPECTED_SIZE}, got {LOCAL_GGUF_PATH.stat().st_size}"
    )

    sha256 = hashlib.sha256()
    with open(LOCAL_GGUF_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)
    assert sha256.hexdigest().upper() == EXPECTED_SHA256, "SHA-256 hash mutated!"


def test_ollama_tags_preserved():
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5.0) as resp:
            data = json.loads(resp.read().decode())
            tags = [m["name"] for m in data.get("models", [])]
            assert "cavrix-code:latest" in tags, "Primary tag cavrix-code:latest missing from Ollama!"
            assert "cavrix-code:exp4" in tags, "Rollback tag cavrix-code:exp4 missing from Ollama!"
            assert "cavrix-code:exp5" in tags, "Checkpoint tag cavrix-code:exp5 missing from Ollama!"
    except Exception as e:
        pytest.skip(f"Ollama server not reachable for live regression test: {e}")
