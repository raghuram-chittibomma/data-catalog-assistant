"""NL->SQL eval gates.

A small golden-set harness that checks the *generation pipeline* (LLM output ->
SQL extraction -> safety/validation) produces safe SQL that references the
expected tables, and that unsafe model output is reliably blocked.

A scripted fake LLM is used so the gate is deterministic and runs in CI without
network or API keys.
"""

import pytest

from src.core.rag_engine import RAGEngine


class ScriptedLLM:
    """Fake LLM that returns a canned response regardless of the prompt."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    def create(self, model, messages, temperature=0.0, max_tokens=512):
        return {"choices": [{"message": {"content": self.response_text}}]}


def _engine(response_text: str) -> RAGEngine:
    return RAGEngine(
        llm_client=ScriptedLLM(response_text),
        config={"llm": {"provider": "openai", "model": "gpt-4"}},
    )


# (question, scripted model output, expected tables/tokens that must appear)
GOLDEN_CASES = [
    (
        "List all customers",
        "SELECT customer_id, company_name FROM customers",
        ["customers"],
    ),
    (
        "Show orders with their customer",
        "SELECT o.order_id, c.company_name FROM orders o JOIN customers c ON o.customer_id = c.customer_id",
        ["orders", "customers"],
    ),
    (
        "Total revenue by product category",
        "SELECT category, SUM(amount) AS revenue FROM product_sales GROUP BY category",
        ["product_sales"],
    ),
]


@pytest.mark.parametrize("question, model_output, expected_tables", GOLDEN_CASES)
def test_generated_sql_is_safe_and_references_expected_tables(
    question, model_output, expected_tables
):
    result = _engine(model_output).generate_query(question)

    assert result["query"], f"expected non-empty SQL for: {question}"
    assert result["confidence"] > 0

    lowered = result["query"].lower()
    assert lowered.lstrip().startswith("select")
    for table in expected_tables:
        assert table in lowered, f"expected table '{table}' in generated SQL for: {question}"


DANGEROUS_OUTPUTS = [
    "DROP TABLE customers;",
    "DELETE FROM orders;",
    "TRUNCATE TABLE product_sales;",
]


@pytest.mark.parametrize("model_output", DANGEROUS_OUTPUTS)
def test_dangerous_sql_is_blocked(model_output):
    result = _engine(model_output).generate_query("do something destructive")

    assert result["query"] == ""
    assert result["confidence"] == 0.0
    assert "Safety check failed" in result["explanation"]
