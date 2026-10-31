"""
Interactive Conversational Terminal for Agent Orix (`orix` / `orix chat`).
Provides a human-first conversational AI interface with live progress indicators,
multi-turn context, and cryptographic approval barriers.
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
from cie.cli.agent import ConversationalAgent
from cie.security_tokens import compute_action_token


class TerminalChat:
    """
    Conversation-first interactive terminal for Agent Orix.
    """

    def __init__(
        self,
        client: Optional[BaseAgentClient] = None,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        no_banner: bool = False,
        show_mascot: bool = False,
    ):
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        self.console = Console(legacy_windows=False)
        self.workspace = os.path.abspath(workspace or os.getcwd())
        self.client = client or LocalAgentClient()
        self.no_banner = no_banner
        self.show_mascot = show_mascot

        self.session_mgr = SessionManager()
        if session_id:
            loaded = self.session_mgr.load_session(session_id)
            self.session = loaded if loaded else self.session_mgr.create_session(session_id, workspace=self.workspace)
        else:
            self.session = self.session_mgr.create_session(workspace=self.workspace)

        # Conversational Agent Driver
        self.agent = ConversationalAgent(client=self.client, workspace=self.workspace)

    def print_startup_greeting(self):
        """Displays friendly conversational startup header with gradient ASCII banner."""
        render_banner(self.console, show_mascot=self.show_mascot)
        self.console.print("\n[bold white]Hey! I'm Orix. What are we working on today?[/bold white]\n")

    def print_help(self):
        table = Table(title="Agent Orix Conversational Shortcuts", show_header=True, header_style="bold cyan")
        table.add_column("Shortcut", style="bold yellow", width=18)
        table.add_column("Purpose")
        table.add_row("/help", "Show optional convenience commands")
        table.add_row("/clear", "Clear terminal screen and start fresh context")
        table.add_row("/history", "Display conversation history in current session")
        table.add_row("/tools", "List available developer skills and action tools")
        table.add_row("/status", "Show engine health, RAM, model, and active session")
        table.add_row("/doctor", "Run comprehensive system diagnostics")
        table.add_row("/exit, /quit", "Exit the conversation gracefully")
        self.console.print(table)
        self.console.print("\n[dim]Note: You do not need to memorize commands. You can simply chat with Orix naturally![/dim]")

    def print_history(self):
        history = self.session_mgr.get_history(self.session.session_id, limit=20)
        if not history:
            self.console.print("[dim]No previous messages in this session.[/dim]")
            return
        self.console.print(f"[bold cyan]Session History ({len(history)} messages):[/bold cyan]")
        for msg in history:
            role_style = "bold green" if msg.role == "user" else "bold cyan"
            label = "You" if msg.role == "user" else "Orix"
            self.console.print(f"[{role_style}]{label}[/{role_style}] [dim]({time.strftime('%H:%M:%S', time.localtime(msg.timestamp))}):[/dim]")
            self.console.print(Markdown(msg.content))
            self.console.print("-" * 40, style="dim")

    async def handle_slash_command(self, cmd_line: str) -> bool:
        parts = cmd_line.strip().split()
        cmd = parts[0].lower()

        if cmd in ("/exit", "/quit"):
            self.console.print("[cyan]Exiting Agent Orix. Catch you later![/cyan]")
            return False

        if cmd == "/help":
            self.print_help()
            return True

        if cmd == "/clear":
            self.console.clear()
            self.session = self.session_mgr.create_session(workspace=self.workspace)
            self.agent = ConversationalAgent(client=self.client, workspace=self.workspace)
            self.print_startup_greeting()
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

        self.console.print(f"[yellow]Unknown shortcut '{cmd}'. Type /help for optional shortcuts, or talk naturally.[/yellow]")
        return True

    def prompt_for_approval(self, action_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        self.console.print(Panel(
            f"[bold red]CRITICAL ACTION CONFIRMATION[/bold red]\n\n"
            f"Action: [bold yellow]{action_name}[/bold yellow]\n"
            f"Target Details: [dim]{params}[/dim]\n\n"
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
        Runs the persistent conversational chat loop.
        """
        if not self.no_banner:
            self.print_startup_greeting()
        else:
            self.console.print(f"[dim]Agent Orix active in workspace: {self.workspace}[/dim]\n")

        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/bold green] [cyan]>[/cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[cyan]Session ended. See you next time![/cyan]")
                break

            if not user_input:
                continue

            # Optional shortcut handling
            if user_input.startswith("/"):
                keep_going = await self.handle_slash_command(user_input)
                if not keep_going:
                    break
                continue

            # Record turn in persistent session storage
            self.session_mgr.add_message(self.session.session_id, "user", user_input)

            # Progress printer callback
            def show_progress(step_msg: str):
                self.console.print(f"[dim cyan]       {step_msg}[/dim cyan]")

            # Run conversational agent loop
            try:
                self.console.print("[bold cyan]Orix[/bold cyan] [cyan]>[/cyan] ", end="")
                reply = await self.agent.handle_message(
                    user_text=user_input,
                    on_progress=show_progress,
                    on_approval=self.prompt_for_approval,
                )
                self.console.print("")
                self.console.print(Markdown(reply))

                # Save assistant response in persistent session storage
                self.session_mgr.add_message(self.session.session_id, "assistant", reply)

            except Exception as e:
                self.console.print(f"\n[bold red]Orix encountered an error:[/bold red] {e}")
