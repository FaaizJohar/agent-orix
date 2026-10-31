"""
Agent Orix Main Command-Line Interface.
Primary user-facing executable entry point for terminal interaction, diagnostics, and tools.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cie import __version__
from cie.cli.banner import render_banner
from cie.cli.client import LocalAgentClient, RemoteAgentClient
from cie.cli.session import SessionManager


if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
console = Console(legacy_windows=False)


def _get_client(remote: Optional[str] = None, token: Optional[str] = None):
    if remote:
        return RemoteAgentClient(endpoint_url=remote, auth_token=token)
    return LocalAgentClient()


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show Agent Orix version and exit.")
@click.option("--no-banner", is_flag=True, help="Disable banner when launching chat.")
@click.option("--remote", help="URL of remote CIE service.")
@click.option("--token", help="Bearer token for remote CIE service.")
@click.pass_context
def cli(ctx, version: bool, no_banner: bool, remote: Optional[str], token: Optional[str]):
    """
    Agent Orix — Interactive Terminal AI & Multi-Action Engine.
    """
    if version:
        console.print(f"[bold cyan]Agent Orix[/bold cyan] version [bold white]{__version__}[/bold white]")
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        # Default behavior when running `orix` directly: launch interactive chat
        ctx.invoke(chat, no_banner=no_banner, remote=remote, token=token)


@cli.command("chat")
@click.option("--session-id", "-s", help="Resume or specify conversation session ID.")
@click.option("--workspace", "-w", default=None, help="Target workspace path.")
@click.option("--no-banner", is_flag=True, help="Suppress ASCII art banner.")
@click.option("--mascot", is_flag=True, help="Display full mascot ASCII art.")
@click.option("--remote", help="URL of remote CIE server.")
@click.option("--token", help="Authentication token for remote server.")
def chat(
    session_id: Optional[str],
    workspace: Optional[str],
    no_banner: bool,
    mascot: bool,
    remote: Optional[str],
    token: Optional[str],
):
    """
    Start an interactive persistent terminal chat session with Agent Orix.
    """
    from cie.cli.terminal import TerminalChat

    client = _get_client(remote, token)
    app = TerminalChat(
        client=client,
        session_id=session_id,
        workspace=workspace,
        no_banner=no_banner,
        show_mascot=mascot,
    )
    asyncio.run(app.start())


@cli.command("run")
@click.argument("prompt")
@click.option("--session-id", "-s", help="Conversation session ID.")
@click.option("--workspace", "-w", default=None, help="Target workspace path.")
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.option("--remote", help="URL of remote CIE server.")
@click.option("--token", help="Authentication token for remote server.")
def run(
    prompt: str,
    session_id: Optional[str],
    workspace: Optional[str],
    output_format: str,
    remote: Optional[str],
    token: Optional[str],
):
    """
    Execute a single-shot natural language instruction through Agent Orix.
    """
    client = _get_client(remote, token)
    sess_mgr = SessionManager()
    sid = session_id or f"run_{int(time_now := sys.modules['time'].time())}"
    ws = workspace or os.getcwd()

    sess_mgr.add_message(sid, "user", prompt, metadata={"workspace": ws})

    async def _execute():
        from cie.cli.agent import ConversationalAgent
        agent = ConversationalAgent(client=client, workspace=ws)
        return await agent.handle_message(prompt)

    content = asyncio.run(_execute())
    sess_mgr.add_message(sid, "assistant", content, metadata={"status": "COMPLETED"})

    if output_format == "json":
        click.echo(json.dumps({"content": content, "status": "COMPLETED"}, indent=2))
    else:
        from rich.markdown import Markdown
        console.print(Markdown(content))


@cli.command("doctor")
def doctor():
    """
    Run comprehensive health and environment diagnostics.
    """
    from cie.cli.doctor import run_diagnostics
    ok = run_diagnostics(console)
    if not ok:
        sys.exit(1)


@cli.command("status")
@click.option("--remote", help="URL of remote CIE server.")
@click.option("--token", help="Authentication token for remote server.")
def status(remote: Optional[str], token: Optional[str]):
    """
    Show current runtime status, Ollama connection, and host metrics.
    """
    client = _get_client(remote, token)
    health = asyncio.run(client.check_health())

    table = Table(title="Agent Orix Runtime Status", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    for k, v in health.items():
        table.add_row(str(k), str(v))

    console.print(table)


@cli.group("tools", invoke_without_command=True)
@click.pass_context
def tools_group(ctx):
    """
    Explore and inspect registered developer tools and capabilities.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(tools_list)


