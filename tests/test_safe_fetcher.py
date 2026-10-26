"""
Tests for SafeWebFetcher: SSRF prevention, URL validation, and HTML sanitization.
"""

import pytest
from cie.research.fetcher import SafeWebFetcher, SecurityValidationError, FetchLimitExceededError


@pytest.fixture
def fetcher():
    return SafeWebFetcher()


def test_scheme_validation(fetcher):
    # Only http and https allowed
    invalid_schemes = [
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
        "gopher://example.com",
        "javascript:alert(1)",
        "data:text/html,<html></html>",
    ]
    for url in invalid_schemes:
        with pytest.raises(SecurityValidationError) as exc:
            fetcher.validate_url_security(url)
        assert "Forbidden URL scheme" in str(exc.value)


def test_localhost_and_internal_domain_blocking(fetcher):
    prohibited_hosts = [
        "http://localhost:8080/admin",
        "http://127.0.0.1/secret",
        "http://127.0.0.100/status",
        "http://[::1]/internal",
        "http://myhost.local/",
    ]
    for url in prohibited_hosts:
        with pytest.raises(SecurityValidationError) as exc:
            fetcher.validate_url_security(url)
        assert ("localhost" in str(exc.value).lower() or 
                "ssrf" in str(exc.value).lower() or 
                "prohibited" in str(exc.value).lower())


def test_ssrf_private_and_cloud_metadata_ips(fetcher):
    # Prohibited RFC 1918 & Cloud metadata IPs
    prohibited_urls = [
        "http://10.0.0.1/api",
        "http://172.16.0.5/dashboard",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP metadata
        "http://169.254.1.1/link-local",
    ]
    for url in prohibited_urls:
        with pytest.raises(SecurityValidationError) as exc:
            fetcher.validate_url_security(url)
        assert "SSRF violation" in str(exc.value)


def test_html_cleaning_and_script_removal(fetcher):
    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Python 3.14 Release Notes</title>
        <script>alert("malicious script execution");</script>
        <style>body { background: red; }</style>
    </head>
    <body>
        <header>Navigation bar and ads</header>
        <nav><a href="/home">Home</a></nav>
        <main>
            <h1>Python 3.14 Official Overview</h1>
            <p>Python 3.14 introduces template strings and faster JIT compiler features.</p>
        </main>
        <footer>Copyright 2026 Python Software Foundation</footer>
        <script>console.log("another script");</script>
    </body>
    </html>
    """
    extracted = fetcher.extract_content(raw_html, "https://example.com/notes")
    assert extracted["title"] == "Python 3.14 Release Notes"
    assert "template strings" in extracted["text"]
    assert "JIT compiler" in extracted["text"]
    # Verify scripts and navigation were stripped
    assert "malicious script" not in extracted["text"]
    assert "another script" not in extracted["text"]
    assert "Navigation bar and ads" not in extracted["text"]
    assert "Copyright 2026" not in extracted["text"]


def test_oversized_response_limit():
    fetcher_small = SafeWebFetcher(max_response_bytes=100)
    raw_html = "A" * 500
    extracted = fetcher_small.extract_content(raw_html, "https://example.com")
    # Character excerpt is bounded
    assert len(extracted["text"]) <= fetcher_small.max_excerpt_chars
