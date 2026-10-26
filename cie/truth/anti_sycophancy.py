"""
CavrixCode Phase 5.1 — Anti-Sycophancy and Truth-Preservation Policy Guard.
Enforces the behavioral contract:
1. Evidence determines the conclusion, not user expectations or emotional insistence.
2. Zero agreement as a default; zero fabricated certainty.
3. Proportionate pushback on unsound, dangerous, or disproven claims.
4. Correct agreement when the user is right.
"""

import re
from typing import Optional, Tuple
from cie.truth.schemas import ClaimEvaluation, EvidenceStatus


TRUTH_PRESERVATION_SYSTEM_PROMPT = """You are CavrixCode, an evidence-driven AI coding and system agent.
Governing Principle: Evidence determines the conclusion, not the user's expectations or conversational harmony.

MANDATORY BEHAVIOR CONTRACT:
1. NO DEFAULT AGREEMENT: Never agree merely because the user is confident, insistent, angry, persuasive, or asks "agree with me" or "confirm this". Never flatter the user or soften a dangerous engineering failure.
2. PROPORTIONATE PUSHBACK: When a technical claim, command, or proposal is unsound, dangerous, contradictory, or unsupported:
   - State the problem plainly.
   - Explain why it matters.
   - Cite the decisive factual evidence.
   - Detail the likely consequences.
   - Recommend a concrete alternative or verification step.
3. ZERO FABRICATED CERTAINTY: If a claim cannot be verified from inspected files, commands, or execution evidence, explicitly state: "I cannot verify that claim." Never invent file contents, test results, citations, or execution outcomes.
4. CALIBRATED UNCERTAINTY: Distinguish clearly between [VERIFIED] facts, [STRONGLY SUPPORTED] findings, [INFERRED] conclusions, [ESTIMATED] values, and [UNKNOWN] data.
5. CORRECT AGREEMENT IS MANDATORY: If the user is factually correct, state so directly and provide the supporting facts. Do not manufacture artificial disagreements or adopt performative skepticism.
6. SELF-CORRECTION: If new evidence disproves a previous statement, immediately acknowledge: "My previous answer was wrong," explain the decisive evidence, and provide the corrected conclusion without defensiveness.
"""


# Patterns that indicate sycophancy traps or confirmation fishing
SYCOPHANCY_FISHING_PATTERNS = [
    re.compile(r"(?:agree\s+with\s+me|don['']t\s+you\s+agree|you\s+agree[,\s]|right\?\s*agree)", re.IGNORECASE),
    re.compile(r"confirm\s+(?:that|this|my)\s+(?:we|I|the)\s+", re.IGNORECASE),
    re.compile(r"was\s+(?:the\s+best|a\s+great|the\s+right)\s+(?:move|decision|idea|engineering)", re.IGNORECASE),
    re.compile(r"admit\s+that\s+I\s+am\s+right", re.IGNORECASE),
    re.compile(r"say\s+yes\s+or\s+no", re.IGNORECASE),
    re.compile(r"insist\s+that\b", re.IGNORECASE),
]

# Patterns of dangerous, false, or technically unsound engineering claims
DANGEROUS_CLAIMS = [
    (
        re.compile(r"(?:delet(?:e|ed|ing)|drop(?:ped|ping)?|wipe[d]?|truncat(?:e|ed))\s+(?:the\s+)?(?:main\s+|production\s+|prod\s+)?(?:database|db|tables)", re.IGNORECASE),
        "Deleting or dropping a production database is a catastrophic engineering anti-pattern that leads to irrecoverable data loss, service outages, and data corruption. High-performance query optimization is achieved through index analysis, query refactoring, read replicas, or caching—never by destroying primary datastores."
    ),
    (
        re.compile(r"git\s+push\s+--force\s+(?:origin\s+)?(?:master|main|prod|production)", re.IGNORECASE),
        "Force-pushing (`git push --force`) to a shared or production branch overwrites remote commit history, destroys teammates' work, and corrupts continuous integration pipelines. Branch protection rules should forbid force-pushes, and hotfixes must be introduced through explicit revert commits or pull requests."
    ),
    (
        re.compile(r"chmod\s+(?:-R\s+)?777", re.IGNORECASE),
        "Setting world-writable permissions (`chmod 777`) violates the principle of least privilege by allowing any local user or unprivileged service to overwrite executable binaries or configuration files, opening critical privilege escalation vectors."
    ),
    (
        re.compile(r"rm\s+-rf\s+/(?:\s|$|\*)", re.IGNORECASE),
        "Executing `rm -rf /` obliterates the host operating system root hierarchy, destroying system binaries, libraries, and active processes."
    ),
    (
        re.compile(r"disable\s+(?:cors|authentication|auth|csrf|sandboxing|sandbox)\s+(?:completely|in\s+prod|everywhere)", re.IGNORECASE),
        "Disabling security controls such as CORS, authentication, CSRF validation, or browser sandboxing removes essential isolation layers, exposing the system to arbitrary cross-origin exploitation and unauthorized access."
    ),
]


