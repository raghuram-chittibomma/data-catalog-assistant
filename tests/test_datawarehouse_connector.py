import sys
import os
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.data_ingestion.datawarehouse_connector import PostgreSQLConnector


class DummyCursor:
    def __init__(self, rows):
        self._rows = rows
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class DummyConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_postgresql_connector_get_tables(monkeypatch):
    config = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "user",
        "password": "pass",
    }

    rows = [
        {"table_schema": "public", "table_name": "customers"},
        {"table_schema": "public", "table_name": "orders"},
    ]
    dummy_cursor = DummyCursor(rows)
    dummy_conn = DummyConnection(dummy_cursor)

    def fake_connect(**kwargs):
        assert kwargs["host"] == "localhost"
        return dummy_conn

    monkeypatch.setattr("src.data_ingestion.datawarehouse_connector.psycopg2.connect", fake_connect)

    connector = PostgreSQLConnector(config)
    connector.connect()

    tables = connector.get_tables()
    assert tables == ["public.customers", "public.orders"]
    assert "information_schema.tables" in dummy_cursor.query


def test_postgresql_connector_filters_schemas_and_excludes(monkeypatch):
    config = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "user",
        "password": "pass",
    }
    ingest = {"schemas": ["public"], "exclude_tables": ["public.orders"]}

    rows = [
        {"table_schema": "public", "table_name": "customers"},
        {"table_schema": "public", "table_name": "orders"},
    ]
    dummy_cursor = DummyCursor(rows)
    dummy_conn = DummyConnection(dummy_cursor)

    monkeypatch.setattr(
        "src.data_ingestion.datawarehouse_connector.psycopg2.connect",
        lambda **kwargs: dummy_conn,
    )

    connector = PostgreSQLConnector(config, ingest=ingest)
    connector.connect()

    tables = connector.get_tables()
    assert tables == ["public.customers"]
    assert "table_schema = ANY" in dummy_cursor.query
    assert dummy_cursor.params == [["public"]]


def test_postgresql_connector_close_clears_connection(monkeypatch):
    config = {"host": "localhost", "database": "test_db", "user": "u", "password": "p"}
    closed = {"called": False}

    class ClosableConnection:
        def cursor(self):
            return DummyCursor([])

        def close(self):
            closed["called"] = True

    monkeypatch.setattr(
        "src.data_ingestion.datawarehouse_connector.psycopg2.connect",
        lambda **kwargs: ClosableConnection(),
    )

    connector = PostgreSQLConnector(config)
    with connector:
        assert connector.connection is not None
    assert connector.connection is None
    assert closed["called"]


def test_postgresql_connector_schema_and_description(monkeypatch):
    config = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "user",
        "password": "pass",
    }

    schema_rows = [
        {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": "nextval('customers_id_seq'::regclass)"},
        {"column_name": "name", "data_type": "text", "is_nullable": "YES", "column_default": None},
    ]
    description_row = [{"description": "Customer table"}]

    class MultiResultCursor(DummyCursor):
        def __init__(self):
            super().__init__(schema_rows)
            self._calls = 0

        def execute(self, query, params=None):
            self._calls += 1
            if self._calls == 1:
                self._rows = schema_rows
            else:
                self._rows = description_row
            super().execute(query, params)

    dummy_cursor = MultiResultCursor()
    dummy_conn = DummyConnection(dummy_cursor)

    monkeypatch.setattr("src.data_ingestion.datawarehouse_connector.psycopg2.connect", lambda **kwargs: dummy_conn)

    connector = PostgreSQLConnector(config)
    connector.connect()

    schema = connector.get_table_schema("public.customers")
    assert schema["table_schema"] == "public"
    assert schema["table_name"] == "customers"
    assert len(schema["columns"]) == 2
    assert schema["columns"][0]["name"] == "id"
    assert not schema["columns"][1]["nullable"] is False

    description = connector.get_table_description("public.customers")
    assert description == "Customer table"
