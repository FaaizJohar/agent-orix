"""
Context management and token budgeting for CIE.
Maintains bounded memory working set on host hardware.
"""

from typing import Tuple, List, Optional
from cie.config import get_config


def estimate_tokens(text: str) -> int:
    """
    Heuristic token estimator for Qwen / BPE tokenizers (~3.6 characters per token + safety margin).
    Conservative estimation prevents context overflow in Ollama.
    """
    if not text:
        return 0
    # Safe conservative multiplier: 1 token ~= 3.5 chars
    return max(1, int(len(text) / 3.5) + 1)


class ContextBudgeter:
    def __init__(self, max_context_tokens: Optional[int] = None, max_output_tokens: Optional[int] = None):
        cfg = get_config()
        self.max_context_tokens = max_context_tokens or cfg.max_context_tokens
        self.max_output_tokens = max_output_tokens or cfg.max_output_tokens
        # Reserve tokens for model response
        self.max_input_tokens = max(128, self.max_context_tokens - self.max_output_tokens - 64)

    def assess_budget(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[bool, int, int, List[str]]:
        """
        Assesses whether the given prompt and system instructions fit within the safe token budget.
        Returns: (is_within_budget, estimated_prompt_tokens, estimated_total_tokens, warnings)
        """
        warnings: List[str] = []
        p_tokens = estimate_tokens(prompt)
        s_tokens = estimate_tokens(system_prompt or "")
        total_input = p_tokens + s_tokens
        
        if total_input > self.max_input_tokens:
            excess = total_input - self.max_input_tokens
            warnings.append(
                f"Prompt + system instructions (~{total_input} tokens) exceed safe input budget "
                f"(~{self.max_input_tokens} tokens) by approx {excess} tokens. "
                "Silent truncation is prohibited to prevent logic corruption."
            )
            return False, p_tokens, total_input, warnings
            
        return True, p_tokens, total_input, warnings
