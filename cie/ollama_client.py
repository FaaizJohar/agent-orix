"""
Ollama HTTP API Client for CIE.
Provides robust async streaming and non-streaming inference against local Ollama.
Never downloads models or routes to cloud services.
"""

import json
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx
from cie.config import get_config


class OllamaClientError(Exception):
    pass


class OllamaConnectionError(OllamaClientError):
    pass


class OllamaModelNotFoundError(OllamaClientError):
    pass


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        cfg = get_config()
        self.base_url = (base_url or cfg.ollama_url).rstrip("/")
        self.model_name = model_name or cfg.model_name
        self.timeout = cfg.request_timeout_seconds
        self.connect_timeout = cfg.ollama_connect_timeout

    async def check_health(self) -> Dict[str, Any]:
        """
        Pings Ollama endpoint and verifies that the required model exists locally.
        """
        cfg = get_config()
        if cfg.offline_mode:
            return {
                "connected": False,
                "offline_mode": True,
                "model_found": False,
                "models": [],
                "error": "CIE is operating in explicit offline mode.",
            }

        try:
            async with httpx.AsyncClient(timeout=self.connect_timeout) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return {
                        "connected": False,
                        "offline_mode": False,
                        "model_found": False,
                        "error": f"Ollama returned HTTP status {resp.status_code}",
                    }
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                # Match full tag (e.g. cavrix-code:latest) or base name
                model_found = any(m == self.model_name or m.startswith(self.model_name) for m in models)
                return {
                    "connected": True,
                    "offline_mode": False,
                    "model_found": model_found,
                    "model_name": self.model_name,
                    "available_models": models,
                }
        except httpx.ConnectError:
            return {
                "connected": False,
                "offline_mode": False,
                "model_found": False,
                "error": f"Connection refused to Ollama at {self.base_url}. Ensure Ollama is running.",
            }
        except Exception as e:
            return {
                "connected": False,
                "offline_mode": False,
                "model_found": False,
                "error": f"Ollama health check failed: {str(e)}",
            }

    async def generate(
        self,
        prompt: str,
        system_override: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        context_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Sends non-streaming inference request to Ollama /api/generate.
        """
        cfg = get_config()
        if cfg.offline_mode:
            raise OllamaConnectionError("CIE is in offline mode. Inference disabled.")

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": context_tokens,
                "repeat_penalty": 1.15,
                "repeat_last_n": 64,
            },
        }
        if system_override:
            payload["system"] = system_override

        try:
            timeout = httpx.Timeout(self.timeout, connect=self.connect_timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                if resp.status_code == 404:
                    raise OllamaModelNotFoundError(f"Model '{self.model_name}' was not found in Ollama.")
                if resp.status_code != 200:
                    raise OllamaClientError(f"Ollama returned HTTP error {resp.status_code}: {resp.text}")
                return resp.json()
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot reach Ollama at {self.base_url}. Check if Ollama is running.") from e
        except httpx.TimeoutException as e:
            raise OllamaClientError(f"Inference request timed out after {self.timeout}s.") from e

    async def generate_stream(
        self,
        prompt: str,
        system_override: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        context_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Streams response tokens chunk-by-chunk from Ollama.
        """
        cfg = get_config()
        if cfg.offline_mode:
            yield "[Error: CIE is in offline mode. Inference disabled.]"
            return

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": context_tokens,
                "repeat_penalty": 1.15,
                "repeat_last_n": 64,
            },
        }
        if system_override:
            payload["system"] = system_override

        timeout = httpx.Timeout(self.timeout, connect=self.connect_timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as resp:
                    if resp.status_code == 404:
                        yield f"[Error: Model '{self.model_name}' not found.]"
                        return
                    if resp.status_code != 200:
                        yield f"[Error: Ollama HTTP {resp.status_code}]"
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            yield chunk.get("response", "")
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            yield f"[Error: Cannot connect to Ollama at {self.base_url}]"
        except httpx.TimeoutException:
            yield f"[Error: Streaming timed out after {self.timeout}s]"
