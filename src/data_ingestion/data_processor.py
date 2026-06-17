"""
Data processor - processes ingested data for vector store.
"""

import logging
from typing import Any

from src.data_ingestion.etl_parser import ETLParser
from src.data_ingestion.sql_parser import SQLParser

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Processes data from DW, SQL files, ETL configs for vector embedding.
    """

    def __init__(
        self,
        embedding_service=None,
        default_owner: str = "unknown",
        default_schema: str = "public",
        sql_parser: SQLParser | None = None,
        etl_parser: ETLParser | None = None,
    ):
        """
        Initialize Data Processor.

        Args:
            embedding_service: EmbeddingService instance
            default_owner: Default owner for catalog assets
            default_schema: Schema prefix for unqualified table names in SQL/ETL
            sql_parser: Optional SQLParser instance
            etl_parser: Optional ETLParser instance
        """
        self.embedding_service = embedding_service
        self.default_owner = default_owner
        self.default_schema = default_schema
        self.sql_parser = sql_parser or SQLParser(default_schema=default_schema)
        self.etl_parser = etl_parser or ETLParser(default_schema=default_schema)
        logger.info("Initialized Data Processor")

    def process_table_metadata(self, table_info: dict[str, Any]) -> dict[str, Any]:
        """
        Process table metadata for embedding.

        Args:
            table_info: Table schema and metadata

        Returns:
            Processed data ready for embedding
        """
        table_schema = table_info.get("schema", {})
        table_name = table_schema.get("table_name") or table_info.get("table_name")
        table_namespace = table_schema.get("table_schema") or "public"
        meta = table_info.get("metadata", {})
        description = table_info.get("description") or meta.get("description", "")
        columns = table_schema.get("columns", [])
        primary_keys = table_schema.get("primary_keys", meta.get("primary_keys", []))
        foreign_keys = table_schema.get("foreign_keys", meta.get("foreign_keys", []))
        display_name = meta.get("name") or f"{table_namespace}.{table_name}"
        owner = meta.get("owner") or self.default_owner
        lineage_edges = meta.get("lineage_edges", [])

        logger.debug(f"Processing table: {table_namespace}.{table_name}")

        column_lines = []
        for col in columns:
            column_lines.append(
                f"{col.get('name')} ({col.get('type')}){' nullable' if col.get('nullable') else ''}"
                + (f" default={col.get('default')}" if col.get("default") else "")
            )

        text_parts = [f"Table {table_namespace}.{table_name}: {description or 'No description'}."]
        if primary_keys:
            text_parts.append(f"Primary keys: {', '.join(primary_keys)}.")
        if foreign_keys:
            fk_lines = [
                f"{fk.get('column')} -> {fk.get('references')}.{fk.get('foreign_column')}"
                for fk in foreign_keys
            ]
            text_parts.append(f"Foreign keys: {'; '.join(fk_lines)}.")
        if columns:
            text_parts.append(f"Columns: {', '.join(col.get('name') for col in columns)}.")
            text_parts.append(f"Details: {'; '.join(column_lines)}.")
        text = " ".join(text_parts).strip()

        return {
            "id": f"{table_namespace}.{table_name}",
            "text": text,
            "metadata": {
                "asset_type": "table",
                "name": display_name,
                "owner": owner,
                "table_schema": table_namespace,
                "table_name": table_name,
                "description": description,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "lineage_edges": lineage_edges,
                **{
                    k: v
                    for k, v in meta.items()
                    if k
                    not in (
                        "asset_type",
                        "name",
                        "owner",
                        "table_schema",
                        "table_name",
                        "description",
                        "columns",
                        "primary_keys",
                        "foreign_keys",
                        "lineage_edges",
                    )
                },
            },
        }

    def process_sql_content(
        self,
        sql: str,
        source: str,
        parse_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process SQL content for embedding.

        Args:
            sql: SQL query
            source: Source path or report name
            parse_result: Optional pre-parsed SQL metadata

        Returns:
            Processed data ready for embedding
        """
        logger.debug("Processing SQL from: %s", source)
        parsed = parse_result or self.sql_parser.parse_query(sql)
        tables = parsed.get("tables", [])
        description = parsed.get(
            "transformation_description"
        ) or self.sql_parser.generate_description(sql, tables=tables)

        safe_source = source.replace("\\", "/")
        doc_id = f"sql:{safe_source}"

        lineage_edges = [
            {
                "source": table,
                "target": doc_id,
                "relationship_type": "sql_reference",
            }
            for table in tables
        ]

        text_parts = [
            f"SQL asset {safe_source}: {description}.",
            f"Statement type: {parsed.get('statement_type', 'QUERY')}.",
        ]
        if tables:
            text_parts.append(f"Tables: {', '.join(tables)}.")
        if parsed.get("joins"):
            join_bits = [f"{j.get('join_type')} {j.get('table')}" for j in parsed["joins"]]
            text_parts.append(f"Joins: {'; '.join(join_bits)}.")
        text_parts.append(f"SQL: {sql.strip()[:2000]}")

        return {
            "id": doc_id,
            "text": " ".join(text_parts).strip(),
            "metadata": {
                "asset_type": "sql",
                "name": safe_source,
                "owner": self.default_owner,
                "source": safe_source,
                "description": description,
                "tables": tables,
                "joins": parsed.get("joins", []),
                "sql": sql.strip(),
                "lineage_edges": lineage_edges,
            },
        }

    def batch_process_sql_files(self, sql_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process SQL file payloads into embedding documents."""
        results = []
        for item in sql_files:
            try:
                doc = self.process_sql_content(
                    sql=item.get("sql", ""),
                    source=item.get("source", "unknown.sql"),
                    parse_result=item.get("parse_result"),
                )
                if doc:
                    results.append(doc)
            except Exception as e:
                logger.error("Failed to process SQL file %s: %s", item.get("source"), e)
        return results

    def process_etl_definition(
        self,
        etl_config: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        """
        Process ETL definition for embedding.

        Args:
            etl_config: Parsed ETL configuration
            source: Config file path for stable document id

        Returns:
            Processed data ready for embedding
        """
        name = etl_config.get("name", "unknown_etl")
        config_path = source or etl_config.get("config_path", name)
        safe_source = str(config_path).replace("\\", "/")
        doc_id = f"etl:{safe_source}#{name}"

        description = self.etl_parser.generate_documentation(etl_config)
        lineage_info = self.etl_parser.extract_lineage(etl_config, doc_id)
        lineage_edges = lineage_info.get("edges", [])
        owner = etl_config.get("owner") or self.default_owner

        text_parts = [
            f"ETL asset {name} ({safe_source}): {description}",
        ]
        if etl_config.get("dependencies"):
            text_parts.append(
                f"Dependencies: {', '.join(str(d) for d in etl_config['dependencies'])}."
            )

        return {
            "id": doc_id,
            "text": " ".join(text_parts).strip(),
            "metadata": {
                "asset_type": "etl",
                "name": name,
                "owner": owner,
                "source": safe_source,
                "description": etl_config.get("description", description),
                "sources": etl_config.get("sources", []),
                "targets": etl_config.get("targets", []),
                "transformations": etl_config.get("transformations", []),
                "schedule": etl_config.get("schedule", ""),
                "dependencies": etl_config.get("dependencies", []),
                "lineage_edges": lineage_edges,
            },
        }

    def batch_process_etl_configs(self, etl_configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process parsed ETL job definitions into embedding documents."""
        results = []
        for item in etl_configs:
            try:
                doc = self.process_etl_definition(
                    etl_config=item.get("etl_config", {}),
                    source=item.get("source"),
                )
                if doc:
                    results.append(doc)
            except Exception as e:
                logger.error("Failed to process ETL %s: %s", item.get("source"), e)
        return results

    def batch_process_tables(self, table_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Batch process multiple tables.

        Args:
            table_list: List of table metadata

        Returns:
            List of processed documents
        """
        logger.debug(f"Batch processing {len(table_list)} tables")
        results = []
        for table_info in table_list:
            try:
                doc = self.process_table_metadata(table_info)
                if doc:
                    results.append(doc)
            except Exception as e:
                logger.error(f"Failed to process table metadata: {e}")
        return results
