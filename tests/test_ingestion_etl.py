"""Tests for ETL ingestion in IngestionPipeline."""

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


def test_fetch_etl_configs_loads_fixtures():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {"etl_paths": ["tests/fixtures/etl"], "default_schema": "public"},
        },
        connector=DummyConnector(),
    )
    etl_items = pipeline.fetch_etl_configs()

    assert len(etl_items) == 2
    names = {item["etl_config"]["name"] for item in etl_items}
    assert "refresh_customer_dim" in names
    assert "sync_order_details" in names


def test_build_documents_includes_etl_lineage():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {"etl_paths": ["tests/fixtures/etl"], "default_schema": "public"},
        },
        connector=DummyConnector(),
        processor=DataProcessor(default_schema="public"),
    )
    etl_items = pipeline.fetch_etl_configs()
    docs = pipeline.build_documents([], etl_configs=etl_items)

    assert len(docs) == 2
    etl_doc = next(d for d in docs if d["metadata"]["asset_type"] == "etl")
    assert etl_doc["id"].startswith("etl:")
    assert etl_doc["metadata"]["sources"]
    assert etl_doc["metadata"]["targets"]
    assert any(e["relationship_type"] == "etl_source" for e in etl_doc["metadata"]["lineage_edges"])


def test_run_reports_etl_count():
    pipeline = IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {
                "etl_paths": ["tests/fixtures/etl"],
                "sql_paths": ["tests/fixtures/sql"],
                "default_schema": "public",
            },
        },
        connector=DummyConnector(),
    )
    docs = pipeline.run()

    etl_count = sum(1 for d in docs if d["metadata"]["asset_type"] == "etl")
    sql_count = sum(1 for d in docs if d["metadata"]["asset_type"] == "sql")
    assert etl_count == 2
    assert sql_count == 2
