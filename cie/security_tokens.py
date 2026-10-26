"""
Cryptographically secure, unforgeable action approval tokens.
Binds tool name, canonical arguments, session ID, timestamp, expiration, and unique nonce.
Signed using a server-held HMAC-SHA256 secret key.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("cie.security_tokens")

# Server-held secret key: initialized securely from environment or 32 random bytes
_ENV_SECRET = os.environ.get("CAVRIX_APPROVAL_SECRET")
if _ENV_SECRET:
    _APPROVAL_SECRET_KEY = _ENV_SECRET.encode("utf-8")
else:
    _APPROVAL_SECRET_KEY = secrets.token_bytes(32)


def get_approval_secret_key() -> bytes:
    """Returns the server-held approval secret key."""
    return _APPROVAL_SECRET_KEY


def mask_token(token: Optional[str]) -> str:
    """Masks a token for safe inclusion in logs or error messages."""
    if not token:
        return "<NONE>"
    token_str = str(token).strip()
    if len(token_str) <= 12:
        return "<REDACTED>"
    return f"{token_str[:8]}...{token_str[-4:]}"


def compute_action_token(
    tool_name: str,
    arguments: Dict[str, Any],
    session_id: Optional[str] = None,
    ttl_seconds: int = 300,
) -> str:
    """
    Computes an unforgeable, HMAC-signed action approval token.
    Binds tool name, canonicalized arguments, session ID, timestamp, expiration, and nonce.
    """
    clean_args = {
        k: v for k, v in arguments.items()
        if k not in ("approval_token", "approved_by_user")
    }
    canonical_args = json.dumps(clean_args, sort_keys=True, separators=(",", ":"))
    args_hash = hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    now = int(time.time())
    payload = {
        "tool": str(tool_name).strip(),
        "args_hash": args_hash,
        "session_id": str(session_id or "").strip(),
        "iat": now,
        "exp": now + max(1, int(ttl_seconds)),
        "nonce": secrets.token_hex(8),
    }

    envelope_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    envelope_b64 = base64.urlsafe_b64encode(envelope_json.encode("utf-8")).decode("utf-8").rstrip("=")
    signature = hmac.new(_APPROVAL_SECRET_KEY, envelope_b64.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"{envelope_b64}.{signature}"


def verify_action_token(
    tool_name: str,
    arguments: Dict[str, Any],
    provided_token: Optional[str],
    session_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verifies that a provided approval token:
    1. Is non-empty and has valid format: <envelope>.<hmac_signature>
    2. Was signed with the server-held HMAC secret key (unforgeable)
    3. Matches the exact tool name (cross-action reuse defense)
    4. Matches the exact canonical arguments hash (tamper defense)
    5. Has not expired (short TTL defense)
    6. Matches the session ID if session_id is specified (cross-session reuse defense)

    Returns (is_valid, reason).
    """
    if not provided_token or not str(provided_token).strip():
        return False, (
            f"Consequential action blocked: Missing action-bound approval token for '{tool_name}'. "
            "A model-supplied boolean alone cannot authorize consequential actions."
        )

    token_str = str(provided_token).strip()
    parts = token_str.split(".")
    if len(parts) != 2:
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            "Invalid or forged approval token structure (missing cryptographic signature)."
        )

    envelope_b64, signature = parts

    # 1. Verify HMAC Signature
    expected_sig = hmac.new(_APPROVAL_SECRET_KEY, envelope_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            "Invalid or forged approval token (cryptographic signature verification failed)."
        )

    # 2. Decode Envelope
    try:
        padded_b64 = envelope_b64 + "=" * (-len(envelope_b64) % 4)
        envelope_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(envelope_bytes.decode("utf-8"))
    except Exception as e:
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            f"Malformed token payload: {e}"
        )

    # 3. Verify Tool Binding
    token_tool = payload.get("tool")
    if token_tool != tool_name:
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            f"Token was issued for tool '{token_tool}', not '{tool_name}'."
        )

    # 4. Verify Arguments Hash
    clean_args = {
        k: v for k, v in arguments.items()
        if k not in ("approval_token", "approved_by_user")
    }
    canonical_args = json.dumps(clean_args, sort_keys=True, separators=(",", ":"))
    expected_args_hash = hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()
    if payload.get("args_hash") != expected_args_hash:
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            "The target element or parameters do not match the approved token."
        )

    # 5. Verify Expiration
    exp = payload.get("exp", 0)
    now = time.time()
    if now > exp:
        return False, (
            f"Consequential action blocked: Action-bound approval token for tool '{tool_name}' has expired "
            f"(expired {int(now - exp)}s ago)."
        )

    # 6. Verify Session Binding
    token_session = payload.get("session_id", "").strip()
    req_session = str(session_id or "").strip()
    if req_session and token_session and req_session != token_session:
        return False, (
            f"Consequential action blocked: Action-bound approval token mismatch for tool '{tool_name}'. "
            f"Token was issued for session '{token_session}', but received '{req_session}'."
        )

    return True, ""
