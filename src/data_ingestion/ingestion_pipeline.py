"""Ingestion pipeline - orchestrates DW extraction, parsing, and document creation."""

import logging
from pathlib import Path
from typing import Dict, List, Any

from src.data_ingestion.data_processor import DataProcessor
from src.data_ingestion.datawarehouse_connector import PostgreSQLConnector
from src.data_ingestion.etl_parser import ETLParser
from src.data_ingestion.sql_parser import SQLParser
from src.utils.config_loader import project_root

logger = logging.getLogger(__name__)

_ETL_SUFFIXES = {".yaml", ".yml", ".json"}


class IngestionPipeline:
    """Pipeline that turns DW metadata, SQL files, and ETL configs into embedding documents."""

    def __init__(self, config: Dict[str, Any] = None, connector=None, processor=None, embedding_service=None):
        self.config = config or {}
        self.connector = connector or self._build_connector()
        ingest = self.config.get("ingest", {}) if isinstance(self.config, dict) else {}
        default_schema = ingest.get("default_schema", "public")

        if processor:
            self.processor = processor
        else:
            self.processor = DataProcessor(
                embedding_service=embedding_service,
                default_owner=ingest.get("default_owner", "unknown"),
                default_schema=default_schema,
                sql_parser=SQLParser(default_schema=default_schema),
                etl_parser=ETLParser(default_schema=default_schema),
            )

        self._sql_parser = SQLParser(default_schema=default_schema)
        self._etl_parser = ETLParser(default_schema=default_schema)

    def _build_connector(self):
        if not isinstance(self.config, dict):
            raise ValueError("Data warehouse config must be a dictionary")

        connection = self.config.get("connection", {})
        ingest = self.config.get("ingest", {})
        backend = self.config.get("type", "postgresql").lower()

        if backend in ("postgres", "postgresql"):
            return PostgreSQLConnector(connection, ingest=ingest)

        raise ValueError(
            f"Unsupported data warehouse backend: {backend}. Use postgresql."
        )

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        rooted = project_root() / candidate
        if rooted.exists():
            return rooted
        return candidate

    def _relative_source(self, file_path: Path) -> str:
        try:
            rel_source = str(file_path.resolve().relative_to(project_root()))
        except ValueError:
            rel_source = str(file_path)
        return rel_source.replace("\\", "/")

    def fetch_sql_files(self) -> List[Dict[str, Any]]:
        """Load SQL files from configured paths and parse them."""
        ingest = self.config.get("ingest", {}) if isinstance(self.config, dict) else {}
        sql_paths = ingest.get("sql_paths") or []
        if not sql_paths:
            logger.debug("No sql_paths configured; skipping SQL file ingestion")
            return []

        sql_files: List[Dict[str, Any]] = []
        seen_paths = set()

        for configured_path in sql_paths:
            resolved = self._resolve_path(configured_path)
            if not resolved.exists():
                logger.warning("SQL path does not exist: %s", resolved)
                continue

            paths_to_read: List[Path] = []
            if resolved.is_file() and resolved.suffix.lower() == ".sql":
                paths_to_read = [resolved]
            elif resolved.is_dir():
                paths_to_read = sorted(resolved.rglob("*.sql"))
            else:
                logger.warning("Skipping non-SQL path: %s", resolved)
                continue

            for file_path in paths_to_read:
                key = str(file_path.resolve())
                if key in seen_paths:
                    continue
                seen_paths.add(key)

                try:
                    sql_text = file_path.read_text(encoding="utf-8").strip()
                except Exception as e:
                    logger.error("Failed to read SQL file %s: %s", file_path, e)
                    continue

                if not sql_text:
                    continue

                rel_source = self._relative_source(file_path)
                sql_files.append(
                    {
                        "sql": sql_text,
                        "source": rel_source,
                        "path": str(file_path),
                        "parse_result": self._sql_parser.parse_query(sql_text),
                    }
                )

        logger.info("Loaded %s SQL files from %s path(s)", len(sql_files), len(sql_paths))
        return sql_files

    def fetch_etl_configs(self) -> List[Dict[str, Any]]:
        """Load ETL YAML/JSON configs from configured paths."""
        ingest = self.config.get("ingest", {}) if isinstance(self.config, dict) else {}
        etl_paths = ingest.get("etl_paths") or []
        if not etl_paths:
            logger.debug("No etl_paths configured; skipping ETL ingestion")
            return []

        etl_items: List[Dict[str, Any]] = []
        seen_jobs = set()

        for configured_path in etl_paths:
            resolved = self._resolve_path(configured_path)
            if not resolved.exists():
                logger.warning("ETL path does not exist: %s", resolved)
                continue

            paths_to_read: List[Path] = []
            if resolved.is_file() and resolved.suffix.lower() in _ETL_SUFFIXES:
                paths_to_read = [resolved]
            elif resolved.is_dir():
                paths_to_read = sorted(
                    p for p in resolved.rglob("*") if p.suffix.lower() in _ETL_SUFFIXES
                )
            else:
                logger.warning("Skipping unsupported ETL path: %s", resolved)
                continue

            for file_path in paths_to_read:
                try:
                    jobs = self._etl_parser.parse_etl_config(file_path)
                except Exception as e:
                    logger.error("Failed to parse ETL config %s: %s", file_path, e)
                    continue

                rel_source = self._relative_source(file_path)
                for job in jobs:
                    job_key = (rel_source, job.get("name"))
                    if job_key in seen_jobs:
                        continue
                    seen_jobs.add(job_key)
                    etl_items.append(
                        {
                            "source": rel_source,
                            "path": str(file_path),
                            "etl_config": job,
                        }
                    )

        logger.info("Loaded %s ETL job(s) from %s path(s)", len(etl_items), len(etl_paths))
        return etl_items

    def fetch_table_metadata(self) -> List[Dict[str, Any]]:
        self.connector.connect()
        if hasattr(self.connector, "fetch_tables_metadata"):
            return self.connector.fetch_tables_metadata()

        tables = self.connector.get_tables()
        documents = []
        ingest = self.config.get("ingest", {}) if isinstance(self.config, dict) else {}
        default_owner = ingest.get("default_owner", "unknown")

        for table_name in tables:
            schema = self.connector.get_table_schema(table_name)
            description = self.connector.get_table_description(table_name) or ""
            metadata = {
                "schema": schema.get("table_schema"),
                "table": schema.get("table_name"),
                "columns": schema.get("columns", []),
                "description": description,
                "asset_type": "table",
                "name": table_name,
                "owner": default_owner,
            }
            documents.append({
                "table_name": table_name,
                "schema": schema,
                "description": description,
                "metadata": metadata,
            })

        return documents

    def build_documents(
        self,
        table_metadata: List[Dict[str, Any]],
        sql_files: List[Dict[str, Any]] = None,
        etl_configs: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        table_docs = self.processor.batch_process_tables(table_metadata)
        sql_docs = self.processor.batch_process_sql_files(sql_files or [])
        etl_docs = self.processor.batch_process_etl_configs(etl_configs or [])
        return table_docs + sql_docs + etl_docs

    def run(self) -> List[Dict[str, Any]]:
        """Fetch DW metadata, SQL files, and ETL configs; return embedding-ready documents."""
        logger.info("Running ingestion pipeline")
        try:
            table_metadata = self.fetch_table_metadata()
            sql_files = self.fetch_sql_files()
            etl_configs = self.fetch_etl_configs()
            documents = self.build_documents(
                table_metadata,
                sql_files=sql_files,
                etl_configs=etl_configs,
            )

            counts = {"table": 0, "sql": 0, "etl": 0}
            for doc in documents:
                asset_type = doc.get("metadata", {}).get("asset_type", "")
                if asset_type in counts:
                    counts[asset_type] += 1

            logger.info(
                "Ingestion pipeline produced %s documents (%s tables, %s sql, %s etl)",
                len(documents),
                counts["table"],
                counts["sql"],
                counts["etl"],
            )
            return documents
        finally:
            if hasattr(self.connector, "close"):
                self.connector.close()
