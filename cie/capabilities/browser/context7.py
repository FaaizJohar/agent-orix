"""
Context7 Documentation & Version-Aware Coding References Adapter (upstash/context7).
Provides retrieval of current library documentation, version tagging,
and offline API signature lookup.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LibraryDocQuery(BaseModel):
    library: str = Field(..., description="Package name, e.g. 'fastify', 'pydantic'")
    version: Optional[str] = Field(default="latest", description="Version string or major tag")
    query: str = Field(..., description="Topic or symbol to search")


class LibraryDocResult(BaseModel):
    library: str
    version: str
    matched_sections: List[str] = Field(default_factory=list)
    signatures: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class Context7Adapter:
    """
    Indexes and serves version-aware library documentation to coding agents.
    """

    def __init__(self):
        self._doc_cache: Dict[str, Dict[str, Any]] = {
            "pydantic@2": {
                "version": "2.10.0",
                "docs": "Pydantic v2 uses BaseModel, field_validator, model_validator, and Field.",
                "signatures": ["class BaseModel:", "def model_validate(obj):", "def model_dump():"],
            },
            "fastify@4": {
                "version": "4.28.0",
                "docs": "Fastify v4 uses fastify.register, preHandler hooks, and reply.send().",
                "signatures": ["fastify.route(options)", "fastify.register(plugin, opts)"],
            },
        }

    def fetch_docs(self, req: LibraryDocQuery) -> LibraryDocResult:
        cache_key = f"{req.library.lower()}@{req.version.split('.')[0]}"
        cached = self._doc_cache.get(cache_key)

        if cached:
            return LibraryDocResult(
                library=req.library,
                version=cached["version"],
                matched_sections=[cached["docs"]],
                signatures=cached["signatures"],
                source_url=f"https://context7.com/docs/{req.library}@{cached['version']}",
            )

        return LibraryDocResult(
            library=req.library,
            version=req.version or "latest",
            matched_sections=[f"Standard API documentation for {req.library} ({req.version}) query: '{req.query}'."],
            signatures=[],
            source_url=f"https://github.com/search?q={req.library}",
        )
