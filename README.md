# Data Catalog Assistant

**RAG-based data warehouse intelligence POC** — semantic catalog search, lineage & change-impact analysis, and natural-language SQL generation with a clear split between **LLM**, **embeddings**, and **metadata**.

[![Tests](https://github.com/raghuram-chittibomma/data-catalog-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/raghuram-chittibomma/data-catalog-assistant/actions/workflows/ci.yml)

> **Portfolio:** [docs/SHOWCASE.md](docs/SHOWCASE.md) · **5-min demo:** [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · **Publish to GitHub:** [docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md)

---

## Problem

Teams lose time finding tables and SQL, tracing lineage manually, and estimating blast radius before schema changes.

## Solution

Ingest warehouse schema plus SQL/ETL samples into **Chroma** (search) and **Postgres metadata** (lineage/impact). Expose the same capabilities through **Gradio** (http://127.0.0.1:7860) and **FastAPI MCP-style tools** (http://localhost:3000). Use **OpenAI only for Generate SQL**, with RAG context from the catalog.

## Screenshots

| Catalog search (embeddings) | Lineage (metadata) |
|:---:|:---:|
| ![Catalog search](docs/images/catalog-search.png) | ![Lineage](docs/images/lineage.png) |

| Change impact (metadata) | Generate SQL (LLM + RAG) |
|:---:|:---:|
| ![Change impact](docs/images/change-impact.png) | ![Generate SQL](docs/images/generate-sql.png) |

---

## Architecture

```mermaid
flowchart TB
  subgraph ingest [Batch refresh]
    DW[(PostgreSQL DW)]
    Files[sql_samples + etl_samples]
    Job[run_refresh_job.py]
  end
  subgraph storage [Storage]
    Chroma[(ChromaDB)]
    Meta[(Postgres metadata)]
  end
  subgraph runtime [Runtime - main.py]
    RAG[RAG Engine]
    Tools[MCP tools - FastAPI]
    UI[Gradio UI]
  end
  DW --> Job
  Files --> Job
  Job --> Chroma
  Job --> Meta
  Chroma --> RAG
  Meta --> Tools
  Meta --> UI
  RAG --> Tools
  RAG --> UI
```

| Component | Path |
|-----------|------|
| Ingestion | `src/data_ingestion/` |
| Vector + metadata | `src/vector_store/` |
| RAG / impact | `src/core/` |
| MCP API | `src/mcp_server/` |
| UI | `src/ui/` |
| Refresh | `batch_jobs/run_refresh_job.py` |

---

## Tech stack

| Area | Stack |
|------|--------|
| Runtime | Python 3.10+, conda env `ai-dev` recommended |
| Warehouse | PostgreSQL (Northwind-style sample) |
| Catalog / lineage | PostgreSQL database `bdw_rag_metadata` |
| Vectors | ChromaDB, `sentence-transformers` (`all-MiniLM-L6-v2`) |
| LLM | OpenAI (GPT-4) — NL→SQL only |
| API | FastAPI, Uvicorn |
| UI | Gradio 4.x |
| Tests | pytest (~95 tests) |

---

## Design decisions

- **Embeddings for search, graph for lineage** — Similarity in Chroma; upstream/downstream and impact scores in Postgres.
- **LLM only where needed** — Generate SQL uses RAG + OpenAI; impact and lineage stay deterministic for demos.
- **Shared services** — `lineage_service`, `ImpactTools` used by MCP and Gradio.
- **Change text drives target table** — Assess change impact parses `on public.customers` even if Asset id still says `public.orders`.
- **SQL validation** — Rule-based checks on generated SQL before display.

Details: [docs/SHOWCASE.md](docs/SHOWCASE.md)

---

## Quick start

### Prerequisites

- Python 3.10+
- PostgreSQL (data warehouse + metadata DB)
- [OpenAI API key](https://platform.openai.com/) (only for **Generate SQL** tab)
- Conda env with dependencies installed (`pip install -r requirements.txt`)

### Setup

```powershell
conda activate ai-dev
cd path\to\data-catalog-assistant

copy .env.example .env
# Edit .env: DW_HOST, DW_USER, DW_PASSWORD, METADATA_DB_HOST, METADATA_DB_*, OPENAI_API_KEY
```

### Refresh catalog (required once)

```powershell
python scripts\preflight_refresh.py
python batch_jobs\run_refresh_job.py
```

Expect ~16 vector documents and lineage relationships in metadata (varies with samples).

### Run application

```powershell
python src\main.py
```

| Service | URL |
|---------|-----|
| Gradio UI | http://127.0.0.1:7860 |
| MCP HTTP API | http://localhost:3000 |

**Note:** Overnight scheduler is **off** by default (`schedule_on_startup: false`). Refresh the catalog with `run_refresh_job.py` (or cron), not via a background loop in `main.py`.

---

## What uses AI in the UI

| Tab | Technology |
|-----|------------|
| Catalog search · Embeddings | Chroma — no chat LLM |
| Catalog browse / Lineage / Impact · Metadata | Postgres lineage — no LLM |
| Validate SQL · Rules | Pattern checks — no LLM |
| Generate SQL · LLM | OpenAI + RAG catalog context |

---

## Tests

```powershell
pytest tests/ -q
pytest tests/ --cov=src
```

CI runs the same suite on push (see `.github/workflows/ci.yml`). Badge links to [github.com/raghuram-chittibomma/data-catalog-assistant](https://github.com/raghuram-chittibomma/data-catalog-assistant).

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/SHOWCASE.md](docs/SHOWCASE.md) | Resume / interview one-pager |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Live demo steps |
| [docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md) | Clean repo checklist |
| [docs/MAIN_PLAN.md](docs/MAIN_PLAN.md) | Phase status (internal) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component deep dive |
| [docs/MCP_DEMO.md](docs/MCP_DEMO.md) | curl / MCP examples |
| [WORKING_COPY.md](WORKING_COPY.md) | Day-to-day dev commands |

---

## MCP tools (summary)

- **Search:** `search_data_assets`
- **Query:** `generate_query`, `validate_query`
- **Impact:** `analyze_data_usage`, `get_lineage`, `assess_change_impact`
- **Catalog:** resources in `data_catalog.py`

---

## Project layout

```
├── src/                 # Application code
├── batch_jobs/          # Catalog refresh
├── config/config.yaml   # DW, Chroma, metadata, LLM
├── sql_samples/         # Lineage SQL assets
├── etl_samples/         # ETL YAML assets
├── tests/               # pytest suite
└── docs/                # Showcase, demo, architecture
```

---

## Security

- Never commit `.env` or API keys.
- Use `.env.example` as a template only.
- Production would add MCP auth, TLS, and secret management (see `docs/MAIN_PLAN.md` Phase 5).

---

## License

[MIT](LICENSE) — see [LICENSE](LICENSE) for details.