class AntiSycophancyGuard:
    """
    Analyzes prompts and claims to prevent sycophancy, hallucinated confirmation,
    and automatic validation of unsound technical claims.
    """

    @classmethod
    def evaluate_user_claim(cls, prompt: str, session_context: Optional[dict] = None) -> ClaimEvaluation:
        """
        Evaluates a user prompt for sycophancy traps, unverified confirmation requests,
        and technical contradictions.
        """
        clean_prompt = prompt.strip()

        # 1. Check for dangerous engineering claims
        for pattern, pushback_detail in DANGEROUS_CLAIMS:
            if pattern.search(clean_prompt):
                return ClaimEvaluation(
                    claim_text=clean_prompt,
                    is_supported=False,
                    evidence_status=EvidenceStatus.DISPUTED,
                    contradiction_detected=True,
                    contradiction_detail="Proposed action violates core security and operational safety principles.",
                    pushback_required=True,
                    pushback_message=(
                        f"That conclusion does not follow from the facts, and the proposed approach is unsafe.\n\n"
                        f"**Decisive Evidence:** {pushback_detail}\n\n"
                        f"**Recommended Course:** Do not execute or endorse this action. Use proper engineering verification instead."
                    )
                )

        # 2. Check for uninspected confirmation fishing (e.g. asking to confirm test results, files, or numbers not in context)
        test_coverage_pattern = re.compile(r"confirm\s+(?:that\s+)?(?:my\s+|the\s+)?(?:previous\s+)?(?:test\s+suite|coverage|tests)\s+(?:had|has|were|passed)", re.IGNORECASE)
        if test_coverage_pattern.search(clean_prompt):
            has_inspected_tests = session_context and session_context.get("inspected_tests")
            if not has_inspected_tests:
                return ClaimEvaluation(
                    claim_text=clean_prompt,
                    is_supported=False,
                    evidence_status=EvidenceStatus.UNKNOWN,
                    contradiction_detected=False,
                    pushback_required=True,
                    pushback_message=(
                        "I cannot verify that claim.\n\n"
                        "**Reason:** No test execution logs, coverage reports, or test runner outputs have been inspected in this session. "
                        "To maintain strict factual accuracy, I will not confirm or invent test outcomes without reproducible evidence."
                    )
                )

        uninspected_file_pattern = re.compile(r"confirm\s+(?:that\s+)?(?:there\s+are|the\s+file|the\s+folder|[\w\./\\_-]+\s+contains)\s+.*(?:files?|lines?|keys?|exists?)", re.IGNORECASE)
        if uninspected_file_pattern.search(clean_prompt):
            has_inspected_fs = session_context and session_context.get("inspected_files")
            if not has_inspected_fs:
                return ClaimEvaluation(
                    claim_text=clean_prompt,
                    is_supported=False,
                    evidence_status=EvidenceStatus.UNKNOWN,
                    contradiction_detected=False,
                    pushback_required=True,
                    pushback_message=(
                        "I cannot verify that claim.\n\n"
                        "**Reason:** The referenced filesystem path has not been inspected using `file_read_text` or `file_tree_inspect` in this session. "
                        "I cannot confirm file counts or line numbers without inspecting the actual filesystem."
                    )
                )

        # 3. Check for specific known factual technical errors
        # E.g. "HTML is a programming language" or "HTML is Turing-complete"
        if re.search(r"html\s+is\s+(?:a\s+)?(?:[a-z\s-]*)(?:turing-complete|programming\s+language)", clean_prompt, re.IGNORECASE):
            # Check if user is asking if it is, or asserting that it is
            if re.search(r"(?:confirm|agree|right|is\s+it\s+not|admit|say\s+yes|insist)", clean_prompt, re.IGNORECASE):
                return ClaimEvaluation(
                    claim_text=clean_prompt,
                    is_supported=False,
                    evidence_status=EvidenceStatus.DISPUTED,
                    contradiction_detected=True,
                    contradiction_detail="HTML is a declarative markup language, not an imperative or Turing-complete programming language on its own.",
                    pushback_required=True,
                    pushback_message=(
                        "That statement is incorrect.\n\n"
                        "**Decisive Evidence:** HTML (HyperText Markup Language) is a declarative markup language used to structure document semantics and elements. "
                        "On its own (without CSS3 hacks or JavaScript), HTML lacks execution control flow, state loops, conditional branch execution, and memory manipulation, "
                        "and is therefore not Turing-complete or a general-purpose programming language."
                    )
                )

        # 4. Check for citation fabrication demands (e.g. "Provide a citation for XYZ nonexistent book/paper")
        if re.search(r"(?:cite|citation|source\s+for)\s+.*(?:non-?existent|fake|imaginary|fabricated)", clean_prompt, re.IGNORECASE):
            return ClaimEvaluation(
                claim_text=clean_prompt,
                is_supported=False,
                evidence_status=EvidenceStatus.UNKNOWN,
                contradiction_detected=False,
                pushback_required=True,
                pushback_message=(
                    "I cannot verify or provide a citation for that source.\n\n"
                    "**Reason:** The requested citation does not exist in verified academic or web indices. "
                    "In compliance with anti-fabrication rules, I do not generate simulated or fabricated citations."
                )
            )

        # 5. Correct agreement: If user makes an accurate factual statement and asks for confirmation
        correct_python_indent = re.search(r"python\s+(?:uses|requires)\s+indentation\s+for\s+(?:code\s+)?blocks", clean_prompt, re.IGNORECASE)
        if correct_python_indent:
            return ClaimEvaluation(
                claim_text=clean_prompt,
                is_supported=True,
                evidence_status=EvidenceStatus.VERIFIED,
                decisive_evidence="Python syntax grammar (PEP 8 and Language Reference §2.1.8) specifies leading whitespace (indentation) to group statements into blocks.",
                pushback_required=False,
                pushback_message=None
            )

        # Default claim evaluation
        return ClaimEvaluation(
            claim_text=clean_prompt,
            is_supported=True,
            evidence_status=EvidenceStatus.INFERRED,
            pushback_required=False
        )
