"""Verify sql_samples/ and etl_samples/ load and parse for refresh."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_ingestion.ingestion_pipeline import IngestionPipeline

ROOT = Path(__file__).resolve().parents[1]


class DummyConnector:
    def connect(self):
        pass

    def close(self):
        pass

    def fetch_tables_metadata(self):
        return []


def _pipeline():
    return IngestionPipeline(
        config={
            "type": "postgresql",
            "connection": {},
            "ingest": {
                "sql_paths": ["sql_samples"],
                "etl_paths": ["etl_samples"],
                "default_schema": "public",
            },
        },
        connector=DummyConnector(),
    )


def test_sql_samples_load_all_files():
    sql_files = _pipeline().fetch_sql_files()
    assert len(sql_files) == 5
    sources = {item["source"] for item in sql_files}
    assert any("product_revenue_by_category.sql" in s for s in sources)
    assert any("employee_sales_totals.sql" in s for s in sources)
    for item in sql_files:
        tables = item["parse_result"]["tables"]
        assert tables, f"no tables parsed for {item['source']}"


def test_etl_samples_load_all_jobs():
    etl_items = _pipeline().fetch_etl_configs()
    assert len(etl_items) == 4
    names = {item["etl_config"]["name"] for item in etl_items}
    assert names == {
        "load_orders_summary",
        "load_order_line_facts",
        "load_product_sales_fact",
        "refresh_employee_dim",
    }


def test_product_revenue_sql_tables():
    sql_path = ROOT / "sql_samples" / "product_revenue_by_category.sql"
    pipeline = _pipeline()
    sql_files = pipeline.fetch_sql_files()
    match = next(f for f in sql_files if "product_revenue_by_category" in f["source"])
    tables = set(match["parse_result"]["tables"])
    assert "public.categories" in tables
    assert "public.products" in tables
    assert "public.order_details" in tables
