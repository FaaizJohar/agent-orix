"""
Phase 2 Agent Loop & Safe File Tools Integration Test Suite.
Verifies file_read_text, file_search_text, security boundaries,
skill registry integration, adaptive planning selection,
and end-to-end plan execution with verification.
"""

import os
import pytest
from pathlib import Path

from cie.skills.schemas import PermissionLevel, RiskLevel
from cie.skills.registry import get_default_registry
from cie.skills.tools.file_tools import (
    file_read_text,
    file_search_text,
    FileReadTextInput,
    FileReadTextOutput,
    FileSearchTextInput,
    FileSearchTextOutput,
)
from cie.skills.path_guard import PathSecurityError
from cie.planning.planner import AdaptivePlanner
from cie.planning.executor import BoundedPlanExecutor
from cie.planning.schemas import PlanStatus, StepStatus, TaskPlan, PlanStep
from cie.schemas import CIERequest, IntentCategory
from cie.router import DeterministicRouter
from cie.orchestrator import CIEOrchestrator


def test_registry_contains_phase2_file_tools():
    """Verify that file_read_text and file_search_text are registered with safe permissions."""
    reg = get_default_registry()
    tools = reg.list_tools(enabled_only=False)
    assert len(tools) >= 18

    tool_names = [t.name for t in tools]
    assert "file_read_text" in tool_names
    assert "file_search_text" in tool_names

    read_def = reg.get_tool("file_read_text")
    assert read_def is not None
    assert read_def.permission == PermissionLevel.READ_ONLY
    assert read_def.risk == RiskLevel.LOW

    search_def = reg.get_tool("file_search_text")
    assert search_def is not None
    assert search_def.permission == PermissionLevel.READ_ONLY
    assert search_def.risk == RiskLevel.LOW


def test_file_read_text_success():
    """Verify reading lines from a valid project file."""
    res = file_read_text("README.md", start_line=1, max_lines=20)
    assert res.error is None
    assert res.lines_returned > 0
    assert "cavrix" in res.content.lower()


def test_file_read_text_bounded_lines():
    """Verify start_line and max_lines bounds."""
    res = file_read_text("README.md", start_line=2, max_lines=3)
    assert res.error is None
    assert res.lines_returned <= 3
    assert res.start_line == 2


def test_file_read_text_security_path_traversal():
    """Verify path traversal is blocked."""
    res = file_read_text("../../../Windows/System32/drivers/etc/hosts")
    assert res.error is not None
    assert "Security/Path error" in res.error or "traversal" in res.error.lower()
    assert res.content == ""


def test_file_read_text_security_sensitive_file():
    """Verify reading sensitive files like .env or keys is blocked."""
    res = file_read_text(".env")
    assert res.error is not None
    assert "Security" in res.error or "sensitive" in res.error.lower()
    assert res.content == ""


def test_file_search_text_success():
    """Verify searching for text within allowed directory."""
    res = file_search_text(query="DeterministicRouter", directory_path="cie", file_extension=".py", max_results=10)
    assert res.error is None
    assert res.matches_count > 0
    assert len(res.matches) > 0
    assert any("router.py" in m.file for m in res.matches)


def test_file_search_text_empty_query():
    """Verify empty query returns error."""
    res = file_search_text(query="", directory_path=".")
    assert res.error == "Search query cannot be empty"
    assert res.matches_count == 0


def test_file_search_text_traversal_blocked():
    """Verify searching outside allowed roots is blocked."""
    res = file_search_text(query="password", directory_path="C:/Windows")
    assert res.error is not None
    assert "Security" in res.error or "prohibited" in res.error or "blocked" in res.error


def test_router_recognizes_file_skills():
    """Verify DeterministicRouter classifies file read and search requests."""
    router = DeterministicRouter()

    r1 = router.route("Please read file pyproject.toml")
    assert r1.category == IntentCategory.SKILL
    assert "file_read_text" in r1.matched_patterns

    r2 = router.route("search in files for DeterministicRouter")
    assert r2.category == IntentCategory.SKILL
    assert "file_search_text" in r2.matched_patterns


def test_planner_selects_file_skills():
    """Verify AdaptivePlanner selects file tools for inspection tasks."""
    planner = AdaptivePlanner()

    plan1 = planner.create_plan("read file cie/config.py")
    assert plan1.status == PlanStatus.PENDING
    assert len(plan1.steps) >= 1
    assert plan1.steps[0].skill_id == "file_read_text"
    assert plan1.steps[0].arguments.get("file_path") == "cie/config.py"

    plan2 = planner.create_plan("search in files for 'DeterministicRouter'")
    assert plan2.status == PlanStatus.PENDING
    assert len(plan2.steps) >= 1
    assert plan2.steps[0].skill_id == "file_search_text"


@pytest.mark.asyncio
async def test_e2e_plan_execution_with_file_tools():
    """Verify end-to-end execution of a compound plan with file inspection and text reading."""
    executor = BoundedPlanExecutor()

    # Create a 2-step DAG plan:
    # Step 1: inspect file tree
    # Step 2: read text from README.md (depends on step 1)
    step1 = PlanStep(
        step_id="step_1",
        skill_id="file_tree_inspect",
        arguments={"directory_path": "cie", "max_depth": 2, "max_files": 30},
        purpose="Inspect project directory tree",
        expected_outcome="Directory tree structure",
        permission=PermissionLevel.READ_ONLY,
        risk=RiskLevel.LOW,
    )
    step2 = PlanStep(
        step_id="step_2",
        skill_id="file_read_text",
        arguments={"file_path": "README.md", "start_line": 1, "max_lines": 10},
        purpose="Read project configuration file",
        expected_outcome="Text lines from file",
        dependencies=["step_1"],
        permission=PermissionLevel.READ_ONLY,
        risk=RiskLevel.LOW,
    )

    plan = TaskPlan(
        task_id="test_phase2_e2e_plan",
        goal="Inspect tree and read config",
        steps=[step1, step2],
    )

    executed = await executor.execute_plan(plan)
    assert executed.status == PlanStatus.COMPLETED
    assert len(executed.steps) == 2
    assert executed.steps[0].status == StepStatus.SUCCEEDED
    assert executed.steps[1].status == StepStatus.SUCCEEDED
    assert executed.steps[1].result is not None
    assert "lines_returned" in executed.steps[1].result


def test_chat_stream_skill_execution():
    """Verify streaming endpoint handles single SKILL route."""
    from fastapi.testclient import TestClient
    from cie.server import app

    client = TestClient(app)
    res = client.post(
        "/v1/chat/stream",
        json={"prompt": "check git status", "metadata": {"tool_name": "git_status"}},
    )
    assert res.status_code == 200
    text = res.text
    assert "data: ⚙️ Executing developer skill" in text
    assert "git_status" in text
    assert "data: [DONE]" in text


def test_chat_stream_plan_mode_execution():
    """Verify streaming endpoint handles adaptive planning mode."""
    from fastapi.testclient import TestClient
    from cie.server import app

    client = TestClient(app)
    res = client.post(
        "/v1/chat/stream",
        json={
            "prompt": "read file README.md",
            "metadata": {"plan_mode": True},
        },
    )
    assert res.status_code == 200
    text = res.text
    assert "data: 📋 Creating adaptive execution plan" in text
    assert "data: [DONE]" in text

