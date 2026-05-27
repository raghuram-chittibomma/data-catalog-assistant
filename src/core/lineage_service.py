"""
Shared lineage resolution for UI, MCP, and RAGEngine.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_VALID_DIRECTIONS = frozenset({"both", "upstream", "downstream"})


def get_asset_lineage(
    metadata_store,
    data_asset: str,
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Resolve upstream/downstream lineage for a catalog asset.

    Args:
        metadata_store: MetadataStore instance (or compatible mock)
        data_asset: Asset id (e.g. public.orders, sql:path/file.sql)
        direction: upstream | downstream | both

    Returns:
        Dict with asset metadata, upstream/downstream id lists, and direction
    """
    asset_id = (data_asset or "").strip()
    dir_norm = (direction or "both").strip().lower()
    if dir_norm not in _VALID_DIRECTIONS:
        dir_norm = "both"

    if not asset_id:
        return {
            "asset": None,
            "asset_id": "",
            "upstream": [],
            "downstream": [],
            "direction": dir_norm,
        }

    if not metadata_store:
        logger.warning("No metadata store configured for lineage")
        return {
            "asset": None,
            "asset_id": asset_id,
            "upstream": [],
            "downstream": [],
            "direction": dir_norm,
        }

    asset_meta = metadata_store.get_asset_metadata(asset_id)
    upstream: List[Any] = []
    downstream: List[Any] = []

    if dir_norm in ("both", "upstream"):
        upstream = metadata_store.get_upstream_assets(asset_id) or []
    if dir_norm in ("both", "downstream"):
        downstream = metadata_store.get_downstream_assets(asset_id) or []

    return {
        "asset": asset_meta,
        "asset_id": asset_id,
        "upstream": upstream,
        "downstream": downstream,
        "direction": dir_norm,
    }
