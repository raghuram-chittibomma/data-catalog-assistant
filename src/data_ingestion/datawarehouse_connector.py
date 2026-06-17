"""
Datawarehouse connector - connects to DW and extracts metadata.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class DataWarehouseConnector(ABC):
    """Abstract base class for DW connectors."""

    @abstractmethod
    def connect(self):
        """Connect to data warehouse."""
        pass

    @abstractmethod
    def get_tables(self) -> list[str]:
        """Get list of all tables."""
        pass

    @abstractmethod
    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get schema for a table."""
        pass

    @abstractmethod
    def get_table_description(self, table_name: str) -> str | None:
        """Get description/comments for a table."""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a query against the DW."""
        pass


class PostgreSQLConnector(DataWarehouseConnector):
    """PostgreSQL data warehouse connector."""

    def __init__(self, config: dict[str, Any], ingest: dict[str, Any] | None = None):
        """
        Initialize PostgreSQL connector.

        Args:
            config: PostgreSQL connection config (host, port, database, user, password)
            ingest: Optional ingest filters (schemas, exclude_tables)
        """
        self.config = config
        self.ingest = ingest or {}
        self.connection = None
        logger.info("Initialized PostgreSQL Connector")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self) -> None:
        """Close the database connection."""
        if self.connection is not None:
            try:
                self.connection.close()
                logger.debug("Closed PostgreSQL connection")
            except Exception as e:
                logger.warning(f"Error closing PostgreSQL connection: {e}")
            finally:
                self.connection = None

    def connect(self):
        """Connect to PostgreSQL."""
        if not self.config:
            raise ValueError("PostgreSQL configuration is required")

        conn_args = {
            "host": self.config.get("host", "localhost"),
            "port": int(self.config.get("port", 5432)),
            "dbname": self.config.get("database"),
            "user": self.config.get("user"),
            "password": self.config.get("password"),
            "sslmode": self.config.get("sslmode", "prefer"),
        }
        conn_args = {k: v for k, v in conn_args.items() if v is not None}

        try:
            self.connection = psycopg2.connect(cursor_factory=RealDictCursor, **conn_args)
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def _ensure_connection(self):
        if not self.connection:
            self.connect()

    def get_tables(self) -> list[str]:
        """Get tables from PostgreSQL, honoring ingest.schemas and ingest.exclude_tables."""
        logger.debug("Fetching tables from PostgreSQL")
        self._ensure_connection()

        schemas = self.ingest.get("schemas") or []
        exclude_tables = set(self.ingest.get("exclude_tables") or [])

        query = """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
        """
        params: list[Any] = []
        if schemas:
            query += " AND table_schema = ANY(%s)"
            params.append(list(schemas))
        query += " ORDER BY table_schema, table_name"

        with self.connection.cursor() as cursor:
            cursor.execute(query, params or None)
            rows = cursor.fetchall()

        tables = [f"{row['table_schema']}.{row['table_name']}" for row in rows]
        if exclude_tables:
            tables = [name for name in tables if name not in exclude_tables]
        logger.debug("Found %s tables after ingest filters", len(tables))
        return tables

    def _ingest_schemas(self) -> list[str]:
        return list(self.ingest.get("schemas") or [])

    def fetch_tables_metadata(self) -> list[dict[str, Any]]:
        """
        Batch-fetch columns, descriptions, primary keys, and foreign keys for all
        tables returned by get_tables() (few queries instead of per-table N+1).
        """
        self._ensure_connection()
        tables = self.get_tables()
        if not tables:
            return []

        schemas = self._ingest_schemas()
        if not schemas:
            schemas = sorted({name.split(".", 1)[0] for name in tables if "." in name})

        schema_set = set(schemas)
        columns_by_table: dict[str, list[dict[str, Any]]] = {}
        descriptions: dict[str, str] = {}
        primary_keys: dict[str, list[str]] = {}
        foreign_keys: dict[str, list[dict[str, Any]]] = {}

        col_query = """
            SELECT table_schema, table_name, column_name, data_type,
                   is_nullable, column_default, ordinal_position
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        """
        col_params: list[Any] = []
        if schemas:
            col_query += " AND table_schema = ANY(%s)"
            col_params.append(schemas)
        col_query += " ORDER BY table_schema, table_name, ordinal_position"

        with self.connection.cursor() as cursor:
            cursor.execute(col_query, col_params or None)
            for row in cursor.fetchall():
                key = f"{row['table_schema']}.{row['table_name']}"
                if key not in tables:
                    continue
                columns_by_table.setdefault(key, []).append(
                    {
                        "name": row["column_name"],
                        "type": row["data_type"],
                        "nullable": row["is_nullable"] == "YES",
                        "default": row["column_default"],
                    }
                )

        desc_query = """
            SELECT n.nspname AS table_schema, c.relname AS table_name,
                   obj_description(c.oid, 'pg_class') AS description
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
        """
        desc_params: list[Any] = []
        if schemas:
            desc_query += " AND n.nspname = ANY(%s)"
            desc_params.append(schemas)

        with self.connection.cursor() as cursor:
            cursor.execute(desc_query, desc_params or None)
            for row in cursor.fetchall():
                key = f"{row['table_schema']}.{row['table_name']}"
                if key in tables and row.get("description"):
                    descriptions[key] = row["description"]

        pk_query = """
            SELECT tc.table_schema, tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        """
        pk_params: list[Any] = []
        if schemas:
            pk_query += " AND tc.table_schema = ANY(%s)"
            pk_params.append(schemas)
        pk_query += " ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position"

        with self.connection.cursor() as cursor:
            cursor.execute(pk_query, pk_params or None)
            for row in cursor.fetchall():
                key = f"{row['table_schema']}.{row['table_name']}"
                if key in tables:
                    primary_keys.setdefault(key, []).append(row["column_name"])

        fk_query = """
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
        """
        fk_params: list[Any] = []
        if schemas:
            fk_query += " AND tc.table_schema = ANY(%s)"
            fk_params.append(schemas)

        with self.connection.cursor() as cursor:
            cursor.execute(fk_query, fk_params or None)
            for row in cursor.fetchall():
                key = f"{row['table_schema']}.{row['table_name']}"
                if key not in tables:
                    continue
                ref = f"{row['foreign_table_schema']}.{row['foreign_table_name']}"
                foreign_keys.setdefault(key, []).append(
                    {
                        "column": row["column_name"],
                        "references": ref,
                        "foreign_column": row["foreign_column_name"],
                        "source": ref,
                        "target": key,
                        "relationship_type": "foreign_key",
                    }
                )

        default_owner = self.ingest.get("default_owner", "unknown")
        results: list[dict[str, Any]] = []

        for table_name in tables:
            if "." in table_name:
                schema_name, table = table_name.split(".", 1)
            else:
                schema_name, table = "public", table_name

            if schema_set and schema_name not in schema_set:
                continue

            schema = {
                "table_schema": schema_name,
                "table_name": table,
                "columns": columns_by_table.get(table_name, []),
                "primary_keys": primary_keys.get(table_name, []),
                "foreign_keys": foreign_keys.get(table_name, []),
            }
            description = descriptions.get(table_name, "")

            results.append(
                {
                    "table_name": table_name,
                    "schema": schema,
                    "description": description,
                    "metadata": {
                        "schema": schema_name,
                        "table": table,
                        "columns": schema["columns"],
                        "primary_keys": schema["primary_keys"],
                        "foreign_keys": schema["foreign_keys"],
                        "description": description,
                        "asset_type": "table",
                        "name": table_name,
                        "owner": default_owner,
                        "lineage_edges": [
                            {
                                "source": fk["source"],
                                "target": fk["target"],
                                "relationship_type": fk["relationship_type"],
                            }
                            for fk in schema["foreign_keys"]
                        ],
                    },
                }
            )

        logger.info("Batch-fetched metadata for %s tables", len(results))
        return results

    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get table schema from PostgreSQL."""
        logger.debug(f"Fetching schema for table: {table_name}")
        self._ensure_connection()

        if "." in table_name:
            schema, table = table_name.split(".", 1)
        else:
            schema, table = "public", table_name

        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query, (schema, table))
            columns = cursor.fetchall()

        return {
            "table_schema": schema,
            "table_name": table,
            "columns": [
                {
                    "name": col["column_name"],
                    "type": col["data_type"],
                    "nullable": col["is_nullable"] == "YES",
                    "default": col["column_default"],
                }
                for col in columns
            ],
        }

    def get_table_description(self, table_name: str) -> str | None:
        """Get table description from PostgreSQL."""
        logger.debug(f"Fetching description for table: {table_name}")
        self._ensure_connection()

        if "." in table_name:
            schema, table = table_name.split(".", 1)
        else:
            schema, table = "public", table_name

        query = """
            SELECT obj_description(c.oid, 'pg_class') AS description
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %s
              AND n.nspname = %s
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query, (table, schema))
            row = cursor.fetchone()

        return row["description"] if row else None

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute query on PostgreSQL."""
        logger.debug(f"Executing query: {query[:50]}...")
        self._ensure_connection()

        with self.connection.cursor() as cursor:
            cursor.execute(query)
            try:
                rows = cursor.fetchall()
            except psycopg2.ProgrammingError:
                # No results to fetch (e.g. DDL statement)
                self.connection.commit()
                return []

        return [dict(row) for row in rows]
