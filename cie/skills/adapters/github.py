"""
Read-Only GitHub API Adapter for CIE.
Provides read-only repository, commit, release, and documentation inspection via GitHub REST API.
"""

import base64
import os
from typing import Any, Dict, List, Optional
import httpx

from cie.safety import redact_secrets


class GitHubAdapterError(Exception):
    pass


class GitHubRateLimitError(GitHubAdapterError):
    pass


import re

IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class GitHubAdapter:
    """
    Read-only GitHub REST API client with bounded limits, token support, and rate-limit handling.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, timeout: float = 10.0):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.timeout = timeout

    def __repr__(self) -> str:
        return f"<GitHubAdapter authenticated={bool(self.token)} timeout={self.timeout}>"

    def _validate_identifier(self, name: str, param_name: str) -> None:
        if not name or not IDENTIFIER_PATTERN.match(name):
            raise GitHubAdapterError(f"Invalid {param_name} format: '{name}'. Only alphanumeric characters, hyphens, underscores, and dots are permitted.")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Cavrix-CIE-Skills-Adapter/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, str):
            return redact_secrets(data)
        elif isinstance(data, dict):
            return {k: self._sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize(v) for v in data]
        return data

    async def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._get_headers(), params=params)

            if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
                raise GitHubRateLimitError("GitHub API rate limit exceeded. Set GITHUB_TOKEN or wait for reset.")

            if resp.status_code == 404:
                raise GitHubAdapterError(f"Resource not found at {endpoint}")

            if resp.status_code >= 400:
                clean_err = redact_secrets(resp.text[:200])
                raise GitHubAdapterError(f"GitHub API error {resp.status_code}: {clean_err}")

            data = resp.json()
            return self._sanitize(data)

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository summary and metadata."""
        self._validate_identifier(owner, "owner")
        self._validate_identifier(repo, "repo")
        data = await self._request(f"/repos/{owner}/{repo}")
        return {
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
            "html_url": data.get("html_url"),
        }

    async def get_branches(self, owner: str, repo: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetch repository branch names and commit SHAs."""
        self._validate_identifier(owner, "owner")
        self._validate_identifier(repo, "repo")
        data = await self._request(f"/repos/{owner}/{repo}/branches", params={"per_page": min(limit, 50)})
        branches = []
        for b in data[:limit]:
            branches.append({
                "name": b.get("name"),
                "commit_sha": b.get("commit", {}).get("sha"),
                "protected": b.get("protected", False),
            })
        return branches

    async def get_commits(self, owner: str, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent commits."""
        self._validate_identifier(owner, "owner")
        self._validate_identifier(repo, "repo")
        data = await self._request(f"/repos/{owner}/{repo}/commits", params={"per_page": min(limit, 30)})
        commits = []
        for c in data[:limit]:
            commit_info = c.get("commit", {})
            commits.append({
                "sha": c.get("sha", "")[:8],
                "message": commit_info.get("message", "").splitlines()[0] if commit_info.get("message") else "",
                "author": commit_info.get("author", {}).get("name"),
                "date": commit_info.get("author", {}).get("date"),
            })
        return commits

    async def get_releases(self, owner: str, repo: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch releases and tags."""
        self._validate_identifier(owner, "owner")
        self._validate_identifier(repo, "repo")
        data = await self._request(f"/repos/{owner}/{repo}/releases", params={"per_page": min(limit, 10)})
        releases = []
        for r in data[:limit]:
            releases.append({
                "tag_name": r.get("tag_name"),
                "name": r.get("name"),
                "published_at": r.get("published_at"),
                "prerelease": r.get("prerelease", False),
            })
        return releases

    async def get_readme(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch and decode the repository README."""
        self._validate_identifier(owner, "owner")
        self._validate_identifier(repo, "repo")
        data = await self._request(f"/repos/{owner}/{repo}/readme")
        raw_b64 = data.get("content", "")
        decoded_text = ""
        if raw_b64:
            try:
                decoded_text = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
            except Exception:
                decoded_text = "[Failed to decode README base64 content]"

        return {
            "name": data.get("name"),
            "path": data.get("path"),
            "size": data.get("size", 0),
            "content": redact_secrets(decoded_text[:10000]),  # Bounded to 10k chars
        }
