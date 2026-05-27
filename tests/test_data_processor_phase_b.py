"""Tests for Phase B data processor enrichment."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_ingestion.data_processor import DataProcessor


def test_process_table_metadata_includes_keys_and_catalog_fields():
    processor = DataProcessor(default_owner="analytics-team")
    table_info = {
        "description": "Customer master",
        "schema": {
            "table_schema": "public",
            "table_name": "customers",
            "columns": [{"name": "id", "type": "integer", "nullable": False, "default": None}],
            "primary_keys": ["id"],
            "foreign_keys": [],
        },
        "metadata": {"name": "public.customers", "owner": "analytics-team", "lineage_edges": []},
    }

    doc = processor.process_table_metadata(table_info)

    assert doc["id"] == "public.customers"
    assert "Primary keys: id" in doc["text"]
    assert doc["metadata"]["name"] == "public.customers"
    assert doc["metadata"]["owner"] == "analytics-team"
    assert doc["metadata"]["primary_keys"] == ["id"]


def test_process_table_metadata_includes_foreign_keys_in_text():
    processor = DataProcessor()
    table_info = {
        "description": "",
        "schema": {
            "table_schema": "public",
            "table_name": "orders",
            "columns": [{"name": "customer_id", "type": "integer", "nullable": False, "default": None}],
            "primary_keys": ["order_id"],
            "foreign_keys": [
                {
                    "column": "customer_id",
                    "references": "public.customers",
                    "foreign_column": "id",
                    "source": "public.customers",
                    "target": "public.orders",
                    "relationship_type": "foreign_key",
                }
            ],
        },
        "metadata": {
            "lineage_edges": [
                {
                    "source": "public.customers",
                    "target": "public.orders",
                    "relationship_type": "foreign_key",
                }
            ]
        },
    }

    doc = processor.process_table_metadata(table_info)

    assert "Foreign keys:" in doc["text"]
    assert "customer_id -> public.customers.id" in doc["text"]
    assert len(doc["metadata"]["lineage_edges"]) == 1
