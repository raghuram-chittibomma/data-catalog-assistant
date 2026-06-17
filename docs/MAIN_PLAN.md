# data-catalog-assistant — Master plan (revised)

**Last updated:** 2026-05-26 — Iteration 5.1 done (5 SQL + 4 ETL samples, demo script); refresh to load into Chroma/metadata.

**Environment:** `conda activate ai-dev` — use this Python for all commands below.

---

## Current baseline (verified)

| Component | Status | Evidence |
|-----------|--------|----------|
| Config + `.env` | Done | `${VAR}` substitution via `config_loader` |
| Stack lock-in | Done | Postgres DW only; Chroma only; local embeddings |
| DW ingest (A–D) | Done | 14 tables; **5 SQL + 4 ETL** samples in repo (`sql_samples/`, `etl_samples/`) |
| `run_refresh_job.py` | Done | `status: completed` ~23s; 16 docs, 16 embeddings, 16 Chroma upserts |
| Postgres `bdw_rag_metadata` | Done | `backend: postgres`; 16 assets, 18 relationships |
| Chroma `chroma_data/` | Done | 16 documents added |
| `sentence-transformers` | Done in ai-dev | Upgraded (2.2.2 + old hub conflict fixed); model cached |
| Unit tests | Done | 62 passed (1 skipped without gradio in CI) |
| Preflight refresh check | Done | 0 fail / 0 warn before last refresh |
| MCP HTTP API (FastAPI) | Done (Phase 2) | `main.py` keep-alive; see `docs/MCP_DEMO.md` |
| Gradio UI | Done (Phase 4) | http://127.0.0.1:7860 — search, lineage, SQL tabs; needs `gradio>=4.44`, `starlette<1` |
| `QueryProcessor` | Done (Phase 2) | Delegates to `RAGEngine`; MCP returns `sql` key |
| RAG context in SQL | Done (Phase 3) | Catalog snippets in LLM prompt |
| `JobScheduler.start()` | Not done | `pass` — scheduled refresh from `main.py` does not run |
| Ingestion Phase E (ops) | Deferred | Incremental ingest, error policy, metrics |
| Full POC Gradio pack | Reverted | Prefer minimal UI later if needed |

---

## Track 1 — Data ingestion

| Phase | Scope | Status | Notes |
|-------|--------|--------|-------|
| **A** | Schema filter, connector `close()`, `run_ingestion.py` | **Done** | `schemas: [public]`, exclude tables |
| **B** | Batch PK/FK metadata, Chroma upsert, catalog fields | **Done** | `fetch_tables_metadata()` bulk path |
| **C** | SQL file ingest + lineage | **Done** | `sql_samples/` → 5 SQL assets (5.1) |
| **D** | ETL YAML/JSON + lineage | **Done** | `etl_samples/` → 4 ETL jobs (5.1) |
| **E** | Incremental ingest, per-asset errors, refresh metrics | **Deferred** | Post-POC / production |

**Refresh command (operational):**

```powershell
conda activate ai-dev
cd c:\Users\raghu\AI-Projects\data-catalog-assistant
python batch_jobs\run_refresh_job.py
```

---

## Track 2 — Application & demo (revised phases)

### Phase 1 — Operable baseline — **Done**

| Task | Status |
|------|--------|
| DW connection | Done (14 tables) |
| Metadata Postgres + auto DDL | Done (`metadata_assets`, `metadata_relationships`) |
| Full refresh end-to-end | Done (2026-05-26 run) |
| Preflight script | Done |
| ai-dev + embeddings | Done |

---

### Phase 2 — Query & MCP polish — **Done**

**Goal:** Reliable API demo without Gradio.

| Task | Status |
|------|--------|
| 2.1 `main.py` lifecycle | Done — MCP keep-alive; scheduler off unless `schedule_on_startup: true` |
| 2.2 `QueryProcessor` → `RAGEngine` | Done — `normalize_llm_result`; MCP `sql` key |
| 2.3 MCP smoke tests / curl doc | Done — `docs/MCP_DEMO.md`, pytest |
| 2.4 `sentence-transformers>=3` in requirements | Done |

**Done when:** `python src/main.py` stays up; curl search + lineage return real post-refresh data.

---

### Phase 3 — RAG-aware SQL — **Done**

**Goal:** `generate_query` uses retrieved catalog context.

