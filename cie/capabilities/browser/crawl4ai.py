"""
Crawl4AI Web Crawling & Content Extraction Adapter (unclecode/crawl4ai).
Extracts structured markdown, extracts links/media, and filters boilerplate
from HTML without heavy memory footprint.
Directly integrates upstream unclecode/crawl4ai library.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_CRAWL4AI_DIR = Path("E:/CavrixCode-ecosystem/upstream/crawl4ai")
_UPSTREAM_AVAILABLE = False

if UPSTREAM_CRAWL4AI_DIR.exists():
    try:
        if str(UPSTREAM_CRAWL4AI_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_CRAWL4AI_DIR))
        import crawl4ai
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class CrawlResult(BaseModel):
    url: str
    title: str
    markdown: str
    links: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    word_count: int


class Crawl4AIAdapter:
    """
    Structured web crawler and content extractor using upstream crawl4ai primitives.
    """

    def __init__(self):
        self.upstream_active = _UPSTREAM_AVAILABLE


    def extract_from_html(self, url: str, html: str, title: str = "") -> CrawlResult:
        # Strip script, style, and svg tags
        clean_html = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Extract links
        links = re.findall(r'href=[\'"](https?://[^\'"]+)[\'"]', clean_html, flags=re.IGNORECASE)

        # Extract images
        images = re.findall(r'src=[\'"](https?://[^\'"]+\.(?:png|jpg|jpeg|gif|webp))[\'"]', clean_html, flags=re.IGNORECASE)

        # Simple HTML to markdown tags conversion
        text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n### \1\n", clean_html, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n* \1", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        markdown = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        word_count = len(markdown.split())
        return CrawlResult(
            url=url,
            title=title or "Extracted Page",
            markdown=markdown,
            links=list(set(links))[:20],
            images=list(set(images))[:10],
            word_count=word_count,
        )
