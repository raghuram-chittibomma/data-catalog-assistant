"""Tests for GradioInterface formatting helpers."""

import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.rag_engine import SearchResult
from src.ui.gradio_interface import GradioInterface


@dataclass
class _FakeProcessor:
    def process(self, text: str):
        return {
            "sql": "SELECT 1",
            "confidence": 0.9,
            "explanation": "ok",
            "tables_used": ["public.orders"],
        }

    def validate_query(self, sql: str) -> bool:
        return sql.strip().upper().startswith("SELECT")


class _FakeRAG:
    def search_data_lineage(self, query, top_k=5):
        return [
            SearchResult(
                data_asset="public.orders",
                description="orders table",
                relevance_score=0.9,
                metadata={"asset_type": "table"},
            )
        ]

    def get_data_lineage(self, asset_name):
        return {
            "asset": {"asset_id": asset_name},
            "upstream": [],
            "downstream": [],
        }


class _FakeImpactTools:
    def get_lineage(self, data_asset: str, direction: str = "both"):
        return {
            "asset": {"asset_id": data_asset},
            "asset_id": data_asset,
            "upstream": ["public.customers"] if direction in ("both", "upstream") else [],
            "downstream": [] if direction == "upstream" else ["sql:foo.sql"],
            "direction": direction,
        }

    def analyze_data_usage(self, data_asset: str):
        return {
            "asset_id": data_asset,
            "impact_score": 0.45,
            "queries": [{"asset_id": "sql:orders_by_customer.sql", "asset_type": "sql"}],
            "etl_jobs": [],
            "reports": [],
            "downstream": [{"asset_id": "sql:orders_by_customer.sql", "asset_type": "sql"}],
        }

    def assess_change_impact(self, data_asset: str, change_description: str):
        return {
            "asset_id": data_asset,
            "change": change_description,
            "risk_level": "medium",
            "impact_score": 0.45,
            "downstream_count": 1,
            "affected_queries": [{"asset_id": "sql:orders_by_customer.sql", "asset_type": "sql"}],
            "affected_etl": [],
            "affected_reports": [],
        }


class _FakeQueryTools:
    def validate_query(self, sql: str):
        ok = "DROP" not in sql.upper()
        return {
            "valid": ok,
            "errors": [] if ok else ["Contains DROP"],
            "warnings": [],
        }


class _FakeCatalog:
    def get_catalog_summary(self):
        return {
            "total_assets": 23,
            "tables": 14,
            "sql_assets": 5,
            "etl_processes": 4,
        }

    def list_tables(self, pattern=None):
        tables = [
            {"asset_id": "public.orders", "name": "public.orders"},
            {"asset_id": "public.customers", "name": "public.customers"},
        ]
        if pattern:
            p = pattern.lower()
            tables = [t for t in tables if p in t["asset_id"]]
        return tables

    def list_etl_processes(self):
        return [{"asset_id": "etl:etl_samples/load_orders_summary.yaml#load_orders_summary"}]


def test_format_search_results():
    ui = GradioInterface(rag_engine=_FakeRAG())
    out = ui.format_search_results("orders", top_k=3)
    assert "public.orders" in out
    assert "0.900" in out


def test_format_lineage_via_impact_tools():
    ui = GradioInterface(impact_tools=_FakeImpactTools())
    diagram, raw_json = ui.format_lineage_views("public.orders", direction="upstream")
    assert "public.customers" in diagram
    assert "▶ public.orders" in diagram
    assert "sql:foo.sql" not in diagram
    assert "Upstream" in diagram
    assert '"public.orders"' in raw_json or "public.orders" in raw_json


def test_format_lineage_downstream_flow():
    ui = GradioInterface(impact_tools=_FakeImpactTools())
    diagram, _ = ui.format_lineage_views("public.orders", direction="downstream")
    assert "▶ public.orders" in diagram
    assert "sql:foo" in diagram
    assert "──▶" in diagram
    assert "public.customers" not in diagram


def test_format_validate_sql_valid():
    ui = GradioInterface(query_tools=_FakeQueryTools())
    out = ui.format_validate_sql("SELECT 1 FROM public.orders")
    assert "**Valid**" in out


def test_format_validate_sql_invalid():
    ui = GradioInterface(query_tools=_FakeQueryTools())
    out = ui.format_validate_sql("DROP TABLE public.orders")
    assert "**Invalid**" in out
    assert "DROP" in out


def test_format_data_usage():
    ui = GradioInterface(impact_tools=_FakeImpactTools())
    html_out, raw = ui.format_data_usage_views("public.orders")
    assert "0.45" in html_out
    assert "orders_by_customer" in html_out
    assert "<details" in html_out
    assert "public.orders" in raw


def test_format_change_impact():
    ui = GradioInterface(impact_tools=_FakeImpactTools())
    html_out, raw = ui.format_change_impact_views("public.orders", "Drop column freight")
    assert "MEDIUM" in html_out
    assert "Drop column freight" in html_out
    assert "orders_by_customer" in html_out
    assert "<details" in html_out
    assert "risk" in html_out.lower() or "MEDIUM" in html_out


def test_format_catalog_summary():
    ui = GradioInterface(data_catalog=_FakeCatalog())
    out = ui.format_catalog_summary("")
    assert "23" in out
    assert "public.orders" in out


def test_format_sql_generation():
    ui = GradioInterface(query_processor=_FakeProcessor())
    out = ui.format_sql_generation("count orders")
    assert "```sql" in out
    assert "SELECT 1" in out
    assert "public.orders" in out


def test_build_interface_returns_blocks():
    gr = pytest.importorskip("gradio")

    ui = GradioInterface(
        rag_engine=_FakeRAG(),
        query_processor=_FakeProcessor(),
        query_tools=_FakeQueryTools(),
        impact_tools=_FakeImpactTools(),
        data_catalog=_FakeCatalog(),
    )
    demo = ui.build_interface()
    assert isinstance(demo, gr.Blocks)
