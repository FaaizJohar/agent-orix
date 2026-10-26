"""
FastAPI HTTP Service for Cavrix Intelligence Engine (CIE).
Binds to 127.0.0.1 by default with zero external cloud dependencies.
"""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import psutil

from cie import __version__
from cie.config import get_config
from cie.orchestrator import CIEOrchestrator
from cie.router import DeterministicRouter
from cie.schemas import CIERequest, CIEResponse, HealthStatus, RouteDecision, IntentCategory
from cie.safety import validate_input, redact_secrets
from cie.research.citations import CitationEngine
from cie.knowledge.grounding import KnowledgeGrounding
from cie.skills.schemas import ToolExecutionRequest
from cie.planning.schemas import TaskPlan
from cie.security_tokens import compute_action_token
from cie.truth import AntiSycophancyGuard, TRUTH_PRESERVATION_SYSTEM_PROMPT
from cie.capabilities.registry import get_capability_registry
from cie.capabilities.verifier import verify_single_capability, verify_all_capabilities

app = FastAPI(
    title="Cavrix Intelligence Engine (CIE)",
    version=__version__,
    description="Lightweight deterministic orchestrator augmenting cavrix-code:latest",
)

# Restrict CORS to local loopback origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_start_time = time.time()
_orchestrator: CIEOrchestrator = CIEOrchestrator()
_router: DeterministicRouter = DeterministicRouter()


