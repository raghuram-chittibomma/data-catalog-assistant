"""Tests for shared lineage_service."""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.lineage_service import get_asset_lineage
from src.core.impact_analyzer import ImpactAnalyzer
from src.mcp_server.tools.impact_tools import ImpactTools


def test_get_asset_lineage_both():
    store = Mock()
    store.get_asset_metadata.return_value = {"asset_id": "public.orders", "asset_type": "table"}
    store.get_upstream_assets.return_value = ["public.customers"]
    store.get_downstream_assets.return_value = ["sql:sql_samples/orders_by_customer.sql"]

    out = get_asset_lineage(store, "public.orders", direction="both")

    assert out["asset_id"] == "public.orders"
    assert out["upstream"] == ["public.customers"]
    assert out["downstream"] == ["sql:sql_samples/orders_by_customer.sql"]
    assert out["direction"] == "both"


def test_get_asset_lineage_upstream_only():
    store = Mock()
    store.get_asset_metadata.return_value = {"asset_id": "public.orders"}
    store.get_upstream_assets.return_value = ["a"]
    store.get_downstream_assets.return_value = ["b"]

    out = get_asset_lineage(store, "public.orders", direction="upstream")

    assert out["upstream"] == ["a"]
    assert out["downstream"] == []


def test_impact_tools_delegates_to_analyzer():
    store = Mock()
    store.get_asset_metadata.return_value = {"asset_id": "public.products"}
    store.get_upstream_assets.return_value = []
    store.get_downstream_assets.return_value = ["sql:x.sql"]

    tools = ImpactTools(impact_analyzer=ImpactAnalyzer(metadata_store=store))
    out = tools.get_lineage("public.products", direction="both")

    assert out["asset"]["asset_id"] == "public.products"
    assert out["downstream"] == ["sql:x.sql"]
