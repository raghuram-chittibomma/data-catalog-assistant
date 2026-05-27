# Data Catalog Assistant — API Reference

## MCP Tools

### Search Tools

#### search_data_assets
Search for data assets by description or keywords.

```
Parameters:
  - query (string): Search query describing what you're looking for
  - top_k (integer): Number of results to return (default: 5)

Returns:
  {
    "results": [
      {
        "asset_id": "customer_fact",
        "name": "Customer Fact Table",
        "type": "table",
        "description": "...",
        "relevance_score": 0.95,
        "metadata": {...}
      }
    ],
    "total": 42
  }
```

#### search_by_table
Get all information related to a specific table.

```
Parameters:
  - table_name (string): Name of the table

Returns:
  {
    "metadata": {
      "columns": [...],
      "description": "...",
      "owner": "...",
      "last_updated": "..."
    },
    "related_queries": [...],
    "usage": {...}
  }
```

#### search_by_owner
Find all data assets owned by a specific person or team.

```
Parameters:
  - owner (string): Owner name or email

Returns:
  {
    "assets": [...],
    "total": 15
  }
```

### Query Tools

#### generate_query
Generate SQL query from natural language description.

```
Parameters:
  - description (string): What data do you want to retrieve?

Returns:
  {
    "sql": "SELECT * FROM customer_fact WHERE created_date > '2024-01-01'",
    "confidence": 0.92,
    "explanation": "This query retrieves all customers created after January 1, 2024",
    "tables_used": ["customer_fact"]
  }
```

#### validate_query
Validate SQL query for syntax and safety.

```
Parameters:
  - sql (string): SQL query to validate

Returns:
  {
    "valid": true,
    "errors": [],
    "warnings": []
  }
```

#### explain_query
Explain what a SQL query does in plain English.

```
Parameters:
  - sql (string): SQL query to explain

Returns:
  {
    "explanation": "This query joins the customer and order tables to find customers who placed orders in the last 30 days, counting their total orders."
  }
```

### Impact Tools

#### analyze_data_usage
Analyze where a data asset is used and its impact.

```
Parameters:
  - data_asset (string): Name of data asset

Returns:
  {
    "asset": "customer_dim",
    "reports": ["Sales Dashboard", "Customer Analytics"],
    "queries": [
      {"name": "daily_sales_extract", "frequency": "daily"},
      ...
    ],
    "downstream_tables": ["customer_agg"],
    "impact_score": 0.87
  }
```

#### get_lineage
Get lineage for a data asset.

```
Parameters:
  - data_asset (string): Name of data asset
  - direction (string): "upstream", "downstream", or "both" (default: "both")

Returns:
  {
    "asset": "sales_fact",
    "upstream": [
      {
        "asset": "customer_dim",
        "type": "table",
        "relationship": "referenced_by"
      }
    ],
    "downstream": [
      {
        "asset": "sales_summary",
        "type": "table",
        "relationship": "feeds_into"
      }
    ]
  }
```

#### assess_change_impact
Assess impact of a change to a data asset.

```
Parameters:
  - data_asset (string): Name of data asset
  - change_description (string): Description of the change

Returns:
  {
    "asset": "customer_fact",
    "change": "Adding new column 'customer_lifetime_value'",
    "affected_reports": ["Revenue Dashboard", "Customer Value Report"],
    "affected_queries": ["daily_revenue_calc"],
    "risk_level": "low"
  }
```

## RAG Engine API

### Direct Python API

```python
from src.core.rag_engine import RAGEngine

# Initialize
rag = RAGEngine(vector_store=vs, llm_client=llm, config=config)

# Search lineage
results = rag.search_data_lineage("where is customer data used?", top_k=5)

# Generate query
result = rag.generate_query("get sales by region for 2024")

# Analyze impact
impact = rag.analyze_impact("customer_dim")

# Get lineage
lineage = rag.get_data_lineage("sales_fact")
```

## Configuration API

### Config YAML Structure

```yaml
# Data warehouse
datawarehouse:
  type: postgresql
  connection: {...}

# Vector store
vector_store:
  type: chroma
  backend: {...}

# Embeddings
embeddings:
  provider: local
  model_name: all-MiniLM-L6-v2
  model: model_name

# LLM
llm:
  provider: openai|anthropic
  model: model_name

# Metadata store
metadata_store:
  type: postgres|mongodb
  connection: {...}

# Services
mcp_server:
  enabled: true
  host: localhost
  port: 3000

ui:
  enabled: true
  host: 127.0.0.1
  port: 7860

batch_jobs:
  vector_db_refresh:
    enabled: true
    schedule: "02:00"
```

## Error Responses

### Common Errors

```json
{
  "error": "invalid_query",
  "message": "SQL query contains dangerous operations",
  "code": 400
}
```

```json
{
  "error": "not_found",
  "message": "Data asset 'unknown_table' not found",
  "code": 404
}
```

```json
{
  "error": "service_unavailable",
  "message": "Vector store is currently unavailable",
  "code": 503
}
```

## Rate Limiting

- API calls: 100 requests per minute
- Batch operations: 10 per hour
- LLM calls: Subject to provider limits

## Authentication

If enabled in config:

```bash
# Add authorization header
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3000/api/search
```

## Response Format

All responses follow this format:

```json
{
  "status": "success|error",
  "data": {...},
  "error": null,
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123"
}
```

## Pagination

Supported by search tools:

```python
# Get next page
results = rag.search_data_lineage(query, top_k=5, offset=5)
```

---

For more details, see individual module documentation.
