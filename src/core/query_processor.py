"""
Query processor - converts natural language to SQL queries with RAG catalog context.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryProcessor:
    """
    Processes user queries and generates SQL using retrieved catalog context.
    """

    def __init__(self, llm_client=None, schema_context=None, rag_engine=None):
        """
        Initialize Query Processor.

        Args:
            llm_client: LLM client for query generation
            schema_context: Config: rag_top_k, max_context_chars, allowed_tables
            rag_engine: RAGEngine for search + SQL generation
        """
        self.llm_client = llm_client
        self.schema_context = schema_context or {}
        self.rag_engine = rag_engine
        self.rag_top_k = int(self.schema_context.get("rag_top_k", 5))
        self.max_context_chars = int(self.schema_context.get("max_context_chars", 3500))
        logger.info("Query Processor initialized")

    @staticmethod
    def normalize_llm_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Map RAGEngine.generate_query keys to MCP tool response shape."""
        sql = result.get("sql") or result.get("query") or ""
        return {
            "sql": sql,
            "confidence": result.get("confidence", 0.0),
            "explanation": result.get("explanation", ""),
            "tables_used": result.get("tables_used", []),
        }

    def build_catalog_context(self, natural_language: str) -> Tuple[str, List[str]]:
        """
        Retrieve relevant catalog snippets for the user question.

        Returns:
            (context_text, tables_used asset ids)
        """
        if not self.rag_engine:
            return "", []

        hits = self.rag_engine.search_data_lineage(natural_language, top_k=self.rag_top_k)
        if not hits:
            logger.info("No catalog hits for query — generating SQL without RAG context")
            return "", []

        blocks: List[str] = []
        tables_used: List[str] = []
        total_len = 0

        for i, hit in enumerate(hits, 1):
            asset_id = hit.data_asset or ""
            meta = hit.metadata or {}
            asset_type = meta.get("asset_type", "asset")
            if asset_type == "table" and asset_id:
                tables_used.append(asset_id)

            snippet = (hit.description or "").strip()
            if len(snippet) > 900:
                snippet = snippet[:900] + "..."

            block = f"--- Catalog asset {i}: {asset_id} ({asset_type}) ---\n{snippet}"
            if total_len + len(block) > self.max_context_chars:
                logger.debug("Truncating RAG context at %s chars", self.max_context_chars)
                break
            blocks.append(block)
            total_len += len(block)

        context = "\n\n".join(blocks)
        unique_tables = list(dict.fromkeys(tables_used))
        logger.info(
            "RAG context: %s hit(s), %s table(s), %s chars",
            len(hits),
            len(unique_tables),
            len(context),
        )
        return context, unique_tables

    def process(self, natural_language: str) -> Dict[str, Any]:
        """
        Convert natural language to SQL query with RAG-augmented prompt.

        Args:
            natural_language: User's English description

        Returns:
            Dict with 'sql', 'confidence', 'explanation', 'tables_used'
        """
        logger.debug("Processing query: %s", natural_language)
        if not self.rag_engine:
            return {}

        catalog_context, tables_used = self.build_catalog_context(natural_language)
        raw = self.rag_engine.generate_query(
            natural_language,
            catalog_context=catalog_context or None,
        )
        out = self.normalize_llm_result(raw)
        if tables_used:
            out["tables_used"] = tables_used
        return out

    def validate_query(self, sql: str) -> bool:
        """
        Validate SQL query syntax and safety.

        Args:
            sql: SQL query to validate

        Returns:
            True if valid, False otherwise
        """
        logger.debug("Validating query: %s...", sql[:50])
        try:
            from src.utils.sql_validator import validate_sql

            allowed = self.schema_context.get("allowed_tables")
            return validate_sql(sql, allowed_tables=allowed)[0]
        except Exception:
            return bool(sql and sql.strip())

    def get_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """Get metadata for a table from the metadata store."""
        logger.debug("Getting metadata for table: %s", table_name)
        if self.rag_engine and self.rag_engine.metadata_store:
            return self.rag_engine.metadata_store.get_asset_metadata(table_name) or {}
        return {}
