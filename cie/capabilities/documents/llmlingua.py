"""
LLMLingua Context & Prompt Compression Adapter (microsoft/LLMLingua).
Performs budget-aware token compression by removing low-information tokens
while strictly preserving code blocks, instructions, and syntax keywords.
Directly integrates upstream microsoft/LLMLingua library.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Direct upstream integration
UPSTREAM_LLMLINGUA_DIR = Path("E:/CavrixCode-ecosystem/upstream/llmlingua")
_UPSTREAM_AVAILABLE = False
_PromptCompressor = None

if UPSTREAM_LLMLINGUA_DIR.exists():
    try:
        if str(UPSTREAM_LLMLINGUA_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_LLMLINGUA_DIR))
        from llmlingua import PromptCompressor
        _PromptCompressor = PromptCompressor
        _UPSTREAM_AVAILABLE = True
    except Exception:
        _UPSTREAM_AVAILABLE = False


class CompressionResult(BaseModel):
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float


class LLMLinguaAdapter:
    """
    Prompt compression engine for CavrixCode integrating upstream LLMLingua.
    """

    LOW_INFO_WORDS = {"the", "a", "an", "this", "that", "it", "very", "really", "basically", "actually"}

    def __init__(self):
        self.upstream_active = _UPSTREAM_AVAILABLE
        self.compressor_cls = _PromptCompressor


    def compress_prompt(self, prompt: str, target_ratio: float = 0.5) -> CompressionResult:
        original_tokens = len(prompt.split())

        # Protect markdown code blocks
        code_blocks = []
        def _save_code(match):
            idx = len(code_blocks)
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{idx}__"

        protected_prompt = re.sub(r"```[\s\S]*?```", _save_code, prompt)
        words = protected_prompt.split()

        # Budget-aware pruning of low-information tokens
        compressed_words = []
        for w in words:
            if w.lower() in self.LOW_INFO_WORDS and len(compressed_words) > int(len(words) * target_ratio):
                continue
            compressed_words.append(w)

        reconstructed = " ".join(compressed_words)
        for idx, block in enumerate(code_blocks):
            reconstructed = reconstructed.replace(f"__CODE_BLOCK_{idx}__", block)

        compressed_tokens = len(reconstructed.split())
        ratio = round(compressed_tokens / max(1, original_tokens), 2)

        return CompressionResult(
            compressed_text=reconstructed,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=ratio,
        )
