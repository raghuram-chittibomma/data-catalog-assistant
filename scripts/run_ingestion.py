#!/usr/bin/env python
"""
Run table metadata ingestion only (no embeddings or Chroma update).

Usage (from project root):
  python scripts/run_ingestion.py
  python scripts/run_ingestion.py --limit 5
"""

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.config_loader import load_config
from src.data_ingestion.ingestion_pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("run_ingestion")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DW table ingestion pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Print only the first N documents (for quick checks)",
    )
    args = parser.parse_args()

    logger.info("Loading configuration")
    config = load_config()
    dw_config = config.get("datawarehouse", {})
    if not dw_config:
        logger.error("No datawarehouse section in config")
        return 1

    ingest = dw_config.get("ingest", {})
    logger.info(
        "Ingest settings: schemas=%s exclude_tables=%s",
        ingest.get("schemas", "all"),
        ingest.get("exclude_tables", []),
    )

    pipeline = IngestionPipeline(config=dw_config)
    documents = pipeline.run()

    if args.limit is not None:
        shown = documents[: args.limit]
    else:
        shown = documents

    table_count = sum(1 for d in documents if d.get("metadata", {}).get("asset_type") == "table")
    sql_count = sum(1 for d in documents if d.get("metadata", {}).get("asset_type") == "sql")
    etl_count = sum(1 for d in documents if d.get("metadata", {}).get("asset_type") == "etl")
    logger.info(
        "Total documents: %s (%s tables, %s sql, %s etl)",
        len(documents),
        table_count,
        sql_count,
        etl_count,
    )
    for doc in shown:
        asset_type = doc.get("metadata", {}).get("asset_type", "?")
        logger.info("  - [%s] %s (%s chars)", asset_type, doc.get("id"), len(doc.get("text", "")))

    if args.limit and len(documents) > args.limit:
        logger.info("  ... and %s more", len(documents) - args.limit)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        sys.exit(2)
