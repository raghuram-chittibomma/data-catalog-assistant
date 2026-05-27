"""Phase 3 tests: RAG context in QueryProcessor and RAGEngine."""

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.query_processor import QueryProcessor
from src.core.rag_engine import RAGEngine, SearchResult


@dataclass
class _Hit:
    data_asset: str
    description: str
    relevance_score: float
    metadata: dict


class RecordingRAGEngine:
    """Minimal stand-in for RAGEngine in unit tests."""

    def __init__(self, hits: List[SearchResult], llm_response: Dict[str, Any]):
        self._hits = hits
        self._llm_response = llm_response
        self.last_catalog_context: Optional[str] = None
        self.last_nl: Optional[str] = None

    def search_data_lineage(self, query: str, top_k: int = 5):
        return self._hits[:top_k]

    def generate_query(self, natural_language: str, catalog_context: Optional[str] = None):
        self.last_nl = natural_language
        self.last_catalog_context = catalog_context
        return self._llm_response


def test_build_catalog_context_extracts_tables():
    hits = [
        SearchResult(
            data_asset="public.orders",
            description="Table orders\nColumns: order_id, customer_id",
            relevance_score=0.9,
            metadata={"asset_type": "table"},
        ),
        SearchResult(
            data_asset="sql:orders_by_customer.sql",
            description="SELECT from customers",
            relevance_score=0.8,
            metadata={"asset_type": "sql"},
        ),
    ]
    engine = RecordingRAGEngine(hits, {"query": "SELECT 1", "confidence": 0.9, "explanation": ""})
    processor = QueryProcessor(rag_engine=engine, schema_context={"rag_top_k": 5})

    context, tables = processor.build_catalog_context("customer orders")

    assert "public.orders" in context
    assert "order_id" in context
    assert tables == ["public.orders"]


def test_process_passes_catalog_context_to_llm():
    hits = [
        SearchResult(
            data_asset="public.customers",
            description="Table customers\nColumns: id, name",
            relevance_score=0.95,
            metadata={"asset_type": "table"},
        ),
    ]
    engine = RecordingRAGEngine(
        hits,
        {"query": "SELECT id, name FROM public.customers", "confidence": 0.85, "explanation": "ok"},
    )
    processor = QueryProcessor(rag_engine=engine)

    out = processor.process("list all customers")

    assert out["sql"].startswith("SELECT")
    assert "public.customers" in out["tables_used"]
    assert engine.last_catalog_context is not None
    assert "public.customers" in engine.last_catalog_context
    assert engine.last_nl == "list all customers"


class MessageCapturingLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.messages: List[Dict[str, str]] = []

    def create(self, model, messages, temperature=0.0, max_tokens=512):
        self.messages = messages
        return {"choices": [{"message": {"content": self.response_text}}]}


def test_rag_engine_includes_catalog_context_in_prompt():
    llm = MessageCapturingLLM("SELECT 1 FROM public.orders\nEXPLANATION: test")
    engine = RAGEngine(
        llm_client=llm,
        config={"llm": {"provider": "openai", "model": "gpt-4"}},
    )
    ctx = "--- Catalog asset 1: public.orders (table) ---\nColumns: order_id"

    engine.generate_query("count orders", catalog_context=ctx)

    user_msg = llm.messages[1]["content"]
    assert "public.orders" in user_msg
    assert "count orders" in user_msg
    assert "Data catalog context" in user_msg
