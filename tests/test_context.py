"""
Tests for CIE context budgeting and token estimation.
"""

from cie.context import ContextBudgeter, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 1
    long_text = "x" * 700
    assert 180 <= estimate_tokens(long_text) <= 220


def test_budget_within_limits():
    budgeter = ContextBudgeter(max_context_tokens=1000, max_output_tokens=200)
    # Available input = 1000 - 200 - 64 = 736 tokens
    prompt = "Write a python function to add two numbers."
    within_budget, p_tokens, total_tokens, warnings = budgeter.assess_budget(prompt)
    assert within_budget is True
    assert len(warnings) == 0


def test_budget_exceeded_no_silent_truncation():
    budgeter = ContextBudgeter(max_context_tokens=200, max_output_tokens=100)
    # Available input = 200 - 100 - 64 = 36 tokens (~120 chars)
    massive_prompt = "word " * 200
    within_budget, p_tokens, total_tokens, warnings = budgeter.assess_budget(massive_prompt)
    assert within_budget is False
    assert any("Silent truncation is prohibited" in w for w in warnings)
