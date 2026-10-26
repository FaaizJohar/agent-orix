"""
CavrixCode Phase 5.1 — Self-Correction Protocol.
Implements:
1. Transparent, non-defensive acknowledgment when earlier claims are disproven.
2. Formats self-correction responses:
   - Identify incorrect claim
   - Acknowledge error
   - Cite decisive evidence
   - State corrected conclusion
   - Identify dependent revisions
3. Validates incoming user corrections against evidence (never blindly agrees).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CorrectionRecord(BaseModel):
    original_claim: str
    is_disproven: bool
    decisive_evidence: str
    corrected_conclusion: str
    dependent_revisions: List[str] = Field(default_factory=list)


class SelfCorrectionEngine:
    """
    Manages correction workflows without defensiveness or retroactive rewriting.
    """

    @classmethod
    def format_self_correction(cls, record: CorrectionRecord) -> str:
        """
        Formats a structured, non-defensive self-correction response.
        """
        output_lines = [
            "### Correction Notice",
            "**My previous answer was wrong.**\n",
            f"- **Incorrect Claim:** {record.original_claim}",
            f"- **Decisive Evidence:** {record.decisive_evidence}",
            f"- **Corrected Conclusion:** {record.corrected_conclusion}",
        ]
        if record.dependent_revisions:
            output_lines.append("\n**Dependent Revisions Required:**")
            for rev in record.dependent_revisions:
                output_lines.append(f"- {rev}")

        return "\n".join(output_lines)

    @classmethod
    def evaluate_user_correction(
        cls,
        user_correction_text: str,
        prior_claim: str,
        inspected_facts: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Evaluates whether a user's correction is factually accurate or mistaken.
        Does not automatically accept or automatically reject user corrections.
        """
        user_lower = user_correction_text.lower()
        
        # Check against ground-truth facts
        for key, fact in inspected_facts.items():
            key_words = [w.strip() for w in key.lower().split() if len(w) >= 3]
            fact_words = [w.strip() for w in fact.lower().split() if len(w) >= 4 and w not in {"with", "that", "from", "based", "have", "total"}]
            is_relevant = (key.lower() in user_lower) or any(w in user_lower for w in key_words) or any(w in user_lower for w in fact_words)
            if is_relevant:
                if fact.lower() in user_lower:
                    # User is right!
                    return {
                        "accepted": True,
                        "explanation": f"The correction is verified by inspected fact: {fact}",
                        "message": f"You are correct. {fact}"
                    }
                else:
                    # User correction contradicts inspected fact
                    return {
                        "accepted": False,
                        "explanation": f"Correction contradicts inspected evidence: {fact}",
                        "message": (
                            f"That correction contradicts inspected evidence.\n\n"
                            f"**Inspected Fact:** {fact}\n\n"
                            f"The earlier conclusion remains grounded in this verifiable fact."
                        )
                    }

        # If indeterminate
        return {
            "accepted": False,
            "explanation": "Insufficient evidence to verify or refute user correction.",
            "message": "I cannot verify that correction with the currently inspected evidence."
        }
