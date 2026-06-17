"""Tests for ETLParser."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_ingestion.etl_parser import ETLParser

FIXTURES = Path(__file__).parent / "fixtures" / "etl"


def test_parse_yaml_etl_job():
    parser = ETLParser(default_schema="public")
    jobs = parser.parse_etl_config(FIXTURES / "refresh_customer_dim.yaml")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["name"] == "refresh_customer_dim"
    assert "public.customers" in job["sources"]
    assert "public.customer_dim" in job["targets"]


def test_parse_json_multiple_jobs():
    parser = ETLParser(default_schema="public")
    jobs = parser.parse_etl_config(FIXTURES / "etl_jobs.json")

    assert len(jobs) == 1
    job = jobs[0]
    assert job["name"] == "sync_order_details"
    assert "public.orders" in job["sources"]
    assert "public.order_details" in job["sources"]
    assert "public.order_details_fact" in job["targets"]


def test_extract_lineage_edges():
    parser = ETLParser(default_schema="public")
    job = {
        "name": "load_orders_summary",
        "sources": ["public.customers"],
        "targets": ["public.orders_summary"],
        "dependencies": ["etl:refresh_customer_dim"],
    }
    lineage = parser.extract_lineage(
        job, "etl:etl_samples/load_orders_summary.yaml#load_orders_summary"
    )

    types = {edge["relationship_type"] for edge in lineage["edges"]}
    assert "etl_source" in types
    assert "etl_target" in types
    assert "etl_depends_on" in types
