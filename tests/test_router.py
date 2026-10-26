"""
Tests for CIE Deterministic Router and Intent Classifier.
"""

import pytest
from cie.router import DeterministicRouter
from cie.schemas import IntentCategory


@pytest.fixture
def router():
    return DeterministicRouter()


def test_route_direct_coding(router):
    cases = [
        "Write a Python function to reverse a linked list.",
        "Implement quicksort algorithm in JavaScript.",
        "Debug this error in my Python code: IndexError: list index out of range",
        "Explain how this function works:\ndef add(a, b): return a + b",
        "```python\ndef solve(): pass\n```",
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.DIRECT, f"Failed for prompt: {prompt}"
        assert decision.confidence >= 0.90
        assert not decision.fallback_applied


def test_route_research(router):
    cases = [
        "Search the web for the latest updates on Python 3.14.",
        "What is the current stock price of Apple today?",
        "Browse the internet and find recent news about AI.",
        "What are the major 2026 releases in web development?",
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.RESEARCH, f"Failed for prompt: {prompt}"
        assert decision.confidence >= 0.90


def test_route_knowledge(router):
    cases = [
        "Tell me about Cavrix Core.",
        "Who founded Cavrix Core?",
        "What is the mission of cavrixcore.com?",
        "Is Faaiz Johar a founder of Cavrix?",
        "Search my indexed documents for the project notes.",
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.KNOWLEDGE, f"Failed for prompt: {prompt}"
        assert decision.confidence >= 0.90


def test_route_code_execution(router):
    cases = [
        "Run this python code and show me the output.",
        "Execute the unit tests using pytest.",
        "Run in terminal and evaluate this snippet.",
        "Execute this script in sandbox mode.",
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.CODE_EXECUTION, f"Failed for prompt: {prompt}"
        assert decision.confidence >= 0.90


def test_route_multilingual(router):
    cases = [
        "यह कोड कैसे काम करता है मुझे बताइए।",  # Devanagari Hindi
        "یہ کوڈ کیا کرتا ہے؟",  # Arabic / Urdu script
        "Mujhe yeh python code samjhao kaise karein",  # Romanized Hinglish
        "Aap mujhe batao yeh function kaise likhein",  # Romanized Hinglish
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.MULTILINGUAL, f"Failed for prompt: {prompt}"
        assert decision.confidence >= 0.90


def test_route_general_fallback(router):
    cases = [
        "Hello!",
        "How are you doing?",
        "Tell me a philosophical joke.",
        "What is the meaning of life?",
    ]
    for prompt in cases:
        decision = router.route(prompt)
        assert decision.category == IntentCategory.GENERAL, f"Failed for prompt: {prompt}"
        assert decision.fallback_applied is True


def test_precedence_execution_over_coding(router):
    # Prompt has both coding keywords ('python function') and execution command ('run this')
    prompt = "Write a python function and execute this script to test it."
    decision = router.route(prompt)
    assert decision.category == IntentCategory.CODE_EXECUTION
