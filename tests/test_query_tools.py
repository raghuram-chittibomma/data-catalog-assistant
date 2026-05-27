"""Tests for QueryTools and QueryProcessor response shape."""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.query_processor import QueryProcessor
from src.mcp_server.tools.query_tools import QueryTools


class _FakeRAG:
    def search_data_lineage(self, query: str, top_k: int = 5):
        return []

    def generate_query(self, description: str, catalog_context=None):
        return {"query": "SELECT 1", "confidence": 0.9, "explanation": "ok"}


def test_normalize_llm_result_maps_query_key():
    out = QueryProcessor.normalize_llm_result({"query": "SELECT 1", "confidence": 0.5})
    assert out["sql"] == "SELECT 1"
    assert out["confidence"] == 0.5


def test_query_processor_delegates_to_rag_engine():
    processor = QueryProcessor(rag_engine=_FakeRAG())
    out = processor.process("count rows")
    assert out["sql"] == "SELECT 1"
    assert out["explanation"] == "ok"


def test_query_tools_uses_processor_first():
    tools = QueryTools(query_processor=QueryProcessor(rag_engine=_FakeRAG()))
    out = tools.generate_query("test")
    assert out["sql"] == "SELECT 1"


def test_query_tools_falls_back_to_rag_engine():
    tools = QueryTools(rag_engine=_FakeRAG())
    out = tools.generate_query("test")
    assert out["sql"] == "SELECT 1"


def test_query_tools_returns_processor_result_when_sql_empty():
    """Phase 3: keep tables_used and explanation even when LLM returns no SQL."""

    class _ProcessorRAG:
        def search_data_lineage(self, query, top_k=5):
            return []

        def generate_query(self, description, catalog_context=None):
            return {"query": "", "confidence": 0.0, "explanation": "LLM failed"}

    from src.core.query_processor import QueryProcessor

    processor = QueryProcessor(rag_engine=_ProcessorRAG())
    tools = QueryTools(query_processor=processor, rag_engine=_ProcessorRAG())
    out = tools.generate_query("test")
    assert out["sql"] == ""
    assert out["explanation"] == "LLM failed"
