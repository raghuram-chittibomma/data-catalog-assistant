"""
Gradio Interface - web UI for Data Catalog Assistant (Phase 4 + 5B parity).
"""

import html
import logging
from typing import Any

from src.ui.impact_view import (
    build_change_impact_html,
    build_impact_json,
    build_usage_impact_html,
)
from src.ui.lineage_view import build_lineage_diagram, build_lineage_json
from src.utils.change_asset_resolver import resolve_change_target_asset

logger = logging.getLogger(__name__)

# Shown in tab labels and per-tab notes so demo audiences know what calls OpenAI.
_DEMO_TECH_LEGEND_HTML = """
<style>
.bdw-demo-legend { font-family: system-ui, sans-serif; font-size: 0.9rem; margin: 0.25rem 0 1rem 0; line-height: 1.6; }
.bdw-chip { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin: 0 6px 4px 0; }
.bdw-chip-llm { background: #dbeafe; color: #1e40af; }
.bdw-chip-emb { background: #e0e7ff; color: #3730a3; }
.bdw-chip-meta { background: #ecfdf5; color: #166534; }
</style>
<div class="bdw-demo-legend">
  <strong>What uses AI in this demo?</strong><br/>
  <span class="bdw-chip bdw-chip-llm">LLM</span> OpenAI chat model — <em>Generate SQL</em> only<br/>
  <span class="bdw-chip bdw-chip-emb">Embeddings</span> Vector search (Chroma) — <em>Catalog search</em>; no text generation<br/>
  <span class="bdw-chip bdw-chip-meta">Metadata / rules</span> Postgres catalog &amp; lineage graph —
  <em>Browse, Lineage, Validate SQL, Impact</em>
</div>
"""

_TECH_NOTE_SEARCH = (
    "> **Embeddings only (no LLM)** — Your phrase is embedded and matched against "
    "the catalog in Chroma; results are ranked by similarity."
)
_TECH_NOTE_BROWSE = (
    "> **No LLM** — Reads table counts and metadata from the catalog store (Postgres)."
)
_TECH_NOTE_LINEAGE = "> **No LLM** — Upstream/downstream links come from ingested SQL/ETL metadata."
_TECH_NOTE_SQL = (
    "> **Uses LLM (OpenAI)** — Retrieves relevant catalog context (embeddings), then "
    "the model writes SQL. Requires `OPENAI_API_KEY`."
)
_TECH_NOTE_VALIDATE = (
    "> **No LLM** — Rule-based SQL safety checks (blocked keywords, basic structure)."
)
_TECH_NOTE_IMPACT = (
    "> **No LLM** — Usage and change impact use the lineage graph and impact scores "
    "in metadata; proposed change text is parsed for the target table only."
)


def _escape(text: Any) -> str:
    return html.escape(str(text))


def _asset_label(asset: Any) -> str:
    if isinstance(asset, dict):
        return str(asset.get("asset_id") or asset.get("name") or asset)
    return str(asset)


def _format_asset_bullets(assets: list, limit: int = 12) -> str:
    if not assets:
        return "- (none)"
    lines = []
    for item in assets[:limit]:
        label = _asset_label(item)
        atype = item.get("asset_type", "") if isinstance(item, dict) else ""
        suffix = f" ({atype})" if atype else ""
        lines.append(f"- `{label}`{suffix}")
    if len(assets) > limit:
        lines.append(f"- … and {len(assets) - limit} more")
    return "\n".join(lines)


