"""
Human-readable lineage diagrams for the Gradio UI.
"""

import json
from typing import Any, Dict, List, Tuple


def _node_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("asset_id") or item.get("name") or "?").strip()
    return str(item).strip()


def _node_type(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("asset_type") or "").strip()
    return ""


def _node_rel(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("relationship_type") or "").strip()
    return ""


def _label(item: Any) -> str:
    nid = _node_id(item)
    ntype = _node_type(item)
    return f"{nid} ({ntype})" if ntype else nid


def _center_from_data(data: Dict[str, Any], fallback: str) -> Tuple[str, str]:
    asset = data.get("asset")
    if isinstance(asset, dict):
        center = str(asset.get("asset_id") or asset.get("name") or fallback).strip()
        center_type = str(asset.get("asset_type") or "").strip()
        return center or fallback, center_type
    center = str(data.get("asset_id") or fallback).strip()
    return center or fallback, ""


def build_lineage_diagram(data: Dict[str, Any], asset_name: str, direction: str = "both") -> str:
    """
    Build a high-level markdown + ASCII lineage view with arrows.

    Upstream nodes appear above the center (flow into asset).
    Downstream nodes appear below (flow out of asset).
    """
    center, center_type = _center_from_data(data, asset_name)
    dir_norm = (direction or "both").strip().lower()
    upstream: List[Any] = list(data.get("upstream") or [])
    downstream: List[Any] = list(data.get("downstream") or [])

    show_up = dir_norm in ("both", "upstream")
    show_down = dir_norm in ("both", "downstream")

    lines = [
        f"## Lineage: `{center}`",
        f"**Direction:** {dir_norm}",
    ]
    if center_type:
        lines.append(f"**Type:** `{center_type}`")
    lines.append("")

    if show_up and upstream:
        lines.append("### Upstream ← *feeds into* this asset")
        for item in upstream:
            rel = _node_rel(item)
            rel_note = f" · _{rel}_" if rel else ""
            lines.append(f"- `{_label(item)}`{rel_note}")
        lines.append("")

    if show_down and downstream:
        lines.append("### Downstream → *fed by* this asset")
        for item in downstream:
            rel = _node_rel(item)
            rel_note = f" · _{rel}_" if rel else ""
            lines.append(f"- `{_label(item)}`{rel_note}")
        lines.append("")

    # ASCII flow
    lines.append("### Flow")
    lines.append("```text")
    diagram_rows: List[str] = []

    if show_up and upstream:
        for item in upstream:
            diagram_rows.append(f"  {_label(item)}")
            diagram_rows.append("       │")
            diagram_rows.append("       ▼")
    elif show_up:
        diagram_rows.append("  (no upstream)")

    center_line = f"  ▶ {center}"
    if center_type:
        center_line += f" ({center_type})"
    center_line += " ◀"
    diagram_rows.append(center_line)

    if show_down and downstream:
        diagram_rows.append("       │")
        for idx, item in enumerate(downstream):
            branch = "├" if idx < len(downstream) - 1 else "└"
            diagram_rows.append(f"       {branch}──▶ {_label(item)}")
    elif show_down:
        diagram_rows.append("       │")
        diagram_rows.append("       └──▶ (no downstream)")

    lines.extend(diagram_rows)
    lines.append("```")

    if not upstream and not downstream:
        lines.append("")
        lines.append("_No lineage edges found in metadata for this direction._")

    return "\n".join(lines)


def build_lineage_json(data: Dict[str, Any]) -> str:
    """Full lineage payload for optional expand view."""
    return f"```json\n{json.dumps(data, indent=2, default=str)}\n```"
