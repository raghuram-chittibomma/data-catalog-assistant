"""
Model Context Protocol (MCP) server for Data Catalog Assistant.

Unlike ``src/mcp_server/server.py`` (a REST/HTTP API that mirrors the tool
surface for demos), this module is a protocol-compliant MCP server built on the
official ``mcp`` Python SDK. It speaks MCP over stdio, so MCP-compatible clients
(Claude Desktop, Cursor, etc.) can discover and call the same catalog, search,
query, and impact tools.

Both interfaces wrap the *same* underlying handlers, so behavior stays in sync.

Run it directly with::

    python -m src.mcp_server.mcp_app
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Allow `python -m src.mcp_server.mcp_app` and `python src/mcp_server/mcp_app.py`.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from src.core.impact_analyzer import ImpactAnalyzer
from src.core.query_processor import QueryProcessor
from src.core.rag_engine import RAGEngine
from src.mcp_server.resources.data_catalog import DataCatalog
from src.mcp_server.tools.impact_tools import ImpactTools
from src.mcp_server.tools.query_tools import QueryTools
from src.mcp_server.tools.search_tools import SearchTools
from src.utils.config_loader import load_config
from src.utils.logging import setup_logging
from src.vector_store.embeddings import LocalEmbedding
from src.vector_store.metadata_store import MetadataStore
from src.vector_store.vector_db import ChromaVectorStore

logger = logging.getLogger(__name__)

SERVER_NAME = "data-catalog-assistant"


def build_backends(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construct the tool handler services (no UI, no HTTP server).

    Connects to the vector store and metadata store so the MCP tools operate on
    real data. Pass ``config`` to override; otherwise it is loaded from disk.
    """
    config = config or load_config()

    emb_cfg = config.get("embeddings", {})
    embedding_service = LocalEmbedding(model_name=emb_cfg.get("model_name", "all-MiniLM-L6-v2"))

    vector_store = ChromaVectorStore(config=config["vector_store"])
    vector_store.connect()

    metadata_store = MetadataStore(config=config.get("metadata_store", {}))

    rag_engine = RAGEngine(
        vector_store=vector_store,
        llm_client=None,
        embedding_service=embedding_service,
        metadata_store=metadata_store,
        config=config,
    )

    query_cfg = {**(config.get("schema_context") or {}), **(config.get("query") or {})}
    query_processor = QueryProcessor(
        llm_client=None,
        schema_context=query_cfg,
        rag_engine=rag_engine,
    )
    impact_analyzer = ImpactAnalyzer(
        vector_store=vector_store,
        metadata_store=metadata_store,
    )

    return {
        "query_tools": QueryTools(query_processor=query_processor, rag_engine=rag_engine),
        "search_tools": SearchTools(rag_engine=rag_engine),
        "impact_tools": ImpactTools(impact_analyzer=impact_analyzer),
        "data_catalog": DataCatalog(metadata_store=metadata_store),
    }


