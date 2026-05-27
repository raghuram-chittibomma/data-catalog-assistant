"""
Data catalog resource - exposes data catalog as MCP resource.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class DataCatalog:
    """
    Exposes data catalog as an MCP resource.
    Allows Claude and other agents to browse available data assets.
    """

    def __init__(self, metadata_store=None):
        """
        Initialize Data Catalog.

        Args:
            metadata_store: MetadataStore instance
        """
        self.metadata_store = metadata_store
        logger.info("Initialized Data Catalog")

    def _assets(self) -> List[Dict[str, Any]]:
        if not self.metadata_store:
            return []
        return list(self.metadata_store.store.get("assets", {}).values())

    def get_catalog_summary(self) -> Dict[str, Any]:
        """
        Get summary of data catalog.

        Returns:
            Counts by asset type, top tables, recent updates, etc.
        """
        logger.debug("Getting catalog summary")
        assets = self._assets()
        counts = {
            "total_assets": len(assets),
            "tables": sum(1 for a in assets if a.get("asset_type") == "table"),
            "views": sum(1 for a in assets if a.get("asset_type") == "view"),
            "reports": sum(1 for a in assets if a.get("asset_type") == "report"),
            "sql_assets": sum(1 for a in assets if a.get("asset_type") == "sql"),
            "etl_processes": sum(1 for a in assets if a.get("asset_type") == "etl"),
            "last_refresh": None,
        }
        return counts

    def list_tables(self, pattern: str = None) -> List[Dict[str, Any]]:
        """
        List all tables in catalog.

        Args:
            pattern: Optional filter pattern

        Returns:
            List of table metadata
        """
        logger.debug(f"Listing tables with pattern: {pattern}")
        tables = [a for a in self._assets() if a.get("asset_type") == "table"]
        if pattern:
            pattern_lower = pattern.lower()
            tables = [t for t in tables if pattern_lower in t.get("name", "").lower() or pattern_lower in t.get("asset_id", "").lower()]
        return tables

    def list_reports(self, owner: str = None) -> List[Dict[str, Any]]:
        """
        List all reports in catalog.

        Args:
            owner: Optional filter by owner

        Returns:
            List of report metadata
        """
        logger.debug(f"Listing reports for owner: {owner}")
        reports = [a for a in self._assets() if a.get("asset_type") == "report"]
        if owner:
            owner_lower = owner.lower()
            reports = [r for r in reports if owner_lower in str(r.get("owner", "")).lower()]
        return reports

    def list_etl_processes(self) -> List[Dict[str, Any]]:
        """
        List all ETL processes.

        Returns:
            List of ETL process metadata
        """
        logger.debug("Listing ETL processes")
        return [a for a in self._assets() if a.get("asset_type") == "etl"]

    def get_asset_details(self, asset_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an asset.

        Args:
            asset_id: Asset ID or name

        Returns:
            Detailed asset information
        """
        logger.debug(f"Getting details for asset: {asset_id}")
        if not self.metadata_store:
            return {}

        asset = self.metadata_store.get_asset_metadata(asset_id)
        if not asset:
            return {}

        return {
            "asset": asset,
            "upstream": self.metadata_store.get_upstream_assets(asset_id),
            "downstream": self.metadata_store.get_downstream_assets(asset_id),
        }
