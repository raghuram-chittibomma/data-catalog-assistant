"""
Main RAG Engine - orchestrates vector search and LLM interactions.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from src.utils.sql_validator import extract_sql_from_llm_text, validate_sql

logger = logging.getLogger(__name__)

_DANGEROUS_SQL_TOKENS = (
    "drop ",
    "truncate ",
    "delete ",
    "alter ",
    "grant ",
    "revoke ",
    "shutdown ",
)


def _sanitize_broken_ssl_env_vars() -> None:
    """Drop SSL cert env vars that point at missing files (breaks httpx on Windows)."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and not os.path.isfile(path):
            logger.warning("Ignoring invalid %s=%s (file not found)", var, path)
            os.environ.pop(var, None)


def _basic_sql_safety(sql_text: str) -> tuple[bool, str]:
    """Fallback safety check used when the full SQL validator is unavailable."""
    lowered = (sql_text or "").lower()
    for token in _DANGEROUS_SQL_TOKENS:
        if token in lowered:
            return False, f"Contains dangerous token: {token.strip()}"
    if not re.search(r"\b(select|with|insert|update)\b", lowered):
        return False, "Generated SQL does not appear to be a SELECT/WITH/INSERT/UPDATE statement"
    return True, ""


@dataclass
class SearchResult:
    """Result from RAG search."""

    data_asset: str
    description: str
    relevance_score: float
    metadata: dict[str, Any]
    sql_context: str | None = None
    impact_info: dict[str, Any] | None = None


