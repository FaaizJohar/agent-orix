"""
Tests for CIE Skills Registry.
"""

import pytest
from pydantic import BaseModel
from cie.skills.schemas import PermissionLevel, RiskLevel, ToolDefinition
from cie.skills.registry import SkillRegistry, SkillRegistryError, get_default_registry


class DummyInput(BaseModel):
    name: str


class DummyOutput(BaseModel):
    greeting: str


def dummy_tool(name: str) -> DummyOutput:
    return DummyOutput(greeting=f"Hello, {name}!")


def test_registry_registration_and_lookup():
    reg = SkillRegistry()
    tool_def = ToolDefinition(
        name="test_dummy",
        display_name="Test Dummy",
        description="A test tool",
        permission=PermissionLevel.READ_ONLY,
        input_model=DummyInput,
        output_model=DummyOutput,
    )
    reg.register(tool_def, dummy_tool)

    assert reg.get_tool("test_dummy") is not None
    assert reg.get_handler("test_dummy") == dummy_tool
    assert reg.get_tool("non_existent") is None


def test_duplicate_registration_fails():
    reg = SkillRegistry()
    tool_def = ToolDefinition(
        name="duplicate_tool",
        display_name="Duplicate",
        description="A test tool",
        permission=PermissionLevel.READ_ONLY,
    )
    reg.register(tool_def, dummy_tool)
    with pytest.raises(SkillRegistryError, match="already registered"):
        reg.register(tool_def, dummy_tool)


def test_list_tools_filtering():
    reg = SkillRegistry()
    reg.register(
        ToolDefinition(name="read_tool", display_name="R", description="", permission=PermissionLevel.READ_ONLY),
        dummy_tool,
    )
    reg.register(
        ToolDefinition(name="net_tool", display_name="N", description="", permission=PermissionLevel.NETWORK_READ),
        dummy_tool,
    )

    all_tools = reg.list_tools()
    assert len(all_tools) == 2

    read_only = reg.list_tools(permission=PermissionLevel.READ_ONLY)
    assert len(read_only) == 1
    assert read_only[0].name == "read_tool"

    reg.set_enabled("read_tool", False)
    enabled_tools = reg.list_tools(enabled_only=True)
    assert len(enabled_tools) == 1
    assert enabled_tools[0].name == "net_tool"


def test_default_registry_contains_16_tools():
    reg = get_default_registry()
    tools = reg.list_tools(enabled_only=False)
    assert len(tools) >= 16

    expected_tools = [
        "python_ast_validate",
        "json_validate",
        "yaml_validate",
        "markdown_check",
        "markdown_to_text",
        "git_status",
        "git_diff_summary",
        "file_tree_inspect",
        "readme_extract",
        "python_project_inspect",
        "dependency_inspect",
        "test_discover",
        "log_parse_errors",
        "file_integrity_verify",
        "http_endpoint_check",
        "github_repo_inspect",
    ]
    for exp in expected_tools:
        tool = reg.get_tool(exp)
        assert tool is not None, f"Tool '{exp}' missing from default registry"
        assert reg.get_handler(exp) is not None
