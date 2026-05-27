"""
Impact analyzer - analyzes where data is used and its impact.
"""

import logging
from typing import Dict, List, Any

from src.core.lineage_service import get_asset_lineage

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """
    Analyzes data lineage and impact.
    """

    def __init__(self, vector_store=None, metadata_store=None):
        """
        Initialize Impact Analyzer.

        Args:
            vector_store: VectorStore instance
            metadata_store: MetadataStore instance
        """
        self.vector_store = vector_store
        self.metadata_store = metadata_store
        logger.info("Impact Analyzer initialized")

    def _all_assets(self) -> List[Dict[str, Any]]:
        if not self.metadata_store:
            return []
        return list(self.metadata_store.store.get("assets", {}).values())

    def analyze_data_usage(self, data_asset: str) -> Dict[str, Any]:
        """
        Analyze where a data asset is used.

        Args:
            data_asset: Name of the data asset

        Returns:
            Dict with 'reports', 'queries', 'downstream_tables', 'impact_score'
        """
        logger.debug(f"Analyzing usage for: {data_asset}")
        asset = self.metadata_store.get_asset_metadata(data_asset) if self.metadata_store else None
        upstream = self.metadata_store.get_upstream_assets(data_asset) if self.metadata_store else []
        downstream = self.metadata_store.get_downstream_assets(data_asset) if self.metadata_store else []
        queries = [a for a in downstream if a.get("asset_type") == "sql"]
        reports = [a for a in downstream if a.get("asset_type") in ("report", "etl")]
        etl_jobs = [a for a in downstream if a.get("asset_type") == "etl"]
        impact_score = self.resolve_impact_score(data_asset, persist=True)

        return {
            "asset": asset,
            "asset_id": data_asset,
            "upstream": upstream,
            "downstream": downstream,
            "reports": reports,
            "queries": queries,
            "etl_jobs": etl_jobs,
            "impact_score": impact_score,
        }

    def get_lineage(self, data_asset: str, direction: str = "both") -> Dict[str, Any]:
        """
        Get lineage for a data asset (shared with MCP get_lineage and Gradio UI).

        Args:
            data_asset: Asset id
            direction: upstream, downstream, or both

        Returns:
            asset metadata plus upstream/downstream dependency lists
        """
        logger.debug("Getting %s lineage for: %s", direction, data_asset)
        return get_asset_lineage(self.metadata_store, data_asset, direction=direction)

    def get_upstream_lineage(self, data_asset: str) -> Dict[str, Any]:
        """
        Get upstream lineage (what data feeds into this asset).

        Args:
            data_asset: Name of the data asset

        Returns:
            Upstream dependency tree
        """
        logger.debug(f"Getting upstream lineage for: {data_asset}")
        upstream = self.metadata_store.get_upstream_assets(data_asset) if self.metadata_store else []
        return {
            "asset": data_asset,
            "upstream": upstream,
        }

    def get_downstream_lineage(self, data_asset: str) -> Dict[str, Any]:
        """
        Get downstream lineage (what uses this asset).

        Args:
            data_asset: Name of the data asset

        Returns:
            Downstream dependency tree
        """
        logger.debug(f"Getting downstream lineage for: {data_asset}")
        downstream = self.metadata_store.get_downstream_assets(data_asset) if self.metadata_store else []
        return {
            "asset": data_asset,
            "downstream": downstream,
        }

    def calculate_impact_score(self, data_asset: str) -> float:
        """
        Calculate impact score for a data asset (0.0 - 1.0).

        Based on upstream + downstream relationship counts in metadata
        (capped at 1.0, divided by 10 so ~10 edges ≈ max score).

        Args:
            data_asset: Name of the data asset

        Returns:
            Impact score
        """
        logger.debug(f"Calculating impact score for: {data_asset}")
        if not self.metadata_store:
            return 0.0

        upstream = self.metadata_store.get_upstream_assets(data_asset)
        downstream = self.metadata_store.get_downstream_assets(data_asset)
        score = min(1.0, (len(upstream) + len(downstream)) / 10.0)
        return score

    def resolve_impact_score(self, data_asset: str, persist: bool = False) -> float:
        """
        Effective impact score: max(graph-based score, stored score).

        Stored 0.0 from ingest is treated as a placeholder; lineage-derived
        score wins when it is higher.

        Args:
            data_asset: Asset id
            persist: Write resolved score back to metadata store when it increases

        Returns:
            Resolved impact score in [0.0, 1.0]
        """
        calculated = self.calculate_impact_score(data_asset)
        asset = self.metadata_store.get_asset_metadata(data_asset) if self.metadata_store else None
        stored = float(asset.get("impact_score", 0) or 0) if asset else 0.0
        score = max(calculated, stored)

        if persist and self.metadata_store and score > stored:
            self.metadata_store.update_impact_score(data_asset, score)
            logger.info(
                "Updated impact score for %s: %.2f -> %.2f (from lineage)",
                data_asset,
                stored,
                score,
            )

        return score

    def recompute_all_impact_scores(self) -> int:
        """
        Recompute and persist impact scores for every registered asset.

        Intended to run after metadata refresh once lineage edges exist.

        Returns:
            Number of assets updated
        """
        if not self.metadata_store:
            return 0

        asset_ids = list(self.metadata_store.store.get("assets", {}).keys())
        updated = 0
        for asset_id in asset_ids:
            score = self.calculate_impact_score(asset_id)
            if self.metadata_store.update_impact_score(asset_id, score):
                updated += 1
        logger.info("Recomputed impact scores for %s assets", updated)
        return updated
