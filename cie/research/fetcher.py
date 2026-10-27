"""
Safe Webpage Fetcher and HTML Extractor with strict SSRF & DNS-rebinding protection.
"""

import ipaddress
import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class SecurityValidationError(Exception):
    pass


class FetchLimitExceededError(Exception):
    pass


# Forbidden IP networks for SSRF mitigation (RFC 1918, RFC 3927, Loopback, Carrier-Grade, Cloud Metadata)
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),        # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),          # IPv4 Loopback
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),        # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),       # Private Class C
    ipaddress.ip_network("198.18.0.0/15"),        # Benchmark testing
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved
    ipaddress.ip_network("255.255.255.255/32"),   # Broadcast
    # IPv6 ranges
    ipaddress.ip_network("::1/128"),              # IPv6 Loopback
    ipaddress.ip_network("::/128"),               # IPv6 Unspecified
    ipaddress.ip_network("::ffff:0:0/96"),         # IPv4-mapped IPv6
    ipaddress.ip_network("100::/64"),             # Discard-only prefix
    ipaddress.ip_network("fc00::/7"),             # Unique local address
    ipaddress.ip_network("fe80::/10"),            # Link-local unicast
    ipaddress.ip_network("ff00::/8"),             # Multicast
]

ALLOWED_CONTENT_TYPES = [
    "text/html",
    "text/plain",
    "application/xhtml+xml",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 (Cavrix-Research-Agent/1.0)"
)


class SafeWebFetcher:
    def __init__(
        self,
        max_response_bytes: int = 1_048_576,  # 1 MB ceiling
        max_redirects: int = 3,
        connect_timeout: float = 4.0,
        read_timeout: float = 6.0,
        max_excerpt_chars: int = 3500,
    ):
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_excerpt_chars = max_excerpt_chars

    def validate_url_security(self, url: str) -> Tuple[str, str, int]:
        """
        Validates URL scheme, resolves DNS, and validates resolved IP addresses
        against forbidden private/internal CIDR ranges.
        Returns: (normalized_url, hostname, port)
        """
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise SecurityValidationError(f"Forbidden URL scheme '{parsed.scheme}'. Only http and https allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise SecurityValidationError("Invalid URL: missing hostname.")

        # Check explicit localhost string or local hostnames
        if hostname.lower() in ("localhost", "local", "ip6-localhost", "ip6-loopback") or hostname.endswith(".local"):
            raise SecurityValidationError(f"Access to localhost/internal domain '{hostname}' is strictly prohibited.")

        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

        # DNS Resolution and SSRF IP check
        try:
            addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise SecurityValidationError(f"DNS resolution failed for hostname '{hostname}': {e}") from e

        if not addr_info:
            raise SecurityValidationError(f"No IP address resolved for hostname '{hostname}'.")

        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError as e:
                raise SecurityValidationError(f"Invalid resolved IP '{ip_str}': {e}") from e

            # Check if resolved IP falls into any forbidden internal / cloud metadata network
            for net in FORBIDDEN_NETWORKS:
                if ip_obj in net:
                    raise SecurityValidationError(
                        f"SSRF violation: Hostname '{hostname}' resolved to prohibited IP '{ip_str}' in range {net}."
                    )

        return url, hostname, port

    async def fetch(self, initial_url: str) -> Dict[str, Any]:
        """
        Safely fetches webpage text while strictly revalidating SSRF on every redirect hop.
        """
        current_url = initial_url
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,text/plain"}
        timeout = httpx.Timeout(self.read_timeout, connect=self.connect_timeout)

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for hop in range(self.max_redirects + 1):
                # Validate URL and resolve DNS before initiating connection
                self.validate_url_security(current_url)

                try:
                    resp = await client.get(current_url, headers=headers)
                except httpx.TimeoutException as e:
                    raise FetchLimitExceededError(f"Fetch timed out for {current_url}") from e
                except httpx.ConnectError as e:
                    raise SecurityValidationError(f"Connection failed to {current_url}: {e}") from e

                # Handle HTTP redirects explicitly with security re-validation
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if not location:
                        raise SecurityValidationError("Redirect received without Location header.")
                    # Resolve relative redirect URLs against current URL
                    current_url = urllib.parse.urljoin(current_url, location)
                    if hop >= self.max_redirects:
                        raise FetchLimitExceededError(f"Exceeded maximum allowed redirects ({self.max_redirects}).")
                    continue

                # Final response reached
                if resp.status_code != 200:
                    raise SecurityValidationError(f"HTTP {resp.status_code} received from {current_url}")

                # Validate Content-Type
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if content_type and not any(content_type == allowed for allowed in ALLOWED_CONTENT_TYPES):
                    raise SecurityValidationError(
                        f"Unsupported Content-Type '{content_type}'. Only text/html and text/plain are permitted."
                    )

                # Validate Response Size
                content_bytes = resp.content
                if len(content_bytes) > self.max_response_bytes:
                    raise FetchLimitExceededError(
                        f"Response size ({len(content_bytes)} bytes) exceeds limit ({self.max_response_bytes} bytes)."
                    )

                # Safe HTML Extraction
                extracted = self.extract_content(resp.text, current_url)
                extracted["final_url"] = current_url
                extracted["http_status"] = resp.status_code
                return extracted

            raise FetchLimitExceededError("Too many redirects.")

    def extract_content(self, html_text: str, source_url: str) -> Dict[str, Any]:
        """
        Extracts clean, readable text from HTML, stripping all scripts, styles, and chrome noise.
        """
        if BeautifulSoup is None:
            clean = re.sub(r"<[^>]+>", " ", html_text)
            return {"title": "Web Page", "pub_date": None, "author": None, "main_text": " ".join(clean.split())[:10000], "excerpt": " ".join(clean.split())[:200]}
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Extract Page Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        if not title:
            parsed = urllib.parse.urlparse(source_url)
            title = parsed.netloc

        # 2. Extract Publication Date from common meta tags
        pub_date = None
        for meta_name in ("article:published_time", "pubdate", "date", "dc.date", "sailthru.date"):
            tag = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                pub_date = tag["content"].strip()
                break

        # 3. Strip dangerous & noisy HTML elements
        for element in soup(["script", "style", "noscript", "svg", "canvas", "nav", "header", "footer", "aside", "form", "iframe"]):
            element.decompose()

        # 4. Extract body text
        text = soup.get_text(separator="\n", strip=True)

        # Normalize redundant blank lines
        cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
        compact_text = "\n".join(cleaned_lines)

        # Bound text length
        if len(compact_text) > self.max_excerpt_chars:
            compact_text = compact_text[:self.max_excerpt_chars] + "\n... [Content truncated for context safety]"

        return {
            "title": title,
            "publication_date": pub_date,
            "text": compact_text,
        }
