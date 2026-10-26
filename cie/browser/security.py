"""
Security boundaries, SSRF prevention, alternate IP resolution, and consequential action classifier for Browser Automation.
"""

import hashlib
import ipaddress
import json
import re
import socket
import urllib.parse
from typing import Any, Dict, Optional, Set, Tuple

from cie.research.fetcher import FORBIDDEN_NETWORKS, SecurityValidationError
from cie.safety import redact_secrets
from cie.security_tokens import (
    compute_action_token,
    verify_action_token as verify_action_token_fn,
    mask_token,
)

CONSEQUENTIAL_KEYWORDS = [
    "submit", "pay", "purchase", "buy", "checkout", "order",
    "delete", "remove", "erase", "destroy", "drop",
    "send email", "send message", "publish", "post",
    "change password", "update credential", "transfer", "confirm payment"
]


class BrowserSecurityError(Exception):
    pass


def parse_alternate_ip(hostname: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """
    Parses alternate IP representations including decimal dwords (e.g. 2130706433),
    hexadecimal (0x7f000001), octal (0177.0.0.1), 2-part shorthand (127.1),
    and bracketed IPv6/IPv4-mapped notation ([::ffff:127.0.0.1]).
    Returns an ipaddress object if valid numeric representation, or None if DNS domain.
    """
    clean = hostname.strip("[]").strip()
    if not clean:
        return None

    # Check standard or mapped IPv6
    try:
        return ipaddress.ip_address(clean)
    except ValueError:
        pass

    # Check single integer (decimal or hex, e.g. 2130706433, 0x7f000001)
    if clean.isdigit() or clean.lower().startswith("0x"):
        try:
            val = int(clean, 0)
            if 0 <= val <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(val)
        except (ValueError, OverflowError):
            pass

    # Check dotted decimal/octal/hex components (e.g. 0177.0.0.1 or 0x7f.0.0.1)
    parts = clean.split(".")
    if len(parts) in (2, 3, 4):
        try:
            numeric_parts = []
            for p in parts:
                if p.lower().startswith("0x"):
                    numeric_parts.append(int(p, 16))
                elif p.startswith("0") and len(p) > 1 and p.isdigit():
                    numeric_parts.append(int(p, 8))
                elif p.isdigit():
                    numeric_parts.append(int(p, 10))
                else:
                    return None

            if len(numeric_parts) == 4 and all(0 <= x <= 255 for x in numeric_parts):
                dword = (numeric_parts[0] << 24) | (numeric_parts[1] << 16) | (numeric_parts[2] << 8) | numeric_parts[3]
                return ipaddress.IPv4Address(dword)
            elif len(numeric_parts) == 2 and 0 <= numeric_parts[0] <= 255 and 0 <= numeric_parts[1] <= 0xFFFFFF:
                dword = (numeric_parts[0] << 24) | numeric_parts[1]
                return ipaddress.IPv4Address(dword)
        except (ValueError, OverflowError):
            pass

    return None


def is_ip_forbidden(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Tuple[bool, str]:
    """
    Checks if an IP address belongs to loopback, private, link-local, carrier-grade NAT,
    cloud metadata, multicast, or any forbidden subnet.
    """
    # Check standard attributes
    if ip_obj.is_loopback:
        return True, f"Loopback address '{ip_obj}' is strictly prohibited."
    if ip_obj.is_private:
        return True, f"Private network address '{ip_obj}' is strictly prohibited."
    if ip_obj.is_link_local:
        return True, f"Link-local / cloud metadata address '{ip_obj}' is strictly prohibited."
    if ip_obj.is_multicast:
        return True, f"Multicast address '{ip_obj}' is prohibited."
    if ip_obj.is_reserved:
        return True, f"Reserved IP address '{ip_obj}' is prohibited."

    # Check mapped IPv4 if IPv6
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        mapped_v4 = ip_obj.ipv4_mapped
        if mapped_v4.is_loopback or mapped_v4.is_private or mapped_v4.is_link_local:
            return True, f"IPv4-mapped address '{ip_obj}' maps to forbidden private IPv4 '{mapped_v4}'."

    # Check against FORBIDDEN_NETWORKS
    for forbidden in FORBIDDEN_NETWORKS:
        if ip_obj in forbidden:
            return True, f"IP address '{ip_obj}' belongs to forbidden network '{forbidden}'."

    return False, ""


class BrowserSecurityManager:
    """
    Enforces URL destination safety, SSRF blocking, alternate IP parsing,
    and action-bound approval token verification.
    """

    @staticmethod
    def validate_destination_url(url: str) -> Tuple[str, str, int]:
        """
        Validates URL scheme, parses alternate IP formats, resolves DNS,
        and blocks private networks, loopbacks, and cloud metadata endpoints.
        Returns: (normalized_url, hostname, port)
        Fails closed on any ambiguity or resolution error.
        """
        if not url or not url.strip():
            raise BrowserSecurityError("URL cannot be empty.")

        parsed = urllib.parse.urlparse(url.strip())
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise BrowserSecurityError(
                f"Forbidden navigation scheme '{scheme}'. Only HTTP and HTTPS are permitted."
            )

        hostname = parsed.hostname
        if not hostname:
            raise BrowserSecurityError(f"Invalid URL: missing hostname in '{url}'.")

        # 1. Block known string aliases
        h_lower = hostname.lower()
        if h_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "local") or h_lower.endswith(".local"):
            raise BrowserSecurityError(f"Access to local destination '{hostname}' is strictly prohibited.")

        port = parsed.port or (443 if scheme == "https" else 80)

        # 2. Check for alternate numeric IP representations (e.g. 2130706433, 0x7f000001, 0177.0.0.1, [::ffff:127.0.0.1])
        parsed_ip = parse_alternate_ip(hostname)
        if parsed_ip is not None:
            forbidden, reason = is_ip_forbidden(parsed_ip)
            if forbidden:
                raise BrowserSecurityError(f"SSRF violation: {reason}")

        # 3. Resolve DNS and verify ALL resolved addresses
        try:
            addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise BrowserSecurityError(f"DNS resolution failed for '{hostname}': {str(e)}") from e

        if not addr_info:
            raise BrowserSecurityError(f"No IP address resolved for hostname '{hostname}'.")

        for item in addr_info:
            ip_str = item[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                forbidden, reason = is_ip_forbidden(ip_obj)
                if forbidden:
                    raise BrowserSecurityError(
                        f"SSRF violation: Hostname '{hostname}' resolves to forbidden IP '{ip_str}': {reason}"
                    )
            except ValueError as ve:
                raise BrowserSecurityError(f"Unparseable resolved IP '{ip_str}' for hostname '{hostname}': {ve}")

        normalized_url = parsed.geturl()
        return normalized_url, hostname, port

    @staticmethod
    def is_consequential_action(
        tag: str,
        role: Optional[str] = None,
        text: Optional[str] = None,
        input_type: Optional[str] = None,
        explicit_flag: bool = False,
    ) -> Tuple[bool, str]:
        """
        Determines whether a browser interaction is consequential and requires explicit user approval.
        Returns: (is_consequential, reason)
        """
        if explicit_flag:
            return True, "User or agent explicitly flagged action as consequential."

        if input_type and input_type.lower() in ("submit", "password"):
            return True, f"Target input type '{input_type}' mutates state or handles credentials."

        combined = f"{tag} {role or ''} {text or ''}".lower()
        for kw in CONSEQUENTIAL_KEYWORDS:
            if kw in combined:
                return True, f"Target element matches consequential action pattern '{kw}'."

        return False, ""

    @staticmethod
    def verify_action_token(
        tool_name: str,
        arguments: Dict[str, Any],
        provided_token: Optional[str],
        session_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies that an unforgeable, action-bound approval token matches the canonical payload.
        Ensures a model-supplied boolean alone cannot authorize consequential actions.
        """
        return verify_action_token_fn(
            tool_name=tool_name,
            arguments=arguments,
            provided_token=provided_token,
            session_id=session_id,
        )
