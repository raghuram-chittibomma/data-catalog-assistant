# Scripts Directory

Development and testing scripts for Data Catalog Assistant.

## Available Scripts

### test_dw_connection.py
Tests PostgreSQL data warehouse connection based on config.yaml.

**Usage:**
```bash
# Using default config and env files
python scripts/test_dw_connection.py

# With custom config file
python scripts/test_dw_connection.py --config path/to/config.yaml

# With custom env file
python scripts/test_dw_connection.py --env path/to/.env
```

**Requirements:**
- PostgreSQL credentials in `.env` file
  - `DW_USER` - Database username
  - `DW_PASSWORD` - Database password
- config.yaml with PostgreSQL connection details

**What it tests:**
1. Configuration loading
2. Environment variable resolution
3. Database connection
4. Database version and info
5. Schema access
6. Table enumeration

**Example Output:**
```
============================================================
PostgreSQL Data Warehouse Connection Test
============================================================
✓ Configuration loaded from config/config.yaml
✓ Data warehouse type: postgresql

Connection Parameters:
  Host: (from ${DW_HOST} in .env)
  Port: 5432
  Database: northwind
  User: postgres
  Password: ****

Attempting connection...
✓ Connection successful!

✓ PostgreSQL Version: PostgreSQL 13.10 on x86_64-pc-linux-gnu
✓ Current Database: northwind
✓ Current User: postgres
✓ Tables in public schema: 25
  Sample tables: customers, orders, order_details, products, suppliers

✓ Available schemas: public

✓ Connection closed
============================================================
✓ All tests passed!
============================================================
```

## Diagnostics

```bash
python scripts/check_chroma.py
```

Reports Chroma document count and a sample search. If `count=0`, run `python batch_jobs/run_refresh_job.py`.

## Setup

### 1. Install Required Packages
```bash
pip install psycopg2-binary pyyaml python-dotenv
```

### 2. Configure Environment
```bash
# Copy and edit .env with your credentials
cp .env.example .env
```

Edit `.env` with your PostgreSQL credentials:
```
DW_HOST=localhost
DW_USER=your_postgres_user
DW_PASSWORD=your_postgres_password
METADATA_DB_HOST=localhost
METADATA_DB_USER=postgres
METADATA_DB_PASSWORD=your_metadata_password
```

### 3. Configure Connection
Hosts come from `.env`; `config/config.yaml` uses placeholders:
```yaml
datawarehouse:
  type: postgresql
  connection:
    host: ${DW_HOST}
    port: 5432
    database: northwind
    user: ${DW_USER}
    password: ${DW_PASSWORD}
```

### 4. Run Test
```bash
python scripts/test_dw_connection.py
```

## Troubleshooting

### "Connection refused"
- Check if PostgreSQL is running
- Verify host and port in config.yaml
- Check firewall rules

### "Authentication failed"
- Verify username/password in .env
- Check that DW_USER and DW_PASSWORD are set
- Try connecting manually: `psql -h host -U user -d database`

### "Database does not exist"
- Verify database name in config.yaml
- Check that user has access to the database
- Create database if needed: `createdb -U user database_name`

### "Module 'psycopg2' not found"
```bash
pip install psycopg2-binary
```

## Future Scripts

Planned scripts for development and testing:
- `demo_chroma.py` - Demo ChromaDB add/search (see `scripts/demo_chroma.py`)
- `run_ingestion.py` - Run DW table ingestion only (no embeddings/Chroma)
- `test_llm_connection.py` - Test OpenAI/Anthropic API
- `test_full_pipeline.py` - End-to-end RAG pipeline test
- `init_metadata_db.py` - Initialize metadata database schema