class RAGEngine:
    """
    Main engine for RAG operations.
    Coordinates vector search, LLM queries, and impact analysis.
    """

    def __init__(
        self,
        vector_store=None,
        llm_client=None,
        embedding_service=None,
        metadata_store=None,
        config=None,
    ):
        """
        Initialize RAG Engine.

        Args:
            vector_store: VectorStore instance
            llm_client: LLM client (e.g., OpenAI)
            embedding_service: Embedding service instance
            metadata_store: MetadataStore instance
            config: Configuration dictionary
        """
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.embedding_service = embedding_service
        self.metadata_store = metadata_store
        self.config = config or {}
        logger.info("RAG Engine initialized")

    def _log_llm_messages(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """Log chat messages immediately before an LLM API call (when enabled in config)."""
        llm_cfg = self.config.get("llm", {}) if self.config else {}
        if not llm_cfg.get("log_prompts", False):
            return

        parts = [
            f"LLM prompt outgoing model={model} temperature={temperature} max_tokens={max_tokens}",
        ]
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            parts.append(f"--- {role} ---\n{content}")
        logger.info("\n".join(parts))

    def search_data_lineage(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """
        Search for data assets related to impact analysis.

        Args:
            query: Natural language query about data usage/impact
            top_k: Number of results to return

        Returns:
            List of SearchResult objects
        """
        logger.debug(f"Searching lineage for: {query}")
        if not self.embedding_service:
            logger.error("No embedding service configured for RAGEngine")
            return []
        if not self.vector_store:
            logger.error("No vector store configured for RAGEngine")
            return []

        try:
            # embed the query and run vector search
            q_emb = self.embedding_service.embed_texts([query])[0]
            hits = self.vector_store.search(q_emb, top_k=top_k)
            results: list[SearchResult] = []
            for doc, score in hits:
                sr = SearchResult(
                    data_asset=doc.get("id") or doc.get("text", ""),
                    description=doc.get("text", ""),
                    relevance_score=score,
                    metadata=doc.get("metadata") or {},
                    sql_context=None,
                    impact_info=None,
                )
                results.append(sr)
            return results
        except Exception as e:
            logger.error(f"Error during lineage search: {e}")
            return []

    @staticmethod
    def _build_sql_messages(
        natural_language: str,
        catalog_context: str | None,
    ) -> list[dict[str, str]]:
        """Build the system/user chat messages for SQL generation."""
        system_prompt = (
            "You are an expert SQL generator for PostgreSQL. "
            "Use only tables and columns that appear in the provided data catalog context. "
            "If context is insufficient, prefer a conservative SELECT with explicit column names. "
            "Produce a single valid SQL statement. "
            "Respond with the SQL only, optionally followed by a short explanation prefixed with 'EXPLANATION:'."
        )
        if catalog_context:
            user_prompt = (
                "Data catalog context (relevant tables, columns, and assets):\n\n"
                f"{catalog_context}\n\n"
                f"User request: {natural_language}"
            )
        else:
            user_prompt = natural_language

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _invoke_llm(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: str | None,
    ) -> str:
        """Call the LLM and return the raw response text.

        Uses an injected ``llm_client`` when present (tests/custom clients),
        otherwise falls back to the OpenAI SDK. Raises on transport errors so the
        caller can convert them into a structured failure result.
        """
        if self.llm_client:
            resp = self.llm_client.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.get("choices", [])[0].get("message", {}).get("content", "")

        import openai

        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        _sanitize_broken_ssl_env_vars()

        # Prefer the modern OpenAI client; fall back to legacy ChatCompletion.
        if hasattr(openai, "OpenAI"):
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                return resp.choices[0].message.content
            except Exception:
                return str(resp)

        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if isinstance(resp, dict):
            return resp.get("choices", [])[0].get("message", {}).get("content", "")
        try:
            return resp.choices[0].message.content
        except Exception:
            return str(resp)

    def _check_sql_safety(self, sql_text: str) -> tuple[bool, str]:
        """Validate generated SQL, falling back to basic checks on validator error."""
        allowed_tables = self.config.get("security", {}).get("allowed_tables")
        try:
            return validate_sql(sql_text, allowed_tables=allowed_tables)
        except Exception:
            return _basic_sql_safety(sql_text)

    def generate_query(
        self,
        natural_language: str,
        catalog_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate SQL query from natural language description.

        Args:
            natural_language: User's English description
            catalog_context: Optional RAG-retrieved schema/catalog text (Phase 3)

        Returns:
            Dictionary with 'query', 'confidence', and 'explanation'
        """
        logger.debug(
            "Generating query for: %s (context=%s)", natural_language, bool(catalog_context)
        )

        llm_cfg = self.config.get("llm", {}) if self.config else {}
        provider = llm_cfg.get("provider", "openai").lower()
        if provider != "openai":
            logger.error("LLM provider '%s' not supported by generate_query()", provider)
            return {
                "query": "",
                "confidence": 0.0,
                "explanation": "LLM provider not configured or supported",
            }

        messages = self._build_sql_messages(natural_language, catalog_context)
        model = llm_cfg.get("model", "gpt-4")
        temperature = llm_cfg.get("temperature", 0.0)
        max_tokens = llm_cfg.get("max_tokens", 512)
        self._log_llm_messages(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

        try:
            text = self._invoke_llm(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=llm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY"),
            )

            sql_text, explanation = extract_sql_from_llm_text(text)

            safe, reason = self._check_sql_safety(sql_text)
            if not safe:
                logger.warning("Generated SQL failed safety check: %s", reason)
                preview = (sql_text or text or "")[:300].replace("\n", " ")
                return {
                    "query": "",
                    "confidence": 0.0,
                    "explanation": f"Safety check failed: {reason}. Model output preview: {preview}",
                }

            # crude confidence metric: prefer to set high for model-generated SQL
            return {"query": sql_text, "confidence": 0.8, "explanation": explanation}

        except ImportError:
            logger.error("OpenAI package not installed or llm client unavailable")
            return {"query": "", "confidence": 0.0, "explanation": "OpenAI package not available"}
        except Exception as e:
            logger.error(f"LLM query generation failed: {e}")
            return {"query": "", "confidence": 0.0, "explanation": str(e)}

    def analyze_impact(self, data_asset: str) -> dict[str, Any]:
        """
        Analyze impact of a data asset.

        Args:
            data_asset: Name of the data asset

        Returns:
            Impact analysis results
        """
        logger.debug(f"Analyzing impact for: {data_asset}")
        if not self.metadata_store:
            logger.warning("No metadata store configured for impact analysis")
            return {}

        asset = self.metadata_store.get_asset_metadata(data_asset)
        upstream = self.metadata_store.get_upstream_assets(data_asset)
        downstream = self.metadata_store.get_downstream_assets(data_asset)
        from src.core.impact_analyzer import ImpactAnalyzer

        analyzer = ImpactAnalyzer(metadata_store=self.metadata_store)
        impact_score = analyzer.resolve_impact_score(data_asset, persist=True)

        return {
            "asset": asset,
            "upstream": upstream,
            "downstream": downstream,
            "impact_score": impact_score,
        }

    def get_data_lineage(self, data_asset: str) -> dict[str, Any]:
        """
        Get lineage information for a data asset.

        Args:
            data_asset: Name of the data asset

        Returns:
            Lineage graph and relationships
        """
        from src.core.lineage_service import get_asset_lineage

        logger.debug("Getting lineage for: %s", data_asset)
        result = get_asset_lineage(self.metadata_store, data_asset, direction="both")
        if not result.get("asset_id"):
            return {}
        return {
            "asset": result.get("asset"),
            "upstream": result.get("upstream", []),
            "downstream": result.get("downstream", []),
        }
