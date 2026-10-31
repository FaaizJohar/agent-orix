"""
Phase 18 Comprehensive Verification Test Suite: Agent Orix CLI & Terminal Engine.
Verifies interactive commands, system diagnostics, session persistence, remote mode,
and multi-action orchestrator integration.
"""

import asyncio
import json
import os
import sys
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cie import __version__
from cie.cli.main import cli
from cie.cli.session import SessionManager, SessionState, MessageTurn
from cie.cli.doctor import (
    check_python_environment,
    check_host_resources,
    check_gguf_invariant,
    check_tool_registry,
    check_security_and_truth,
    run_diagnostics,
)
from cie.cli.client import LocalAgentClient, RemoteAgentClient
from cie.cli.terminal import TerminalChat


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_cli_version_flag(cli_runner):
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "Agent Orix version 1.0.0" in result.output


def test_cli_help_flag(cli_runner):
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Agent Orix" in result.output
    assert "chat" in result.output
    assert "doctor" in result.output
    assert "tools" in result.output
    assert "sessions" in result.output
    assert "run" in result.output


def test_cli_status(cli_runner):
    result = cli_runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "Agent Orix Runtime Status" in result.output
    assert "tool_count" in result.output


def test_cli_tools_list(cli_runner):
    result = cli_runner.invoke(cli, ["tools", "list"])
    assert result.exit_code == 0
    assert "Agent Orix Registered Tools" in result.output
    assert "python_ast_validate" in result.output


def test_cli_tools_list_json(cli_runner):
    result = cli_runner.invoke(cli, ["tools", "list", "--json-output"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 44
    assert any(t["name"] == "python_ast_validate" for t in data)


def test_cli_config(cli_runner):
    result = cli_runner.invoke(cli, ["config"])
    assert result.exit_code == 0
    assert "Agent Orix Configuration" in result.output
    assert "model_name" in result.output
    assert "cavrix-code:latest" in result.output


def test_doctor_unit_checks():
    # 1. Python environment
    py_ok, comp, det = check_python_environment()
    assert py_ok is True
    assert "3." in det

    # 2. Host Resources
    res = check_host_resources()
    assert len(res) == 2
    assert "RAM" in res[0][1]

    # 3. Model GGUF hash invariant
    g_ok, g_comp, g_det = check_gguf_invariant()
    assert g_ok is True
    assert "Verified bitwise" in g_det

    # 4. Tool Registry
    t_ok, t_comp, t_det = check_tool_registry()
    assert t_ok is True
    assert "registered tools" in t_det

    # 5. Security & Truth
    sec_checks = check_security_and_truth()
    assert len(sec_checks) == 2
    assert all(c[0] is True for c in sec_checks)


def test_session_manager(tmp_path):
    mgr = SessionManager(session_dir=tmp_path)
    state = mgr.create_session("test_sess_01", workspace=str(tmp_path))
    assert state.session_id == "test_sess_01"

    # Add messages
    turn1 = mgr.add_message("test_sess_01", "user", "Hello Orix!")
    assert turn1.role == "user"
    assert turn1.content == "Hello Orix!"

    # Secret redaction verification in session memory
    secret_text = "Here is my secret token: sk-live-1234567890abcdef1234567890abcdef"
    turn2 = mgr.add_message("test_sess_01", "user", secret_text)
    assert "sk-live-1234567890abcdef" not in turn2.content
    assert "[REDACTED" in turn2.content

    # Load session
    loaded = mgr.load_session("test_sess_01")
    assert loaded is not None
    assert len(loaded.messages) == 2

    # History retrieval
    hist = mgr.get_history("test_sess_01", limit=10)
    assert len(hist) == 2

    # List sessions
    all_sess = mgr.list_sessions()
    assert len(all_sess) == 1
    assert all_sess[0]["session_id"] == "test_sess_01"

    # Clear session
    assert mgr.clear_session("test_sess_01") is True
    assert mgr.load_session("test_sess_01") is None


@pytest.mark.asyncio
async def test_terminal_slash_commands(tmp_path):
    client = LocalAgentClient()
    terminal = TerminalChat(
        client=client,
        session_id="test_terminal_session",
        workspace=str(tmp_path),
        no_banner=True,
    )
    terminal.session_mgr = SessionManager(session_dir=tmp_path)
    terminal.session = terminal.session_mgr.create_session("test_terminal_session")

    # /help
    assert await terminal.handle_slash_command("/help") is True

    # /status
    assert await terminal.handle_slash_command("/status") is True

    # /tools
    assert await terminal.handle_slash_command("/tools") is True

    # /clear
    assert await terminal.handle_slash_command("/clear") is True
    assert terminal.session.session_id != "test_terminal_session"

    # /exit
    assert await terminal.handle_slash_command("/exit") is False


@pytest.mark.asyncio
async def test_remote_client_graceful_offline():
    client = RemoteAgentClient(endpoint_url="http://127.0.0.1:59999", timeout=1.0)
    health = await client.check_health()
    assert health["connected"] is False
    assert health["mode"] == "remote"

    chat_resp = await client.chat("Test prompt")
    assert chat_resp["status"] == "FAILED"
    assert "remote" in chat_resp["warnings"][0].lower() or "connection" in chat_resp["content"].lower()


def test_cli_connect_offline(cli_runner):
    result = cli_runner.invoke(cli, ["connect", "http://127.0.0.1:59999"])
    assert result.exit_code == 1
    assert "Connection failed" in result.output or "Failed to reach" in result.output
