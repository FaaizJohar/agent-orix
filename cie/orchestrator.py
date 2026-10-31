"""
Central Intelligence Orchestrator for CIE.
Coordinates intent routing, context budgeting, concurrency semaphores, and step boundedness.
"""

import asyncio
import logging
import re
import time
from typing import List, Optional
import psutil

from cie.config import get_config
from cie.context import ContextBudgeter
from cie.ollama_client import OllamaClient, OllamaClientError
from cie.router import DeterministicRouter
from cie.safety import validate_input, redact_secrets
from cie.research.citations import CitationEngine
from cie.research.engine import ResearchEngine
from cie.knowledge.retriever import KnowledgeRetriever
from cie.knowledge.grounding import KnowledgeGrounding
from cie.skills.executor import SkillExecutor
from cie.skills.schemas import ToolExecutionRequest
from cie.planning.schemas import PlanStatus, TaskPlan
from cie.planning.planner import AdaptivePlanner
from cie.planning.executor import BoundedPlanExecutor
from cie.planning.task_manager import TaskManager
from cie.truth import (
    AntiSycophancyGuard,
    TRUTH_PRESERVATION_SYSTEM_PROMPT,
    PostconditionVerifier,
    EvidenceStatus,
    TaskLifecycleStatus,
)
from cie.capabilities.agent.hermes import HermesAgentAdapter
from cie.schemas import (
    CIERequest,
    CIEResponse,
    ExecutionStatus,
    IntentCategory,
    RouteDecision,
    StepRecord,
)

logger = logging.getLogger("cie.orchestrator")


