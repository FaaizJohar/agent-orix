"""
Phase 16 Runtime Proof & Integration Gap Closure Test Suite.
Verifies:
1. End-to-end execution of MarkItDown, Crawl4AI, SWE-ReX, DSPy, and Inspect AI through CIEOrchestrator.
2. Robust error handling (malformed inputs, boundary violations, token tampering).
3. Consequential security barriers (HMAC-SHA256 approval tokens, workspace path containment).
4. Truthful verification endpoint behavior (honest reporting of offline remote daemons).
5. Natural language intent routing for all 5 upstream capabilities.
6. Bitwise immutability of the GGUF model weights.
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
CIE_ROOT = Path(__file__).resolve().parent.parent
if str(CIE_ROOT) not in sys.path:
    sys.path.insert(0, str(CIE_ROOT))

from cie.server import app
from cie.orchestrator import CIEOrchestrator
from cie.router import DeterministicRouter
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory
from cie.security_tokens import compute_action_token
from cie.capabilities.verifier import verify_single_capability, verify_all_capabilities


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.fixture
def router():
    return DeterministicRouter()


# =========================================================================
# 1. ORCHESTRATOR END-TO-END EXECUTION: 5 UPSTREAM CAPABILITIES
# =========================================================================

@pytest.mark.asyncio
async def test_markitdown_orchestrator_execution(orchestrator):
    """
    Traces MarkItDown through orchestrator -> router/metadata -> skill_executor -> upstream MarkItDown.
    """
    req = CIERequest(
        prompt="Convert this HTML document to markdown",
        metadata={
            "tool_name": "markitdown_convert",
            "arguments": {
                "content": "<article><h1>Phase 16 Runtime Proof</h1><p>Verifying MarkItDown stream conversion.</p></article>",
                "is_file_path": False,
            },
        },
    )
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert "# Phase 16 Runtime Proof" in resp.content
    assert "Verifying MarkItDown stream conversion." in resp.content
    assert resp.metadata.get("tool_name") == "markitdown_convert"
    assert resp.metadata["result"]["upstream_used"] is True


@pytest.mark.asyncio
async def test_markitdown_error_handling(orchestrator):
    """
    Verifies graceful error handling for non-existent files.
    """
    req = CIERequest(
        prompt="Convert missing file",
        metadata={
            "tool_name": "markitdown_convert",
            "arguments": {
                "file_path": "missing_document_phase16.docx",
            },
        },
    )
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.metadata["result"]["success"] is False
    assert "not found" in resp.metadata["result"]["error"].lower()


@pytest.mark.asyncio
async def test_crawl4ai_orchestrator_execution(orchestrator):
    """
    Traces Crawl4AI through orchestrator -> skill_executor -> upstream crawl4ai extraction.
    """
    sample_html = """
    <html>
      <head><title>Crawl4AI Page</title></head>
      <body>
        <h1>Crawl4AI Real Content</h1>
        <p>Testing structured crawler extraction.</p>
        <a href="https://example.com/docs">Documentation</a>
      </body>
    </html>
    """
    req = CIERequest(
        prompt="Extract structured content",
        metadata={
            "tool_name": "crawl4ai_extract",
            "arguments": {
                "url": "https://example.com/page",
                "html": sample_html,
                "title": "Crawl4AI Page",
            },
        },
    )
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert "Crawl4AI Real Content" in resp.content
    assert "https://example.com/docs" in resp.metadata["result"]["links"]
    if not resp.metadata["result"].get("upstream_used"):
        pytest.skip("Upstream Crawl4AI not installed in this environment; native fallback verified.")
    assert resp.metadata["result"]["upstream_used"] is True


@pytest.mark.asyncio
async def test_swerex_orchestrator_execution_and_barriers(orchestrator):
    """
    Traces SWE-ReX isolated command execution through orchestrator, verifying:
    1. Valid execution with action-bound HMAC approval token.
    2. Rejection of unapproved requests.
    3. Blocked path traversal attack.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_out = Path(tmp_dir) / "phase16.txt"
        args_valid = {
            "command": ["python", "-c", f"open(r'{test_out}', 'w').write('SWEREX_P16_SUCCESS')"],
            "workspace_root": tmp_dir,
        }
        token_valid = compute_action_token("swerex_execute", args_valid, session_id="sess_p16")

        # 1. Valid execution with approval token
        req_valid = CIERequest(
            prompt="Run isolated python command",
            session_id="sess_p16",
            metadata={
                "tool_name": "swerex_execute",
                "arguments": args_valid,
                "approved_by_user": True,
                "approval_token": token_valid,
            },
        )
        resp_valid = await orchestrator.process_request(req_valid)
        assert resp_valid.status == ExecutionStatus.COMPLETED
        assert test_out.exists()
        assert "SWEREX_P16_SUCCESS" in test_out.read_text()

        # 2. Consequential action blocked without approval token
        req_unapproved = CIERequest(
            prompt="Run isolated python command unapproved",
            session_id="sess_p16",
            metadata={
                "tool_name": "swerex_execute",
                "arguments": args_valid,
                "approved_by_user": True,  # Boolean alone cannot authorize!
            },
        )
        resp_unapproved = await orchestrator.process_request(req_unapproved)
        assert resp_unapproved.status == ExecutionStatus.ERROR
        assert "requires a valid action-bound approval token" in resp_unapproved.content

        # 3. Path traversal outside workspace blocked
        args_traversal = {
            "command": ["cmd.exe", "/c", "dir"],
            "workspace_root": tmp_dir,
            "cwd": "C:/Windows/System32",
        }
        token_traversal = compute_action_token("swerex_execute", args_traversal, session_id="sess_p16")
        req_traversal = CIERequest(
            prompt="Run directory traversal command",
            session_id="sess_p16",
            metadata={
                "tool_name": "swerex_execute",
                "arguments": args_traversal,
                "approved_by_user": True,
                "approval_token": token_traversal,
            },
        )
        resp_traversal = await orchestrator.process_request(req_traversal)
        assert resp_traversal.status == ExecutionStatus.ERROR
        assert "SecurityViolation" in resp_traversal.content or "Path traversal" in resp_traversal.content


