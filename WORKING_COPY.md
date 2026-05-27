# Developer notes — data-catalog-assistant

**Master plan:** [docs/MAIN_PLAN.md](docs/MAIN_PLAN.md)

**Status:** POC + 5.1 + 5B (UI/MCP parity). Portfolio: [README.md](README.md), [docs/SHOWCASE.md](docs/SHOWCASE.md), [docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md). Demo: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

**Stack:** PostgreSQL (DW) + Chroma (`chroma_data/`) + local embeddings (`all-MiniLM-L6-v2`). OpenAI only for Generate SQL. Metadata DB name unchanged: `bdw_rag_metadata`.

**Run (ai-dev):**

```powershell
conda activate ai-dev
cd c:\Users\raghu\AI-Projects\data-catalog-assistant

python scripts\preflight_refresh.py
python batch_jobs\run_refresh_job.py
python src\main.py
```

Gradio http://127.0.0.1:7860 · MCP http://localhost:3000

**Regenerate after schema/sample changes:** `python batch_jobs\run_refresh_job.py`

Legacy folder name was `BDW-RAG-copy`; original prototype may still exist at `../BDW-RAG`.
