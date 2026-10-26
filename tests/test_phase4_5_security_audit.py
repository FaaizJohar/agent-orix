"""
Adversarial Security & Reliability Audit Test Suite for Phase 4.5.
Validates permission enforcement, approval tokens, SSRF firewalls, path traversal,
sensitive file redactions, GitHub adapter safety, concurrency, and orchestrator bounds.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from cie.research.fetcher import SafeWebFetcher, SecurityValidationError
from cie.safety import redact_secrets, validate_input
from cie.skills.adapters.github import GitHubAdapter, GitHubAdapterError
from cie.skills.executor import SkillExecutor
from cie.skills.path_guard import (
    PathSecurityError,
    is_sensitive_filename,
    is_sensitive_path,
    validate_safe_path,
)
from cie.skills.registry import SkillRegistry
from cie.skills.schemas import (
    PermissionLevel,
    RiskLevel,
    ToolDefinition,
    ToolExecutionRequest,
    compute_action_token,
)
from cie.skills.tools.dependency_inspect import dependency_inspect
from cie.skills.tools.file_integrity import file_integrity_verify
from cie.skills.tools.file_tools import file_tree_inspect
from cie.skills.tools.git_tools import git_diff_summary, git_status
from cie.skills.tools.http_tools import http_endpoint_check
from cie.skills.tools.log_tools import log_parse_errors
from cie.skills.tools.readme_tools import readme_extract
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


# ==============================================================================
# 1. SKILL PERMISSIONS AND ACTION-BOUND APPROVALS
# ==============================================================================

class SampleWriteInput(BaseModel):
    filepath: str
    data: str


def sample_write_tool(filepath: str, data: str) -> dict:
    return {"written": len(data), "target": filepath}


@pytest.fixture
def security_executor():
    reg = SkillRegistry()
    reg.register(
        ToolDefinition(
            name="guarded_write_tool",
            display_name="Guarded Write Tool",
            description="Tool requiring explicit user approval",
            permission=PermissionLevel.LOCAL_WRITE,
            risk=RiskLevel.HIGH,
            requires_approval=True,
            input_model=SampleWriteInput,
        ),
        sample_write_tool,
    )
    return SkillExecutor(registry=reg)


@pytest.mark.asyncio
async def test_unauthorized_write_operation_is_rejected(security_executor):
    req = ToolExecutionRequest(
        tool_name="guarded_write_tool",
        arguments={"filepath": "test.txt", "data": "hello"},
        approved_by_user=False,  # Unauthorized
    )
    res = await security_executor.execute(req)
    assert res.success is False
    assert "Permission denied: Tool 'guarded_write_tool' requires explicit user approval" in res.error
    assert res.permission_used == PermissionLevel.LOCAL_WRITE


@pytest.mark.asyncio
async def test_invalid_or_missing_arguments_rejected(security_executor):
    valid_token = compute_action_token("guarded_write_tool", {"filepath": "test.txt"})
    req = ToolExecutionRequest(
        tool_name="guarded_write_tool",
        arguments={"filepath": "test.txt"},  # Missing 'data'
        approval_token=valid_token,
        approved_by_user=True,
    )
    res = await security_executor.execute(req)
    assert res.success is False
    assert "Input validation failed" in res.error


@pytest.mark.asyncio
async def test_approval_token_binding_prevents_tampering(security_executor):
    initial_args = {"filepath": "important.txt", "data": "original"}
    valid_token = compute_action_token("guarded_write_tool", initial_args)

    # 1. Valid token and matching arguments succeed
    req_valid = ToolExecutionRequest(
        tool_name="guarded_write_tool",
        arguments=initial_args,
        approved_by_user=True,
        approval_token=valid_token,
    )
    res_valid = await security_executor.execute(req_valid)
    assert res_valid.success is True

    # 2. Tampered arguments with original approval token FAIL
    tampered_args = {"filepath": "important.txt", "data": "malicious payload"}
    req_tampered = ToolExecutionRequest(
        tool_name="guarded_write_tool",
        arguments=tampered_args,
        approved_by_user=True,
        approval_token=valid_token,  # Mismatched token!
    )
    res_tampered = await security_executor.execute(req_tampered)
    assert res_tampered.success is False
    assert "Action-bound approval token mismatch" in res_tampered.error

    # 3. Token generated for different tool FAILS
    swapped_tool_token = compute_action_token("other_tool", initial_args)
    req_swapped = ToolExecutionRequest(
        tool_name="guarded_write_tool",
        arguments=initial_args,
        approved_by_user=True,
        approval_token=swapped_tool_token,
    )
    res_swapped = await security_executor.execute(req_swapped)
    assert res_swapped.success is False
    assert "Action-bound approval token mismatch" in res_swapped.error


# ==============================================================================
# 2. HTTP AND SSRF MITIGATION
# ==============================================================================

@pytest.mark.asyncio
async def test_ssrf_prohibited_destinations():
    fetcher = SafeWebFetcher()

    prohibited = [
        "http://127.0.0.1:8080/admin",
        "http://127.0.0.2:80/",
        "http://localhost:3000",
        "http://local:80/",
        "http://10.0.0.1/status",
        "http://172.16.0.5/api",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/test",
        "http://[::1]:8080/",
        "http://[::ffff:127.0.0.1]:80/",
        "http://[::ffff:169.254.169.254]:80/",
    ]

    for url in prohibited:
        with pytest.raises(SecurityValidationError) as exc_info:
            fetcher.validate_url_security(url)
        assert any(term in str(exc_info.value).lower() for term in ["prohibited", "ssrf", "localhost", "internal"])


def test_ssrf_forbidden_schemes():
    fetcher = SafeWebFetcher()
    forbidden = [
        "file:///C:/Windows/win.ini",
        "ftp://example.com/test",
        "gopher://example.com/",
        "dict://example.com/",
    ]
    for url in forbidden:
        with pytest.raises(SecurityValidationError, match="Forbidden URL scheme"):
            fetcher.validate_url_security(url)


@pytest.mark.asyncio
async def test_redirect_to_blocked_ssrf_target_detected():
    # Simulate a public URL redirecting to 127.0.0.1
    mock_head_302 = MagicMock()
    mock_head_302.status_code = 302
    mock_head_302.headers = {"Location": "http://127.0.0.1:8088/secret"}

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock) as mock_head, \
         patch("cie.research.fetcher.SafeWebFetcher.validate_url_security") as mock_val:

        def mock_validate(target_url):
            if "127.0.0.1" in target_url:
                raise SecurityValidationError("SSRF violation: Hostname resolved to loopback.")
            return target_url, "example.com", 80

        mock_val.side_effect = mock_validate
        mock_head.return_value = mock_head_302

        res = await http_endpoint_check("http://example.com/redirect")
        assert res.accessible is False
        assert "SSRF security restriction: Redirect target blocked" in res.error


# ==============================================================================
# 3. FILESYSTEM SAFETY AND PATH TRAVERSAL
# ==============================================================================

def test_path_traversal_detection():
    # Attempt traversing outside allowed boundaries
    traversal_paths = [
        "../../../../Windows/System32/cmd.exe",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "C:\\Program Files\\app",
        "/etc/passwd",
        "/etc/shadow",
        "test\x00file.txt",
    ]
    for p in traversal_paths:
        with pytest.raises(PathSecurityError):
            validate_safe_path(p, must_exist=False)


def test_sensitive_file_identification():
    sensitive_names = [
        ".env",
        ".env.local",
        ".env.production",
        ".env.stage.backup",
        "my_project.env",
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "server.key",
        "private.pem",
        "client_secret.json",
        "credentials.json",
        "service_account.json",
        "db_password.txt",
        "api_secrets.yaml",
    ]
    for name in sensitive_names:
        assert is_sensitive_filename(name) is True, f"Failed to identify sensitive file: {name}"

    benign_names = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "test_suite.py",
        "main.py",
        "environment_setup.py",
    ]
    for name in benign_names:
        assert is_sensitive_filename(name) is False, f"False positive on benign file: {name}"


def test_file_tree_inspect_excludes_sensitive_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create normal files
        with open(os.path.join(tmp_dir, "README.md"), "w") as f:
            f.write("# Hello")
        with open(os.path.join(tmp_dir, "main.py"), "w") as f:
            f.write("print(1)")

        # Create sensitive files
        with open(os.path.join(tmp_dir, ".env"), "w") as f:
            f.write("SECRET=123")
        with open(os.path.join(tmp_dir, ".env.production"), "w") as f:
            f.write("PROD=123")
        with open(os.path.join(tmp_dir, "id_rsa"), "w") as f:
            f.write("KEY")
        with open(os.path.join(tmp_dir, "credentials.json"), "w") as f:
            f.write("{}")

        res = file_tree_inspect(tmp_dir, max_depth=2)
        assert res.error is None
        found_names = [c["name"] for c in res.tree.get("children", [])]

        assert "README.md" in found_names
        assert "main.py" in found_names
        # Sensitive files MUST NOT appear in the tree
        assert ".env" not in found_names
        assert ".env.production" not in found_names
        assert "id_rsa" not in found_names
        assert "credentials.json" not in found_names


def test_tools_reject_reading_sensitive_files():
    # 1. readme_extract rejects .env
    res_readme = readme_extract(".env", is_path=True)
    assert res_readme.error is not None
    assert any(term in res_readme.error.lower() for term in ["security", "sensitive", "invalid"])

    # 2. dependency_inspect rejects credentials.json
    res_dep = dependency_inspect("credentials.json")
    assert res_dep.error is not None
    assert any(term in res_dep.error.lower() for term in ["security", "sensitive", "invalid"])

    # 3. log_parse_errors rejects id_rsa
    res_log = log_parse_errors("id_rsa", is_path=True)
    assert res_log.error is not None
    assert any(term in res_log.error.lower() for term in ["security", "sensitive", "invalid"])


def test_git_tools_reject_argument_injection():
    # Attempt argument injection flags
    injected_paths = [
        "--exec-path=/tmp",
        "-c core.editor=malicious",
        "-c http.proxy=malicious",
        "--upload-pack=exploit",
    ]
    for flag in injected_paths:
        res = git_status(flag)
        assert res.is_git_repo is False
        assert "Argument injection rejected" in res.error

        res_diff = git_diff_summary(flag)
        assert res_diff.is_git_repo is False
        assert "Argument injection rejected" in res_diff.error


# ==============================================================================
# 4. SECRETS REDACTION & GITHUB ADAPTER
# ==============================================================================

def test_secrets_redaction_comprehensive():
    samples = [
        ("URL with password: https://admin:SuperSecret123@api.github.com/v1", "URL with password: https://admin:[REDACTED_CREDENTIALS]@api.github.com/v1"),
        ("Postgres: postgres://dbuser:MyDatabasePassword456!@localhost:5432/prod", "Postgres: postgres://dbuser:[REDACTED_CREDENTIALS]@localhost:5432/prod"),
        ("OpenAI key: sk-abcdefghijklmnopqrstuvwxyz1234567890", "OpenAI key: [REDACTED_API_KEY]"),
        ("GitHub token: ghp_123456789012345678901234567890123456", "GitHub token: [REDACTED_GITHUB_TOKEN]"),
        ("Google key: AIzaSyD1234567890123456789012345678901", "Google key: [REDACTED_GOOGLE_KEY]"),
        ("Slack token: " + "xoxb" + "-mocktokensamplepart1-mocktokensamplepart2", "Slack token: [REDACTED_SLACK_TOKEN]"),
        ("Bearer token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123", "Bearer token: Bearer [REDACTED_TOKEN]"),
        ("AWS Key: AKIAIOSFODNN7EXAMPLE", "AWS Key: [REDACTED_AWS_KEY]"),
        ("Quoted password: password='SuperSecretPassword'", "Quoted password: '[REDACTED_SECRET]'"),
        ("Unquoted api_key: api_key=verySecretToken12345", "Unquoted api_key: api_key=[REDACTED_SECRET]"),
        ("PEM Block: -----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----", "PEM Block: [REDACTED_PRIVATE_KEY_BLOCK]"),
    ]

    for raw, expected in samples:
        clean = redact_secrets(raw)
        assert clean == expected, f"Redaction failed for: {raw}\nGot: {clean}\nExpected: {expected}"


def test_github_adapter_identifier_validation():
    adapter = GitHubAdapter()

    invalid_identifiers = [
        "../../malicious",
        "owner/extra",
        "repo; rm -rf",
        "name with spaces",
        "repo$dollar",
    ]

    for ident in invalid_identifiers:
        with pytest.raises(GitHubAdapterError, match="Invalid (owner|repo) format"):
            asyncio.run(adapter.get_repo(ident, "valid-repo"))

        with pytest.raises(GitHubAdapterError, match="Invalid (owner|repo) format"):
            asyncio.run(adapter.get_repo("valid-owner", ident))


def test_github_adapter_repr_masks_token():
    adapter = GitHubAdapter(token="ghp_SuperSecretToken12345678901234567890")
    repr_str = repr(adapter)
    assert "ghp_" not in repr_str
    assert "SuperSecret" not in repr_str
    assert "authenticated=True" in repr_str


# ==============================================================================
# 5. CONCURRENCY & ORCHESTRATOR INTEGRITY
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_rate_limiting_thread_safety():
    reg = SkillRegistry()
    reg.register(
        ToolDefinition(
            name="rapid_tool",
            display_name="Rapid Tool",
            description="",
            permission=PermissionLevel.READ_ONLY,
            rate_limit_per_minute=10,
        ),
        lambda: {"status": "ok"},
    )
    executor = SkillExecutor(registry=reg)

    # Launch 20 concurrent requests
    async def make_call(i):
        req = ToolExecutionRequest(tool_name="rapid_tool", arguments={})
        return await executor.execute(req)

    results = await asyncio.gather(*[make_call(i) for i in range(20)])
    successful = [r for r in results if r.success]
    blocked = [r for r in results if not r.success and "Rate limit exceeded" in (r.error or "")]

    assert len(successful) == 10
    assert len(blocked) == 10


@pytest.mark.asyncio
async def test_orchestrator_three_step_bound_enforced():
    orchestrator = CIEOrchestrator()
    req = CIERequest(prompt="Check json: {'foo': 1}")
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert len(resp.steps_taken) <= 3
    for step in resp.steps_taken:
        assert step.step_number in (1, 2, 3)
