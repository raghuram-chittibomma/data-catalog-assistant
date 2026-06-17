"""Tests for SQL file ingestion in IngestionPipeline."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_ingestion.data_processor import DataProcessor
from src.data_ingestion.ingestion_pipeline import IngestionPipeline


class DummyConnector:
    def connect(self):
        pass

    def close(self):
        pass

    def fetch_tables_metadata(self):
        return []


def test_fetch_sql_files_loads_fixtures():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {
                "sql_paths": ["tests/fixtures/sql"],
                "default_schema": "public",
            },
        },
        connector=DummyConnector(),
    )
    sql_files = pipeline.fetch_sql_files()

    assert len(sql_files) == 2
    sources = {item["source"] for item in sql_files}
    assert any("customers_with_orders.sql" in s for s in sources)
    assert all(item.get("parse_result", {}).get("tables") for item in sql_files)


def test_build_documents_includes_sql_assets():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {"sql_paths": ["tests/fixtures/sql"], "default_schema": "public"},
        },
        connector=DummyConnector(),
        processor=DataProcessor(default_schema="public"),
    )
    sql_files = pipeline.fetch_sql_files()
    docs = pipeline.build_documents([], sql_files=sql_files)

    assert len(docs) == 2
    sql_doc = next(d for d in docs if d["metadata"]["asset_type"] == "sql")
    assert sql_doc["id"].startswith("sql:")
    assert "public.customers" in sql_doc["metadata"]["tables"]
    assert sql_doc["metadata"]["lineage_edges"]
    assert sql_doc["metadata"]["lineage_edges"][0]["relationship_type"] == "sql_reference"


def test_run_combines_tables_and_sql():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {"sql_paths": ["tests/fixtures/sql"], "default_schema": "public"},
        },
        connector=DummyConnector(),
    )
    docs = pipeline.run()

    assert len(docs) == 2
    assert all(doc["metadata"]["asset_type"] == "sql" for doc in docs)
