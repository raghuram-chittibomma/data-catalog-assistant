"""
Query tools - MCP tools for query generation.
"""

import logging
from typing import Dict, List, Any

from src.core.query_processor import QueryProcessor
from src.utils.sql_validator import validate_sql

logger = logging.getLogger(__name__)


class QueryTools:
    """
    Tools for generating SQL queries from natural language.
    """

    def __init__(self, query_processor=None, rag_engine=None):
        """
        Initialize Query Tools.

        Args:
            query_processor: QueryProcessor instance
            rag_engine: RAGEngine instance
        """
        self.query_processor = query_processor
        self.rag_engine = rag_engine
        logger.info("Initialized Query Tools")

    def generate_query(self, description: str) -> Dict[str, Any]:
        """
        Generate SQL query from natural language description.

        MCP Tool: generate_query
        Parameters:
            - description (string): What data do you want to get?

        Returns:
            Generated SQL, confidence score, and explanation
        """
        logger.debug(f"Generating query: {description}")
        if self.query_processor:
            generated = self.query_processor.process(description)
            if generated:
                return generated
        if self.rag_engine:
            return QueryProcessor.normalize_llm_result(
                self.rag_engine.generate_query(description)
            )

        return {
            "sql": "",
            "confidence": 0.0,
            "explanation": "No query processor available",
            "tables_used": []
        }

    def validate_query(self, sql: str) -> Dict[str, Any]:
        """
        Validate a SQL query.

        MCP Tool: validate_query
        Parameters:
            - sql (string): SQL query to validate

        Returns:
            Validation result with any errors/warnings
        """
        logger.debug(f"Validating query: {sql[:50]}...")
        if self.query_processor:
            validation = self.query_processor.validate_query(sql)
            if isinstance(validation, bool):
                return {
                    "valid": validation,
                    "errors": [] if validation else ["Query failed processor validation"],
                    "warnings": []
                }
            if isinstance(validation, dict):
                return validation

        valid, reason = validate_sql(sql)
        return {
            "valid": valid,
            "errors": [] if valid else [reason],
            "warnings": []
        }

    def explain_query(self, sql: str) -> Dict[str, Any]:
        """
        Explain what a SQL query does in plain English.

        MCP Tool: explain_query
        Parameters:
            - sql (string): SQL query to explain

        Returns:
            English explanation of query
        """
        logger.debug(f"Explaining query: {sql[:50]}...")
        lower_sql = sql.strip().lower()
        explanation = "This query executes a SQL statement."
        if lower_sql.startswith("select"):
            explanation = "Selects data from one or more tables."
        elif lower_sql.startswith("insert"):
            explanation = "Inserts new rows into a table."
        elif lower_sql.startswith("update"):
            explanation = "Updates existing rows in a table."
        elif lower_sql.startswith("delete"):
            explanation = "Deletes rows from a table."

        return {"explanation": explanation}

    def suggest_optimizations(self, sql: str) -> Dict[str, Any]:
        """
        Suggest optimizations for a SQL query.

        MCP Tool: suggest_optimizations
        Parameters:
            - sql (string): SQL query to optimize

        Returns:
            List of optimization suggestions
        """
        logger.debug(f"Suggesting optimizations for: {sql[:50]}...")
        suggestions = []
        if "select *" in sql.lower():
            suggestions.append("Avoid SELECT * and specify only needed columns.")
        if "join" in sql.lower() and "on" not in sql.lower():
            suggestions.append("Include an explicit JOIN condition to avoid Cartesian products.")
        if not suggestions:
            suggestions.append("Review indexes on referenced tables and limit returned rows if possible.")

        return {"suggestions": suggestions}
