"""
HTTP Endpoint Health and Status Inspection Tool.
Uses SafeWebFetcher SSRF mitigation to check remote URLs without exposing internal/private resources.
"""

import time
from typing import Optional
import httpx
from pydantic import BaseModel, Field

from cie.research.fetcher import SafeWebFetcher, SecurityValidationError


class HttpEndpointCheckInput(BaseModel):
    url: str = Field(..., description="Target HTTP/HTTPS URL to check")
    timeout_seconds: float = Field(default=5.0, description="Request timeout in seconds")


class HttpEndpointCheckOutput(BaseModel):
    url: str
    accessible: bool
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    error: Optional[str] = None


async def http_endpoint_check(
    url: str,
    timeout_seconds: float = 5.0,
) -> HttpEndpointCheckOutput:
    """
    Checks HTTP endpoint status, latency, and headers with SSRF protection.
    Blocks private IP addresses, loopback, and metadata endpoints.
    """
    fetcher = SafeWebFetcher(connect_timeout=timeout_seconds, read_timeout=timeout_seconds)

    # 1. SSRF Validation
    try:
        scheme, host, port = fetcher.validate_url_security(url)
    except SecurityValidationError as sve:
        return HttpEndpointCheckOutput(
            url=url,
            accessible=False,
            error=f"SSRF security restriction: {str(sve)}",
        )
    except Exception as e:
        return HttpEndpointCheckOutput(
            url=url,
            accessible=False,
            error=f"URL validation error: {str(e)}",
        )

    # 2. Execution with timing and safe redirect verification
    start_time = time.perf_counter()
    headers = {"User-Agent": "Cavrix-CIE-EndpointChecker/1.0"}
    current_url = url
    max_hops = 3

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            for hop in range(max_hops + 1):
                # HEAD request with GET range fallback
                resp = await client.head(current_url, headers=headers)
                if resp.status_code == 405:
                    headers["Range"] = "bytes=0-1024"
                    resp = await client.get(current_url, headers=headers)

                # Check if response is a redirect
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if not location:
                        break
                    import urllib.parse
                    next_url = urllib.parse.urljoin(current_url, location)
                    # Strictly re-validate redirect destination for SSRF
                    try:
                        fetcher.validate_url_security(next_url)
                    except SecurityValidationError as sve:
                        latency_ms = (time.perf_counter() - start_time) * 1000
                        return HttpEndpointCheckOutput(
                            url=current_url,
                            accessible=False,
                            status_code=resp.status_code,
                            response_time_ms=round(latency_ms, 2),
                            error=f"SSRF security restriction: Redirect target blocked: {str(sve)}",
                        )
                    current_url = next_url
                    continue

                # Non-redirect response reached
                latency_ms = (time.perf_counter() - start_time) * 1000
                content_length = None
                if "content-length" in resp.headers:
                    try:
                        content_length = int(resp.headers["content-length"])
                    except ValueError:
                        pass

                return HttpEndpointCheckOutput(
                    url=current_url,
                    accessible=True,
                    status_code=resp.status_code,
                    response_time_ms=round(latency_ms, 2),
                    content_type=resp.headers.get("content-type"),
                    content_length=content_length,
                    error=None,
                )

            # Exceeded redirect hops
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HttpEndpointCheckOutput(
                url=current_url,
                accessible=False,
                response_time_ms=round(latency_ms, 2),
                error=f"Exceeded maximum allowed redirects ({max_hops}).",
            )
    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return HttpEndpointCheckOutput(
            url=url,
            accessible=False,
            response_time_ms=round(latency_ms, 2),
            error=f"Connection timed out after {timeout_seconds} seconds.",
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return HttpEndpointCheckOutput(
            url=url,
            accessible=False,
            response_time_ms=round(latency_ms, 2),
            error=f"HTTP connection failed: {str(exc)}",
        )