class CIEOrchestrator:
    def __init__(
        self,
        router: Optional[DeterministicRouter] = None,
        ollama_client: Optional[OllamaClient] = None,
        budgeter: Optional[ContextBudgeter] = None,
        research_engine: Optional[ResearchEngine] = None,
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
        skill_executor: Optional[SkillExecutor] = None,
    ):
        cfg = get_config()
        self.router = router or DeterministicRouter()
        self.ollama_client = ollama_client or OllamaClient()
        self.budgeter = budgeter or ContextBudgeter()
        self.research_engine = research_engine or ResearchEngine()
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever()
        self.skill_executor = skill_executor or SkillExecutor()
        self.planner = AdaptivePlanner(registry=self.skill_executor.registry)
        self.plan_executor = BoundedPlanExecutor(skill_executor=self.skill_executor)
        self.task_manager = TaskManager()
        # Concurrency semaphore strictly enforces single-inference queue on 5.9 GB host
        self._inference_semaphore = asyncio.Semaphore(cfg.max_concurrent_inferences)
        self.max_steps = cfg.max_steps_per_request

    async def process_request(self, req: CIERequest) -> CIEResponse:
        start_time = time.perf_counter()
        steps: List[StepRecord] = []
        warnings: List[str] = []

        # -------------------------------------------------------------
        # Step 1: Input Validation, Secret Redaction & Safety
        # -------------------------------------------------------------
        s1_start = time.perf_counter()
        is_valid, sanitized_prompt, val_warnings = validate_input(req.prompt)
        warnings.extend(val_warnings)
        steps.append(
            StepRecord(
                step_number=1,
                action="InputValidationAndSafety",
                status="PASSED" if is_valid else "FAILED",
                detail=f"Length: {len(sanitized_prompt)} chars; warnings: {len(val_warnings)}",
                duration_ms=(time.perf_counter() - s1_start) * 1000,
            )
        )

        if not is_valid:
            total_duration = (time.perf_counter() - start_time) * 1000
            return CIEResponse(
                status=ExecutionStatus.REJECTED,
                content=f"Request rejected: {'; '.join(val_warnings)}",
                route=RouteDecision(
                    category=IntentCategory.GENERAL,
                    confidence=0.0,
                    reason="Input validation failed.",
                    fallback_applied=True,
                ),
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
            )

        # -------------------------------------------------------------
        # Step 1.5: Truth and Anti-Sycophancy Verification Gate
        # -------------------------------------------------------------
        claim_eval = AntiSycophancyGuard.evaluate_user_claim(sanitized_prompt, session_context=req.metadata)
        if claim_eval.pushback_required:
            steps.append(
                StepRecord(
                    step_number=2,
                    action="AntiSycophancyAndTruthVerification",
                    status="PUSHBACK_APPLIED",
                    detail=f"Status: {claim_eval.evidence_status.value}; Reason: {claim_eval.contradiction_detail or 'Unverified claim'}",
                    duration_ms=(time.perf_counter() - s1_start) * 1000,
                )
            )
            total_duration = (time.perf_counter() - start_time) * 1000
            return CIEResponse(
                status=ExecutionStatus.COMPLETED,
                content=claim_eval.pushback_message,
                route=RouteDecision(
                    category=IntentCategory.GENERAL,
                    confidence=1.0,
                    reason="Anti-sycophancy and truth-preservation guard applied proportionate pushback.",
                    fallback_applied=False,
                ),
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
                metadata={"claim_evaluation": claim_eval.model_dump()},
            )

        # -------------------------------------------------------------
        # Step 2: Deterministic Intent Classification
        # -------------------------------------------------------------
        s2_start = time.perf_counter()
        if req.metadata.get("tool_name"):
            route = RouteDecision(
                category=IntentCategory.SKILL,
                confidence=1.0,
                reason=f"Explicit tool_name '{req.metadata['tool_name']}' supplied in request metadata.",
                matched_patterns=[req.metadata["tool_name"]],
                fallback_applied=False,
            )
        else:
            route = self.router.route(sanitized_prompt)
        steps.append(
            StepRecord(
                step_number=2,
                action="DeterministicIntentRouting",
                status="COMPLETED",
                detail=f"Route: {route.category.value} (confidence: {route.confidence:.2f})",
                duration_ms=(time.perf_counter() - s2_start) * 1000,
            )
        )

        # -------------------------------------------------------------
        # Step 3: Execution / Dispatch according to Route or Plan Mode
        # -------------------------------------------------------------
        s3_start = time.perf_counter()

        # Route: ADAPTIVE PLANNING (Phase 5 Plan-and-Execute)
        if req.metadata.get("plan_mode"):
            plan_start = time.perf_counter()
            plan = self.planner.create_plan(sanitized_prompt, metadata=req.metadata)
            executed_plan = await self.plan_executor.execute_plan(plan)
            self.task_manager.store_task(executed_plan)

            steps.append(
                StepRecord(
                    step_number=3,
                    action="AdaptivePlanExecution",
                    status=executed_plan.status.value,
                    detail=f"Steps: {len(executed_plan.steps)}, Status: {executed_plan.status.value}",
                    duration_ms=(time.perf_counter() - plan_start) * 1000,
                )
            )
            total_duration = (time.perf_counter() - start_time) * 1000

            exec_status = (
                ExecutionStatus.COMPLETED
                if executed_plan.status == PlanStatus.COMPLETED
                else (ExecutionStatus.REJECTED if executed_plan.status == PlanStatus.BLOCKED else ExecutionStatus.ERROR)
            )
            return CIEResponse(
                status=exec_status,
                content=executed_plan.final_summary or "",
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
                metadata={"plan": executed_plan.model_dump()},
            )

        # -------------------------------------------------------------
        # Route: RESEARCH (Phase 2 Live Research & Citation Verification)
        # -------------------------------------------------------------
        if route.category == IntentCategory.RESEARCH:
            res_start = time.perf_counter()
            evidence = await self.research_engine.gather_evidence(sanitized_prompt)
            warnings.extend(evidence.warnings)

            if evidence.is_empty():
                steps.append(
                    StepRecord(
                        step_number=3,
                        action="LiveResearchAndEvidenceGathering",
                        status="COMPLETED_EMPTY",
                        detail=f"Query '{evidence.query}' returned 0 accessible sources.",
                        duration_ms=(time.perf_counter() - res_start) * 1000,
                    )
                )
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.COMPLETED,
                    content=(
                        f"Live research was unable to find accessible web sources for the query: '{evidence.query}'.\n\n"
                        "To maintain strict factual integrity, no unverified facts or citations were fabricated. "
                        "Please refine your query or check search provider connectivity."
                    ),
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                )

            # Grounded prompt construction
            grounded_sys, grounded_user = CitationEngine.format_grounded_prompt(sanitized_prompt, evidence)
            within_budget, p_tokens, total_tokens, budget_warnings = self.budgeter.assess_budget(
                grounded_user, grounded_sys
            )
            warnings.extend(budget_warnings)

            try:
                async with self._inference_semaphore:
                    ollama_resp = await self.ollama_client.generate(
                        prompt=grounded_user,
                        system_override=grounded_sys,
                        temperature=req.temperature,
                        max_tokens=req.max_tokens,
                        context_tokens=self.budgeter.max_context_tokens,
                    )

                raw_answer = ollama_resp.get("response", "")
                verified_cites, unverified_cites, enriched_answer = CitationEngine.validate_citations(
                    raw_answer, evidence
                )

                if unverified_cites:
                    warnings.append(f"Model generated unverified citation markers: {unverified_cites}")

                steps.append(
                    StepRecord(
                        step_number=3,
                        action="GroundedResearchAndSynthesis",
                        status="COMPLETED",
                        detail=(
                            f"Sources: {len(evidence.sources)}, "
                            f"Verified cites: {len(verified_cites)}, "
                            f"Unverified: {len(unverified_cites)}"
                        ),
                        duration_ms=(time.perf_counter() - res_start) * 1000,
                    )
                )

                clean_content = redact_secrets(enriched_answer)
                clean_content = re.sub(r"[a-zA-Z]:\\[^\s\)\`\]\>]+", "[local documentation]", clean_content)
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.COMPLETED,
                    content=clean_content,
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    prompt_tokens=ollama_resp.get("prompt_eval_count"),
                    completion_tokens=ollama_resp.get("eval_count"),
                    warnings=warnings,
                    metadata={
                        "sources_count": len(evidence.sources),
                        "verified_citations": verified_cites,
                        "unverified_citations": unverified_cites,
                        "retrieved_sources": [
                            {"id": s.source_id, "title": s.title, "url": s.url, "date": s.publication_date}
                            for s in evidence.sources
                        ],
                    },
                )
            except OllamaClientError as e:
                steps.append(
                    StepRecord(
                        step_number=3,
                        action="GroundedResearchAndSynthesis",
                        status="ERROR",
                        detail=str(e),
                        duration_ms=(time.perf_counter() - res_start) * 1000,
                    )
                )
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.ERROR,
                    content=f"Research synthesis failed: {str(e)}",
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                )

        # -------------------------------------------------------------
        # Route: KNOWLEDGE (Phase 3 Local Knowledge & Verified Memory RAG)
        # -------------------------------------------------------------
        if route.category == IntentCategory.KNOWLEDGE:
            know_start = time.perf_counter()
            evidence = self.knowledge_retriever.retrieve(sanitized_prompt)
            warnings.extend(evidence.warnings)

            prompt_summary = sanitized_prompt.splitlines()[0] if len(sanitized_prompt) > 80 else sanitized_prompt
            if evidence.is_empty():
                steps.append(
                    StepRecord(
                        step_number=3,
                        action="LocalKnowledgeRetrieval",
                        status="COMPLETED_EMPTY",
                        detail=f"Query '{evidence.query}' returned 0 matching local document chunks.",
                        duration_ms=(time.perf_counter() - know_start) * 1000,
                    )
                )
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.COMPLETED,
                    content=(
                        f"The available local documentation does not establish an answer for: '{prompt_summary}'.\n\n"
                        "To maintain strict factual integrity, no unverified facts or corporate claims were fabricated."
                    ),
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                )

            # Check evidence sufficiency to prevent ungrounded small-model fabrication
            is_sufficient, missing_topics = KnowledgeGrounding.check_evidence_sufficiency(sanitized_prompt, evidence)
            if not is_sufficient:
                steps.append(
                    StepRecord(
                        step_number=3,
                        action="LocalKnowledgeEvidenceSufficiencyCheck",
                        status="INSUFFICIENT_EVIDENCE",
                        detail=f"Query subjects not found in local evidence: {missing_topics}",
                        duration_ms=(time.perf_counter() - know_start) * 1000,
                    )
                )
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.COMPLETED,
                    content=(
                        f"The available local documentation does not establish an answer for: '{prompt_summary}'.\n\n"
                        "To maintain strict factual integrity, no unverified facts or corporate claims were fabricated."
                    ),
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                    metadata={"missing_topics": missing_topics},
                )

            # Grounded prompt construction
            grounded_sys, grounded_user = KnowledgeGrounding.format_grounded_prompt(sanitized_prompt, evidence)
            within_budget, p_tokens, total_tokens, budget_warnings = self.budgeter.assess_budget(
                grounded_user, grounded_sys
            )
            warnings.extend(budget_warnings)

            try:
                async with self._inference_semaphore:
                    ollama_resp = await self.ollama_client.generate(
                        prompt=grounded_user,
                        system_override=grounded_sys,
                        temperature=req.temperature,
                        max_tokens=req.max_tokens,
                        context_tokens=self.budgeter.max_context_tokens,
                    )

                raw_answer = ollama_resp.get("response", "")
                verified_cites, unverified_cites, enriched_answer = KnowledgeGrounding.validate_citations(
                    raw_answer, evidence
                )

                if unverified_cites:
                    warnings.append(f"Model generated unverified chunk citation markers: {unverified_cites}")

                steps.append(
                    StepRecord(
                        step_number=3,
                        action="LocalKnowledgeSynthesisAndVerification",
                        status="COMPLETED",
                        detail=(
                            f"Chunks: {len(evidence.chunks)}, "
                            f"Verified cites: {len(verified_cites)}, "
                            f"Unverified: {len(unverified_cites)}"
                        ),
                        duration_ms=(time.perf_counter() - know_start) * 1000,
                    )
                )

                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.COMPLETED,
                    content=redact_secrets(enriched_answer),
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    prompt_tokens=ollama_resp.get("prompt_eval_count"),
                    completion_tokens=ollama_resp.get("eval_count"),
                    warnings=warnings,
                    metadata={
                        "chunks_count": len(evidence.chunks),
                        "verified_citations": verified_cites,
                        "unverified_citations": unverified_cites,
                        "retrieved_chunks": [
                            {"id": c.chunk_identifier, "title": c.title, "source": c.source_path, "score": c.score}
                            for c in evidence.chunks
                        ],
                    },
                )
            except OllamaClientError as e:
                steps.append(
                    StepRecord(
                        step_number=3,
                        action="LocalKnowledgeSynthesisAndVerification",
                        status="ERROR",
                        detail=str(e),
                        duration_ms=(time.perf_counter() - know_start) * 1000,
                    )
                )
                total_duration = (time.perf_counter() - start_time) * 1000
                return CIEResponse(
                    status=ExecutionStatus.ERROR,
                    content=f"Knowledge synthesis failed: {str(e)}",
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                )

        # -------------------------------------------------------------
        # Route: SKILL (Phase 4 Typed Skills & Secure Developer Tools)
        # -------------------------------------------------------------
        if route.category == IntentCategory.SKILL:
            skill_start = time.perf_counter()

            # Determine tool name
            tool_name = req.metadata.get("tool_name")
            if not tool_name and route.matched_patterns:
                tool_name = route.matched_patterns[0]

            if not tool_name:
                tool_name = "python_ast_validate"

            # Determine arguments
            args = req.metadata.get("arguments", {})
            if not args:
                if tool_name == "python_ast_validate":
                    code_match = re.search(r"```(?:python)?\n([\s\S]*?)```", sanitized_prompt)
                    if code_match:
                        code = code_match.group(1)
                    else:
                        split_match = re.search(r"(?:code|snippet|python):\s*([\s\S]+)$", sanitized_prompt, re.IGNORECASE)
                        code = split_match.group(1).strip() if split_match else sanitized_prompt
                    args = {"code": code}
                elif tool_name == "json_validate":
                    json_match = re.search(r"```(?:json)?\n([\s\S]*?)```", sanitized_prompt)
                    if json_match:
                        content = json_match.group(1)
                    else:
                        start_idx = -1
                        for i, ch in enumerate(sanitized_prompt):
                            if ch in ("{", "["):
                                start_idx = i
                                break
                        if start_idx != -1:
                            closing = "}" if sanitized_prompt[start_idx] == "{" else "]"
                            end_idx = sanitized_prompt.rfind(closing)
                            content = sanitized_prompt[start_idx:end_idx+1] if end_idx > start_idx else sanitized_prompt[start_idx:]
                        else:
                            content = sanitized_prompt
                    args = {"content": content}
                elif tool_name == "yaml_validate":
                    yaml_match = re.search(r"```(?:yaml)?\n([\s\S]*?)```", sanitized_prompt)
                    content = yaml_match.group(1) if yaml_match else sanitized_prompt
                    args = {"content": content}
                elif tool_name in ("git_status", "git_diff_summary"):
                    args = {"repo_path": "."}
                elif tool_name == "file_tree_inspect":
                    args = {"directory_path": "."}
                elif tool_name == "python_project_inspect":
                    args = {"project_dir": "."}
                elif tool_name == "test_discover":
                    args = {"directory_path": "."}
                elif tool_name == "readme_extract":
                    args = {"file_path_or_content": "README.md", "is_path": True}
                elif tool_name == "markdown_check":
                    args = {"content": sanitized_prompt}
                elif tool_name == "markdown_to_text":
                    args = {"content": sanitized_prompt}
                elif tool_name == "log_parse_errors":
                    args = {"log_content_or_path": sanitized_prompt, "is_path": False}
                elif tool_name == "file_integrity_verify":
                    args = {"file_path": sanitized_prompt.strip()}
                elif tool_name == "file_read_text":
                    path_m = re.search(r"(?:file|path|read|from)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", sanitized_prompt)
                    f_path = path_m.group(1) if path_m else sanitized_prompt.strip()
                    args = {"file_path": f_path, "start_line": 1, "max_lines": 200}
                elif tool_name == "file_search_text":
                    q_m = re.search(r"(?:for|query|search|grep)\s+['\"]([^'\"]+)['\"]", sanitized_prompt)
                    query_val = q_m.group(1) if q_m else sanitized_prompt.strip()
                    args = {"query": query_val, "directory_path": ".", "max_results": 30}
                elif tool_name == "http_endpoint_check":
                    url_match = re.search(r"https?://[^\s]+", sanitized_prompt)
                    args = {"url": url_match.group(0) if url_match else sanitized_prompt.strip()}
                elif tool_name == "github_repo_inspect":
                    gh_match = re.search(r"github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)", sanitized_prompt)
                    if gh_match:
                        args = {"owner": gh_match.group(1), "repo": gh_match.group(2)}
                    else:
                        parts = sanitized_prompt.split()
                        owner = parts[-2] if len(parts) >= 2 else "cavrix"
                        repo = parts[-1] if len(parts) >= 1 else "cavrix_cie"
                        args = {"owner": owner, "repo": repo}
                elif tool_name == "document_extract_text":
                    path_m = re.search(r"(?:from|file|path|document)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", sanitized_prompt, re.IGNORECASE)
                    args = {"file_path": path_m.group(1) if path_m else sanitized_prompt.strip()}
                elif tool_name == "document_qa":
                    path_m = re.search(r"(?:in|from|document|file)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", sanitized_prompt, re.IGNORECASE)
                    f_path = path_m.group(1) if path_m else "document.pdf"
                    args = {"file_path": f_path, "question": sanitized_prompt.strip()}
                elif tool_name == "browser_open":
                    url_match = re.search(r"https?://[^\s]+", sanitized_prompt)
                    args = {"url": url_match.group(0) if url_match else sanitized_prompt.strip()}
                elif tool_name == "browser_back":
                    args = {}
                elif tool_name == "browser_get_page_snapshot":
                    args = {"include_interactive_only": False}
                elif tool_name == "browser_find_text":
                    q_m = re.search(r"(?:for|text|find)\s+['\"]([^'\"]+)['\"]", sanitized_prompt)
                    args = {"query": q_m.group(1) if q_m else sanitized_prompt.strip()}
                elif tool_name == "browser_click_element":
                    ref_m = re.search(r"(@ref_\d+)", sanitized_prompt)
                    args = {"ref_id": ref_m.group(1)} if ref_m else {"text": sanitized_prompt.strip()}
                elif tool_name == "browser_fill_field":
                    ref_m = re.search(r"(@ref_\d+)", sanitized_prompt)
                    val_m = re.search(r"(?:with|value)\s+['\"]([^'\"]+)['\"]", sanitized_prompt)
                    args = {
                        "ref_id": ref_m.group(1) if ref_m else "@ref_1",
                        "value": val_m.group(1) if val_m else sanitized_prompt.strip(),
                    }
                elif tool_name == "browser_select_option":
                    args = {"option_value": sanitized_prompt.strip()}
                elif tool_name == "browser_list_tabs":
                    args = {}
                elif tool_name == "browser_switch_tab":
                    args = {"tab_index": 0}
                elif tool_name == "browser_close_tab":
                    args = {}
                elif tool_name == "browser_take_screenshot":
                    args = {"filename_prefix": "screenshot"}
                elif tool_name == "browser_wait_for_text":
                    args = {"text": sanitized_prompt.strip()}
                elif tool_name == "markitdown_convert":
                    path_m = re.search(r"(?:file|path)\s+([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)", sanitized_prompt, re.IGNORECASE)
                    if path_m:
                        args = {"file_path": path_m.group(1), "is_file_path": True}
                    else:
                        args = {"content": sanitized_prompt.strip(), "is_file_path": False}
                elif tool_name == "crawl4ai_extract":
                    url_m = re.search(r"https?://[^\s]+", sanitized_prompt)
                    args = {
                        "url": url_m.group(0) if url_m else "https://local.test",
                        "html": sanitized_prompt if "<html" in sanitized_prompt.lower() else None,
                    }
                elif tool_name == "swerex_execute":
                    cmd_m = re.search(r"(?:command|cmd|run):\s*(.+)$", sanitized_prompt, re.IGNORECASE)
                    cmd_str = cmd_m.group(1).strip() if cmd_m else sanitized_prompt.strip()
                    args = {
                        "command": cmd_str.split(),
                        "workspace_root": req.metadata.get("workspace_root", "."),
                    }
                elif tool_name == "dspy_compile_signature":
                    args = {
                        "name": "GeneralTask",
                        "instructions": sanitized_prompt.strip(),
                        "inputs": [{"name": "input", "desc": "User prompt", "prefix": "Input:"}],
                        "outputs": [{"name": "output", "desc": "Model response", "prefix": "Output:"}],
                        "input_values": {"input": sanitized_prompt.strip()},
                    }
                elif tool_name == "inspect_ai_eval":
                    args = {
                        "task_name": "prompt_eval",
                        "samples": [{"id": "s1", "input": sanitized_prompt.strip(), "target": "PASS"}],
                    }
                elif tool_name == "hermes_format_tool_call":
                    args = {
                        "tool_name": "execute_task",
                        "arguments": {"prompt": sanitized_prompt.strip()},
                    }
                elif tool_name == "lightrag_query_graph":
                    args = {
                        "query": sanitized_prompt.strip(),
                        "mode": "dual",
                    }

            approved = bool(req.metadata.get("approved_by_user", False))
            tool_req = ToolExecutionRequest(
                tool_name=tool_name,
                arguments=args,
                approved_by_user=approved,
                approval_token=req.metadata.get("approval_token"),
                session_id=req.session_id,
            )

            tool_result = await self.skill_executor.execute(tool_req)
            exec_duration = (time.perf_counter() - skill_start) * 1000

            steps.append(
                StepRecord(
                    step_number=3,
                    action="SkillExecution",
                    status="COMPLETED" if tool_result.success else "FAILED",
                    detail=f"Tool: {tool_name}, Duration: {tool_result.duration_ms:.2f}ms, Success: {tool_result.success}",
                    duration_ms=exec_duration,
                )
            )

            total_duration = (time.perf_counter() - start_time) * 1000

            if not tool_result.success:
                return CIEResponse(
                    status=ExecutionStatus.ERROR,
                    content=f"Tool execution failed for '{tool_name}': {tool_result.error}",
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                    metadata={"tool_name": tool_name, "error": tool_result.error},
                )

            import json
            formatted_output = (
                f"### Skill Execution: `{tool_name}`\n"
                f"**Permission Used:** `{tool_result.permission_used.value}` | "
                f"**Execution Time:** `{tool_result.duration_ms:.2f}ms`\n\n"
                f"```json\n{json.dumps(tool_result.result, indent=2)}\n```"
            )

            return CIEResponse(
                status=ExecutionStatus.COMPLETED,
                content=formatted_output,
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
                metadata={"tool_name": tool_name, "result": tool_result.result},
            )

        if route.category == IntentCategory.CODE_EXECUTION:
            cmd_m = re.search(r"(?:command|cmd|run|execute):\s*(.+)$", sanitized_prompt, re.IGNORECASE)
            cmd_str = cmd_m.group(1).strip() if cmd_m else sanitized_prompt.strip()

            approved = bool(req.metadata.get("approved_by_user", False))
            tool_req = ToolExecutionRequest(
                tool_name="project_command_run",
                arguments={"command": cmd_str, "cwd": req.metadata.get("workspace_root", ".")},
                approved_by_user=approved,
                approval_token=req.metadata.get("approval_token"),
                session_id=req.session_id,
            )
            tool_result = await self.skill_executor.execute(tool_req)
            exec_duration = (time.perf_counter() - s3_start) * 1000
            steps.append(
                StepRecord(
                    step_number=3,
                    action="CodeExecution",
                    status="COMPLETED" if tool_result.success else "FAILED",
                    detail=f"Tool: project_command_run, Command: {cmd_str[:60]}, Success: {tool_result.success}",
                    duration_ms=exec_duration,
                )
            )
            total_duration = (time.perf_counter() - start_time) * 1000
            if not tool_result.success:
                return CIEResponse(
                    status=ExecutionStatus.ERROR,
                    content=f"Code execution failed: {tool_result.error}",
                    route=route,
                    steps_taken=steps,
                    execution_time_ms=total_duration,
                    warnings=warnings,
                    metadata={"error": tool_result.error},
                )
            res_dict = tool_result.result if isinstance(tool_result.result, dict) else {}
            out_str = res_dict.get("stdout", "") or res_dict.get("stderr", "") or "Execution finished."
            return CIEResponse(
                status=ExecutionStatus.COMPLETED,
                content=f"### Code Execution: `project_command_run`\n\n- **Command:** `{cmd_str}`\n- **Exit Code:** `{res_dict.get('exit_code', 0)}`\n\n```text\n{out_str}\n```",
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
                metadata=res_dict,
            )

        if route.category == IntentCategory.MULTILINGUAL:
            steps.append(
                StepRecord(
                    step_number=3,
                    action="RouteDispatch",
                    status="COMPLETED",
                    detail="Dispatched multilingual prompt to bilingual model.",
                    duration_ms=(time.perf_counter() - s3_start) * 1000,
                )
            )

        # Handle DIRECT and GENERAL routes via bounded inference
        within_budget, p_tokens, total_tokens, budget_warnings = self.budgeter.assess_budget(
            sanitized_prompt, req.system_override
        )
        warnings.extend(budget_warnings)
        if not within_budget:
            steps.append(
                StepRecord(
                    step_number=3,
                    action="ContextBudgetAssessment",
                    status="REJECTED",
                    detail=f"Tokens {total_tokens} exceeded budget.",
                    duration_ms=(time.perf_counter() - s3_start) * 1000,
                )
            )
            total_duration = (time.perf_counter() - start_time) * 1000
            return CIEResponse(
                status=ExecutionStatus.REJECTED,
                content=(
                    "Request exceeded allowable input context budget. "
                    "To prevent silent instruction truncation, please shorten the input or request."
                ),
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
            )

        # Concurrency-controlled model invocation
        try:
            effective_system = req.system_override or TRUTH_PRESERVATION_SYSTEM_PROMPT
            async with self._inference_semaphore:
                ollama_resp = await self.ollama_client.generate(
                    prompt=sanitized_prompt,
                    system_override=effective_system,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    context_tokens=self.budgeter.max_context_tokens,
                )

            raw_content = ollama_resp.get("response", "")
            # Ensure output is also scrubbed of any echoed secrets
            clean_content = redact_secrets(raw_content)

            # Eliminate generic refusals
            generic_refusal_patterns = [
                r"i(?:'m| am)? sorry,?(?: but)? i can(?:'t|not) (?:assist|help) with that",
                r"i cannot fulfill this request",
                r"as an ai(?: language model)?,? i cannot",
            ]
            for pat in generic_refusal_patterns:
                if re.search(pat, clean_content, re.IGNORECASE):
                    clean_content = (
                        "To complete this task, please specify the exact command, target file, or operation. "
                        "You can ask me to run commands, inspect the workspace, fix tests, or create code."
                    )
                    break

            steps.append(
                StepRecord(
                    step_number=3,
                    action="LocalModelInference",
                    status="COMPLETED",
                    detail=f"Tokens: {ollama_resp.get('prompt_eval_count', 0)} prompt, {ollama_resp.get('eval_count', 0)} completion",
                    duration_ms=(time.perf_counter() - s3_start) * 1000,
                )
            )

            resp_meta = {"total_duration_ollama_ns": ollama_resp.get("total_duration")}

            # Hermes tool-call extraction integration
            if "<tool_call>" in clean_content:
                try:
                    hermes_adapter = HermesAgentAdapter()
                    parsed_calls = hermes_adapter.parse_tool_calls(clean_content)
                    if parsed_calls:
                        resp_meta["hermes_tool_calls"] = [
                            {"name": tc.name, "arguments": tc.arguments} for tc in parsed_calls
                        ]
                        steps.append(
                            StepRecord(
                                step_number=4,
                                action="HermesToolCallExtraction",
                                status="COMPLETED",
                                detail=f"Extracted {len(parsed_calls)} tool call(s) via upstream Hermes parser.",
                                duration_ms=0.0,
                            )
                        )
                except Exception as hermes_err:
                    warnings.append(f"Hermes tool extraction error: {hermes_err}")

            total_duration = (time.perf_counter() - start_time) * 1000
            return CIEResponse(
                status=ExecutionStatus.COMPLETED,
                content=clean_content,
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                prompt_tokens=ollama_resp.get("prompt_eval_count"),
                completion_tokens=ollama_resp.get("eval_count"),
                warnings=warnings,
                metadata=resp_meta,
            )

        except OllamaClientError as e:
            steps.append(
                StepRecord(
                    step_number=3,
                    action="LocalModelInference",
                    status="ERROR",
                    detail=str(e),
                    duration_ms=(time.perf_counter() - s3_start) * 1000,
                )
            )
            total_duration = (time.perf_counter() - start_time) * 1000
            return CIEResponse(
                status=ExecutionStatus.ERROR,
                content=f"Inference failed: {str(e)}",
                route=route,
                steps_taken=steps,
                execution_time_ms=total_duration,
                warnings=warnings,
            )

    def get_memory_usage_mb(self) -> float:
        """
        Returns active physical resident set size (RSS) of this Python process in MB.
        """
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
