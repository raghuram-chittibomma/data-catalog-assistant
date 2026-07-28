# Data Catalog Assistant — Setup Guide

## Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment manager (venv or conda)
- API Keys:
  - OpenAI (optional, for cloud LLM / SQL generation)
  - Optional local Ollama host (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) for offline/local SQL generation
  - sentence-transformers (local embeddings, via requirements.txt)
  - ChromaDB via `pip install -r requirements.txt` (no separate server required)

## Installation Steps

### 1. Clone or Download Project

```bash
cd data-catalog-assistant
```

### 2. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n ai-dev python=3.10
conda activate ai-dev
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
# Copy template
cp .env.example .env

# Edit with your settings
# Add your API keys and database credentials
```

### 5. Application Configuration

Edit `config/config.yaml` with:
- Data warehouse credentials
- Vector store settings
- LLM provider and model
- UI port and settings
- Batch job schedule

### 6. Populate the index, then run

```bash
# Build/refresh the Chroma vector index + metadata store from the DW, SQL, and ETL samples
python batch_jobs/run_refresh_job.py

# Launch the Gradio UI + REST API
python src/main.py
```

Gradio UI: http://127.0.0.1:7860 · REST API: http://localhost:3000

Re-run `python batch_jobs/run_refresh_job.py` whenever the schema or the `sql_samples/` / `etl_samples/` change.

### 7. Run as an MCP server (stdio)

The project also ships a real Model Context Protocol server (built on the official
`mcp` Python SDK) that exposes the same catalog/query/impact tools to MCP-compatible
clients (Claude Desktop, Cursor, etc.) over stdio:

```bash
python -m src.mcp_server.mcp_app
```

Example client config (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "data-catalog-assistant": {
      "command": "python",
      "args": ["-m", "src.mcp_server.mcp_app"],
      "cwd": "/absolute/path/to/data-catalog-assistant",
      "env": { "OPENAI_API_KEY": "sk-..." }
    }
  }
}
```

> The REST API (`src/main.py`, port 3000) and the MCP server (`mcp_app`) wrap the
> same underlying tool handlers — REST is convenient for HTTP/demos, MCP is the
> protocol-compliant interface for agents.

## Configuration Details

### Data Warehouse Setup

#### PostgreSQL
```yaml
datawarehouse:
  type: postgresql
  connection:
    host: localhost
    port: 5432
    database: your_database
    user: postgres
```

### ChromaDB (vector store)

```yaml
vector_store:
  type: chroma
  backend:
    persist_directory: chroma_data
  collection_name: bdw_rag_collection
  embedding_dimension: 384
```

Data is stored locally under `persist_directory`. No separate Chroma server is required.

### LLM Configuration

Generate SQL supports **OpenAI** and **local Ollama** (OpenAI-compatible `/v1`). The Gradio UI can switch per request; REST/MCP accept optional `provider` / `model` (omit to use config defaults).

#### OpenAI (default)
```yaml
llm:
  provider: openai
  model: gpt-4
  api_key: ${OPENAI_API_KEY}
  temperature: 0.7
  timeout_seconds: 60
```

#### Local Ollama
```yaml
llm:
  provider: openai   # default for APIs when UI does not override
  local:
    enabled: true
    base_url: ${OLLAMA_BASE_URL}  # e.g. http://192.168.4.52:11434/v1
    api_key: ollama
    model: ${OLLAMA_MODEL}        # e.g. qwen3:8b
    timeout_seconds: 300
```

In `.env`:
```bash
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://192.168.4.52:11434/v1
OLLAMA_MODEL=qwen3:8b
```

Confirm models on the Ollama host: `curl http://HOST:11434/api/tags`

REST example (local override):
```bash
curl -X POST http://localhost:3000/tools/generate_query \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"top 5 customers by order count\",\"provider\":\"ollama\"}"
```
## First Run Checklist

- [ ] Virtual environment created and activated
- [ ] Dependencies installed (pip install -r requirements.txt)
- [ ] .env file configured with API keys
- [ ] config.yaml updated with your DW credentials
- [ ] Metadata database initialized (if using external DB)
- [ ] Test connection to data warehouse
- [ ] Vector store initialized

## Testing Setup

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src

# Run specific test file
pytest tests/test_rag_engine.py
```

## Troubleshooting

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### API Connection Issues
- Verify API keys in .env
- Check network connectivity
- Review API rate limits
- Check API key permissions

### ChromaDB Issues
- Confirm `persist_directory` exists and is writable
- Run `python batch_jobs/run_refresh_job.py` to populate the index
- Reinstall if needed: `pip install chromadb`

### Data Warehouse Connection Issues
- Test DW credentials separately
- Verify network access to DW
- Check DW user permissions
- Review firewall rules

## Docker Deployment (Optional)

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
```

Build and run:
```bash
docker build -t data-catalog-assistant .
docker run -e OPENAI_API_KEY=sk-... -p 3000:3000 -p 7860:7860 data-catalog-assistant
```

## Next Steps

1. Review ARCHITECTURE.md for system design
2. Configure your data sources
3. Run initial vector DB refresh
4. Access Gradio UI at http://localhost:7860
5. Test MCP server integration

## Support

- Check logs in logs/bdw_rag.log
- Review component-specific documentation
- Test with pytest
- Enable debug logging in config.yaml