@app.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Diagnostic health check verifying local process metrics and Ollama connectivity.
    """
    cfg = get_config()
    ollama_health = await _orchestrator.ollama_client.check_health()
    process = psutil.Process()
    process_ram_mb = process.memory_info().rss / (1024 * 1024)
    total_ram_mb = psutil.virtual_memory().total / (1024 * 1024)

    is_healthy = ollama_health.get("connected", False) or cfg.offline_mode

    return HealthStatus(
        status="HEALTHY" if is_healthy else "DEGRADED",
        version=__version__,
        ollama_endpoint=cfg.ollama_url,
        ollama_connected=ollama_health.get("connected", False),
        model_name=cfg.model_name,
        model_available=ollama_health.get("model_found", False),
        offline_mode=cfg.offline_mode,
        process_ram_mb=round(process_ram_mb, 2),
        total_visible_ram_mb=round(total_ram_mb, 2),
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@app.post("/v1/route", response_model=RouteDecision)
async def classify_route(req: CIERequest) -> RouteDecision:
    """
    Sub-millisecond deterministic intent classification without running LLM inference.
    """
    return _router.route(req.prompt)


@app.post("/v1/chat", response_model=CIEResponse)
async def chat_endpoint(req: CIERequest) -> CIEResponse:
    """
    Full request orchestration: validation -> routing -> budgeted inference -> synthesis.
    """
    return await _orchestrator.process_request(req)


@app.post("/v1/chat/stream")
async def chat_stream_endpoint(req: CIERequest):
    """
    Server-Sent Events (SSE) streaming endpoint supporting DIRECT, GENERAL,
    RESEARCH (with real-time source retrieval and grounding), and KNOWLEDGE (with FTS5 memory).
    """
    is_valid, sanitized_prompt, val_warnings = validate_input(req.prompt)
    if not is_valid:
        async def invalid_generator():
            yield f"data: Request rejected: {'; '.join(val_warnings)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(invalid_generator(), media_type="text/event-stream")

    # Anti-Sycophancy & Truth Preservation Gate
    claim_eval = AntiSycophancyGuard.evaluate_user_claim(sanitized_prompt, session_context=req.metadata)
    if claim_eval.pushback_required:
        async def pushback_generator():
            yield f"data: {claim_eval.pushback_message}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(pushback_generator(), media_type="text/event-stream")

    if req.metadata.get("tool_name"):
        route = RouteDecision(
            category=IntentCategory.SKILL,
            confidence=1.0,
            reason=f"Explicit tool_name '{req.metadata['tool_name']}' supplied in request metadata.",
            matched_patterns=[req.metadata["tool_name"]],
            fallback_applied=False,
        )
    else:
        route = _router.route(sanitized_prompt)

    async def event_generator():
        try:
            # 1. Adaptive Planning mode execution
            if req.metadata.get("plan_mode"):
                yield "data: 📋 Creating adaptive execution plan...\n\n"
                plan = _orchestrator.planner.create_plan(sanitized_prompt, metadata=req.metadata)
                if plan.steps:
                    yield f"data: 📋 Plan created with {len(plan.steps)} step(s).\n\n"
                    for idx, s in enumerate(plan.steps, start=1):
                        yield f"data: - Step {idx}: {s.purpose}\n\n"

                executed_plan = await _orchestrator.plan_executor.execute_plan(plan)
                _orchestrator.task_manager.store_task(executed_plan)

                if executed_plan.final_summary:
                    yield f"data: \n\n{executed_plan.final_summary}\n\n"
                elif executed_plan.direct_answer:
                    yield f"data: \n\n{executed_plan.direct_answer}\n\n"
                elif executed_plan.clarification_needed:
                    yield f"data: \n\n⚠️ Clarification required: {executed_plan.clarification_needed}\n\n"
                else:
                    yield f"data: \n\nPlan execution finished with status: {executed_plan.status.value}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 2. Single Skill execution
            elif route.category == IntentCategory.SKILL:
                tool_name = req.metadata.get("tool_name") or (route.matched_patterns[0] if route.matched_patterns else "developer_tool")
                yield f"data: ⚙️ Executing developer skill: `{tool_name}`...\n\n"
                resp = await _orchestrator.process_request(req)
                yield f"data: {resp.content}\n\n"
                yield "data: [DONE]\n\n"
                return

            elif route.category == IntentCategory.RESEARCH:
                evidence = await _orchestrator.research_engine.gather_evidence(sanitized_prompt)
                if evidence.is_empty():
                    yield f"data: Live research found no accessible web sources for query: '{evidence.query}'. No unverified facts were fabricated.\n\n"
                    yield "data: [DONE]\n\n"
                    return

                grounded_sys, grounded_user = CitationEngine.format_grounded_prompt(sanitized_prompt, evidence)
                async for chunk in _orchestrator.ollama_client.generate_stream(
                    prompt=grounded_user,
                    system_override=grounded_sys,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    context_tokens=_orchestrator.budgeter.max_context_tokens,
                ):
                    yield f"data: {chunk}\n\n"

                sources_footer = "\n\n**Sources:**\n" + "\n".join(
                    [f"- [{s.source_id}] {s.title} ({s.url})" for s in evidence.sources]
                )
                yield f"data: {sources_footer}\n\n"
                yield "data: [DONE]\n\n"

            elif route.category == IntentCategory.KNOWLEDGE:
                evidence = _orchestrator.knowledge_retriever.retrieve(sanitized_prompt)
                if evidence.is_empty():
                    yield f"data: The local documentation does not establish an answer for: '{sanitized_prompt}'. No unverified claims were fabricated.\n\n"
                    yield "data: [DONE]\n\n"
                    return

                grounded_sys, grounded_user = KnowledgeGrounding.format_grounded_prompt(sanitized_prompt, evidence)
                async for chunk in _orchestrator.ollama_client.generate_stream(
                    prompt=grounded_user,
                    system_override=grounded_sys,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    context_tokens=_orchestrator.budgeter.max_context_tokens,
                ):
                    yield f"data: {chunk}\n\n"

                ref_footer = "\n\n**Verified References:**\n" + "\n".join(
                    [f"- [{c.chunk_identifier}] {c.title}" for c in evidence.chunks]
                )
                yield f"data: {ref_footer}\n\n"
                yield "data: [DONE]\n\n"

            else:
                # DIRECT, CODE, GENERAL, MULTILINGUAL
                effective_system = req.system_override or TRUTH_PRESERVATION_SYSTEM_PROMPT
                async for chunk in _orchestrator.ollama_client.generate_stream(
                    prompt=sanitized_prompt,
                    system_override=effective_system,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    context_tokens=_orchestrator.budgeter.max_context_tokens,
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

        except Exception as exc:
            yield f"data: [Error: {str(exc)}]\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/v1/skills")
async def list_skills():
    """
    List all registered tools in the Skills Registry.
    """
    tools = _orchestrator.skill_executor.registry.list_tools()
    return [t.model_dump() for t in tools]


@app.post("/v1/skills/execute")
async def execute_skill(req: ToolExecutionRequest):
    """
    Directly execute an approved skill via the SkillExecutor broker.
    """
    return await _orchestrator.skill_executor.execute(req)


class ApproveTokenRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    ttl_seconds: int = 300


@app.post("/v1/auth/approve-token")
async def issue_approval_token(req: ApproveTokenRequest):
    """
    Issues an unforgeable, HMAC-signed action approval token for explicit user confirmation.
    """
    token = compute_action_token(
        tool_name=req.tool_name,
        arguments=req.arguments,
        session_id=req.session_id,
        ttl_seconds=req.ttl_seconds,
    )
    return {
        "approval_token": token,
        "tool_name": req.tool_name,
        "expires_in": req.ttl_seconds,
    }


# ==============================================================================
# Phase 5: Adaptive Planning & Execution Endpoints
# ==============================================================================

class PlanCreateRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=4096)
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutePlanRequest(BaseModel):
    plan: Optional[TaskPlan] = None
    task_id: Optional[str] = None
    approval_tokens: Dict[str, str] = Field(default_factory=dict, description="Map of step_id to approval_token")


@app.post("/v1/tasks/plan", response_model=TaskPlan)
async def create_task_plan(req: PlanCreateRequest) -> TaskPlan:
    """
    Decomposes user goal into an ordered, validated TaskPlan using registered skills.
    """
    plan = _orchestrator.planner.create_plan(
        goal=req.goal,
        task_id=req.task_id,
        metadata=req.metadata,
    )
    _orchestrator.task_manager.store_task(plan)
    return plan


@app.post("/v1/tasks/execute", response_model=TaskPlan)
async def execute_task_plan(req: ExecutePlanRequest) -> TaskPlan:
    """
    Executes a new or existing TaskPlan with DAG ordering, retries, and outcome verification.
    """
    if req.plan:
        plan = req.plan
    elif req.task_id:
        plan = _orchestrator.task_manager.get_task(req.task_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Task '{req.task_id}' not found.")
        # Attach approval tokens if provided
        for step in plan.steps:
            if step.step_id in req.approval_tokens:
                step.approval_token = req.approval_tokens[step.step_id]
    else:
        raise HTTPException(status_code=400, detail="Either 'plan' or 'task_id' must be provided.")

    executed_plan = await _orchestrator.plan_executor.execute_plan(plan)
    _orchestrator.task_manager.store_task(executed_plan)
    return executed_plan


@app.get("/v1/tasks/{task_id}", response_model=TaskPlan)
async def get_task_status(task_id: str) -> TaskPlan:
    """
    Retrieves the status, trace, and outcomes of a task by ID with scrubbed secrets.
    """
    plan = _orchestrator.task_manager.get_task(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return plan


@app.post("/v1/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str):
    """
    Cancels an active or pending task.
    """
    _orchestrator.plan_executor.cancel_task(task_id)
    return {"task_id": task_id, "status": "CANCELLED"}


# ─── Multi-Step Domain Workflows (Phase 17) ──────────────────────────────────
from cie.workflows.engine import WorkflowEngine
from cie.workflows.schemas import WorkflowRequest, WorkflowResult
_workflow_engine = WorkflowEngine(skill_executor=_orchestrator.skill_executor)


@app.post("/v1/workflows/run", response_model=WorkflowResult)
async def run_workflow_endpoint(request: WorkflowRequest) -> WorkflowResult:
    """
    Executes a multi-step domain workflow:
    - DOCUMENT_INTELLIGENCE
    - CODEBASE_REPAIR
    - RESEARCH_VERIFICATION
    """
    return await _workflow_engine.run_workflow(request)


@app.post("/v1/workflows/{workflow_id}/cancel")
async def cancel_workflow_endpoint(workflow_id: str):
    """
    Signals immediate cancellation for an in-flight workflow.
    """
    _workflow_engine.cancel_workflow(workflow_id)
    return {"workflow_id": workflow_id, "status": "CANCELLED"}


@app.get("/v1/workflows/{workflow_id}/checkpoint")
async def get_workflow_checkpoint(workflow_id: str):
    """
    Retrieves the resumable checkpoint state for a paused workflow.
    """
    ckpt = _workflow_engine.get_checkpoint(workflow_id)
    if not ckpt:
        raise HTTPException(status_code=404, detail=f"No checkpoint found for workflow '{workflow_id}'.")
    return {"workflow_id": workflow_id, "checkpoint": ckpt}



@app.get("/v1/capabilities")
async def list_capabilities():
    """
    Returns all 30 ecosystem capabilities, their integration reality statuses, and summary metrics.
    """
    reg = get_capability_registry()
    return {
        "total": len(reg.list_all()),
        "status_summary": reg.get_status_summary(),
        "capabilities": [c.model_dump() for c in reg.list_all()],
    }


@app.get("/v1/capabilities/{capability_id}")
async def get_capability_detail(capability_id: int):
    """
    Returns metadata, upstream remote, commit SHA, and license for a specific capability.
    """
    reg = get_capability_registry()
    cap = reg.get(capability_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability ID {capability_id} not found.")
    return cap.model_dump()


@app.post("/v1/capabilities/{capability_id}/verify")
async def verify_capability_endpoint(capability_id: int):
    """
    Executes in-memory live verification for a specific capability.
    """
    res = verify_single_capability(capability_id)
    if not res.get("verified") and res.get("error") and "not registered" in res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.post("/v1/capabilities/verify_all")
async def verify_all_capabilities_endpoint():
    """
    Executes verification across all 30 ecosystem capabilities and returns system-wide metrics.
    """
    return verify_all_capabilities()


@app.on_event("shutdown")
async def on_shutdown():
    """
    Releases Playwright browser processes and resources upon server termination.
    """
    try:
        from cie.browser.manager import get_browser_manager
        bm = get_browser_manager()
        await bm.close()
    except Exception:
        pass


def start_server():
    import uvicorn
    cfg = get_config()
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info" if not cfg.debug else "debug")


if __name__ == "__main__":
    start_server()

