"""Tests for impact diagram HTML builders."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.impact_view import (
    build_change_impact_html,
    build_impact_json,
    build_usage_impact_html,
    risk_level_from_score,
)


def test_build_usage_impact_html_tree_and_details():
    data = {
        "asset": {"asset_id": "public.orders", "asset_type": "table", "description": "Orders fact"},
        "asset_id": "public.orders",
        "impact_score": 0.35,
        "queries": [{"asset_id": "sql:sql_samples/orders_by_customer.sql", "asset_type": "sql"}],
        "etl_jobs": [
            {
                "asset_id": "etl:etl_samples/load_orders_summary.yaml#load_orders_summary",
                "asset_type": "etl",
            }
        ],
        "downstream": [],
    }
    html = build_usage_impact_html(data, "public.orders")

    assert "bdw-impact" in html
    assert "public.orders" in html
    assert "Impact score" in html
    assert "0.35" in html
    assert "<details" in html
    assert "SQL (1)" in html or "sql" in html.lower()
    assert "orders_by_customer" in html


def test_build_change_impact_html_risk_badge():
    data = {
        "asset_id": "public.orders",
        "change": "Drop column freight",
        "risk_level": "high",
        "impact_score": 0.75,
        "downstream_count": 2,
        "affected_queries": [{"asset_id": "sql:foo.sql", "asset_type": "sql"}],
        "affected_etl": [],
        "affected_reports": [],
    }
    html = build_change_impact_html(data, "public.orders")

    assert "HIGH" in html
    assert "Drop column freight" in html
    assert "Blast radius" in html
    assert "<details" in html
    assert "foo.sql" in html


def test_risk_level_from_score_thresholds():
    assert risk_level_from_score(0.1) == "low"
    assert risk_level_from_score(0.35) == "medium"
    assert risk_level_from_score(0.61) == "high"
    assert risk_level_from_score(1.0) == "high"


def test_usage_impact_high_score_shows_high_badge():
    data = {
        "asset_id": "public.orders",
        "impact_score": 1.0,
        "queries": [],
        "etl_jobs": [],
        "downstream": [],
    }
    html = build_usage_impact_html(data, "public.orders")

    assert "HIGH" in html
    assert "#b91c1c" in html
    assert "LOW" not in html


def test_build_impact_json():
    out = build_impact_json({"asset_id": "public.orders"})
    assert "```json" in out
