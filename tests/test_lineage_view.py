"""Tests for lineage diagram formatting."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.lineage_view import build_lineage_diagram, build_lineage_json


def test_build_lineage_diagram_both_directions():
    data = {
        "asset": {"asset_id": "public.orders", "asset_type": "table"},
        "asset_id": "public.orders",
        "upstream": [
            {"asset_id": "public.customers", "asset_type": "table", "relationship_type": "fk"},
        ],
        "downstream": [
            {"asset_id": "sql:sql_samples/orders_by_customer.sql", "asset_type": "sql"},
        ],
        "direction": "both",
    }
    md = build_lineage_diagram(data, "public.orders", direction="both")

    assert "## Lineage: `public.orders`" in md
    assert "public.customers" in md
    assert "orders_by_customer" in md
    assert "▶ public.orders" in md
    assert "──▶" in md
    assert "```json" not in md


def test_build_lineage_json():
    data = {"asset_id": "public.orders", "upstream": []}
    out = build_lineage_json(data)
    assert "```json" in out
    assert "public.orders" in out
