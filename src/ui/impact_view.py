"""
Human-readable impact diagrams for the Gradio UI (HTML + expandable details).
"""

import html
import json
from typing import Any

from src.ui.lineage_view import _label, _node_id, _node_type

_TYPE_ORDER = ("table", "sql", "etl", "report", "other")
_RISK_STYLES = {
    "low": ("#1b7a3d", "LOW"),
    "medium": ("#b8860b", "MEDIUM"),
    "high": ("#b91c1c", "HIGH"),
}


def risk_level_from_score(score: float) -> str:
    """Align UI badge with ImpactTools.assess_change_impact thresholds."""
    score = max(0.0, min(1.0, float(score or 0.0)))
    if score > 0.6:
        return "high"
    if score > 0.3:
        return "medium"
    return "low"


def _escape(text: Any) -> str:
    return html.escape(str(text))


def _score_bar(score: float, width: int = 16) -> str:
    score = max(0.0, min(1.0, float(score or 0.0)))
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)


def _risk_badge(risk_level: str | None, score: float) -> str:
    # Badge always reflects impact score (usage analysis does not pass risk_level)
    key = risk_level_from_score(score)
    color, label = _RISK_STYLES.get(key, ("#555", key.upper()))
    bar = _score_bar(score)
    return (
        f'<span class="bdw-risk" style="background:{color}">{label}</span> '
        f'<span class="bdw-score">Impact score: <strong>{score:.2f}</strong></span> '
        f'<code class="bdw-bar">{bar}</code>'
    )


def _asset_summary_line(item: Any) -> str:
    return _escape(_label(item))


def _asset_details_html(item: Any, title: str | None = None) -> str:
    """Click-to-expand block for one asset."""
    if isinstance(item, dict):
        payload = item
    else:
        payload = {"asset_id": str(item)}
    summary = _escape(title or _label(item))
    body = _escape(json.dumps(payload, indent=2, default=str))
    desc = ""
    if isinstance(item, dict):
        d = (item.get("description") or "")[:400]
        if d:
            desc = f'<p class="bdw-desc">{_escape(d)}</p>'
    return (
        f"<details class='bdw-details'>"
        f"<summary>{summary}</summary>"
        f"{desc}"
        f"<pre class='bdw-pre'>{body}</pre>"
        f"</details>"
    )


