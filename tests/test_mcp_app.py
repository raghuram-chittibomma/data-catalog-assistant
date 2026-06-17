"""Tests for the protocol-compliant MCP server (src/mcp_server/mcp_app.py).

These verify that the MCP surface (tools + resources) is registered correctly
without touching the real vector/metadata stores, by injecting stub backends.
"""

import asyncio

import pytest

# Skip the whole module cleanly if the MCP SDK isn't installed in this env.
pytest.importorskip("mcp")

from src.mcp_server.mcp_app import build_mcp  # noqa: E402


class _StubQueryTools:
    def generate_query(self, description):
        return {"sql": "SELECT 1", "called_with": description}

    def validate_query(self, sql):
        return {"valid": True}

    def explain_query(self, sql):
        return {"explanation": "ok"}

    def suggest_optimizations(self, sql):
        return {"suggestions": []}


class _StubSearchTools:
    def search_data_assets(self, query, top_k=5):
        return {"results": [], "total": 0, "top_k": top_k}

    def search_similar_queries(self, query, top_k=3):
        return {"results": [], "total": 0}

    def search_by_table(self, table_name):
        return {"metadata": {}, "table": table_name}

    def search_by_owner(self, owner):
        return {"assets": [], "total": 0}


class _StubImpactTools:
    def analyze_data_usage(self, data_asset):
        return {"asset": data_asset, "impact_score": 0.0}

    def get_lineage(self, data_asset, direction="both"):
        return {"asset_id": data_asset, "direction": direction}

    def assess_change_impact(self, data_asset, change_description):
        return {"asset_id": data_asset, "change": change_description}

    def compare_data_assets(self, asset1, asset2):
        return {"similarities": [], "differences": []}


class _StubDataCatalog:
    def get_catalog_summary(self):
        return {"total_assets": 3}

    def list_tables(self):
        return [{"asset_id": "public.customers"}]

    def list_reports(self):
        return []

    def list_etl_processes(self):
        return []

    def get_asset_details(self, asset_id):
        return {"asset": {"asset_id": asset_id}}


@pytest.fixture
def mcp_server():
    backends = {
        "query_tools": _StubQueryTools(),
        "search_tools": _StubSearchTools(),
        "impact_tools": _StubImpactTools(),
        "data_catalog": _StubDataCatalog(),
    }
    return build_mcp(backends=backends)


EXPECTED_TOOLS = {
    "generate_query",
    "validate_query",
    "explain_query",
    "suggest_optimizations",
    "search_data_assets",
    "search_similar_queries",
    "search_by_table",
    "search_by_owner",
    "analyze_data_usage",
    "get_lineage",
    "assess_change_impact",
    "compare_data_assets",
    "get_asset_details",
}

EXPECTED_RESOURCES = {
    "catalog://summary",
    "catalog://tables",
    "catalog://reports",
    "catalog://etl",
}


def test_all_tools_registered(mcp_server):
    tools = asyncio.run(mcp_server.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED_TOOLS == names


def test_all_resources_registered(mcp_server):
    resources = asyncio.run(mcp_server.list_resources())
    uris = {str(r.uri) for r in resources}
    assert EXPECTED_RESOURCES.issubset(uris)


def test_tools_expose_input_schema(mcp_server):
    tools = asyncio.run(mcp_server.list_tools())
    by_name = {t.name: t for t in tools}
    # generate_query should advertise a `description` string parameter.
    props = by_name["generate_query"].inputSchema.get("properties", {})
    assert "description" in props
