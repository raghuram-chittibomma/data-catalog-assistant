"""Tests for LLM prompt logging in RAGEngine."""

import logging

from src.core.rag_engine import RAGEngine


class MessageCapturingLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def create(self, model, messages, temperature=0.0, max_tokens=512):
        return {"choices": [{"message": {"content": self.response_text}}]}


def test_log_prompts_emits_full_messages_when_enabled(caplog):
    caplog.set_level(logging.INFO)
    llm = MessageCapturingLLM("SELECT 1\nEXPLANATION: ok")
    engine = RAGEngine(
        llm_client=llm,
        config={
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "log_prompts": True,
            }
        },
    )

    engine.generate_query(
        "count orders",
        catalog_context="--- Catalog asset 1: public.orders ---\norder_id",
    )

    text = caplog.text
    assert "LLM prompt outgoing" in text
    assert "--- system ---" in text
    assert "--- user ---" in text
    assert "expert SQL generator" in text
    assert "public.orders" in text
    assert "count orders" in text


def test_log_prompts_skipped_when_disabled(caplog):
    caplog.set_level(logging.INFO)
    llm = MessageCapturingLLM("SELECT 1")
    engine = RAGEngine(
        llm_client=llm,
        config={
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "log_prompts": False,
            }
        },
    )

    engine.generate_query("count orders")

    assert "LLM prompt outgoing" not in caplog.text
