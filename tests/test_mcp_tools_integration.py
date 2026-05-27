"""HTTP integration tests for MCP tool endpoints."""

import os
import sys
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.mcp_server.server import MCPServer
from src.mcp_server.tools.impact_tools import ImpactTools
from src.mcp_server.tools.query_tools import QueryTools
from src.mcp_server.tools.search_tools import SearchTools


@dataclass
class _Hit:
    data_asset: str
    description: str
    relevance_score: float
    metadata: dict
    sql_context: str = None
    impact_info: dict = None


def _mcp_with_mocks():
    rag = Mock()
    rag.search_data_lineage.return_value = [
        _Hit("public.orders", "orders table", 0.92, {"asset_type": "table"}),
    ]
    rag.get_data_lineage = Mock(
        return_value={"asset": {"asset_id": "public.orders"}, "upstream": [], "downstream": []}
    )
    rag.generate_query.return_value = {
        "query": "SELECT * FROM orders",
        "confidence": 0.8,
        "explanation": "demo",
    }

    metadata = Mock()
    metadata.store = {"assets": {"public.orders": {"asset_type": "table"}}}
    metadata.get_asset_metadata.return_value = {"asset_id": "public.orders"}
    metadata.get_upstream_assets.return_value = []
    metadata.get_downstream_assets.return_value = [{"asset_id": "sql:foo"}]

    impact = Mock()
    impact.analyze_data_usage.return_value = {"asset": "public.orders", "impact_score": 1.0}
    impact.get_lineage.return_value = {
        "asset": {"asset_id": "public.orders"},
        "asset_id": "public.orders",
        "upstream": [],
        "downstream": [{"asset_id": "sql:foo"}],
        "direction": "both",
    }

    from src.core.query_processor import QueryProcessor

    server = MCPServer()
    search = SearchTools(rag_engine=rag)
    query = QueryTools(query_processor=QueryProcessor(rag_engine=rag), rag_engine=rag)
    impact_tools = ImpactTools(impact_analyzer=impact)

    server.register_tool(
        "search_data_assets",
        search.search_data_assets,
        "search",
        {"query": {"type": "string", "required": True}},
    )
    server.register_tool(
        "get_lineage",
        impact_tools.get_lineage,
        "lineage",
        {"data_asset": {"type": "string", "required": True}},
    )
    server.register_tool(
        "generate_query",
        query.generate_query,
        "sql",
        {"description": {"type": "string", "required": True}},
    )
    return server, rag


@pytest.fixture
def mcp_client():
    server, _ = _mcp_with_mocks()
    return TestClient(server.app)


def test_mcp_root_lists_tools(mcp_client):
    r = mcp_client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "tools" in body
    names = {t["name"] for t in body["tools"]}
    assert "search_data_assets" in names


def test_search_data_assets(mcp_client):
    r = mcp_client.post(
        "/tools/search_data_assets",
        json={"query": "customer orders", "top_k": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["data_asset"] == "public.orders"


def test_get_lineage(mcp_client):
    r = mcp_client.post(
        "/tools/get_lineage",
        json={"data_asset": "public.orders", "direction": "both"},
    )
    assert r.status_code == 200


def test_generate_query_returns_sql_key(mcp_client):
    r = mcp_client.post(
        "/tools/generate_query",
        json={"description": "list orders"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sql"] == "SELECT * FROM orders"
    assert body["confidence"] == 0.8
