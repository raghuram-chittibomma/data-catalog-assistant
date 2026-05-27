"""Tests for SQLParser."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_ingestion.sql_parser import SQLParser

FIXTURES = Path(__file__).parent / "fixtures" / "sql"


def test_extract_tables_qualified_join():
    sql = (FIXTURES / "customers_with_orders.sql").read_text(encoding="utf-8")
    parser = SQLParser(default_schema="public")
    tables = parser.extract_tables(sql)

    assert "public.customers" in tables
    assert "public.orders" in tables


def test_extract_tables_adds_default_schema():
    sql = (FIXTURES / "product_sales.sql").read_text(encoding="utf-8")
    parser = SQLParser(default_schema="public")
    tables = parser.extract_tables(sql)

    assert "public.products" in tables
    assert "public.order_details" in tables


def test_parse_query_includes_description_and_joins():
    sql = (FIXTURES / "customers_with_orders.sql").read_text(encoding="utf-8")
    parser = SQLParser(default_schema="public")
    result = parser.parse_query(sql)

    assert result["statement_type"] == "SELECT"
    assert "public.customers" in result["tables"]
    assert any("JOIN" in j.get("join_type", "") for j in result["joins"])
    assert "tables:" in result["transformation_description"].lower()
