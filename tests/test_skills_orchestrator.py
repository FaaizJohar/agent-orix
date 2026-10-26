"""
End-to-end integration tests for Skills execution through CIEOrchestrator.
"""

import pytest
from cie.orchestrator import CIEOrchestrator
from cie.schemas import CIERequest, ExecutionStatus, IntentCategory


@pytest.fixture
def orchestrator():
    return CIEOrchestrator()


@pytest.mark.asyncio
async def test_orchestrator_routes_to_skill_and_executes(orchestrator):
    prompt = "Validate python syntax in this snippet: def hello(): return 'world'"
    req = CIERequest(prompt=prompt)
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.SKILL
    assert resp.route.matched_patterns == ["python_ast_validate"]
    assert len(resp.steps_taken) == 3
    assert resp.steps_taken[2].action == "SkillExecution"
    assert "### Skill Execution: `python_ast_validate`" in resp.content
    assert '"valid": true' in resp.content.lower()


@pytest.mark.asyncio
async def test_orchestrator_executes_json_validate(orchestrator):
    prompt = 'Check json syntax: {"name": "Cavrix", "active": true}'
    req = CIERequest(prompt=prompt)
    resp = await orchestrator.process_request(req)

    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.route.category == IntentCategory.SKILL
    assert resp.route.matched_patterns == ["json_validate"]
    assert '"valid": true' in resp.content.lower()


@pytest.mark.asyncio
async def test_orchestrator_handles_explicit_metadata_tool(orchestrator):
    req = CIERequest(
        prompt="Inspect the project",
        metadata={
            "tool_name": "python_project_inspect",
            "arguments": {"project_dir": "."},
        },
    )
    # Force route category or let metadata drive execution
    req.metadata["tool_name"] = "python_project_inspect"
    resp = await orchestrator.process_request(req)
    assert resp.status == ExecutionStatus.COMPLETED
    assert resp.metadata.get("tool_name") == "python_project_inspect"
