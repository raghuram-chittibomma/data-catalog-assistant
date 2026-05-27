"""
Search tools - MCP tools for vector search operations.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class SearchTools:
    """
    Tools for searching data lineage and metadata.
    """

    def __init__(self, rag_engine=None):
        """
        Initialize Search Tools.

        Args:
            rag_engine: RAGEngine instance
        """
        self.rag_engine = rag_engine
        logger.info("Initialized Search Tools")

    def _asset_dict(self, result) -> Dict[str, Any]:
        return {
            "data_asset": result.data_asset,
            "description": result.description,
            "relevance_score": result.relevance_score,
            "metadata": result.metadata,
            "sql_context": result.sql_context,
            "impact_info": result.impact_info,
        }

    def search_data_assets(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search for data assets by description or keywords.

        MCP Tool: search_data_assets
        Parameters:
            - query (string): Search query
            - top_k (integer): Number of results to return

        Returns:
            List of relevant data assets with scores
        """
        logger.debug(f"Searching data assets: {query}")
        if not self.rag_engine:
            return {"results": [], "total": 0}

        hits = self.rag_engine.search_data_lineage(query, top_k=top_k)
        return {
            "results": [self._asset_dict(hit) for hit in hits],
            "total": len(hits)
        }

    def search_similar_queries(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Find similar queries/reports in the system.

        MCP Tool: search_similar_queries
        Parameters:
            - query (string): Query to find similar to
            - top_k (integer): Number of results

        Returns:
            List of similar queries with SQL and descriptions
        """
        logger.debug(f"Searching similar queries: {query}")
        if not self.rag_engine:
            return {"results": [], "total": 0}

        hits = self.rag_engine.search_data_lineage(query, top_k=top_k)
        return {
            "results": [self._asset_dict(hit) for hit in hits],
            "total": len(hits)
        }

    def search_by_table(self, table_name: str) -> Dict[str, Any]:
        """
        Search all information related to a specific table.

        MCP Tool: search_by_table
        Parameters:
            - table_name (string): Name of the table

        Returns:
            Table metadata, related queries, and usage
        """
        logger.debug(f"Searching table: {table_name}")
        if not self.rag_engine or not self.rag_engine.metadata_store:
            return {"metadata": {}, "related_queries": [], "usage": {}}

        metadata = self.rag_engine.metadata_store.get_asset_metadata(table_name) or {}
        upstream = self.rag_engine.metadata_store.get_upstream_assets(table_name)
        downstream = self.rag_engine.metadata_store.get_downstream_assets(table_name)
        return {
            "metadata": metadata,
            "related_queries": [],
            "usage": {"upstream": upstream, "downstream": downstream}
        }

    def search_by_owner(self, owner: str) -> Dict[str, Any]:
        """
        Find all data assets owned by a specific person/team.

        MCP Tool: search_by_owner
        Parameters:
            - owner (string): Owner name or email

        Returns:
            List of owned data assets
        """
        logger.debug(f"Searching assets by owner: {owner}")
        if not self.rag_engine or not self.rag_engine.metadata_store:
            return {"assets": [], "total": 0}

        owner_lower = owner.lower()
        assets = [
            asset for asset in self.rag_engine.metadata_store.store.get("assets", {}).values()
            if owner_lower in str(asset.get("owner", "")).lower()
        ]
        return {"assets": assets, "total": len(assets)}
