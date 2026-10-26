"""
Configuration management for Cavrix Intelligence Engine (CIE).
Loads from environment variables with safe defaults.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class CIEConfig(BaseModel):
    # Host & Server
    host: str = Field(default_factory=lambda: os.getenv("CIE_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("CIE_PORT", "8088")))
    debug: bool = Field(default_factory=lambda: os.getenv("CIE_DEBUG", "false").lower() == "true")

    # Storage Paths (Rooted on Drive E:)
    base_dir: Path = Field(default_factory=lambda: Path(os.getenv("CIE_BASE_DIR", r"E:\cavrix_cie")))
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("CIE_DATA_DIR", r"E:\cavrix_cie\data")))
    log_dir: Path = Field(default_factory=lambda: Path(os.getenv("CIE_LOG_DIR", r"E:\cavrix_cie\logs")))

    # Ollama Integration
    ollama_url: str = Field(default_factory=lambda: os.getenv("CIE_OLLAMA_URL", "http://127.0.0.1:11434"))
    model_name: str = Field(default_factory=lambda: os.getenv("CIE_MODEL_NAME", "cavrix-code:latest"))
    offline_mode: bool = Field(default_factory=lambda: os.getenv("CIE_OFFLINE_MODE", "false").lower() == "true")

    # Timeouts & Concurrency limits
    request_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("CIE_REQUEST_TIMEOUT", "30.0")))
    ollama_connect_timeout: float = Field(default_factory=lambda: float(os.getenv("CIE_CONNECT_TIMEOUT", "5.0")))
    max_concurrent_inferences: int = Field(default_factory=lambda: int(os.getenv("CIE_MAX_CONCURRENCY", "1")))
    max_steps_per_request: int = Field(default=3)

    # Context & Token Budgeting
    max_context_tokens: int = Field(default=2048)  # Bounds Ollama num_ctx on 5.9 GB RAM host
    max_output_tokens: int = Field(default=512)
    max_prompt_chars: int = Field(default=32000)

    # Process Memory Watchdog
    max_process_memory_mb: float = Field(default=1500.0)  # Safe threshold for Python orchestrator process


_config_instance: Optional[CIEConfig] = None


def get_config() -> CIEConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = CIEConfig()
        _config_instance.data_dir.mkdir(parents=True, exist_ok=True)
        _config_instance.log_dir.mkdir(parents=True, exist_ok=True)
    return _config_instance


def set_config(cfg: CIEConfig) -> None:
    global _config_instance
    _config_instance = cfg
