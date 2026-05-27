"""
SQL parser - extracts information from SQL statements in reports/ETLs.
"""

import logging
import re
from typing import Dict, List, Any, Set, Optional

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import Keyword

logger = logging.getLogger(__name__)

_TABLE_KEYWORDS = frozenset({"FROM", "JOIN", "INTO", "UPDATE", "TABLE"})


class SQLParser:
    """
    Parses SQL queries to extract tables, joins, and a short description.
    """

    def __init__(self, default_schema: str = "public"):
        self.default_schema = default_schema
        logger.info("Initialized SQL Parser (default_schema=%s)", default_schema)

    def parse_query(self, sql: str) -> Dict[str, Any]:
        """Parse SQL and return structured metadata."""
        logger.debug("Parsing SQL: %s...", sql[:80])
        tables = sorted(self.extract_tables(sql))
        columns = sorted(self.extract_columns(sql))
        joins = self.extract_joins(sql)
        statements = sqlparse.parse(sql)
        statement_type = statements[0].get_type() if statements else "UNKNOWN"

        return {
            "tables": tables,
            "columns": columns,
            "joins": joins,
            "filters": [],
            "aggregations": [],
            "subqueries": [],
            "statement_type": statement_type,
            "transformation_description": self.generate_description(sql, tables=tables),
        }

    def extract_tables(self, sql: str) -> Set[str]:
        """Extract table names from SQL."""
        tables: Set[str] = set()
        for statement in sqlparse.parse(sql):
            if statement.get_type() == "UNKNOWN" and not str(statement).strip():
                continue
            tables.update(self._tables_from_statement(statement))
        return tables

    def _is_table_keyword(self, token) -> bool:
        if token.ttype is not Keyword:
            return False
        value = token.value.upper()
        return value in _TABLE_KEYWORDS or "JOIN" in value

    def _tables_from_statement(self, statement) -> Set[str]:
        tables: Set[str] = set()
        pending = False

        for token in statement.tokens:
            if getattr(token, "is_whitespace", False):
                if pending:
                    continue
                continue

            if pending:
                found = self._names_from_token(token)
                if found:
                    tables.update(found)
                    pending = False
                continue

            if self._is_table_keyword(token):
                pending = True
                continue

            if isinstance(token, Parenthesis):
                tables.update(self._tables_from_statement(token))

        return tables

    def _names_from_token(self, token) -> Set[str]:
        names: Set[str] = set()
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                names.add(self._normalize_table(self._identifier_name(identifier)))
        elif isinstance(token, Identifier):
            names.add(self._normalize_table(self._identifier_name(token)))
        elif isinstance(token, Parenthesis):
            names.update(self._tables_from_statement(token))
        elif token.ttype is Keyword:
            return names
        else:
            raw = str(token).strip()
            if raw and not raw.startswith("("):
                for part in re.split(r"\s*,\s*", raw):
                    cleaned = part.strip().strip(",")
                    if cleaned and cleaned.upper() not in _TABLE_KEYWORDS:
                        names.add(self._normalize_table(cleaned))
        return {n for n in names if n}

    def _identifier_name(self, identifier: Identifier) -> str:
        parent = identifier.get_parent_name() if hasattr(identifier, "get_parent_name") else None
        name = identifier.get_real_name() or str(identifier)
        if parent:
            return f"{parent}.{name}"
        return name

    def _normalize_table(self, name: str) -> str:
        cleaned = name.strip().strip('"').strip("'").strip("`")
        if not cleaned or cleaned == "*":
            return ""
        if "." in cleaned:
            return cleaned.lower()
        return f"{self.default_schema}.{cleaned.lower()}"

    def extract_columns(self, sql: str) -> Set[str]:
        """Extract simple column-like identifiers from SELECT lists (best effort)."""
        columns: Set[str] = set()
        for statement in sqlparse.parse(sql):
            if statement.get_type() != "SELECT":
                continue
            select_seen = False
            from_seen = False
            for token in statement.tokens:
                if token.ttype is Keyword and token.value.upper() == "SELECT":
                    select_seen = True
                    continue
                if token.ttype is Keyword and token.value.upper() == "FROM":
                    from_seen = True
                    break
                if select_seen and not from_seen:
                    columns.update(self._column_names_from_select_token(token))
        return columns

    def _column_names_from_select_token(self, token) -> Set[str]:
        names: Set[str] = set()
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                names.add(self._column_name_from_identifier(identifier))
        elif isinstance(token, Identifier):
            names.add(self._column_name_from_identifier(token))
        return {n for n in names if n}

    def _column_name_from_identifier(self, identifier: Identifier) -> str:
        name = identifier.get_real_name() or ""
        if name == "*":
            return ""
        return name.lower()

    def extract_joins(self, sql: str) -> List[Dict[str, str]]:
        """Extract join keywords and joined table names."""
        joins: List[Dict[str, str]] = []
        for statement in sqlparse.parse(sql):
            join_type = None
            pending = False
            for token in statement.tokens:
                if getattr(token, "is_whitespace", False):
                    continue
                if token.ttype is Keyword and "JOIN" in token.value.upper():
                    join_type = token.value.upper()
                    pending = True
                    continue
                if pending:
                    for table in self._names_from_token(token):
                        joins.append({"join_type": join_type or "JOIN", "table": table})
                    pending = False
        return joins

    def generate_description(
        self,
        sql: str,
        tables: Optional[List[str]] = None,
    ) -> str:
        """Generate a short human-readable description."""
        tables = tables if tables is not None else sorted(self.extract_tables(sql))
        stmt_type = "QUERY"
        parsed = sqlparse.parse(sql)
        if parsed:
            stmt_type = parsed[0].get_type() or "QUERY"

        if tables:
            return f"{stmt_type} using tables: {', '.join(tables)}"
        return f"{stmt_type} (no tables detected)"
