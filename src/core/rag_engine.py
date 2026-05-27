"""
Main RAG Engine - orchestrates vector search and LLM interactions.
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _sanitize_broken_ssl_env_vars() -> None:
    """Drop SSL cert env vars that point at missing files (breaks httpx on Windows)."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and not os.path.isfile(path):
            logger.warning("Ignoring invalid %s=%s (file not found)", var, path)
            os.environ.pop(var, None)


@dataclass
class SearchResult:
    """Result from RAG search."""
    data_asset: str
    description: str
    relevance_score: float
    metadata: Dict[str, Any]
    sql_context: Optional[str] = None
    impact_info: Optional[Dict[str, Any]] = None


class RAGEngine:
    """
    Main engine for RAG operations.
    Coordinates vector search, LLM queries, and impact analysis.
    """

    def __init__(self, vector_store=None, llm_client=None, embedding_service=None, metadata_store=None, config=None):
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
        messages: List[Dict[str, str]],
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

    def search_data_lineage(self, query: str, top_k: int = 5) -> List[SearchResult]:
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
            results: List[SearchResult] = []
            for doc, score in hits:
                sr = SearchResult(
                    data_asset=doc.get("id") or doc.get("text", ""),
                    description=doc.get("text", ""),
                    relevance_score=score,
                    metadata=doc.get("metadata") or {},
                    sql_context=None,
                    impact_info=None
                )
                results.append(sr)
            return results
        except Exception as e:
            logger.error(f"Error during lineage search: {e}")
            return []

    def generate_query(
        self,
        natural_language: str,
        catalog_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language description.

        Args:
            natural_language: User's English description
            catalog_context: Optional RAG-retrieved schema/catalog text (Phase 3)

        Returns:
            Dictionary with 'query', 'confidence', and 'explanation'
        """
        logger.debug("Generating query for: %s (context=%s)", natural_language, bool(catalog_context))
        # Use configured LLM (fall back to OpenAI if llm_client not provided)
        llm_cfg = self.config.get("llm", {}) if self.config else {}
        provider = llm_cfg.get("provider", "openai").lower()

        def _basic_sql_safety(sql_text: str) -> (bool, str):
            """Basic safety checks for generated SQL."""
            dangerous = ["drop ", "truncate ", "delete ", "alter ", "grant ", "revoke ", "shutdown "]
            lowered = sql_text.lower()
            for token in dangerous:
                if token in lowered:
                    return False, f"Contains dangerous token: {token.strip()}"
            # require SELECT or WITH or common DML
            if not re.search(r"\b(select|with|insert|update)\b", lowered):
                return False, "Generated SQL does not appear to be a SELECT/WITH/INSERT/UPDATE statement"
            return True, ""

        if provider != "openai":
            logger.error(f"LLM provider '{provider}' not supported by generate_query()")
            return {"query": "", "confidence": 0.0, "explanation": "LLM provider not configured or supported"}

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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        model = llm_cfg.get("model", "gpt-4")
        temperature = llm_cfg.get("temperature", 0.0)
        max_tokens = llm_cfg.get("max_tokens", 512)
        self._log_llm_messages(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Try using provided llm_client first
        try:
            if self.llm_client:
                resp = self.llm_client.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.get("choices", [])[0].get("message", {}).get("content", "")
            else:
                import openai
                api_key = llm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return {
                        "query": "",
                        "confidence": 0.0,
                        "explanation": "OPENAI_API_KEY not set",
                    }
                _sanitize_broken_ssl_env_vars()

                # Prefer new OpenAI client API if available (openai.OpenAI), otherwise use legacy ChatCompletion
                if hasattr(openai, "OpenAI"):
                    client = openai.OpenAI(api_key=api_key)
                    resp = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    try:
                        text = resp.choices[0].message.content
                    except Exception:
                        text = str(resp)
                else:
                    resp = openai.ChatCompletion.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if isinstance(resp, dict):
                        text = resp.get("choices", [])[0].get("message", {}).get("content", "")
                    else:
                        try:
                            text = resp.choices[0].message.content
                        except Exception:
                            text = str(resp)

            from src.utils.sql_validator import extract_sql_from_llm_text, validate_sql

            sql_text, explanation = extract_sql_from_llm_text(text)

            allowed_tables = self.config.get("security", {}).get("allowed_tables")
            try:
                safe, reason = validate_sql(sql_text, allowed_tables=allowed_tables)
            except Exception:
                safe, reason = _basic_sql_safety(sql_text)
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

    def analyze_impact(self, data_asset: str) -> Dict[str, Any]:
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

    def get_data_lineage(self, data_asset: str) -> Dict[str, Any]:
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
