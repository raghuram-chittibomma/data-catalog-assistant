from src.utils.sql_validator import extract_sql_from_llm_text, validate_sql


def test_validate_select_ok():
    sql = "SELECT id, name FROM customers WHERE id > 10"
    ok, reason = validate_sql(sql)
    assert ok
    assert reason == ""


def test_validate_blocked_keyword():
    sql = "DROP TABLE users;"
    ok, reason = validate_sql(sql)
    assert not ok
    assert "dangerous" in reason.lower() or "contains" in reason.lower()


def test_validate_allowed_tables():
    sql = 'SELECT * FROM sales.orders o JOIN customers c ON o.customer_id = c.id'
    ok, reason = validate_sql(sql, allowed_tables=["customers", "orders"]) 
    assert ok


def test_validate_disallowed_table():
    sql = 'SELECT * FROM admin.secret'
    ok, reason = validate_sql(sql, allowed_tables=["public_table"]) 
    assert not ok
    assert "disallowed" in reason.lower() or "references" in reason.lower()


def test_validate_select_without_trailing_space():
    sql = "SELECT\n  c.customer_id,\n  COUNT(*) AS order_count\nFROM public.customers c"
    ok, reason = validate_sql(sql)
    assert ok
    assert reason == ""


def test_extract_sql_from_markdown_fence():
    raw = """```sql
SELECT c.customer_id, COUNT(*) AS cnt
FROM public.customers c
JOIN public.orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id
ORDER BY cnt DESC
LIMIT 5;
```
EXPLANATION: top customers by orders"""
    sql, expl = extract_sql_from_llm_text(raw)
    assert sql.lower().startswith("select")
    assert "limit 5" in sql.lower()
    assert "top customers" in expl.lower()
