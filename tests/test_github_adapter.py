"""
Tests for CIE GitHubAdapter.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cie.skills.adapters.github import GitHubAdapter, GitHubRateLimitError, GitHubAdapterError


@pytest.fixture
def github_adapter():
    return GitHubAdapter(token="mock_token_12345")


def test_adapter_headers(github_adapter):
    headers = github_adapter._get_headers()
    assert headers["Authorization"] == "Bearer mock_token_12345"
    assert "User-Agent" in headers


@pytest.mark.asyncio
async def test_get_repo_mocked(github_adapter):
    fake_payload = {
        "full_name": "cavrix/cavrix_cie",
        "description": "Cavrix Intelligence Engine",
        "default_branch": "main",
        "stargazers_count": 42,
        "forks_count": 5,
        "open_issues_count": 1,
        "license": {"spdx_id": "MIT"},
        "html_url": "https://github.com/cavrix/cavrix_cie",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        repo = await github_adapter.get_repo("cavrix", "cavrix_cie")
        assert repo["full_name"] == "cavrix/cavrix_cie"
        assert repo["stars"] == 42
        assert repo["license"] == "MIT"


@pytest.mark.asyncio
async def test_rate_limit_error(github_adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"x-ratelimit-remaining": "0"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with pytest.raises(GitHubRateLimitError, match="rate limit exceeded"):
            await github_adapter.get_repo("cavrix", "cavrix_cie")


@pytest.mark.asyncio
async def test_get_readme_decoding(github_adapter):
    import base64
    raw_text = "# Cavrix Readme\nToken: sk-test12345678901234567890"
    b64_content = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")

    fake_payload = {
        "name": "README.md",
        "path": "README.md",
        "size": len(raw_text),
        "content": b64_content,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        readme = await github_adapter.get_readme("cavrix", "cavrix_cie")
        assert readme["name"] == "README.md"
        assert "# Cavrix Readme" in readme["content"]
        # Ensure secret scrubbing worked on readme content
        assert "[REDACTED_API_KEY]" in readme["content"]
