#!/usr/bin/env python
"""Preflight checks before batch_jobs/run_refresh_job.py."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PLACEHOLDERS = {
    "",
    "your_password",
    "your_dw_user",
    "your_dw_password",
    "your_metadata_password",
    "sk-...",
    "changeme",
}


def main() -> int:
    checks = []

    def ok(msg):
        checks.append(("OK", msg))

    def warn(msg):
        checks.append(("WARN", msg))

    def fail(msg):
        checks.append(("FAIL", msg))

    ok(f"Python: {sys.executable}")

    from src.utils.config_loader import load_config

    try:
        cfg = load_config()
        ok("config.yaml loads")
    except Exception as e:
        fail(f"config load: {e}")
        _print(checks)
        return 1

    for key in (
        "DW_HOST",
        "DW_USER",
        "DW_PASSWORD",
        "METADATA_DB_HOST",
        "METADATA_DB_USER",
        "METADATA_DB_PASSWORD",
    ):
        val = os.environ.get(key, "")
        if not val:
            fail(f".env missing or empty: {key}")
        elif val.lower() in PLACEHOLDERS or "your_" in val.lower():
            warn(f"{key} looks like a placeholder")
        else:
            ok(f"{key} is set")

    dw = cfg.get("datawarehouse", {}).get("connection", {})
    for field in ("host", "database", "user", "password"):
        if not dw.get(field):
            fail(f"datawarehouse.connection.{field} empty after substitution")
    if all(dw.get(f) for f in ("host", "database", "user", "password")):
        ok("DW connection fields populated")

    ms = cfg.get("metadata_store", {}).get("connection", {})
    for field in ("host", "database", "user", "password"):
        if not ms.get(field):
            fail(f"metadata_store.connection.{field} empty after substitution")
    if all(ms.get(f) for f in ("host", "database", "user", "password")):
        ok("metadata connection fields populated")

    for rel in ("sql_samples", "etl_samples", "config/config.yaml"):
        if (ROOT / rel).exists():
            ok(f"path exists: {rel}")
        else:
            fail(f"missing: {rel}")

    try:
        import psycopg2  # noqa: F401

        ok("psycopg2 installed")
    except ImportError:
        fail("psycopg2 not installed — pip install psycopg2-binary")

    try:
        import chromadb  # noqa: F401

        ok("chromadb installed")
    except ImportError:
        fail("chromadb not installed")

    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401

        ok("sentence-transformers import OK")
    except ImportError as e:
        try:
            import importlib.util

            if importlib.util.find_spec("sentence_transformers"):
                fail(
                    "sentence-transformers installed but broken import "
                    f"(often huggingface_hub mismatch): {e}"
                )
            else:
                fail("sentence-transformers not installed — pip install sentence-transformers")
        except Exception:
            fail(f"sentence-transformers check failed: {e}")

    try:
        import gradio  # noqa: F401

        ok(f"gradio installed ({gradio.__version__})")
    except ImportError:
        fail("gradio not installed — pip install -r requirements.txt (required for UI)")

    try:
        import starlette

        major = int(starlette.__version__.split(".", 1)[0])
        if major >= 1:
            fail(
                f"starlette {starlette.__version__} breaks Gradio UI — "
                "pip install 'starlette>=0.40,<1.0' then restart main.py"
            )
    except ImportError:
        pass

    try:
        from src.data_ingestion.datawarehouse_connector import PostgreSQLConnector

        ingest = cfg["datawarehouse"].get("ingest", {})
        conn = PostgreSQLConnector(cfg["datawarehouse"]["connection"], ingest=ingest)
        conn.connect()
        tables = conn.get_tables()
        conn.close()
        ok(f"DW connect OK ({len(tables)} tables in scope)")
    except Exception as e:
        fail(f"DW connect: {e}")

    try:
        from src.vector_store.metadata_store import MetadataStore

        store = MetadataStore(cfg["metadata_store"])
        n = len(store.store.get("assets", {}))
        if store.backend == "postgres":
            ok(f"metadata Postgres backend ({n} assets already loaded)")
        else:
            warn(f"metadata using {store.backend} backend ({n} assets) — not Postgres")
    except Exception as e:
        fail(f"metadata store: {e}")

    try:
        from src.vector_store.vector_db import ChromaVectorStore

        vs = ChromaVectorStore(cfg["vector_store"])
        vs.connect()
        ok("Chroma connect OK")
    except Exception as e:
        fail(f"Chroma: {e}")

    _print(checks)
    fails = sum(1 for s, _ in checks if s == "FAIL")
    return 1 if fails else 0


def _print(checks):
    print("--- Preflight for run_refresh_job ---")
    for status, msg in checks:
        print(f"[{status}] {msg}")
    fails = sum(1 for s, _ in checks if s == "FAIL")
    warns = sum(1 for s, _ in checks if s == "WARN")
    print(f"--- {fails} fail, {warns} warn ---")


if __name__ == "__main__":
    sys.exit(main())
