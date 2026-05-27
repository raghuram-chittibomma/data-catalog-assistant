"""
Validators - for validating inputs and SQL queries.
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)


class Validator:
    """
    Validation utilities.
    """

    @staticmethod
    def validate_table_name(table_name: str) -> Tuple[bool, str]:
        """
        Validate table name.

        Args:
            table_name: Table name to validate

        Returns:
            (is_valid, error_message)
        """
        if not table_name or len(table_name) == 0:
            return False, "Table name is empty"
        if len(table_name) > 128:
            return False, "Table name is too long"
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            return False, "Table name contains invalid characters"
        return True, ""

    @staticmethod
    def validate_column_name(column_name: str) -> Tuple[bool, str]:
        """
        Validate column name.

        Args:
            column_name: Column name to validate

        Returns:
            (is_valid, error_message)
        """
        if not column_name or len(column_name) == 0:
            return False, "Column name is empty"
        if len(column_name) > 128:
            return False, "Column name is too long"
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
            return False, "Column name contains invalid characters"
        return True, ""

    @staticmethod
    def validate_sql_query(sql: str) -> Tuple[bool, str]:
        """
        Basic SQL validation.

        Args:
            sql: SQL query to validate

        Returns:
            (is_valid, error_message)
        """
        if not sql or len(sql) == 0:
            return False, "SQL query is empty"
        
        # Check for dangerous operations
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER']
        sql_upper = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"Query contains dangerous keyword: {keyword}"
        
        # Check for basic SQL syntax
        if 'SELECT' not in sql_upper:
            return False, "Query must contain SELECT statement"
        
        return True, ""

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email address.

        Args:
            email: Email address to validate

        Returns:
            (is_valid, error_message)
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, ""
        return False, "Invalid email address"
