#!/usr/bin/env bash
# ==============================================================================
# Agent Orix - Universal One-Click & One-Line Installer for macOS & Linux
# Supports both local execution and piped execution:
#   curl -sSL https://raw.githubusercontent.com/FaaizJohar/agent-orix/main/install.sh | bash
# ==============================================================================
set -e

# Detect if running from an existing repository or via remote pipe (curl | bash)
if [ -n "${BASH_SOURCE[0]}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    SCRIPT_DIR=""
fi

if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
    INSTALL_DIR="${ORIX_HOME:-$HOME/.agent-orix}"
    echo "======================================================================"
    echo "                    AGENT ORIX - INSTALLER"
    echo "       Conversational Terminal AI & Local Workspace Assistant"
    echo "======================================================================"
    echo "Setting up Agent Orix in: $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    if command -v git >/dev/null 2>&1; then
        if [ -d "$INSTALL_DIR/.git" ]; then
            echo "[*] Updating existing repository in $INSTALL_DIR..."
            git -C "$INSTALL_DIR" pull --quiet
        else
            echo "[*] Downloading Agent Orix repository..."
            git clone --depth 1 https://github.com/FaaizJohar/agent-orix.git "$INSTALL_DIR"
        fi
    else
        echo "[*] Downloading Agent Orix archive..."
        curl -sSL https://github.com/FaaizJohar/agent-orix/archive/refs/heads/main.tar.gz | tar -xz -C "$INSTALL_DIR" --strip-components=1
    fi
    SCRIPT_DIR="$INSTALL_DIR"
else
    echo "======================================================================"
    echo "                    AGENT ORIX - INSTALLER"
    echo "       Conversational Terminal AI & Local Workspace Assistant"
    echo "======================================================================"
fi

cd "$SCRIPT_DIR"
echo ""

# Step 1: Detect Python 3.10+
echo "[1/5] Checking Python installation..."
PYTHON_BIN=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON_BIN="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3.10 or newer was not detected."
    echo "Please install Python 3.10+ from https://www.python.org/downloads/ or your package manager:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    echo "  macOS (Homebrew): brew install python@3.11"
    exit 1
fi

PY_VER="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
echo "[OK] Detected Python $PY_VER at $(command -v $PYTHON_BIN)"

# Step 2: Create isolated virtual environment
echo ""
echo "[2/5] Setting up isolated Python environment .venv..."
VENV_DIR="$SCRIPT_DIR/.venv"
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]; then
    echo "[OK] Existing virtual environment found at: $VENV_DIR"
else
    echo "Creating virtual environment in: $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created successfully."
fi

VENV_PY="$VENV_DIR/bin/python"

# Step 3: Install Agent Orix packages
echo ""
echo "[3/5] Installing Agent Orix packages and dependencies..."
"$VENV_PY" -m pip install -e "$SCRIPT_DIR"
echo "[OK] Agent Orix installed in editable mode."

# Step 4: Check Ollama & Model
echo ""
echo "[4/5] Checking local AI runtime Ollama..."
OLLAMA_FOUND=0
MODEL_FOUND=0
if command -v curl >/dev/null 2>&1; then
    TAGS_JSON=$(curl -s --connect-timeout 2 http://127.0.0.1:11434/api/tags 2>/dev/null || true)
    if [ -n "$TAGS_JSON" ]; then
        OLLAMA_FOUND=1
        if echo "$TAGS_JSON" | grep -qi "cavrix-code"; then
            MODEL_FOUND=1
        fi
    fi
fi

if [ "$OLLAMA_FOUND" -eq 1 ]; then
    echo "[OK] Ollama service detected running on http://127.0.0.1:11434"
    if [ "$MODEL_FOUND" -eq 1 ]; then
        echo "[OK] Target AI model 'cavrix-code:latest' is available in Ollama."
    else
        echo "[NOTE] Ollama is running, but model 'cavrix-code:latest' was not found in tags."
        echo "       Orix can run tools offline, or you can point to another model via:"
        echo "       export CIE_MODEL_NAME=your-model-name"
    fi
else
    echo "[INFO] Ollama local service was not detected on localhost:11434."
    echo "       Orix can run in standalone tool/scripting mode right away."
    echo "       For full conversational AI chat, install and run Ollama from: https://ollama.com/"
fi

# Step 5: Create launcher
echo ""
echo "[5/5] Creating launcher scripts..."
cat << 'EOF' > "$SCRIPT_DIR/run-orix.sh"
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" -m cie.cli.main "$@"
else
    exec python3 -m cie.cli.main "$@"
fi
EOF
chmod +x "$SCRIPT_DIR/run-orix.sh"
echo "[OK] Created launcher: $SCRIPT_DIR/run-orix.sh"

if [ -d "$HOME/.local/bin" ] || mkdir -p "$HOME/.local/bin" 2>/dev/null; then
    ln -sf "$SCRIPT_DIR/run-orix.sh" "$HOME/.local/bin/orix"
    echo "[OK] Created command: $HOME/.local/bin/orix"
fi

echo ""
echo "======================================================================"
echo "                     INSTALLATION COMPLETE!"
echo "======================================================================"
echo ""
echo "You can start Agent Orix anytime by running:"
echo "  $SCRIPT_DIR/run-orix.sh"
if [ -f "$HOME/.local/bin/orix" ]; then
    echo "or simply:"
    echo "  orix"
fi
echo ""

if [ "$NON_INTERACTIVE" = "1" ]; then
    exit 0
fi

if [ -t 0 ]; then
    read -p "Would you like to launch Agent Orix now? (y/N): " -r LAUNCH_NOW || true
    if [[ "$LAUNCH_NOW" =~ ^[Yy]$ ]]; then
        exec "$SCRIPT_DIR/run-orix.sh"
    fi
fi
