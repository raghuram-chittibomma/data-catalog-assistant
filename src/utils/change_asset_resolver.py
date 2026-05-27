"""
Resolve which catalog asset a proposed change applies to.

Change assessment should analyze the table named in the change text, not
blindly reuse the Asset id field (often left from a prior usage analysis).
"""

import re
from typing import Any, Dict, Optional, Tuple

# schema.table or table after "on" / "to" / "from"
_QUALIFIED_TABLE = re.compile(
    r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_]+)\b",
    re.IGNORECASE,
)
_ON_TABLE = re.compile(
    r"\bon\s+((?:[a-z][a-z0-9_]+\.)?[a-z][a-z0-9_]+)\b",
    re.IGNORECASE,
)
# Only schema.table after "to" (avoids "rename col to legal_name")
_TO_TABLE = re.compile(
    r"\bto\s+([a-z][a-z0-9_]+\.[a-z][a-z0-9_]+)\b",
    re.IGNORECASE,
)


def _normalize_table_ref(name: str, default_schema: str = "public") -> str:
    cleaned = (name or "").strip().lower().strip("`\"'")
    if not cleaned:
        return ""
    if "." in cleaned:
        schema, table = cleaned.split(".", 1)
        return f"{schema}.{table}"
    return f"{default_schema}.{cleaned}"


def extract_asset_from_change_description(
    change_description: str,
    default_schema: str = "public",
) -> Optional[str]:
    """
    Parse a target table from free-text change descriptions.

    Examples:
        "Rename column X on public.customers" -> public.customers
        "Drop column freight on orders" -> public.orders
    """
    text = (change_description or "").strip()
    if not text:
        return None

    for pattern in (_ON_TABLE, _TO_TABLE):
        match = pattern.search(text)
        if match:
            ref = _normalize_table_ref(match.group(1), default_schema)
            if ref:
                return ref

    qualified = _QUALIFIED_TABLE.findall(text)
    if qualified:
        return _normalize_table_ref(qualified[-1], default_schema)

    return None


def resolve_change_target_asset(
    field_asset: str,
    change_description: str,
    default_schema: str = "public",
) -> Tuple[str, Dict[str, Any]]:
    """
    Pick the asset id to analyze for assess_change_impact.

    Priority:
      1. Table parsed from change_description (if present)
      2. Asset id field

    Returns:
        (effective_asset_id, metadata dict with source + optional warning)
    """
    field_asset = (field_asset or "").strip()
    inferred = extract_asset_from_change_description(change_description, default_schema)

    meta: Dict[str, Any] = {
        "field_asset": field_asset or None,
        "inferred_asset": inferred,
        "source": "field",
    }

    if inferred:
        meta["source"] = "change_text"
        effective = inferred
        if field_asset and field_asset.lower() != inferred.lower():
            meta["warning"] = (
                f"Asset id field was `{field_asset}` but the proposed change "
                f"targets `{inferred}` — analysis uses **{inferred}**."
            )
        return effective, meta

    if field_asset:
        return field_asset, meta

    return "", meta
