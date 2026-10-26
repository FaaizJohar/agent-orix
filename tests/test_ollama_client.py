"""
Tests for CIE Ollama Client.
"""

import pytest
from cie.config import CIEConfig, set_config, get_config
from cie.ollama_client import OllamaClient, OllamaConnectionError


@pytest.mark.asyncio
async def test_offline_mode_blocks_requests():
    cfg = get_config()
    original_offline = cfg.offline_mode
    try:
        cfg.offline_mode = True
        client = OllamaClient()
        health = await client.check_health()
        assert health["offline_mode"] is True
        assert health["connected"] is False

        with pytest.raises(OllamaConnectionError):
            await client.generate("test prompt")
    finally:
        cfg.offline_mode = original_offline


@pytest.mark.asyncio
async def test_invalid_endpoint_connection_error():
    client = OllamaClient(base_url="http://127.0.0.1:59999")  # Unused port
    health = await client.check_health()
    assert health["connected"] is False
    assert "error" in health


@pytest.mark.asyncio
async def test_live_ollama_health_if_running():
    client = OllamaClient()
    health = await client.check_health()
    # If Ollama is running on port 11434, connected should be True and cavrix-code:latest present
    if health["connected"]:
        assert health["model_found"] is True
        assert "cavrix-code:latest" in health["available_models"]