| Task | Status |
|------|--------|
| 3.1 Retrieve top-k docs before LLM | Done — `QueryProcessor.build_catalog_context()` |
| 3.2 Prompt with table/column text from hits | Done — `RAGEngine.generate_query(..., catalog_context=)` |
| 3.3 Tests with mocked LLM | Done — `tests/test_query_processor_rag.py` |
| 3.4 Config `query.rag_top_k`, `max_context_chars` | Done |

**Requires:** `OPENAI_API_KEY` for live SQL gen. Run `main.py` + refresh job beforehand.

---

### Phase 4 — UI & automation — **Mostly done**

| Task | Status |
|------|--------|
| 4.1 Minimal Gradio (search + lineage + SQL tabs) | **Done** — `src/ui/gradio_interface.py` |
| 4.2 `JobScheduler.start()` loop (`schedule.run_pending`) | **Todo** — still `pass`; refresh is manual CLI |
| 4.3 Disable scheduler on startup by default | **Done** — `schedule_on_startup: false` in `config.yaml` |
| 4.4 Gradio deps (Starlette &lt;1, Gradio ≥4.44) | **Done** — `requirements.txt` + preflight check |

---

### Phase 5 — Production — **Later**

**Platform & security**

- MCP auth / TLS / secret management
- Integration tests against real DW (pytest marker)
- Official MCP SDK (optional)
- Logging to `logs/bdw_rag.log` in production

**Ingestion Phase E + ETL/report platform integration**

- Incremental ingest, per-asset errors, refresh metrics (Phase E)
- **Enterprise reporting platform** — direct integration to source report definitions and dependencies into the catalog (not file samples only)
- Direct integration to **report and ETL servers** for incremental catalog/embedding updates (not only DW schema + local sample files)
- **Informatica (example):** Workflow XML, Mapping XML, source/target definitions → parse lineage and refresh vectors on change

**Search & RAG**

- **LLM in catalog search** — NLP-assisted discovery (POC search is embeddings-only in Chroma)
- **Richer RAG context** — include matching report metadata and ETL/SQL in retrieval (extend beyond current catalog snippets for `generate_query`)

---

## Priority order (from here)

POC demo path is **complete**. Pick next work by audience:

| Order | Item | When |
|-------|------|------|
| ~~**1**~~ | ~~More `sql_samples/` / `etl_samples/`~~ | **Done (5.1)** — see `docs/DEMO_SCRIPT.md` |
| ~~**2**~~ | ~~Lineage unification + Gradio validate SQL tab~~ | **Done (5B)** — `lineage_service`, Validate SQL + Catalog browse tabs |
| ~~**3**~~ | ~~Gradio impact tab~~ | **Done (5B)** — `analyze_data_usage`, `assess_change_impact` |
| **4** (optional) | `JobScheduler.start()` loop | Nightly refresh without cron |
| **5** (later) | Ingestion Phase E + Phase 5 | Production / ops hardening |

---

## Verification checklist (current)

```text
[x] test_dw_connection.py / preflight DW OK
[x] run_refresh_job.py completed
[x] 16 assets in Postgres metadata
[x] 18 relationships in Postgres metadata
[x] Chroma populated (16 documents)
[x] MCP search + lineage (main.py + mcp_smoke or curl)
[x] generate_query with OPENAI_API_KEY (RAG context + tables_used)
[x] Gradio UI at http://127.0.0.1:7860 (search, lineage, SQL)
[x] Expanded catalog samples (5.1 — 5 SQL, 4 ETL; refresh applied)
[x] UI/MCP lineage parity + Validate SQL + Catalog browse + Impact tab (5B complete)
[ ] JobScheduler loop (optional — manual refresh OK for POC)
[ ] Ingestion Phase E (deferred)
```

---

## Known non-blocking log warnings

- Chroma `chroma_impl` config ignored (uses default persistent client)
- Chroma PostHog telemetry `capture()` error
- Windows HuggingFace symlink cache warning

---

## Quick reference

| Path | Purpose |
|------|---------|
| `config/config.yaml` | DW, Chroma, metadata, ingest paths |
| `.env` | `DW_*`, `METADATA_DB_*`, `OPENAI_API_KEY` |
| `chroma_data/` | Vector index |
| `bdw_rag_metadata` | Catalog + lineage (Postgres) |
| `sql_samples/`, `etl_samples/` | File-based lineage sources |

See also: [SETUP_GUIDE.md](SETUP_GUIDE.md) for setup and run commands.