@tools_group.command("list")
@click.option("--category", "-c", help="Filter tools by category.")
@click.option("--json-output", is_flag=True, help="Print tools as JSON.")
def tools_list(category: Optional[str], json_output: bool):
    """
    List all available developer skills and action tools.
    """
    client = LocalAgentClient()
    tools = client.get_tools()

    if category:
        tools = [t for t in tools if category.lower() in t.get("category", "").lower()]

    if json_output:
        click.echo(json.dumps(tools, indent=2))
        return

    table = Table(title=f"Agent Orix Registered Tools ({len(tools)} total)", show_header=True, header_style="bold cyan")
    table.add_column("Tool Name", style="bold yellow", width=26)
    table.add_column("Category", style="cyan", width=14)
    table.add_column("Risk", style="magenta", width=10)
    table.add_column("Approval", style="red", width=10)
    table.add_column("Description")

    for t in tools:
        approval_str = "Required" if t.get("requires_approval") else "Auto"
        table.add_row(
            t.get("name", ""),
            t.get("category", "general"),
            t.get("risk_level", "low"),
            approval_str,
            t.get("description", "")[:60] + "..." if len(t.get("description", "")) > 60 else t.get("description", ""),
        )

    console.print(table)


@cli.command("config")
def show_config():
    """
    Show active configuration with secrets safely redacted.
    """
    from cie.config import get_config
    from cie.safety import redact_secrets

    cfg = get_config()
    cfg_dict = cfg.model_dump()

    table = Table(title="Agent Orix Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    sensitive_suffixes = ("_key", "_secret", "_token", "_password", "api_key", "secret_key")
    for k, v in cfg_dict.items():
        v_str = str(v)
        if any(k.lower().endswith(s) or k.lower() == s for s in sensitive_suffixes):
            v_str = "********"
        else:
            v_str = redact_secrets(v_str)
        table.add_row(k, v_str)

    console.print(table)


@cli.group("sessions")
def sessions_group():
    """
    Manage conversation sessions and context history.
    """
    pass


@sessions_group.command("list")
def list_sessions():
    """
    List past conversation sessions.
    """
    mgr = SessionManager()
    sessions = mgr.list_sessions()

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title=f"Stored Sessions ({len(sessions)})", show_header=True, header_style="bold cyan")
    table.add_column("Session ID", style="bold yellow")
    table.add_column("Messages", justify="center")
    table.add_column("Last Active", style="dim")
    table.add_column("Workspace")

    for s in sessions:
        import time
        updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.get("updated_at", 0)))
        table.add_row(s.get("session_id", ""), str(s.get("message_count", 0)), updated, str(s.get("workspace", "")))

    console.print(table)


@sessions_group.command("clear")
@click.argument("session_id")
def clear_session(session_id: str):
    """
    Delete a saved conversation session.
    """
    mgr = SessionManager()
    if mgr.clear_session(session_id):
        console.print(f"[green]Session '{session_id}' cleared successfully.[/green]")
    else:
        console.print(f"[red]Session '{session_id}' not found or could not be removed.[/red]")


@cli.command("connect")
@click.argument("url")
@click.option("--token", help="Optional authentication bearer token.")
def connect_test(url: str, token: Optional[str]):
    """
    Test and validate connection to a remote CIE server.
    """
    console.print(f"[cyan]Testing connection to {url}...[/cyan]")
    client = RemoteAgentClient(endpoint_url=url, auth_token=token)
    try:
        health = asyncio.run(client.check_health())
        if health.get("connected"):
            console.print(Panel(
                f"[bold green]Successfully connected to remote CIE instance![/bold green]\n\n"
                f"Latency: {health.get('latency_ms')} ms\n"
                f"Status: {health.get('status', 'OK')}\n"
                f"Model: {health.get('model_name', 'unknown')}\n"
                f"Version: {health.get('version', 'unknown')}",
                title="Remote Connection Test",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[bold red]Connection failed.[/bold red]\n\n"
                f"Status code: {health.get('status_code')}\n"
                f"Error: {health.get('error')}",
                title="Remote Connection Test",
                border_style="red",
            ))
            sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to reach {url}:[/bold red] {e}")
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
