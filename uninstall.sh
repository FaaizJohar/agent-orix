#!/usr/bin/env bash
# ==============================================================================
# Agent Orix - Uninstaller for macOS & Linux
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "                   AGENT ORIX - UNINSTALLER"
echo "======================================================================"
echo ""
echo "This will safely remove:"
echo " - Isolated virtual environment (.venv)"
echo " - Generated build and test artifacts"
echo " - Local run-orix.sh launcher"
echo ""
echo "Your personal project files and git repository will NOT be affected."
echo ""

if [ "$NON_INTERACTIVE" != "1" ]; then
    read -p "Are you sure you want to uninstall Agent Orix environment? (y/N): " -r CONFIRM || true
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
fi

echo "Removing virtual environment..."
rm -rf "$SCRIPT_DIR/.venv"

echo "Cleaning build and cache directories..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR/"*.egg-info "$SCRIPT_DIR/.pytest_cache"

if [ -f "$SCRIPT_DIR/run-orix.sh" ]; then
    rm -f "$SCRIPT_DIR/run-orix.sh"
fi

echo ""
echo "[OK] Agent Orix has been successfully uninstalled from this directory."