def _group_assets(items: list[Any]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {k: [] for k in _TYPE_ORDER}
    seen = set()
    for item in items:
        aid = _node_id(item)
        if not aid or aid in seen:
            continue
        seen.add(aid)
        atype = _node_type(item) or "other"
        bucket = atype if atype in groups else "other"
        groups[bucket].append(item)
    return {k: v for k, v in groups.items() if v}


def _collect_usage_groups(data: dict[str, Any]) -> dict[str, list[Any]]:
    combined: list[Any] = []
    for key in ("queries", "etl_jobs", "reports", "downstream_tables", "downstream"):
        combined.extend(list(data.get(key) or []))
    return _group_assets(combined)


def _collect_change_groups(data: dict[str, Any]) -> dict[str, list[Any]]:
    combined: list[Any] = []
    for key in ("affected_queries", "affected_etl", "affected_reports"):
        combined.extend(list(data.get(key) or []))
    return _group_assets(combined)


def _center_meta(data: dict[str, Any], fallback: str) -> tuple[str, str]:
    asset = data.get("asset")
    if isinstance(asset, dict):
        center = str(asset.get("asset_id") or asset.get("name") or fallback).strip()
        return center or fallback, str(asset.get("asset_type") or "").strip()
    center = str(data.get("asset_id") or fallback).strip()
    return center or fallback, ""


def _ascii_impact_tree(center: str, center_type: str, groups: dict[str, list[Any]]) -> str:
    rows: list[str] = []
    center_line = f"  ▶ {center}"
    if center_type:
        center_line += f" ({center_type})"
    rows.append(center_line)
    if not groups:
        rows.append("       └──▶ (no downstream dependents)")
        return "\n".join(rows)

    rows.append("       │")
    type_keys = [k for k in _TYPE_ORDER if k in groups]
    for ti, atype in enumerate(type_keys):
        items = groups[atype]
        t_branch = "├" if ti < len(type_keys) - 1 else "└"
        rows.append(f"       {t_branch}──▶ {atype.upper()} ({len(items)})")
        for ii, item in enumerate(items):
            i_branch = "├" if ii < len(items) - 1 else "└"
            prefix = "       │   " if ti < len(type_keys) - 1 else "           "
            rows.append(f"{prefix}{i_branch}── {_label(item)}")
    return "\n".join(rows)


def _impact_styles() -> str:
    return """
<style>
.bdw-impact { font-family: system-ui, sans-serif; line-height: 1.45; }
.bdw-impact h3 { margin: 0 0 0.5rem 0; }
.bdw-risk { color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }
.bdw-score { margin-left: 0.5rem; }
.bdw-bar { margin-left: 0.5rem; letter-spacing: 1px; }
.bdw-tree { background: #f6f8fa; padding: 12px; border-radius: 6px; font-size: 0.9rem; }
.bdw-details { margin: 0.35rem 0; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0 0.5rem; }
.bdw-details summary { cursor: pointer; font-weight: 500; padding: 0.35rem 0; }
.bdw-pre { font-size: 0.8rem; overflow-x: auto; margin: 0.25rem 0 0.5rem 0; }
.bdw-desc { color: #475569; font-size: 0.85rem; margin: 0.25rem 0; }
.bdw-section { margin-top: 0.75rem; }
.bdw-change { background: #fffbeb; border-left: 4px solid #b8860b; padding: 8px 12px; margin: 0.5rem 0; }
.bdw-warn { background: #fef2f2; border-left: 4px solid #b91c1c; padding: 8px 12px; margin: 0.5rem 0; color: #7f1d1d; }
</style>
"""


def build_usage_impact_html(data: dict[str, Any], asset_name: str) -> str:
    """Usage analysis: hierarchical tree + expandable asset details."""
    center, center_type = _center_meta(data, asset_name)
    score = float(data.get("impact_score", 0.0) or 0.0)
    groups = _collect_usage_groups(data)

    parts = [
        _impact_styles(),
        '<div class="bdw-impact">',
        f"<h3>Usage impact: <code>{_escape(center)}</code></h3>",
        f"<p>{_risk_badge(risk_level_from_score(score), score)}</p>",
        "<p><em>Downstream dependents may be affected if this asset changes.</em></p>",
        '<div class="bdw-section"><strong>Dependency tree</strong>',
        f'<pre class="bdw-tree">{_escape(_ascii_impact_tree(center, center_type, groups))}</pre></div>',
        '<div class="bdw-section"><strong>Assets (click to expand details)</strong>',
        f"<details class='bdw-details'><summary>▶ Center: {_escape(_label(data.get('asset') or center))}</summary>",
    ]
    center_payload = (
        data.get("asset")
        if isinstance(data.get("asset"), dict)
        else {"asset_id": center, "asset_type": center_type}
    )
    parts.append(
        f"<pre class='bdw-pre'>{_escape(json.dumps(center_payload, indent=2, default=str))}</pre></details>"
    )

    for atype in _TYPE_ORDER:
        for item in groups.get(atype, []):
            parts.append(_asset_details_html(item))

    if not groups:
        parts.append("<p><em>No downstream SQL/ETL/table dependencies in metadata.</em></p>")

    parts.append("</div></div>")
    return "\n".join(parts)


def build_change_impact_html(
    data: dict[str, Any],
    asset_name: str,
    resolution_warning: str | None = None,
) -> str:
    """Change assessment: risk badge + blast-radius tree + expandable affected assets."""
    center, center_type = _center_meta(data, asset_name)
    score = float(data.get("impact_score", 0.0) or 0.0)
    risk = risk_level_from_score(score)
    change = str(data.get("change") or "").strip()
    groups = _collect_change_groups(data)
    downstream_count = int(data.get("downstream_count") or sum(len(v) for v in groups.values()))

    parts = [
        _impact_styles(),
        '<div class="bdw-impact">',
        f"<h3>Change impact: <code>{_escape(center)}</code></h3>",
        f"<p>{_risk_badge(risk, score)} · <span>Dependents: <strong>{downstream_count}</strong></span></p>",
    ]
    if change:
        parts.append(
            f'<div class="bdw-change"><strong>Proposed change:</strong> {_escape(change)}</div>'
        )
    warn = resolution_warning or data.get("resolution_warning")
    if warn:
        parts.append(f'<div class="bdw-warn"><strong>Note:</strong> {_escape(warn)}</div>')
    if data.get("asset_resolved_from") == "change_text":
        parts.append(
            f"<p><em>Blast radius is for <code>{_escape(center)}</code> "
            f"(parsed from proposed change text).</em></p>"
        )

    parts.extend(
        [
            '<div class="bdw-section"><strong>Blast radius</strong>',
            f'<pre class="bdw-tree">{_escape(_ascii_impact_tree(center, center_type, groups))}</pre></div>',
            '<div class="bdw-section"><strong>Affected assets (click to expand)</strong>',
            f"<details class='bdw-details'><summary>▶ Source: {_escape(_label(data.get('asset') or center))}</summary>",
        ]
    )
    center_payload = (
        data.get("asset")
        if isinstance(data.get("asset"), dict)
        else {"asset_id": center, "asset_type": center_type}
    )
    parts.append(
        f"<pre class='bdw-pre'>{_escape(json.dumps(center_payload, indent=2, default=str))}</pre></details>"
    )

    for atype in _TYPE_ORDER:
        for item in groups.get(atype, []):
            parts.append(_asset_details_html(item))

    if not groups:
        parts.append("<p><em>No affected SQL/ETL assets detected for this change.</em></p>")

    parts.append("</div></div>")
    return "\n".join(parts)


def build_impact_json(data: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(data, indent=2, default=str)}\n```"
