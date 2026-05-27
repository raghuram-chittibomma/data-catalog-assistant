import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_ingestion.ingestion_pipeline import IngestionPipeline
from src.data_ingestion.data_processor import DataProcessor


class DummyConnector:
    def __init__(self):
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True

    def get_tables(self):
        return ["public.customers", "public.orders"]

    def get_table_schema(self, table_name):
        if table_name == "public.customers":
            return {
                "table_schema": "public",
                "table_name": "customers",
                "columns": [
                    {"name": "id", "type": "integer", "nullable": False, "default": "nextval('customers_id_seq'::regclass)"},
                    {"name": "name", "type": "text", "nullable": True, "default": None}
                ]
            }
        return {
            "table_schema": "public",
            "table_name": "orders",
            "columns": [
                {"name": "order_id", "type": "integer", "nullable": False, "default": None},
                {"name": "customer_id", "type": "integer", "nullable": False, "default": None}
            ]
        }

    def get_table_description(self, table_name):
        return "Test description" if table_name == "public.customers" else "Order metadata"

    def fetch_tables_metadata(self):
        return [
            {
                "table_name": "public.customers",
                "schema": {
                    "table_schema": "public",
                    "table_name": "customers",
                    "columns": [
                        {"name": "id", "type": "integer", "nullable": False, "default": None},
                        {"name": "name", "type": "text", "nullable": True, "default": None},
                    ],
                    "primary_keys": ["id"],
                    "foreign_keys": [],
                },
                "description": "Test description",
                "metadata": {
                    "name": "public.customers",
                    "owner": "test-owner",
                    "asset_type": "table",
                    "lineage_edges": [],
                },
            },
            {
                "table_name": "public.orders",
                "schema": {
                    "table_schema": "public",
                    "table_name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "integer", "nullable": False, "default": None},
                        {"name": "customer_id", "type": "integer", "nullable": False, "default": None},
                    ],
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
                "description": "Order metadata",
                "metadata": {
                    "name": "public.orders",
                    "owner": "test-owner",
                    "asset_type": "table",
                    "lineage_edges": [
                        {
                            "source": "public.customers",
                            "target": "public.orders",
                            "relationship_type": "foreign_key",
                        }
                    ],
                },
            },
        ]


def test_ingestion_pipeline_creates_documents():
    connector = DummyConnector()
    pipeline = IngestionPipeline(
        config={"type": "postgresql", "connection": {}, "ingest": {"schemas": ["public"]}},
        connector=connector,
        processor=DataProcessor(),
    )
    documents = pipeline.run()

    assert connector.closed
    assert len(documents) == 2
    ids = {doc["id"] for doc in documents}
    assert "public.customers" in ids
    assert "public.orders" in ids
    customer_doc = next(doc for doc in documents if doc["id"] == "public.customers")
    orders_doc = next(doc for doc in documents if doc["id"] == "public.orders")
    assert "Primary keys: id" in customer_doc["text"]
    assert customer_doc["metadata"]["table_name"] == "customers"
    assert customer_doc["metadata"]["owner"] == "test-owner"
    assert len(customer_doc["metadata"]["columns"]) == 2
    assert "Foreign keys:" in orders_doc["text"]
    assert len(orders_doc["metadata"]["lineage_edges"]) == 1


def test_fetch_table_metadata_uses_bulk_path():
    connector = DummyConnector()
    pipeline = IngestionPipeline(
        config={"type": "postgresql", "connection": {}},
        connector=connector,
        processor=DataProcessor(),
    )
    rows = pipeline.fetch_table_metadata()
    assert rows[0]["schema"]["primary_keys"] == ["id"]
    assert rows[1]["schema"]["foreign_keys"][0]["source"] == "public.customers"
