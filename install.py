#!/usr/bin/env python3
"""
Agent Orix - Universal Cross-Platform One-Click Installer
Supports Windows, macOS, Linux, and Unix-like operating systems.
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import urllib.request
import venv
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

def log_header():
    print("=" * 70)
    print("                    AGENT ORIX - UNIVERSAL INSTALLER")
    print("       Conversational Terminal AI & Local Workspace Assistant")
    print("=" * 70)
    print()

def check_python_version():
    print("[1/5] Checking Python environment...")
    v = sys.version_info
    v_str = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        print(f"[ERROR] Python {v_str} detected. Agent Orix requires Python 3.10 or newer.")
        print("Please download and install Python 3.10+ from: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"[OK] Python {v_str} ({platform.architecture()[0]}) running on {platform.system()}")

def setup_virtualenv() -> Path:
    print("\n[2/5] Setting up isolated Python environment (.venv)...")
    venv_dir = SCRIPT_DIR / ".venv"
    if sys.platform == "win32":
        venv_py = venv_dir / "Scripts" / "python.exe"
    else:
        venv_py = venv_dir / "bin" / "python"

    if venv_py.exists():
        print(f"[OK] Existing virtual environment found at: {venv_dir}")
    else:
        print(f"Creating isolated environment at: {venv_dir}")
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_dir)
        print("[OK] Virtual environment created successfully.")

    return venv_py

def install_dependencies(venv_py: Path):
    print("\n[3/5] Installing Agent Orix and core dependencies in editable mode...")
    cmd = [str(venv_py), "-m", "pip", "install", "-e", str(SCRIPT_DIR)]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("[ERROR] Failed to install dependencies. Please check network connection.")
        sys.exit(1)
    print("[OK] Agent Orix installed successfully.")

def check_ollama_runtime():
    print("\n[4/5] Checking local AI runtime (Ollama)...")
    ollama_url = "http://127.0.0.1:11434/api/tags"
    try:
        req = urllib.request.Request(ollama_url, headers={"User-Agent": "AgentOrixInstaller/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                has_model = any("cavrix-code" in m for m in models)
                print(f"[OK] Ollama local service detected with {len(models)} model(s).")
                if has_model:
                    print("[OK] Target AI model 'cavrix-code:latest' is available in Ollama.")
                else:
                    print("[NOTE] Ollama is online, but model 'cavrix-code:latest' was not found.")
                    print("       Orix will run tools offline or you can configure another model via:")
                    print("       set CIE_MODEL_NAME=your-model-name (Windows) or export CIE_MODEL_NAME=... (Unix)")
                return
    except Exception:
        pass

    print("[INFO] Ollama local service not detected on localhost:11434.")
    print("       Agent Orix will operate in standalone tool & inspection mode immediately.")
    print("       For full conversational AI chat, download and run Ollama from: https://ollama.com/")

def create_launchers(venv_py: Path):
    print("\n[5/5] Creating device-specific launchers...")
    if sys.platform == "win32":
        launcher_bat = SCRIPT_DIR / "run-orix.bat"
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul 2>&1\r\n"
            "set \"SCRIPT_DIR=%~dp0\"\r\n"
            "if \"%SCRIPT_DIR:~-1%\"==\"\\\" set \"SCRIPT_DIR=%SCRIPT_DIR:~0,-1%\"\r\n"
            "\"%SCRIPT_DIR%\\.venv\\Scripts\\python.exe\" -m cie.cli.main %*\r\n"
        )
        with open(launcher_bat, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] Created launcher: {launcher_bat}")
    else:
        launcher_sh = SCRIPT_DIR / "run-orix.sh"
        content = (
            "#!/usr/bin/env bash\n"
            "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
            "exec \"$SCRIPT_DIR/.venv/bin/python\" -m cie.cli.main \"$@\"\n"
        )
        with open(launcher_sh, "w", encoding="utf-8") as f:
            f.write(content)
        launcher_sh.chmod(0o755)
        print(f"[OK] Created launcher: {launcher_sh}")

def main():
    log_header()
    check_python_version()
    venv_py = setup_virtualenv()
    install_dependencies(venv_py)
    check_ollama_runtime()
    create_launchers(venv_py)

    print("\n" + "=" * 70)
    print("                     INSTALLATION COMPLETE!")
    print("=" * 70)
    if sys.platform == "win32":
        print("\nYou can launch Agent Orix anytime by running:\n  .\\run-orix.bat")
    else:
        print("\nYou can launch Agent Orix anytime by running:\n  ./run-orix.sh")
    print()

    is_non_interactive = os.environ.get("NON_INTERACTIVE") == "1" or "--non-interactive" in sys.argv
    if not is_non_interactive:
        try:
            launch = input("Would you like to launch Agent Orix now? (y/N): ").strip().lower()
            if launch == "y":
                print("Launching Agent Orix...\n")
                subprocess.run([str(venv_py), "-m", "cie.cli.main"])
        except (KeyboardInterrupt, EOFError):
            print("\nSetup exited cleanly.")

if __name__ == "__main__":
    main()
