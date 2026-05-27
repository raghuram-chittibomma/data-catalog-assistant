"""
Impact tools - MCP tools for data impact and lineage analysis.
"""

import logging
from typing import Dict, List, Any

from src.utils.change_asset_resolver import resolve_change_target_asset

logger = logging.getLogger(__name__)


class ImpactTools:
    """
    Tools for analyzing data lineage and impact.
    """

    def __init__(self, impact_analyzer=None):
        """
        Initialize Impact Tools.

        Args:
            impact_analyzer: ImpactAnalyzer instance
        """
        self.impact_analyzer = impact_analyzer
        logger.info("Initialized Impact Tools")

    def analyze_data_usage(self, data_asset: str) -> Dict[str, Any]:
        """
        Analyze where a data asset is used and its impact.

        MCP Tool: analyze_data_usage
        Parameters:
            - data_asset (string): Name of data asset (table/view/report)

        Returns:
            Usage information including reports, queries, impact score
        """
        logger.debug(f"Analyzing usage: {data_asset}")
        if not self.impact_analyzer:
            return {
                "asset": data_asset,
                "reports": [],
                "queries": [],
                "downstream_tables": [],
                "impact_score": 0.0,
            }

        usage = self.impact_analyzer.analyze_data_usage(data_asset)
        downstream = usage.get("downstream", [])
        downstream_tables = [
            a for a in downstream if a.get("asset_type") == "table"
        ]
        return {
            "asset": usage.get("asset"),
            "asset_id": usage.get("asset_id", data_asset),
            "reports": usage.get("reports", []),
            "queries": usage.get("queries", []),
            "etl_jobs": usage.get("etl_jobs", []),
            "downstream_tables": downstream_tables,
            "downstream": downstream,
            "impact_score": usage.get("impact_score", 0.0),
        }

    def get_lineage(self, data_asset: str, direction: str = "both") -> Dict[str, Any]:
        """
        Get lineage for a data asset.

        MCP Tool: get_lineage
        Parameters:
            - data_asset (string): Name of data asset
            - direction (string): "upstream", "downstream", or "both"

        Returns:
            Lineage graph with relationships
        """
        logger.debug("Getting %s lineage for: %s", direction, data_asset)
        if not self.impact_analyzer:
            return {
                "asset": None,
                "asset_id": data_asset,
                "upstream": [],
                "downstream": [],
                "direction": direction or "both",
            }

        return self.impact_analyzer.get_lineage(data_asset, direction=direction)

    def assess_change_impact(self, data_asset: str, change_description: str) -> Dict[str, Any]:
        """
        Assess impact of a change to a data asset.

        MCP Tool: assess_change_impact
        Parameters:
            - data_asset (string): Name of data asset being changed
            - change_description (string): Description of the change

        Returns:
            Predicted impact including affected reports, queries, downstream assets
        """
        effective_asset, resolution = resolve_change_target_asset(data_asset, change_description)
        logger.debug(
            "Assessing impact of change: field=%s effective=%s source=%s",
            data_asset,
            effective_asset,
            resolution.get("source"),
        )
        if not self.impact_analyzer:
            return {
                "asset": None,
                "asset_id": effective_asset or data_asset,
                "asset_id_field": data_asset,
                "asset_resolved_from": resolution.get("source"),
                "resolution_warning": resolution.get("warning"),
                "change": change_description,
                "affected_reports": [],
                "affected_queries": [],
                "affected_etl": [],
                "downstream_count": 0,
                "impact_score": 0.0,
                "risk_level": "low",
            }

        if not effective_asset:
            return {
                "asset": None,
                "asset_id": "",
                "change": change_description,
                "error": "Provide an asset id or include a table in the change text (e.g. on public.customers).",
                "affected_reports": [],
                "affected_queries": [],
                "affected_etl": [],
                "downstream_count": 0,
                "impact_score": 0.0,
                "risk_level": "low",
            }

        usage = self.impact_analyzer.analyze_data_usage(effective_asset)
        score = usage.get("impact_score", 0.0)
        risk_level = "low"
        if score > 0.6:
            risk_level = "high"
        elif score > 0.3:
            risk_level = "medium"

        return {
            "asset": usage.get("asset"),
            "asset_id": effective_asset,
            "asset_id_field": data_asset,
            "asset_resolved_from": resolution.get("source"),
            "resolution_warning": resolution.get("warning"),
            "change": change_description,
            "affected_reports": usage.get("reports", []),
            "affected_queries": usage.get("queries", []),
            "affected_etl": usage.get("etl_jobs", []),
            "downstream_count": len(usage.get("downstream", [])),
            "impact_score": score,
            "risk_level": risk_level,
        }

    def compare_data_assets(self, asset1: str, asset2: str) -> Dict[str, Any]:
        """
        Compare two data assets.

        MCP Tool: compare_data_assets
        Parameters:
            - asset1 (string): First data asset
            - asset2 (string): Second data asset

        Returns:
            Comparison including shared sources, shared destinations, etc.
        """
        logger.debug(f"Comparing: {asset1} vs {asset2}")
        if not self.impact_analyzer:
            return {
                "similarities": [],
                "differences": []
            }

        asset1_upstream = self.impact_analyzer.get_upstream_lineage(asset1).get("upstream", [])
        asset2_upstream = self.impact_analyzer.get_upstream_lineage(asset2).get("upstream", [])
        asset1_downstream = self.impact_analyzer.get_downstream_lineage(asset1).get("downstream", [])
        asset2_downstream = self.impact_analyzer.get_downstream_lineage(asset2).get("downstream", [])

        similarities = [a for a in asset1_upstream if a in asset2_upstream] + [a for a in asset1_downstream if a in asset2_downstream]
        differences = {
            "asset1_only_upstream": [a for a in asset1_upstream if a not in asset2_upstream],
            "asset2_only_upstream": [a for a in asset2_upstream if a not in asset1_upstream],
            "asset1_only_downstream": [a for a in asset1_downstream if a not in asset2_downstream],
            "asset2_only_downstream": [a for a in asset2_downstream if a not in asset1_downstream],
        }

        return {
            "similarities": similarities,
            "differences": differences
        }
