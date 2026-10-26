"""
Desktop application allowlist, prohibited window barriers, and consequential action classifier.
Prevents computer-use tools from accessing system shells, password managers, or administrative consoles.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Set, Tuple

from cie.safety import redact_secrets
from cie.security_tokens import verify_action_token

logger = logging.getLogger("cie.desktop.security")


class DesktopSecurityError(Exception):
    pass


PROHIBITED_PROCESSES: Set[str] = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "bash.exe",
    "wsl.exe",
    "regedit.exe",
    "taskmgr.exe",
    "mmc.exe",
    "services.exe",
    "secpol.exe",
    "conhost.exe",
    "1password.exe",
    "bitwarden.exe",
    "keepass.exe",
}

PROHIBITED_WINDOW_PATTERNS = [
    r"\badministrator\b",
    r"\buser account control\b",
    r"\buac\b",
    r"\bregistry editor\b",
    r"\bwindows powershell\b",
    r"\bcommand prompt\b",
    r"\btask manager\b",
    r"\bcredential manager\b",
    r"\bcomputer management\b",
]

ALLOWED_PROCESS_NAMES: Set[str] = {
    "electron.exe",
    "nox ai.exe",
    "cavrix flow.exe",
    "code.exe",
    "notepad.exe",
    "calc.exe",
    "calculatorapp.exe",
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "explorer.exe",
    "python.exe",
    "pytest.exe",
}

CONSEQUENTIAL_KEYWORDS = [
    "submit", "pay", "purchase", "order", "buy", "checkout",
    "delete", "remove", "erase", "destroy", "drop", "format",
    "send email", "send message", "send", "post", "publish",
    "install", "uninstall", "change password", "update credential",
    "transfer", "confirm payment", "kill", "terminate",
    "rm ", "rm -rf", "sudo", "password", "secret",
]


class DesktopSecurityManager:
    """
    Enforces application allowlists, window isolation barriers,
    and action-bound approval tokens for OS-level interactions.
    """

    @classmethod
    def is_window_permitted(
        cls,
        title: str,
        process_name: str,
    ) -> Tuple[bool, str]:
        """
        Validates whether a window is safe to inspect and interact with.
        Fails closed if the process or title matches administrative consoles,
        system shells, or password managers.
        """
        proc_clean = (process_name or "").strip().lower()
        title_clean = (title or "").strip().lower()

        # 1. Check prohibited process blacklist
        if proc_clean in PROHIBITED_PROCESSES:
            return False, f"Access to system shell or administrative process '{process_name}' is strictly prohibited."

        # 2. Check prohibited title patterns (e.g. UAC, Registry Editor, Admin shells)
        for pattern in PROHIBITED_WINDOW_PATTERNS:
            if re.search(pattern, title_clean, re.IGNORECASE):
                return False, f"Window title '{redact_secrets(title)}' matches prohibited administrative pattern '{pattern}'."

        # 3. Check application allowlist
        if ALLOWED_PROCESS_NAMES:
            if proc_clean and proc_clean not in ALLOWED_PROCESS_NAMES:
                # If process name is known and not on allowlist, block interaction
                return False, f"Process '{process_name}' is not in the desktop application allowlist."

        return True, ""

    @classmethod
    def is_consequential_desktop_action(
        cls,
        action_type: str,
        window_title: Optional[str] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
        explicit_flag: bool = False,
    ) -> Tuple[bool, str]:
        """
        Determines whether a desktop interaction is consequential and requires explicit user approval.
        """
        if explicit_flag:
            return True, "Action was explicitly flagged as consequential."

        combined = f"{action_type} {window_title or ''} {text or ''} {key or ''}".lower()

        for kw in CONSEQUENTIAL_KEYWORDS:
            if kw in combined:
                return True, f"Action target or parameters match consequential keyword '{kw}'."

        # Special consequential keys: Enter on sensitive forms, Ctrl+W or Alt+F4 to close windows
        if key and key.lower() in ("enter", "return") and any(w in (text or "").lower() for w in ("rm ", "del ", "delete", "format")):
            return True, f"Keypress '{key}' triggers execution of dangerous command text."

        return False, ""

    @staticmethod
    def verify_action_token(
        tool_name: str,
        arguments: Dict[str, Any],
        provided_token: Optional[str],
        session_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies that an unforgeable, action-bound approval token matches the canonical desktop payload.
        Ensures a model-supplied boolean alone cannot authorize consequential desktop actions.
        """
        return verify_action_token(
            tool_name=tool_name,
            arguments=arguments,
            provided_token=provided_token,
            session_id=session_id,
        )
