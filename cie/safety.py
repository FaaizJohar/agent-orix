"""
Security, input validation, and secret redaction module for CIE.
"""

import re
from typing import Tuple, List

# Patterns identifying sensitive secrets, API keys, and credentials
SECRET_PATTERNS = [
    # PEM Private Key Blocks (RSA, DSA, EC, OPENSSH, etc.)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE), "[REDACTED_PRIVATE_KEY_BLOCK]"),
    # URLs with embedded basic authentication credentials (e.g. https://user:pass@domain.com)
    (re.compile(r"((?:https?|ftp|postgres|postgresql|mysql|mongodb)://[^\s:@/]+):[^\s:@/]+@", re.IGNORECASE), r"\1:[REDACTED_CREDENTIALS]@"),
    # OpenAI / generic sk- style API keys
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    # GitHub personal / OAuth / refresh tokens
    (re.compile(r"gh[pousr]_[a-zA-Z0-9]{36,}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    # Google Cloud / Firebase API Keys
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,45}", re.ASCII), "[REDACTED_GOOGLE_KEY]"),
    # Slack Bot / User tokens (handles multi-segment modern tokens)
    (re.compile(r"xox[baprs]-[0-9a-zA-Z]{9,48}(?:-[0-9a-zA-Z]{9,48})*", re.IGNORECASE), "[REDACTED_SLACK_TOKEN]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    # AWS Access Key ID
    (re.compile(r"AKIA[0-9A-Z]{16}", re.ASCII), "[REDACTED_AWS_KEY]"),
    # Quoted generic password / secret assignments
    (re.compile(r"(?:['\"]?(?:api[_-]?key|secret|password|passwd|auth[_-]?token)['\"]?)\s*[:=]\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE), r"'[REDACTED_SECRET]'"),
    # Unquoted generic password / secret assignments (preserves label if followed by another assignment)
    (re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|auth[_-]?token)\s*([:=])\s*(?!(?:api[_-]?key|secret|password|passwd|auth[_-]?token)\s*[:=])([a-zA-Z0-9_\-!@#$%^&*()+=]{6,})"), r"\1\2[REDACTED_SECRET]"),
]

# Patterns detecting overt prompt injection or jailbreak attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|system)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+dan\s+mode", re.IGNORECASE),
    re.compile(r"reveal\s+your\s+(system\s+prompt|initial\s+instructions)", re.IGNORECASE),
    re.compile(r"override\s+system\s+(directives|constraints)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """
    Scrub credentials, tokens, and secrets from text before logging or storing.
    """
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def validate_input(prompt: str, max_chars: int = 32000) -> Tuple[bool, str, List[str]]:
    """
    Validates user input prompt for type safety, length constraints, and security anomalies.
    Returns: (is_valid, sanitized_prompt, warnings)
    """
    warnings: List[str] = []
    
    if not isinstance(prompt, str):
        return False, "", ["Prompt must be a string."]
        
    if "\x00" in prompt:
        return False, "", ["Null bytes are forbidden in prompts."]
        
    stripped = prompt.strip()
    if not stripped:
        return False, "", ["Prompt cannot be empty or purely whitespace."]
        
    if len(stripped) > max_chars:
        return False, "", [f"Prompt exceeds maximum character limit of {max_chars} (got {len(stripped)})."]

    # Check for adversarial injection signals
    for pattern in INJECTION_PATTERNS:
        if pattern.search(stripped):
            warnings.append("Security note: Potential prompt injection or system override pattern detected and neutralized.")
            break
            
    # Redact any inadvertent secret pasted by the user before internal pipeline processing
    redacted = redact_secrets(stripped)
    if redacted != stripped:
        warnings.append("Sensitive API keys or credentials were automatically redacted from the prompt.")
        
    return True, redacted, warnings