def build_mcp(backends: dict[str, Any] | None = None) -> FastMCP:
    """Build a FastMCP server with all tools and resources registered.

    ``backends`` lets tests inject stub handlers without touching the vector or
    metadata stores.
    """
    backends = backends if backends is not None else build_backends()
    query_tools: QueryTools = backends["query_tools"]
    search_tools: SearchTools = backends["search_tools"]
    impact_tools: ImpactTools = backends["impact_tools"]
    data_catalog: DataCatalog = backends["data_catalog"]

    mcp = FastMCP(SERVER_NAME)

    # ------------------------------------------------------------------ #
    # Query tools (LLM is used only by generate_query)
    # ------------------------------------------------------------------ #
    @mcp.tool()
    def generate_query(description: str) -> dict[str, Any]:
        """Generate a PostgreSQL SELECT from a natural-language description (LLM-backed)."""
        return query_tools.generate_query(description)

    @mcp.tool()
    def validate_query(sql: str) -> dict[str, Any]:
        """Validate SQL syntax and safety using rule-based checks (no LLM)."""
        return query_tools.validate_query(sql)

    @mcp.tool()
    def explain_query(sql: str) -> dict[str, Any]:
        """Explain what a SQL statement does in plain English (rule-based)."""
        return query_tools.explain_query(sql)

    @mcp.tool()
    def suggest_optimizations(sql: str) -> dict[str, Any]:
        """Suggest optimizations for a SQL query (rule-based)."""
        return query_tools.suggest_optimizations(sql)

    # ------------------------------------------------------------------ #
    # Search tools (embeddings + metadata)
    # ------------------------------------------------------------------ #
    @mcp.tool()
    def search_data_assets(query: str, top_k: int = 5) -> dict[str, Any]:
        """Semantic search over the catalog/lineage store (embeddings)."""
        return search_tools.search_data_assets(query, top_k=top_k)

    @mcp.tool()
    def search_similar_queries(query: str, top_k: int = 3) -> dict[str, Any]:
        """Find similar saved queries/reports by description (embeddings)."""
        return search_tools.search_similar_queries(query, top_k=top_k)

    @mcp.tool()
    def search_by_table(table_name: str) -> dict[str, Any]:
        """Look up catalog metadata and lineage for a table (metadata)."""
        return search_tools.search_by_table(table_name)

    @mcp.tool()
    def search_by_owner(owner: str) -> dict[str, Any]:
        """List data assets owned by a person or team (metadata)."""
        return search_tools.search_by_owner(owner)

    # ------------------------------------------------------------------ #
    # Impact / lineage tools (metadata graph)
    # ------------------------------------------------------------------ #
    @mcp.tool()
    def analyze_data_usage(data_asset: str) -> dict[str, Any]:
        """Analyze where a data asset is used and its impact score (metadata)."""
        return impact_tools.analyze_data_usage(data_asset)

    @mcp.tool()
    def get_lineage(data_asset: str, direction: str = "both") -> dict[str, Any]:
        """Get upstream/downstream lineage for an asset (metadata)."""
        return impact_tools.get_lineage(data_asset, direction=direction)

    @mcp.tool()
    def assess_change_impact(data_asset: str, change_description: str) -> dict[str, Any]:
        """Assess the blast radius of a proposed change.

        Resolves the target table from the change description when it differs
        from ``data_asset`` (metadata).
        """
        return impact_tools.assess_change_impact(data_asset, change_description)

    @mcp.tool()
    def compare_data_assets(asset1: str, asset2: str) -> dict[str, Any]:
        """Compare two assets and surface shared upstream/downstream lineage (metadata)."""
        return impact_tools.compare_data_assets(asset1, asset2)

    @mcp.tool()
    def get_asset_details(asset_id: str) -> dict[str, Any]:
        """Get detailed metadata plus upstream/downstream for a single asset (metadata)."""
        return data_catalog.get_asset_details(asset_id)

    # ------------------------------------------------------------------ #
    # Catalog resources (read-only browse)
    # ------------------------------------------------------------------ #
    @mcp.resource("catalog://summary")
    def catalog_summary() -> str:
        """High-level counts of cataloged assets by type."""
        return json.dumps(data_catalog.get_catalog_summary(), indent=2, default=str)

    @mcp.resource("catalog://tables")
    def catalog_tables() -> str:
        """All tables in the catalog."""
        return json.dumps(data_catalog.list_tables(), indent=2, default=str)

    @mcp.resource("catalog://reports")
    def catalog_reports() -> str:
        """All reports in the catalog."""
        return json.dumps(data_catalog.list_reports(), indent=2, default=str)

    @mcp.resource("catalog://etl")
    def catalog_etl() -> str:
        """All ETL processes in the catalog."""
        return json.dumps(data_catalog.list_etl_processes(), indent=2, default=str)

    return mcp


def main() -> None:
    """Entry point: initialize backends and serve MCP over stdio."""
    # Logs go to stderr/file (never stdout), so they don't corrupt the stdio
    # MCP protocol stream.
    setup_logging(level="INFO")
    logger.info("Starting %s MCP server (stdio)", SERVER_NAME)
    mcp = build_mcp()
    mcp.run()


if __name__ == "__main__":
    main()
