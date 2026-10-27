"""
Tests for CIE SkillExecutor.
"""

import asyncio
import time
import pytest
from pydantic import BaseModel, Field
from cie.skills.schemas import (
    PermissionLevel,
    RiskLevel,
    ToolDefinition,
    ToolExecutionRequest,
)
from cie.skills.registry import SkillRegistry
from cie.skills.executor import SkillExecutor


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    echo: str


def echo_handler(message: str) -> EchoOutput:
    return EchoOutput(echo=message)


async def async_slow_handler(seconds: float) -> dict:
    await asyncio.sleep(seconds)
    return {"slept": seconds}


class WriteInput(BaseModel):
    content: str


def write_handler(content: str) -> dict:
    return {"written": len(content)}


@pytest.fixture
def executor():
    reg = SkillRegistry()

    # Normal read tool
    reg.register(
        ToolDefinition(
            name="echo",
            display_name="Echo",
            description="Echoes message",
            permission=PermissionLevel.READ_ONLY,
            input_model=EchoInput,
            output_model=EchoOutput,
            rate_limit_per_minute=5,
        ),
        echo_handler,
    )

    # Slow tool with 0.1s timeout
    reg.register(
        ToolDefinition(
            name="slow_tool",
            display_name="Slow",
            description="Slow async tool",
            permission=PermissionLevel.READ_ONLY,
            timeout_seconds=0.1,
        ),
        async_slow_handler,
    )

    # Write tool requiring approval
    reg.register(
        ToolDefinition(
            name="local_write_tool",
            display_name="Write Tool",
            description="Local write tool",
            permission=PermissionLevel.LOCAL_WRITE,
            requires_approval=True,
            input_model=WriteInput,
        ),
        write_handler,
    )

    return SkillExecutor(registry=reg)


@pytest.mark.asyncio
async def test_successful_tool_execution(executor):
    req = ToolExecutionRequest(
        tool_name="echo",
        arguments={"message": "Hello Cavrix"},
    )
    res = await executor.execute(req)
    assert res.success is True
    assert res.result == {"echo": "Hello Cavrix"}
    assert res.permission_used == PermissionLevel.READ_ONLY
    assert len(executor.audit_log) == 1
    assert executor.audit_log[0]["success"] is True


@pytest.mark.asyncio
async def test_input_validation_failure(executor):
    req = ToolExecutionRequest(
        tool_name="echo",
        arguments={},  # Missing required field 'message'
    )
    res = await executor.execute(req)
    assert res.success is False
    assert "Input validation failed" in res.error
    assert len(executor.audit_log) == 1
    assert executor.audit_log[0]["success"] is False


@pytest.mark.asyncio
async def test_permission_approval_required(executor):
    req = ToolExecutionRequest(
        tool_name="local_write_tool",
        arguments={"content": "test file"},
        approved_by_user=False,  # Unapproved!
    )
    res = await executor.execute(req)
    assert res.success is False
    assert "requires explicit user approval" in res.error

    # Now execute with user approval and valid action token
    from cie.security_tokens import compute_action_token
    req.approved_by_user = True
    req.approval_token = compute_action_token("local_write_tool", {"content": "test file"})
    res_approved = await executor.execute(req)
    assert res_approved.success is True
    assert res_approved.result == {"written": 9}


@pytest.mark.asyncio
async def test_rate_limit_enforcement(executor):
    # Tool limit is 5 per minute
    for _ in range(5):
        req = ToolExecutionRequest(tool_name="echo", arguments={"message": "ping"})
        res = await executor.execute(req)
        assert res.success is True

    # 6th request should fail due to rate limit
    req_blocked = ToolExecutionRequest(tool_name="echo", arguments={"message": "ping"})
    res_blocked = await executor.execute(req_blocked)
    assert res_blocked.success is False
    assert "Rate limit exceeded" in res_blocked.error


@pytest.mark.asyncio
async def test_timeout_enforcement(executor):
    req = ToolExecutionRequest(
        tool_name="slow_tool",
        arguments={"seconds": 0.5},
    )
    res = await executor.execute(req)
    assert res.success is False
    assert "timed out after 0.1 seconds" in res.error


@pytest.mark.asyncio
async def test_secret_scrubbing_in_output(executor):
    req = ToolExecutionRequest(
        tool_name="echo",
        arguments={"message": "Here is my key: sk-abcdefghijklmnopqrstuvwxyz123456789"},
    )
    res = await executor.execute(req)
    assert res.success is True
    assert "sk-" not in res.result["echo"]
    assert "[REDACTED_API_KEY]" in res.result["echo"]


@pytest.mark.asyncio
async def test_unknown_tool(executor):
    req = ToolExecutionRequest(
        tool_name="non_existent_tool",
        arguments={},
    )
    res = await executor.execute(req)
    assert res.success is False
    assert "not registered" in res.error
