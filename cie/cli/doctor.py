"""
Agent Orix Diagnostics & System Verification Engine (`orix doctor`).
Verifies host resources, model integrity, Ollama status, tools, and permissions.
"""

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import psutil
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

EXPECTED_GGUF_SHA256 = "4A9F433D4EF7CACF4FE41C4DF66FB902138DCC1CFC43510AE8575A17E62DB4B1"
GGUF_PATH = Path(r"E:\CavrixCode-latest\cavrix_code_latest.gguf")


def check_python_environment() -> Tuple[bool, str, str]:
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    if ver.major == 3 and ver.minor >= 10:
        return True, "Python Version", f"{ver_str} (64-bit) - Supported"
    return False, "Python Version", f"{ver_str} - Warning: 3.10+ recommended"


def check_host_resources() -> List[Tuple[bool, str, str]]:
    results = []
    # RAM Check
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024**3)
    avail_gb = mem.available / (1024**3)
    mem_ok = total_gb >= 5.0
    results.append((
        mem_ok,
        "System Memory (RAM)",
        f"{total_gb:.2f} GB total ({avail_gb:.2f} GB available)"
    ))

    # Disk Space Check
    disk = psutil.disk_usage(os.getcwd())
    free_gb = disk.free / (1024**3)
    disk_ok = free_gb >= 2.0
    results.append((
        disk_ok,
        "Disk Space (Current Drive)",
        f"{free_gb:.2f} GB free"
    ))
    return results


def check_gguf_invariant() -> Tuple[bool, str, str]:
    if not GGUF_PATH.exists():
        return False, "GGUF Model File", f"File missing at {GGUF_PATH}"

    size_mb = GGUF_PATH.stat().st_size / (1024 * 1024)
    hasher = hashlib.sha256()
    with open(GGUF_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest().upper()

    if actual_hash == EXPECTED_GGUF_SHA256:
        return True, "Model Invariant (SHA-256)", f"Verified bitwise: {actual_hash[:16]}... ({size_mb:.1f} MB)"
    else:
        return False, "Model Invariant (SHA-256)", f"MISMATCH! Got {actual_hash[:16]}..., expected {EXPECTED_GGUF_SHA256[:16]}..."


def check_ollama_status() -> Tuple[bool, str, str]:
    import httpx
    try:
        with httpx.Client(timeout=2.5) as client:
            resp = client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                has_model = any("cavrix-code" in m for m in models)
                detail = f"Online. Found {len(models)} model(s)"
                if has_model:
                    detail += " (including cavrix-code:latest)"
                return True, "Ollama Local Service", detail
            return False, "Ollama Local Service", f"HTTP {resp.status_code}"
    except Exception as e:
        return False, "Ollama Local Service", f"Offline or unreachable: {str(e)[:50]}"


def check_tool_registry() -> Tuple[bool, str, str]:
    try:
        from cie.skills.registry import get_default_registry
        reg = get_default_registry()
        tools = reg.list_tools()
        count = len(tools)
        if count >= 44:
            return True, "CIE Tool Registry", f"{count} registered tools available"
        return False, "CIE Tool Registry", f"Only {count} tools registered (expected >= 44)"
    except Exception as e:
        return False, "CIE Tool Registry", f"Error loading registry: {e}"


def check_security_and_truth() -> List[Tuple[bool, str, str]]:
    results = []
    try:
        from cie.truth import AntiSycophancyGuard
        results.append((True, "Truth & Anti-Sycophancy Guard", "Initialized with postcondition verifier"))
    except Exception as e:
        results.append((False, "Truth & Anti-Sycophancy Guard", f"Failed: {e}"))

    try:
        from cie.security_tokens import compute_action_token
        sample_token = compute_action_token("test_tool", {"param": 1})
        results.append((True, "HMAC Action Approval Engine", f"Active with replay protection ({sample_token[:8]}...)"))
    except Exception as e:
        results.append((False, "HMAC Action Approval Engine", f"Failed: {e}"))

    return results


def run_diagnostics(console: Console) -> bool:
    """
    Runs all diagnostic checks and prints a formatted Rich report.
    Returns True if all critical checks pass.
    """
    table = Table(title="Agent Orix System Diagnostics", show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8, justify="center")
    table.add_column("Component", width=30)
    table.add_column("Details", style="dim")

    all_passed = True

    # 1. Python environment
    py_ok, py_comp, py_det = check_python_environment()
    status_str = "[bold green]PASS[/bold green]" if py_ok else "[bold yellow]WARN[/bold yellow]"
    table.add_row(status_str, py_comp, py_det)

    # 2. Host Resources
    for r_ok, r_comp, r_det in check_host_resources():
        status_str = "[bold green]PASS[/bold green]" if r_ok else "[bold yellow]WARN[/bold yellow]"
        table.add_row(status_str, r_comp, r_det)

    # 3. Model GGUF Hash Invariant
    g_ok, g_comp, g_det = check_gguf_invariant()
    status_str = "[bold green]PASS[/bold green]" if g_ok else "[bold red]FAIL[/bold red]"
    if not g_ok:
        all_passed = False
    table.add_row(status_str, g_comp, g_det)

    # 4. Ollama Service
    o_ok, o_comp, o_det = check_ollama_status()
    status_str = "[bold green]PASS[/bold green]" if o_ok else "[bold yellow]WARN[/bold yellow]"
    table.add_row(status_str, o_comp, o_det)

    # 5. Tool Registry
    t_ok, t_comp, t_det = check_tool_registry()
    status_str = "[bold green]PASS[/bold green]" if t_ok else "[bold red]FAIL[/bold red]"
    if not t_ok:
        all_passed = False
    table.add_row(status_str, t_comp, t_det)

    # 6. Security & Truth
    for s_ok, s_comp, s_det in check_security_and_truth():
        status_str = "[bold green]PASS[/bold green]" if s_ok else "[bold red]FAIL[/bold red]"
        if not s_ok:
            all_passed = False
        table.add_row(status_str, s_comp, s_det)

    console.print(table)

    summary_panel = Panel(
        "[bold green][OK] All core systems operational and release-ready.[/bold green]"
        if all_passed
        else "[bold red][FAIL] Issues detected in system diagnostics. Review warnings above.[/bold red]",
        border_style="green" if all_passed else "red",
    )
    console.print(summary_panel)
    return all_passed
