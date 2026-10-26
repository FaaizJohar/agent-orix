"""
Unit and integration tests for all 15 CIE developer tools.
"""

import os
import tempfile
import pytest

from cie.skills.tools.python_ast import python_ast_validate
from cie.skills.tools.json_validator import json_validate
from cie.skills.tools.yaml_validator import yaml_validate
from cie.skills.tools.markdown_tools import markdown_check, markdown_to_text
from cie.skills.tools.git_tools import git_status, git_diff_summary
from cie.skills.tools.file_tools import file_tree_inspect
from cie.skills.tools.readme_tools import readme_extract
from cie.skills.tools.project_inspect import python_project_inspect
from cie.skills.tools.dependency_inspect import dependency_inspect
from cie.skills.tools.test_discover import test_discover as run_test_discover
from cie.skills.tools.log_tools import log_parse_errors
from cie.skills.tools.file_integrity import file_integrity_verify
from cie.skills.tools.http_tools import http_endpoint_check
from cie.skills.tools.github_tools import github_repo_inspect


def test_python_ast_validate():
    valid_code = """
import os
from sys import path

class Engine:
    def start(self):
        pass

def calculate(x, y):
    return x + y
"""
    res = python_ast_validate(valid_code)
    assert res.valid is True
    assert "Engine" in res.classes
    assert "start" in res.functions
    assert "calculate" in res.functions
    assert "os" in res.imports

    invalid_code = "def syntax_broken(: pass"
    res_err = python_ast_validate(invalid_code)
    assert res_err.valid is False
    assert res_err.error_line is not None


def test_json_validate():
    valid_json = '{"project": "Cavrix", "active": true, "version": 1.0}'
    res = json_validate(valid_json)
    assert res.valid is True
    assert res.data_type == "object"
    assert res.key_count == 3

    invalid_json = '{"unclosed": "brace"'
    res_err = json_validate(invalid_json)
    assert res_err.valid is False
    assert "JSONDecodeError" in res_err.error


def test_yaml_validate():
    valid_yaml = """
services:
  app:
    image: python:3.11
    ports:
      - "8000:8000"
"""
    res = yaml_validate(valid_yaml)
    assert res.valid is True
    assert res.data_type == "dict"
    assert res.key_count == 1

    invalid_yaml = "services:\n  - unaligned:\n key: value\n   bad indentation"
    res_err = yaml_validate(invalid_yaml)
    assert res_err.valid is False


def test_markdown_check_and_to_text():
    md = """# Title
## Section 1
Here is a [link](https://example.com).

```python
def foo():
    pass
```
"""
    check_res = markdown_check(md)
    assert check_res.valid is True
    assert len(check_res.headers) == 2
    assert check_res.code_blocks_count == 1
    assert check_res.link_count == 1

    unclosed_md = "```python\ndef open_fence(): pass"
    unclosed_res = markdown_check(unclosed_md)
    assert unclosed_res.valid is False
    assert unclosed_res.unclosed_code_blocks is True

    text_res = markdown_to_text(md)
    assert "# Title" not in text_res.text
    assert "link (https://example.com)" in text_res.text
    assert text_res.word_count > 0


def test_git_tools():
    # Run against current project dir
    status_res = git_status(".")
    assert isinstance(status_res.is_git_repo, bool)

    diff_res = git_diff_summary(".")
    assert isinstance(diff_res.is_git_repo, bool)


def test_file_tree_inspect():
    res = file_tree_inspect(".", max_depth=2, max_files=50)
    assert res.error is None
    assert res.total_directories > 0
    assert res.total_files > 0
    assert res.tree["type"] == "directory"


def test_readme_extract():
    content = """# Cavrix Project
[![CI](https://github.com/ci.svg)](https://github.com)

## Installation
Run `pip install .`

## Usage
```python
import cie
```
"""
    res = readme_extract(content, is_path=False)
    assert res.title == "Cavrix Project"
    assert "Installation" in res.sections
    assert "Usage" in res.sections
    assert res.badge_count == 1
    assert "python" in res.code_languages


def test_python_project_inspect():
    res = python_project_inspect(".")
    assert res.is_python_project is True
    assert res.python_files_count > 0
    assert res.has_tests is True


def test_dependency_inspect():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix="requirements.txt") as tmp:
        tmp.write("fastapi>=0.100.0\nuvicorn\npydantic>=2.0\n# comment\n")
        tmp_path = tmp.name

    try:
        res = dependency_inspect(tmp_path)
        assert res.file_type == "requirements.txt"
        assert res.dependencies_count == 3
        names = [d.name for d in res.dependencies]
        assert "fastapi" in names
        assert "pydantic" in names
    finally:
        os.remove(tmp_path)


def test_test_discover():
    res = run_test_discover("tests")
    assert res.test_files_count > 0
    assert "pytest" in res.frameworks_detected
    assert res.test_cases_count > 0


def test_log_parse_errors():
    log_sample = """2026-10-17 12:00:00 INFO Server started on port 8000
2026-10-17 12:00:01 WARNING High latency detected in worker
2026-10-17 12:00:02 ERROR Failed to connect with secret key: sk-secret123456789012345
Traceback (most recent call last):
  File "server.py", line 42, in connect
    raise ConnectionRefusedError("Connection refused")
ConnectionRefusedError: Connection refused
"""
    res = log_parse_errors(log_sample, is_path=False)
    assert res.error_count >= 1
    assert res.warning_count >= 1
    assert len(res.tracebacks) >= 1
    assert "[REDACTED_API_KEY]" in res.errors[0]["text"]


def test_file_integrity_verify():
    with tempfile.NamedTemporaryFile("wb+", delete=False) as tmp:
        tmp.write(b"Cavrix Intelligence Engine Hash Integrity")
        tmp_path = tmp.name

    try:
        res = file_integrity_verify(tmp_path)
        assert res.exists is True
        assert res.size_bytes == 41
        assert "sha256" in res.hashes
        assert "md5" in res.hashes
        assert len(res.hashes["sha256"]) == 64
    finally:
        os.remove(tmp_path)


@pytest.mark.asyncio
async def test_http_endpoint_check_ssrf_blocking():
    # Attempt SSRF to private IP
    res_private = await http_endpoint_check("http://127.0.0.1:8000")
    assert res_private.accessible is False
    assert "SSRF security restriction" in res_private.error

    # Attempt SSRF to AWS metadata
    res_meta = await http_endpoint_check("http://169.254.169.254/latest/meta-data/")
    assert res_meta.accessible is False
    assert "SSRF security restriction" in res_meta.error
