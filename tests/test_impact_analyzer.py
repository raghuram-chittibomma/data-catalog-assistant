"""Tests for ImpactAnalyzer usage and change assessment."""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.impact_analyzer import ImpactAnalyzer
from src.mcp_server.tools.impact_tools import ImpactTools


def _store_with_downstream():
    store = Mock()
    store.get_asset_metadata.return_value = {
        "asset_id": "public.orders",
        "asset_type": "table",
    }
    store.get_upstream_assets.return_value = [
        {"asset_id": "public.customers", "asset_type": "table"}
    ]
    store.get_downstream_assets.return_value = [
        {"asset_id": "sql:sql_samples/orders_by_customer.sql", "asset_type": "sql"},
        {
            "asset_id": "etl:etl_samples/load_orders_summary.yaml#load_orders_summary",
            "asset_type": "etl",
        },
    ]
    return store


def test_analyze_data_usage_uses_downstream_not_all_sql():
    analyzer = ImpactAnalyzer(metadata_store=_store_with_downstream())
    out = analyzer.analyze_data_usage("public.orders")

    assert len(out["queries"]) == 1
    assert out["queries"][0]["asset_type"] == "sql"
    assert len(out["etl_jobs"]) == 1
    assert out["impact_score"] == 0.3


def test_stored_zero_uses_lineage_calculated_score():
    store = _store_with_downstream()
    store.get_asset_metadata.return_value = {
        "asset_id": "public.orders",
        "asset_type": "table",
        "impact_score": 0.0,
    }
    store.update_impact_score.return_value = True

    analyzer = ImpactAnalyzer(metadata_store=store)
    score = analyzer.resolve_impact_score("public.orders", persist=True)

    assert score == 0.3
    store.update_impact_score.assert_called_once_with("public.orders", 0.3)


def test_recompute_all_impact_scores():
    store = Mock()
    store.store = {
        "assets": {
            "public.orders": {"asset_id": "public.orders", "impact_score": 0.0},
            "public.customers": {"asset_id": "public.customers", "impact_score": 0.0},
        }
    }

    def downstream(asset_id):
        if asset_id == "public.orders":
            return [{"asset_id": "sql:foo", "asset_type": "sql"}]
        return []

    store.get_upstream_assets.side_effect = lambda aid: (
        [{"asset_id": "public.customers"}] if aid == "public.orders" else []
    )
    store.get_downstream_assets.side_effect = downstream
    store.update_impact_score.return_value = True

    analyzer = ImpactAnalyzer(metadata_store=store)
    updated = analyzer.recompute_all_impact_scores()

    assert updated == 2
    assert store.update_impact_score.call_count == 2


def test_assess_change_impact_risk_from_score():
    store = _store_with_downstream()
    analyzer = ImpactAnalyzer(metadata_store=store)
    tools = ImpactTools(impact_analyzer=analyzer)

    out = tools.assess_change_impact("public.orders", "Rename order_id column")

    assert out["risk_level"] in ("low", "medium", "high")
    assert out["change"] == "Rename order_id column"
    assert out["asset_id"] == "public.orders"
    assert out["asset_resolved_from"] == "field"
    assert len(out["affected_queries"]) == 1


def test_assess_change_impact_uses_table_from_change_text():
    store = _store_with_downstream()
    store.get_asset_metadata.side_effect = lambda aid: {
        "asset_id": aid,
        "asset_type": "table",
    }
    analyzer = ImpactAnalyzer(metadata_store=store)
    tools = ImpactTools(impact_analyzer=analyzer)

    out = tools.assess_change_impact(
        "public.orders",
        "Rename column company_name to legal_name on public.customers",
    )

    assert out["asset_id"] == "public.customers"
    assert out["asset_resolved_from"] == "change_text"
    assert out["resolution_warning"]
    store.get_asset_metadata.assert_any_call("public.customers")
