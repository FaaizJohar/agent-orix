"""
GitHub Repository Inspection Tool.
Fetches public repository details and README summary using GitHubAdapter.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from cie.skills.adapters.github import GitHubAdapter


class GithubRepoInspectInput(BaseModel):
    owner: str = Field(..., description="Repository owner / organization name")
    repo: str = Field(..., description="Repository name")
    include_readme: bool = Field(default=False, description="Whether to include README content")


class GithubRepoInspectOutput(BaseModel):
    owner: str
    repo: str
    info: Dict[str, Any] = Field(default_factory=dict)
    readme: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


async def github_repo_inspect(
    owner: str,
    repo: str,
    include_readme: bool = False,
) -> GithubRepoInspectOutput:
    """
    Safely inspects a GitHub repository without mutating any remote resources.
    """
    adapter = GitHubAdapter()
    try:
        repo_info = await adapter.get_repo(owner, repo)
        readme_info = None
        if include_readme:
            try:
                readme_info = await adapter.get_readme(owner, repo)
            except Exception:
                readme_info = {"content": "README not available"}

        return GithubRepoInspectOutput(
            owner=owner,
            repo=repo,
            info=repo_info,
            readme=readme_info,
            error=None,
        )
    except Exception as e:
        return GithubRepoInspectOutput(
            owner=owner,
            repo=repo,
            info={},
            readme=None,
            error=str(e),
        )
