"""SQL validation helpers for safety checks and basic parsing."""
import re
from typing import List, Optional, Tuple

import sqlparse


def extract_sql_from_llm_text(text: str) -> Tuple[str, str]:
    """
    Pull SQL out of common LLM response shapes (markdown fences, prose, EXPLANATION:).

    Returns:
        (sql_text, explanation)
    """
    if not text:
        return "", ""

    explanation = ""
    body = text.strip()
    if "EXPLANATION:" in body.upper():
        # case-insensitive split on first EXPLANATION:
        idx = body.upper().index("EXPLANATION:")
        sql_part = body[:idx]
        explanation = body[idx + len("EXPLANATION:") :].strip()
    else:
        sql_part = body

    fenced = re.search(r"```(?:sql)?\s*\n?(.*?)```", sql_part, re.DOTALL | re.IGNORECASE)
    if fenced:
        sql_text = fenced.group(1).strip()
    else:
        sql_text = sql_part.strip().strip("`").strip()

    # Drop a lone leading "sql" label from ```sql blocks
    if sql_text.lower().startswith("sql\n"):
        sql_text = sql_text[4:].strip()

    # If still prose-heavy, keep from first SELECT/WITH/INSERT/UPDATE onward
    match = re.search(
        r"\b((?:WITH|SELECT|INSERT|UPDATE)\b[\s\S]*)",
        sql_text,
        re.IGNORECASE,
    )
    if match:
        sql_text = match.group(1).strip()

    # Trim trailing prose after semicolon
    if ";" in sql_text:
        sql_text = sql_text[: sql_text.index(";") + 1]

    return sql_text, explanation


def _extract_table_names(sql: str) -> List[str]:
    """Naive extraction of table names from FROM and JOIN clauses."""
    tables = []
    # basic regex to capture FROM/JOIN table tokens (handles simple cases)
    for m in re.finditer(r"\bfrom\s+([\w\.\"]+)", sql, flags=re.IGNORECASE):
        tables.append(m.group(1).strip('"'))
    for m in re.finditer(r"\bjoin\s+([\w\.\"]+)", sql, flags=re.IGNORECASE):
        tables.append(m.group(1).strip('"'))
    return tables


def validate_sql(sql_text: str, allowed_tables: Optional[List[str]] = None, blocked_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
    """Validate SQL for safety.

    Checks performed:
    - presence of blocked keywords (DROP, TRUNCATE, etc.)
    - if `allowed_tables` provided, ensure referenced tables are within the allowlist
    - ensure statement looks like SQL (has SELECT/INSERT/UPDATE/with)

    Returns (is_valid, reason). If valid, reason is empty string.
    """
    if not sql_text or not sql_text.strip():
        return False, "Empty SQL"

    blk = blocked_keywords or ["drop", "truncate", "delete", "alter", "grant", "revoke", "shutdown"]
    lowered = sql_text.lower()
    for token in blk:
        if re.search(r"\b" + re.escape(token) + r"\b", lowered):
            return False, f"Contains dangerous keyword: {token}"

    if not re.search(r"\b(select|with|insert|update)\b", lowered):
        return False, "SQL does not appear to be a SELECT/INSERT/UPDATE/WITH statement"

    # parse using sqlparse to ensure valid parse tree for basic sanity
    try:
        parsed = sqlparse.parse(sql_text)
        if not parsed:
            return False, "Failed to parse SQL"
    except Exception as e:
        return False, f"SQL parse error: {e}"

    if allowed_tables:
        refs = _extract_table_names(sql_text)
        # normalize for simple matching
        refs_norm = [r.split('.')[-1].strip('"') for r in refs]
        allowed_norm = [a.split('.')[-1].strip('"') for a in allowed_tables]
        for r in refs_norm:
            if r and r.lower() not in [a.lower() for a in allowed_norm]:
                return False, f"References disallowed table: {r}"

    return True, ""