@pytest.mark.asyncio
async def test_dspy_orchestrator_execution(orchestrator):
    """
    Traces Stanford DSPy declarative signature compilation through orchestrator.
    """
    req = CIERequest(
        prompt="Compile DSPy prompt signature",
        metadata={
            "tool_name": "dspy_compile_signature",
            "arguments": {
                "name": "CodeReviewer",
                "instructions": "Review the provided code snippet for memory leaks.",
                "inputs": [{"name": "code_snippet", "desc": "Source code", "prefix": "Code:"}],
                "outputs": [{"name": "review", "desc": "Critique and recommendations", "prefix": "Review:"}],
                "input_values": {"code_snippet": "char* buf = malloc(1024);"},
            },
        },
    )
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert "Review the provided code snippet for memory leaks." in resp.content
    assert "Code: char* buf = malloc(1024);" in resp.content
    assert "Review:" in resp.content
    if not resp.metadata["result"].get("upstream_used"):
        pytest.skip("Upstream DSPy not installed in this environment; native fallback verified.")
    assert resp.metadata["result"]["upstream_used"] is True


@pytest.mark.asyncio
async def test_inspect_ai_orchestrator_execution(orchestrator):
    """
    Traces UK AISI Inspect AI benchmark evaluation through orchestrator.
    """
    samples = [
        {"id": "math_1", "input": "Calculate 15 * 3", "target": "45"},
        {"id": "math_2", "input": "Calculate 100 / 4", "target": "25"},
    ]
    predictions = {
        "Calculate 15 * 3": "45",
        "Calculate 100 / 4": "25",
    }
    req = CIERequest(
        prompt="Evaluate benchmark task with Inspect AI",
        metadata={
            "tool_name": "inspect_ai_eval",
            "arguments": {
                "task_name": "arithmetic_eval",
                "samples": samples,
                "predictions": predictions,
            },
        },
    )
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.metadata["result"]["total_samples"] == 2
    assert resp.metadata["result"]["mean_accuracy"] == 1.0
    if not resp.metadata["result"].get("upstream_used"):
        pytest.skip("Upstream Inspect AI not installed in this environment; native fallback verified.")
    assert resp.metadata["result"]["upstream_used"] is True


# =========================================================================
# 2. EVIDENCE-BASED CAPABILITY VERIFIER & TRUTHFULNESS
# =========================================================================

def test_verifier_truthful_remote_service_reporting():
    """
    Ensures that for remote services (n8n, OpenViking, Langfuse, Frigate),
    the verifier probes localhost and honestly reports daemon reachability.
    Never claims an offline remote service is live.
    """
    # Capability 15: n8n (Remote Service)
    n8n_res = verify_single_capability(15)
    assert n8n_res["test_type"] == "REMOTE_SERVICE_CLIENT"
    assert n8n_res["live_service_active"] is False  # Honest reporting: offline
    assert "offline" in n8n_res["details"]["note"].lower()

    # Capability 16: OpenViking (Remote Service)
    viking_res = verify_single_capability(16)
    assert viking_res["test_type"] == "REMOTE_SERVICE_CLIENT"
    assert viking_res["live_service_active"] is False
    assert "offline" in viking_res["details"]["note"].lower()

    # Capability 24: MarkItDown (Local Upstream)
    md_res = verify_single_capability(24)
    assert md_res["test_type"] == "LOCAL_UPSTREAM_EXECUTION"
    assert md_res["verified"] is True


def test_verifier_all_breakdown():
    """
    Verifies that verify_all_capabilities() categorizes tests into truthful execution buckets.
    """
    res = verify_all_capabilities()
    assert res["total_capabilities"] == 30
    breakdown = res["breakdown"]
    assert breakdown["local_upstream_passed"] == 8
    assert breakdown["local_custom_passed"] == 14
    assert breakdown["protocol_spec_passed"] == 4
    assert breakdown["remote_service_client_passed"] == 4


# =========================================================================
# 3. ROUTER NATURAL LANGUAGE INTENT CLASSIFICATION
# =========================================================================

def test_router_natural_language_intent(router):
    """
    Verifies that natural language queries map to the 5 upstream developer tools.
    """
    assert router.route("markitdown parse markdown stream").matched_patterns[0] == "markitdown_convert"
    assert router.route("crawl4ai extract structured web content").matched_patterns[0] == "crawl4ai_extract"
    assert router.route("run in swe-rex isolated workspace").matched_patterns[0] == "swerex_execute"
    assert router.route("compile prompt signature with dspy").matched_patterns[0] == "dspy_compile_signature"
    assert router.route("evaluate benchmark using inspect_ai").matched_patterns[0] == "inspect_ai_eval"


# =========================================================================
# 4. GGUF MODEL INVARIANT
# =========================================================================

def test_gguf_model_sha256_invariant():
    """
    Strict bitwise immutability check on cavrix_code_latest.gguf.
    """
    gguf_path = Path("E:/CavrixCode-latest/cavrix_code_latest.gguf")
    assert gguf_path.exists(), "cavrix_code_latest.gguf not found"

    sha = hashlib.sha256()
    with open(gguf_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)

    expected = "4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1".lower()
    assert sha.hexdigest().lower() == expected, f"GGUF modified! Got {sha.hexdigest()}"