class GradioInterface:
    """
    Gradio web UI: catalog search, lineage, SQL generation, validation, catalog browse.
    Uses the same MCP tool classes as the HTTP API where noted.
    """

    def __init__(
        self,
        rag_engine=None,
        query_processor=None,
        query_tools=None,
        impact_tools=None,
        data_catalog=None,
        config: dict[str, Any] = None,
    ):
        self.rag_engine = rag_engine
        self.query_processor = query_processor
        self.query_tools = query_tools
        self.impact_tools = impact_tools
        self.data_catalog = data_catalog
        self.config = config or {}
        logger.info("Initialized Gradio Interface")

    def format_search_results(self, query: str, top_k: int = 5) -> str:
        if not self.rag_engine:
            return "RAG engine not configured."
        query = (query or "").strip()
        if not query:
            return "Enter a search phrase."

        hits = self.rag_engine.search_data_lineage(query, top_k=int(top_k))
        if not hits:
            return "No results. Run `python batch_jobs\\run_refresh_job.py` to populate Chroma."

        blocks = []
        for i, hit in enumerate(hits, 1):
            asset_type = (hit.metadata or {}).get("asset_type", "asset")
            blocks.append(
                f"### {i}. {hit.data_asset} ({asset_type}, score={hit.relevance_score:.3f})\n"
                f"{hit.description[:1500]}"
            )
        return "\n\n".join(blocks)

    def _fetch_lineage_data(self, asset_name: str, direction: str = "both") -> dict[str, Any]:
        asset_name = (asset_name or "").strip()
        dir_norm = direction or "both"
        if self.impact_tools:
            return self.impact_tools.get_lineage(asset_name, direction=dir_norm)
        if self.rag_engine:
            data = self.rag_engine.get_data_lineage(asset_name)
            data["direction"] = dir_norm
            return data
        return {}

    def format_lineage(self, asset_name: str, direction: str = "both") -> str:
        """High-level diagram only (backward compatible)."""
        diagram, _ = self.format_lineage_views(asset_name, direction)
        return diagram

    def format_lineage_views(self, asset_name: str, direction: str = "both") -> tuple[str, str]:
        """
        Return (diagram markdown, raw JSON markdown) for Gradio dual outputs.
        """
        asset_name = (asset_name or "").strip()
        if not asset_name:
            msg = "Enter an asset id (e.g. `public.orders` or `sql:sql_samples/orders_by_customer.sql`)."
            return msg, ""

        if not self.impact_tools and not self.rag_engine:
            return "Lineage tools not configured.", ""

        data = self._fetch_lineage_data(asset_name, direction)
        if not data.get("asset") and not data.get("upstream") and not data.get("downstream"):
            msg = f"No lineage found for `{asset_name}` (direction={direction})."
            return msg, build_lineage_json(data)

        diagram = build_lineage_diagram(data, asset_name, direction=direction or "both")
        return diagram, build_lineage_json(data)

    def format_validate_sql(self, sql: str) -> str:
        sql = (sql or "").strip()
        if not sql:
            return "Paste a SQL statement to validate."

        if self.query_tools:
            result = self.query_tools.validate_query(sql)
        elif self.query_processor:
            valid = self.query_processor.validate_query(sql)
            result = {
                "valid": valid,
                "errors": [] if valid else ["Query failed processor validation"],
                "warnings": [],
            }
        else:
            from src.utils.sql_validator import validate_sql

            ok, reason = validate_sql(sql)
            result = {
                "valid": ok,
                "errors": [] if ok else [reason],
                "warnings": [],
            }

        valid = result.get("valid", False)
        status = "**Valid**" if valid else "**Invalid**"
        errors = result.get("errors") or []
        warnings = result.get("warnings") or []
        lines = [status]
        if errors:
            lines.append("**Errors:**\n" + "\n".join(f"- {e}" for e in errors))
        if warnings:
            lines.append("**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings))
        return "\n\n".join(lines)

    def format_catalog_summary(self, table_pattern: str = "") -> str:
        if not self.data_catalog:
            return "Data catalog not configured."

        summary = self.data_catalog.get_catalog_summary()
        tables = self.data_catalog.list_tables(pattern=table_pattern or None)
        etl_jobs = self.data_catalog.list_etl_processes()

        lines = [
            "## Catalog summary",
            f"- **Total assets:** {summary.get('total_assets', 0)}",
            f"- **Tables:** {summary.get('tables', 0)}",
            f"- **SQL assets:** {summary.get('sql_assets', 0)}",
            f"- **ETL jobs:** {summary.get('etl_processes', 0)}",
            "",
            f"## Tables ({len(tables)})",
        ]
        for t in tables[:25]:
            tid = t.get("asset_id") or t.get("name", "?")
            lines.append(f"- `{tid}`")
        if len(tables) > 25:
            lines.append(f"- … and {len(tables) - 25} more")

        lines.append("")
        lines.append(f"## ETL processes ({len(etl_jobs)})")
        for job in etl_jobs[:15]:
            jid = job.get("asset_id") or job.get("name", "?")
            lines.append(f"- `{jid}`")

        return "\n".join(lines)

    def format_data_usage(self, asset_name: str) -> str:
        """Backward compatible: HTML diagram only."""
        html_out, _ = self.format_data_usage_views(asset_name)
        return html_out

    def format_data_usage_views(self, asset_name: str) -> tuple[str, str]:
        asset_name = (asset_name or "").strip()
        if not asset_name:
            return "<p>Enter an asset id (e.g. <code>public.orders</code>).</p>", ""
        if not self.impact_tools:
            return "<p>Impact tools not configured.</p>", ""

        data = self.impact_tools.analyze_data_usage(asset_name)
        return build_usage_impact_html(data, asset_name), build_impact_json(data)

    def format_change_impact(self, asset_name: str, change_description: str) -> str:
        html_out, _ = self.format_change_impact_views(asset_name, change_description)
        return html_out

    def format_change_impact_views(
        self, asset_name: str, change_description: str
    ) -> tuple[str, str]:
        asset_name = (asset_name or "").strip()
        change_description = (change_description or "").strip()
        if not change_description:
            return "<p>Describe the proposed change (e.g. drop column, rename field).</p>", ""
        effective, _ = resolve_change_target_asset(asset_name, change_description)
        if not effective:
            return (
                "<p>Enter an asset id or name the target table in the change text "
                "(e.g. <code>on public.customers</code>).</p>",
                "",
            )
        if not self.impact_tools:
            return "<p>Impact tools not configured.</p>", ""

        data = self.impact_tools.assess_change_impact(asset_name, change_description)
        if data.get("error"):
            return f"<p>{_escape(data['error'])}</p>", build_impact_json(data)

        effective = data.get("asset_id") or asset_name
        return (
            build_change_impact_html(
                data,
                effective,
                resolution_warning=data.get("resolution_warning"),
            ),
            build_impact_json(data),
        )

    def format_sql_generation(self, natural_language: str) -> str:
        if not self.query_processor and not self.rag_engine:
            return "Query processor not configured."

        natural_language = (natural_language or "").strip()
        if not natural_language:
            return "Describe the data you want in plain English."

        if self.query_processor:
            result = self.query_processor.process(natural_language)
        else:
            from src.core.query_processor import QueryProcessor

            result = QueryProcessor.normalize_llm_result(
                self.rag_engine.generate_query(natural_language)
            )

        sql = result.get("sql") or result.get("query") or ""
        explanation = result.get("explanation", "")
        confidence = result.get("confidence", 0.0)
        tables = result.get("tables_used") or []

        if not sql:
            return f"**Could not generate SQL.**\n\n{explanation or 'Check OPENAI_API_KEY and server logs.'}"

        tables_line = ", ".join(tables) if tables else "(none)"
        return (
            f"**Confidence:** {confidence}\n\n"
            f"**Tables used (RAG):** {tables_line}\n\n"
            f"**SQL:**\n```sql\n{sql}\n```\n\n"
            f"**Explanation:** {explanation or '(none)'}"
        )

    def build_interface(self):
        try:
            import gradio as gr
        except ImportError as e:
            raise ImportError(
                "Gradio is not installed. Run: pip install -r requirements.txt "
                "in your active environment (conda activate ai-dev)."
            ) from e

        with gr.Blocks(title="Data Catalog Assistant") as demo:
            gr.Markdown(
                "# Data Catalog Assistant\n"
                "Explore your warehouse: semantic search, lineage, change impact, "
                "SQL generation, and validation."
            )
            gr.HTML(_DEMO_TECH_LEGEND_HTML)

            with gr.Tab("Catalog search · Embeddings"):
                gr.Markdown(_TECH_NOTE_SEARCH)
                search_query = gr.Textbox(
                    label="Search",
                    placeholder="e.g. customer orders, product sales, ETL summary",
                )
                search_top_k = gr.Slider(1, 15, value=5, step=1, label="Results")
                search_btn = gr.Button("Search", variant="primary")
                search_out = gr.Markdown()
                search_btn.click(
                    self.format_search_results,
                    inputs=[search_query, search_top_k],
                    outputs=search_out,
                )

            with gr.Tab("Catalog browse · Metadata"):
                gr.Markdown(_TECH_NOTE_BROWSE)
                table_filter = gr.Textbox(
                    label="Table name filter (optional)",
                    placeholder="orders",
                )
                browse_btn = gr.Button("Show summary", variant="primary")
                browse_out = gr.Markdown()
                browse_btn.click(
                    self.format_catalog_summary,
                    inputs=table_filter,
                    outputs=browse_out,
                )

            with gr.Tab("Lineage · Metadata"):
                gr.Markdown(_TECH_NOTE_LINEAGE)
                lineage_asset = gr.Textbox(
                    label="Asset id",
                    placeholder="public.orders",
                )
                lineage_direction = gr.Radio(
                    ["both", "upstream", "downstream"],
                    value="both",
                    label="Direction",
                )
                lineage_btn = gr.Button("Get lineage", variant="primary")
                lineage_diagram_out = gr.Markdown(label="Lineage diagram")
                with gr.Accordion("Raw JSON (expand for full payload)", open=False):
                    lineage_json_out = gr.Markdown()
                lineage_btn.click(
                    self.format_lineage_views,
                    inputs=[lineage_asset, lineage_direction],
                    outputs=[lineage_diagram_out, lineage_json_out],
                )

            with gr.Tab("Generate SQL · LLM"):
                gr.Markdown(_TECH_NOTE_SQL)
                nl_query = gr.Textbox(
                    label="Natural language",
                    placeholder="top 5 customers by order count",
                    lines=3,
                )
                sql_btn = gr.Button("Generate SQL", variant="primary")
                sql_out = gr.Markdown()
                sql_btn.click(
                    self.format_sql_generation,
                    inputs=nl_query,
                    outputs=sql_out,
                )

            with gr.Tab("Validate SQL · Rules"):
                gr.Markdown(_TECH_NOTE_VALIDATE)
                sql_input = gr.Textbox(
                    label="SQL",
                    placeholder="SELECT ...",
                    lines=8,
                )
                validate_btn = gr.Button("Validate", variant="primary")
                validate_out = gr.Markdown()
                validate_btn.click(
                    self.format_validate_sql,
                    inputs=sql_input,
                    outputs=validate_out,
                )

            with gr.Tab("Impact · Metadata"):
                gr.Markdown(_TECH_NOTE_IMPACT)
                gr.Markdown(
                    "MCP tools: `analyze_data_usage` and `assess_change_impact`. "
                    "**Analyze usage** uses the Asset id field. **Assess change impact** "
                    "uses the table named in the proposed change (e.g. `on public.customers`); "
                    "Asset id is only a fallback. Tree view with **risk score**; expand **Raw JSON** for the API payload."
                )
                with gr.Row():
                    impact_asset = gr.Textbox(
                        label="Asset id",
                        placeholder="public.orders (usage); change text can override for assess",
                        scale=2,
                    )
                usage_btn = gr.Button("Analyze usage", variant="primary")
                usage_html_out = gr.HTML(label="Usage impact")
                with gr.Accordion("Raw JSON — usage (expand for full payload)", open=False):
                    usage_json_out = gr.Markdown()
                usage_btn.click(
                    self.format_data_usage_views,
                    inputs=impact_asset,
                    outputs=[usage_html_out, usage_json_out],
                )
                change_desc = gr.Textbox(
                    label="Proposed change",
                    placeholder="Drop column freight on orders",
                    lines=2,
                )
                change_btn = gr.Button("Assess change impact", variant="secondary")
                change_html_out = gr.HTML(label="Change impact")
                with gr.Accordion(
                    "Raw JSON — change assessment (expand for full payload)", open=False
                ):
                    change_json_out = gr.Markdown()
                change_btn.click(
                    self.format_change_impact_views,
                    inputs=[impact_asset, change_desc],
                    outputs=[change_html_out, change_json_out],
                )

        return demo

    def launch(self, host: str = "127.0.0.1", port: int = 7860, share: bool = False):
        """Launch Gradio (blocks until stopped)."""
        logger.info("Launching Gradio interface on %s:%s", host, port)
        demo = self.build_interface()
        demo.launch(
            server_name=host,
            server_port=port,
            share=share,
            show_error=True,
            inbrowser=False,
            prevent_thread_lock=False,
        )

    def query_builder_callback(self, query: str) -> dict[str, Any]:
        if self.query_tools:
            return self.query_tools.generate_query(query)
        if self.query_processor:
            return self.query_processor.process(query)
        if self.rag_engine:
            from src.core.query_processor import QueryProcessor

            return QueryProcessor.normalize_llm_result(self.rag_engine.generate_query(query))
        return {"sql": "", "explanation": ""}

    def lineage_callback(self, asset_name: str, direction: str = "both") -> dict[str, Any]:
        if self.impact_tools:
            return self.impact_tools.get_lineage(asset_name, direction=direction)
        if self.rag_engine:
            return self.rag_engine.get_data_lineage(asset_name)
        return {}

    def impact_callback(self, asset_name: str) -> dict[str, Any]:
        if self.impact_tools:
            return self.impact_tools.analyze_data_usage(asset_name)
        if self.rag_engine:
            return self.rag_engine.analyze_impact(asset_name)
        return {}
