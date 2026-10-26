"""
Unified Client for Agent Orix: Local in-process and Remote HTTP operation.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional
import httpx

from cie.schemas import CIERequest, CIEResponse, ExecutionStatus
from cie.skills.registry import get_default_registry
from cie.workflows.schemas import (
    WorkflowType,
    WorkflowRequest,
    WorkflowResult,
    DocumentIntelligenceInput,
    CodebaseRepairInput,
    ResearchVerificationInput,
)

logger = logging.getLogger("cie.cli.client")


class BaseAgentClient:
    async def check_health(self) -> Dict[str, Any]:
        raise NotImplementedError

    async def chat(
        self,
        prompt: str,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def run_workflow(
        self,
        workflow_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def get_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class LocalAgentClient(BaseAgentClient):
    """
    Direct in-process execution using CIE Orchestrator and Workflow Engine.
    """

    def __init__(self):
        from cie.orchestrator import CIEOrchestrator
        from cie.workflows.engine import WorkflowEngine
        from cie.router import DeterministicRouter

        self.orchestrator = CIEOrchestrator()
        self.workflow_engine = WorkflowEngine(skill_executor=self.orchestrator.skill_executor)
        self.router = DeterministicRouter()
        self.registry = get_default_registry()

    async def check_health(self) -> Dict[str, Any]:
        import psutil
        ollama_health = await self.orchestrator.ollama_client.check_health()
        process = psutil.Process()
        return {
            "mode": "local",
            "connected": True,
            "ollama_connected": ollama_health.get("connected", False),
            "model_found": ollama_health.get("model_found", False),
            "model_name": ollama_health.get("model_name", "cavrix-code:latest"),
            "offline_mode": ollama_health.get("offline_mode", False),
            "process_ram_mb": round(process.memory_info().rss / (1024 * 1024), 2),
            "available_models": ollama_health.get("available_models", []),
            "tool_count": len(self.registry.list_tools()),
        }

    async def chat(
        self,
        prompt: str,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        req_meta = metadata or {}
        req_meta["session_id"] = session_id
        cie_req = CIERequest(prompt=prompt, metadata=req_meta)

        if on_chunk:
            on_chunk("Thinking...")

        resp: CIEResponse = await self.orchestrator.process_request(cie_req)
        return {
            "status": resp.status.value,
            "content": resp.content,
            "category": resp.route.category.value if resp.route else "UNKNOWN",
            "confidence": resp.route.confidence if resp.route else 0.0,
            "execution_time_ms": resp.execution_time_ms,
            "steps": [s.model_dump() for s in resp.steps_taken],
            "warnings": resp.warnings,
        }

    async def run_workflow(
        self,
        workflow_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        wf_type_upper = workflow_type.upper().strip()
        if "DOC" in wf_type_upper:
            wftype = WorkflowType.DOCUMENT_INTELLIGENCE
            wf_input = DocumentIntelligenceInput(
                document_path=params.get("document_path", ""),
                query=params.get("query"),
                extract_tables=params.get("extract_tables", True),
                format_markdown=params.get("format_markdown", True),
            )
        elif "CODE" in wf_type_upper or "REPAIR" in wf_type_upper:
            wftype = WorkflowType.CODEBASE_REPAIR
            wf_input = CodebaseRepairInput(
                file_path=params.get("file_path", ""),
                instruction=params.get("instruction", "Inspect and validate"),
                target_root=params.get("target_root"),
                auto_revert_on_test_failure=params.get("auto_revert_on_test_failure", True),
            )
        elif "RESEARCH" in wf_type_upper or "VERIF" in wf_type_upper:
            wftype = WorkflowType.RESEARCH_VERIFICATION
            wf_input = ResearchVerificationInput(
                topic=params.get("topic", ""),
                source_urls=params.get("source_urls", []),
                max_sources=params.get("max_sources", 3),
            )
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        wf_req = WorkflowRequest(
            workflow_type=wftype,
            input_data=wf_input.model_dump(),
        )
        res: WorkflowResult = await self.workflow_engine.run_workflow(wf_req)
        return res.model_dump()

    def get_tools(self) -> List[Dict[str, Any]]:
        tools = self.registry.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": getattr(t, "category", "general"),
                "risk_level": getattr(t, "risk_level", "low"),
                "requires_approval": getattr(t, "requires_approval", False),
            }
            for t in tools
        ]


class RemoteAgentClient(BaseAgentClient):
    """
    Remote HTTP client connecting to a running CIE or Fastify backend.
    """

    def __init__(self, endpoint_url: str, auth_token: Optional[str] = None, timeout: float = 30.0):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def check_health(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 5.0)) as client:
                resp = await client.get(f"{self.endpoint_url}/health", headers=self._headers())
                latency_ms = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    data = resp.json()
                    data["connected"] = True
                    data["mode"] = "remote"
                    data["latency_ms"] = round(latency_ms, 2)
                    return data
                return {
                    "mode": "remote",
                    "connected": False,
                    "status_code": resp.status_code,
                    "error": resp.text,
                    "latency_ms": round(latency_ms, 2),
                }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "mode": "remote",
                "connected": False,
                "status_code": None,
                "error": f"Failed to connect to remote server: {e}",
                "latency_ms": round(latency_ms, 2),
            }

    async def chat(
        self,
        prompt: str,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        req_meta = metadata or {}
        req_meta["session_id"] = session_id
        payload = {"prompt": prompt, "metadata": req_meta}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.endpoint_url}/v1/chat",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code != 200:
                    return {
                        "status": "FAILED",
                        "content": f"Remote server returned HTTP {resp.status_code}: {resp.text}",
                        "execution_time_ms": 0,
                        "steps": [],
                        "warnings": [f"Remote error: {resp.status_code}"],
                    }
                return resp.json()
        except Exception as e:
            return {
                "status": "FAILED",
                "content": f"Remote connection error: {e}",
                "execution_time_ms": 0,
                "steps": [],
                "warnings": [f"Remote connection failure: {e}"],
            }

    async def run_workflow(
        self,
        workflow_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "workflow_type": workflow_type,
            "input_data": params,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.endpoint_url}/v1/workflows/run",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Remote workflow execution failed: HTTP {resp.status_code} - {resp.text}")
            return resp.json()

    def get_tools(self) -> List[Dict[str, Any]]:
        # Remote tools fetch
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.endpoint_url}/v1/capabilities", headers=self._headers())
                if resp.status_code == 200:
                    caps = resp.json().get("capabilities", [])
                    return [
                        {
                            "name": c.get("name", ""),
                            "description": c.get("summary", ""),
                            "category": c.get("category", "general"),
                            "risk_level": "medium",
                            "requires_approval": False,
                        }
                        for c in caps
                    ]
        except Exception as e:
            logger.warning(f"Failed to fetch remote capabilities: {e}")
        # Fallback to local default registry
        reg = get_default_registry()
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": getattr(t, "category", "general"),
                "risk_level": getattr(t, "risk_level", "low"),
                "requires_approval": getattr(t, "requires_approval", False),
            }
            for t in reg.list_tools()
        ]
