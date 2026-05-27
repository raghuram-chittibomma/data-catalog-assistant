# Demo script

Run after catalog refresh and app start:

```powershell
conda activate ai-dev
cd C:\Users\raghu\AI-Projects\data-catalog-assistant
python scripts\preflight_refresh.py
python batch_jobs\run_refresh_job.py
python src\main.py
```

Open **http://127.0.0.1:7860** — UI title: **Data Catalog Assistant**. The top legend explains **LLM / Embeddings / Metadata**.

---

## 5-minute interview demo

Use this order for recruiters or hiring managers (~5 min). Mention the legend: *only Generate SQL calls OpenAI*.

| Step | Time | Tab | What to say + do |
|------|------|-----|------------------|
| 1 | 0:30 | *(top legend)* | “Search uses vectors; lineage and impact use our metadata graph; SQL generation is the only LLM call.” |
| 2 | 1:00 | **Catalog search · Embeddings** | Query: `product revenue by category` → show SQL + table hits. |
| 3 | 1:00 | **Lineage · Metadata** | Asset: `public.orders`, direction **both** → ASCII upstream/downstream. |
| 4 | 1:30 | **Impact · Metadata** | See [Change impact scenario](#change-impact-scenario) below — shows smart table resolution. |
| 5 | 1:00 | **Generate SQL · LLM** | `top 5 customers by order count` → SQL + **Tables used (RAG)**. Optional: terminal `LLM prompt outgoing` if `llm.log_prompts: true`. |
| 6 | 0:30 | *(optional)* | **Validate SQL · Rules** — paste `DROP TABLE x` → blocked. Or curl one MCP call (below). |

**Closer:** “Same tools are on FastAPI port 3000 for agents; refresh job rebuilds Chroma and metadata from the warehouse and sample files.”

---

## Change impact scenario

Shows **solution design** (field vs change text):

| Field | Value |
|-------|--------|
| Asset id | `public.orders` *(can stay from prior usage demo)* |
| Proposed change | `Rename column company_name to legal_name on public.customers` |

**Expected:** Header **Change impact: public.customers**; warning that Asset id was `public.orders`; blast radius for **customers** dependents (not orders-only tree).

For a simpler case, set Asset id to `public.customers` with the same change text — no warning.

---

## Gradio — Catalog search · Embeddings

| Try this query | Expected hits |
|----------------|---------------|
| product revenue by category | `sql_samples/product_revenue_by_category.sql`, `public.products` |
| employee sales revenue | `sql_samples/employee_sales_totals.sql`, `public.employees` |
| shipper shipped orders | `sql_samples/recent_orders_by_shipper.sql` |
| ETL product sales fact | `etl_samples/load_product_sales_fact.yaml` |
| customer order count | `sql_samples/orders_by_customer.sql` |

---

## Gradio — Catalog browse · Metadata

Click **Show summary** (optional filter `orders`) — table and ETL counts (MCP `data_catalog_summary` / `list_tables`).

---

## Gradio — Lineage · Metadata

Same path as MCP `get_lineage` (`lineage_service` via `ImpactTools`). **ASCII diagram** + **Raw JSON** accordion.

| Asset id | What to show |
|----------|----------------|
| `sql:sql_samples/product_revenue_by_category.sql` | upstream: categories, products, order_details |
| `etl:etl_samples/load_product_sales_fact.yaml#load_product_sales_fact` | sources + dependency on order line facts |
| `public.orders` | FK to customers; SQL/ETL downstream edges |

---

## Gradio — Validate SQL · Rules

Paste generated SQL or `DROP TABLE x` — mirrors MCP `validate_query` (no LLM).

---

## Gradio — Impact · Metadata

| Action | Asset / change | Example |
|--------|----------------|---------|
| **Analyze usage** | `public.orders` | Tree by type (SQL/ETL/table) + impact score |
| **Assess change impact** | See [Change impact scenario](#change-impact-scenario) | Risk badge + blast-radius tree |

Expand asset rows and **Raw JSON** accordions for full MCP-shaped payloads.

```powershell
curl.exe -X POST "http://localhost:3000/tools/analyze_data_usage" `
  -H "Content-Type: application/json" `
  -d "{\"data_asset\": \"public.orders\"}"
```

---

## Gradio — Generate SQL · LLM

Requires `OPENAI_API_KEY` in `.env`.

| Natural language | Should use tables (RAG) |
|----------------|-------------------------|
| top 5 customers by order count | customers, orders |
| revenue by product category | categories, products, order_details |
| orders shipped by each shipper in 1998 | orders, shippers |

Check terminal for `LLM prompt outgoing` when `llm.log_prompts: true` in `config/config.yaml`.

---

## MCP (curl)

```powershell
curl.exe -X POST "http://localhost:3000/tools/search_data_assets" `
  -H "Content-Type: application/json" `
  -d "{\"query\": \"employee sales ETL\", \"top_k\": 8}"
```

More examples: [MCP_DEMO.md](MCP_DEMO.md).

---

## Screenshots for README

Capture four images per [images/README.md](images/README.md) after a successful demo run.
