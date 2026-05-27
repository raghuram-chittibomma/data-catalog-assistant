# MCP API demo (Phase 2)

Data Catalog Assistant exposes a FastAPI MCP-style server on **http://localhost:3000** (configurable).

## Prerequisites

```powershell
conda activate ai-dev
cd c:\Users\raghu\AI-Projects\data-catalog-assistant
python batch_jobs\run_refresh_job.py
python src\main.py
# or: python -m src.main
```

Leave `main.py` running (Ctrl+C to stop).

- **Gradio UI:** http://127.0.0.1:7860 (catalog search, lineage, generate SQL)
- **MCP API:** http://localhost:3000 (scripts/curl)

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health + tool/resource lists |
| GET | `/tools` | List tools |
| POST | `/tools/{tool_name}` | Run tool (JSON body = parameters) |
| GET | `/resources` | List resources |
| POST | `/resources/{resource_name}` | Run resource |

## Example requests (PowerShell)

PowerShell aliases `curl` to `Invoke-WebRequest`. Use **`curl.exe`** or **`Invoke-RestMethod`** below.

**Catalog search**

```powershell
curl.exe http://localhost:3000/

curl.exe -X POST "http://localhost:3000/tools/search_data_assets" `
  -H "Content-Type: application/json" `
  -d "{\"query\": \"customer orders\", \"top_k\": 5}"
```

**Lineage**

```powershell
curl.exe -X POST "http://localhost:3000/tools/get_lineage" `
  -H "Content-Type: application/json" `
  -d "{\"data_asset\": \"public.orders\", \"direction\": \"both\"}"
```

**Catalog summary (resource)**

```powershell
curl.exe -X POST "http://localhost:3000/resources/data_catalog_summary"
```

**SQL generation** (requires `OPENAI_API_KEY` in `.env`)

Phase 3: `generate_query` **searches the catalog first**, then sends top matching table/SQL snippets to the LLM. Response includes **`tables_used`** (asset ids from search).

Requires compatible packages: `openai>=1.55` (see `requirements.txt`). If you see `unexpected keyword argument 'proxies'`, run:

```powershell
pip install "openai>=1.55.0,<2.0.0"
```

Then **restart** `python src\main.py`.

```powershell
curl.exe -X POST "http://localhost:3000/tools/generate_query" `
  -H "Content-Type: application/json" `
  -d "{\"description\": \"top 5 customers by order count\"}"
```

Or:

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:3000/tools/generate_query" `
  -ContentType "application/json" `
  -Body '{"description": "top 5 customers by order count"}'
```

Response uses **`sql`** (not `query`), plus **`tables_used`** when RAG hits tables.

**If `sql` is empty**, check the `explanation` field:

| explanation | Fix |
|---------------|-----|
| `OPENAI_API_KEY not set` | Set key in `.env`, restart `main.py` |
| `unexpected keyword argument 'proxies'` | `pip install "openai>=1.55.0"` and restart `main.py` |
| `[Errno 2] No such file or directory` | Invalid `SSL_CERT_FILE` in environment — restart after code fix, or run `$env:SSL_CERT_FILE = $null` before `main.py` |
| `Safety check failed` | Model returned disallowed SQL |

**Show full response in PowerShell:**

```powershell
$r = Invoke-RestMethod -Method POST -Uri "http://localhost:3000/tools/generate_query" `
  -ContentType "application/json" `
  -Body '{"description": "top 5 customers by order count"}'
$r | Format-List *
```

## Smoke script (server must be running)

```powershell
python scripts\mcp_smoke.py
```

## Automated tests

```powershell
python -m pytest tests/test_mcp_tools_integration.py tests/test_query_tools.py -q
```
