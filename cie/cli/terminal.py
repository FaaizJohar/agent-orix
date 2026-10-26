"""
Interactive Terminal Interface for Agent Orix (`orix` / `orix chat`).
Provides rich terminal styling, session continuity, slash commands, and approval prompts.
"""

import asyncio
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from cie.cli.banner import render_banner
from cie.cli.client import BaseAgentClient, LocalAgentClient, RemoteAgentClient
from cie.cli.session import SessionManager, SessionState
from cie.security_tokens import compute_action_token


class TerminalChat:
    """
    Rich interactive terminal session for Agent Orix.
    """

    def __init__(
        self,
        client: BaseAgentClient,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        no_banner: bool = False,
        show_mascot: bool = False,
    ):
        self.console = Console()
        self.client = client
        self.workspace = workspace or os.getcwd()
        self.no_banner = no_banner
        self.show_mascot = show_mascot

        self.session_mgr = SessionManager()
        if session_id:
            loaded = self.session_mgr.load_session(session_id)
            self.session = loaded if loaded else self.session_mgr.create_session(session_id, workspace=self.workspace)
        else:
            self.session = self.session_mgr.create_session(workspace=self.workspace)

    def print_help(self):
        table = Table(title="Agent Orix Interactive Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="bold yellow", width=18)
        table.add_column("Description")
        table.add_row("/help", "Show this help table")
        table.add_row("/clear", "Clear terminal screen and start fresh session context")
        table.add_row("/history", "Display recent conversation turns in current session")
        table.add_row("/tools", "List available developer skills and action tools")
        table.add_row("/workflow <type>", "Trigger multi-step workflow (doc, code, research)")
        table.add_row("/status", "Show engine health, RAM, model, and active session")
        table.add_row("/doctor", "Run comprehensive system diagnostics")
        table.add_row("/exit, /quit", "Exit the interactive session gracefully")
        self.console.print(table)

    def print_history(self):
        history = self.session_mgr.get_history(self.session.session_id, limit=20)
        if not history:
            self.console.print("[dim]No previous messages in this session.[/dim]")
            return
        self.console.print(f"[bold cyan]Session History ({len(history)} messages):[/bold cyan]")
        for msg in history:
            role_style = "bold green" if msg.role == "user" else "bold cyan"
            self.console.print(f"[{role_style}]{msg.role.upper()}[/{role_style}] [dim]({time.strftime('%H:%M:%S', time.localtime(msg.timestamp))}):[/dim]")
            self.console.print(Markdown(msg.content))
            self.console.print("-" * 40, style="dim")

    async def handle_slash_command(self, cmd_line: str) -> bool:
        parts = cmd_line.strip().split()
        cmd = parts[0].lower()

        if cmd in ("/exit", "/quit"):
            self.console.print("[cyan]Exiting Agent Orix. Goodbye![/cyan]")
            return False

        if cmd == "/help":
            self.print_help()
            return True

        if cmd == "/clear":
            self.console.clear()
            self.session = self.session_mgr.create_session(workspace=self.workspace)
            self.console.print(f"[green]Session cleared. New session ID: {self.session.session_id}[/green]")
            return True

        if cmd == "/history":
            self.print_history()
            return True

        if cmd == "/tools":
            tools = self.client.get_tools()
            table = Table(title=f"Registered Tools ({len(tools)} available)", show_header=True, header_style="bold cyan")
            table.add_column("Tool Name", style="bold yellow")
            table.add_column("Category", style="cyan")
            table.add_column("Risk", style="magenta")
            table.add_column("Approval", style="red")
            for t in tools[:25]:
                req_app = "YES" if t.get("requires_approval") else "No"
                table.add_row(t.get("name", ""), t.get("category", "general"), t.get("risk_level", "low"), req_app)
            self.console.print(table)
            if len(tools) > 25:
                self.console.print(f"[dim]... and {len(tools) - 25} more. Run 'orix tools list' for full catalog.[/dim]")
            return True

        if cmd == "/status":
            health = await self.client.check_health()
            self.console.print(Panel(
                f"[bold]Mode:[/bold] {health.get('mode', 'unknown')}\n"
                f"[bold]Ollama Connected:[/bold] {health.get('ollama_connected', False)}\n"
                f"[bold]Model:[/bold] {health.get('model_name', 'cavrix-code:latest')}\n"
                f"[bold]Memory RSS:[/bold] {health.get('process_ram_mb', 0)} MB\n"
                f"[bold]Session ID:[/bold] {self.session.session_id}\n"
                f"[bold]Workspace:[/bold] {self.workspace}",
                title="Agent Orix Status",
                border_style="cyan",
            ))
            return True

        if cmd == "/doctor":
            from cie.cli.doctor import run_diagnostics
            run_diagnostics(self.console)
            return True

        if cmd == "/workflow":
            if len(parts) < 2:
                self.console.print("[yellow]Usage: /workflow <document|codebase|research> [target][/yellow]")
                return True
            wf_type = parts[1]
            target = parts[2] if len(parts) > 2 else ""
            params = {"document_path": target, "file_path": target, "topic": target}
            self.console.print(f"[bold cyan]Running workflow: {wf_type.upper()}...[/bold cyan]")
            try:
                with self.console.status("[bold cyan]Executing multi-step workflow...[/bold cyan]", spinner="dots"):
                    wf_res = await self.client.run_workflow(wf_type, params)
                summary = wf_res.get("summary", "")
                success = wf_res.get("success", False)
                style = "green" if success else "red"
                self.console.print(Panel(summary or str(wf_res), title=f"Workflow Result: {wf_type}", border_style=style))
            except Exception as e:
                self.console.print(f"[bold red]Workflow Error:[/bold red] {e}")
            return True

        self.console.print(f"[yellow]Unknown command '{cmd}'. Type /help for available commands.[/yellow]")
        return True

    def prompt_for_approval(self, action_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        self.console.print(Panel(
            f"[bold red]CRITICAL ACTION CONFIRMATION[/bold red]\n\n"
            f"Action: [bold yellow]{action_name}[/bold yellow]\n"
            f"Parameters: [dim]{params}[/dim]\n\n"
            f"This action may modify files or execute system processes in: {self.workspace}",
            border_style="red",
            title="Human Approval Barrier",
        ))
        approved = Confirm.ask("Do you authorize this action?", default=False)
        if approved:
            token = compute_action_token(action_name, params)
            return True, token
        return False, None

    async def start(self):
        """
        Runs the interactive chat loop.
        """
        if not self.no_banner:
            health = await self.client.check_health()
            render_banner(
                self.console,
                compact=True,
                show_mascot=self.show_mascot,
                model_name=health.get("model_name", "cavrix-code:latest"),
                tools_count=health.get("tool_count", 46),
                remote_url=getattr(self.client, "endpoint_url", None),
            )

        self.console.print(f"[dim]Active Session: {self.session.session_id} | Workspace: {self.workspace}[/dim]\n")

        while True:
            try:
                user_input = Prompt.ask("\n[bold green]orix[/bold green] [cyan]>[/cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[cyan]Session ended. Goodbye![/cyan]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                keep_going = await self.handle_slash_command(user_input)
                if not keep_going:
                    break
                continue

            # Record turn in session memory
            self.session_mgr.add_message(self.session.session_id, "user", user_input)

            # Execution with spinner status
            try:
                with self.console.status("[bold cyan]Agent Orix is reasoning...[/bold cyan]", spinner="dots"):
                    resp = await self.client.chat(
                        prompt=user_input,
                        session_id=self.session.session_id,
                        metadata={"workspace": self.workspace},
                    )

                content = resp.get("content", "")
                category = resp.get("category", "GENERAL")
                exec_time = resp.get("execution_time_ms", 0.0)
                status = resp.get("status", "COMPLETED")

                # Format and render response
                self.console.print(f"\n[bold cyan]Agent Orix[/bold cyan] [dim]({category} • {exec_time:.0f}ms)[/dim]:")
                self.console.print(Markdown(content))

                # Record assistant turn in session
                self.session_mgr.add_message(
                    self.session.session_id,
                    "assistant",
                    content,
                    metadata={"category": category, "execution_time_ms": exec_time, "status": status},
                )

            except Exception as e:
                self.console.print(f"[bold red]Execution Error:[/bold red] {e}")
