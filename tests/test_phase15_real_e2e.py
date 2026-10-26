"""
Phase 15 Real Upstream Integration & End-to-End Execution Test Suite.
Validates:
1. All 30 capabilities verified through central registry and verification engine.
2. Live FastAPI endpoints (/v1/capabilities, /v1/capabilities/{id}, /v1/capabilities/{id}/verify, /v1/capabilities/verify_all).
3. Live skill executions (markitdown_convert, crawl4ai_extract, swerex_execute).
4. Orchestrator Hermes tool call parsing via upstream NousResearch utilities.
5. Invariant preservation (model SHA256 immutability, license auditing, approval token barriers).
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

# Ensure CIE on sys.path
CIE_ROOT = Path("E:/cavrix_cie")
if str(CIE_ROOT) not in sys.path:
    sys.path.insert(0, str(CIE_ROOT))

from cie.server import app
from cie.capabilities.registry import get_capability_registry
from cie.capabilities.verifier import verify_single_capability, verify_all_capabilities
from cie.skills.registry import get_default_registry
from cie.skills.executor import SkillExecutor
from cie.skills.schemas import ToolExecutionRequest, PermissionLevel
from cie.security_tokens import compute_action_token
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus


@pytest.fixture
def client():
    return TestClient(app)


# =========================================================================
# 1. CAPABILITIES API ENDPOINTS VERIFICATION
# =========================================================================

def test_capabilities_list_endpoint(client):
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 30
    assert "status_summary" in data
    assert len(data["capabilities"]) == 30

    summary = data["status_summary"]
    assert summary.get("UPSTREAM_LIBRARY_INTEGRATED") == 8
    assert summary.get("REMOTE_SERVICE_CLIENT_IMPLEMENTED") == 4
    assert summary.get("PROTOCOL_ADAPTER_ONLY") == 4
    assert summary.get("CUSTOM_REIMPLEMENTATION") == 14


def test_capabilities_detail_endpoint(client):
    # Capability 1: Hermes Agent
    resp_hermes = client.get("/v1/capabilities/1")
    assert resp_hermes.status_code == 200
    data_hermes = resp_hermes.json()
    assert data_hermes["id"] == 1
    assert data_hermes["name"] == "Hermes Agent"
    assert data_hermes["license"] == "MIT"
    assert data_hermes["status"] == "UPSTREAM_LIBRARY_INTEGRATED"

    # Capability 16: OpenViking (AGPL-3.0 audit verification)
    resp_viking = client.get("/v1/capabilities/16")
    assert resp_viking.status_code == 200
    data_viking = resp_viking.json()
    assert data_viking["license"] == "AGPL-3.0"
    assert data_viking["status"] == "REMOTE_SERVICE_CLIENT_IMPLEMENTED"

    # Capability 24: MarkItDown
    resp_md = client.get("/v1/capabilities/24")
    assert resp_md.status_code == 200
    data_md = resp_md.json()
    assert data_md["name"] == "MarkItDown"
    assert data_md["status"] == "UPSTREAM_LIBRARY_INTEGRATED"

    # 404 for invalid capability ID
    resp_missing = client.get("/v1/capabilities/999")
    assert resp_missing.status_code == 404


def test_capability_verify_single_endpoint(client):
    # Test verify endpoint for MarkItDown
    resp = client.post("/v1/capabilities/24/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["capability_id"] == 24
    assert data["verified"] is True
    assert data["error"] is None

    # Test verify endpoint for SWE-ReX
    resp_swe = client.post("/v1/capabilities/7/verify")
    assert resp_swe.status_code == 200
    data_swe = resp_swe.json()
    assert data_swe["capability_id"] == 7
    assert data_swe["verified"] is True


def test_capability_verify_all_endpoint(client):
    resp = client.post("/v1/capabilities/verify_all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_capabilities"] == 30
    assert data["verified_passed"] == 30
    assert data["verified_failed"] == 0


# =========================================================================
# 2. REAL UPSTREAM SKILL EXECUTIONS
# =========================================================================

@pytest.mark.asyncio
async def test_markitdown_skill_execution():
    executor = SkillExecutor()
    req = ToolExecutionRequest(
        tool_name="markitdown_convert",
        arguments={
            "content": "<h1>CavrixCode Phase 15</h1><p>Integrated with upstream MarkItDown.</p>",
            "is_file_path": False,
        },
    )
    res = await executor.execute(req)
    assert res.success is True
    assert "# CavrixCode Phase 15" in res.result["markdown"]
    assert "Integrated with upstream MarkItDown." in res.result["markdown"]


@pytest.mark.asyncio
async def test_crawl4ai_skill_execution():
    executor = SkillExecutor()
    html = """
    <html>
      <head><title>Crawl4AI Real Test</title></head>
      <body>
        <h1>Crawl4AI Header</h1>
        <p>Testing structured crawler extraction.</p>
        <a href="https://cavrix.ai/docs">Documentation Link</a>
      </body>
    </html>
    """
    req = ToolExecutionRequest(
        tool_name="crawl4ai_extract",
        arguments={
            "url": "https://cavrix.ai/test",
            "html": html,
        },
    )
    res = await executor.execute(req)
    assert res.success is True
    assert "Crawl4AI Header" in res.result["markdown"]
    assert "https://cavrix.ai/docs" in res.result["links"]


@pytest.mark.asyncio
async def test_swerex_isolated_execution_with_barriers():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a sample file inside isolated workspace
        target_file = Path(tmp_dir) / "output.txt"
        executor = SkillExecutor()

        args_in = {
            "command": ["python", "-c", f"open(r'{target_file}', 'w').write('SWEREX_SUCCESS')"],
            "workspace_root": tmp_dir,
        }
        token_in = compute_action_token("swerex_execute", args_in, session_id="test_sess")

        # In-bounds execution approved with valid token
        req_in = ToolExecutionRequest(
            tool_name="swerex_execute",
            arguments=args_in,
            approval_token=token_in,
            session_id="test_sess",
            approved_by_user=True,
        )
        res_in = await executor.execute(req_in)
        assert res_in.success is True
        assert res_in.result["exit_code"] == 0
        assert target_file.exists()
        assert "SWEREX_SUCCESS" in target_file.read_text()

        # Out-of-bounds traversal attack blocked
        args_attack = {
            "command": ["cmd.exe", "/c", "dir"],
            "cwd": "C:/Windows/System32",
            "workspace_root": tmp_dir,
        }
        token_attack = compute_action_token("swerex_execute", args_attack, session_id="test_sess")
        req_attack = ToolExecutionRequest(
            tool_name="swerex_execute",
            arguments=args_attack,
            approval_token=token_attack,
            session_id="test_sess",
            approved_by_user=True,
        )
        res_attack = await executor.execute(req_attack)
        assert res_attack.success is False
        assert "SecurityViolation" in res_attack.error or "Path traversal" in res_attack.error


# =========================================================================
# 3. HERMES TOOL EXTRACTION IN ORCHESTRATION PIPELINE
# =========================================================================

def test_hermes_xml_tool_parsing():
    from cie.capabilities.agent.hermes import HermesAgentAdapter

    adapter = HermesAgentAdapter()
    sample_llm_response = (
        "I will now convert the document for you.\n"
        "<tool_call>\n"
        '{"name": "markitdown_convert", "arguments": {"content": "<h1>Title</h1>"}}\n'
        "</tool_call>\n"
        "Please wait while I process the file."
    )
    calls = adapter.parse_tool_calls(sample_llm_response)
    assert len(calls) == 1
    assert calls[0].name == "markitdown_convert"
    assert calls[0].arguments == {"content": "<h1>Title</h1>"}


# =========================================================================
# 4. GGUF MODEL INVARIANT
# =========================================================================

def test_gguf_model_sha256_invariant():
    gguf_path = Path("E:/CavrixCode-latest/cavrix_code_latest.gguf")
    assert gguf_path.exists(), "Model file missing"

    sha = hashlib.sha256()
    with open(gguf_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)

    expected = "4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1".lower()
    assert sha.hexdigest().lower() == expected, f"GGUF model hash modified! Got {sha.hexdigest()}"
