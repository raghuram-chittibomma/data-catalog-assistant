"""
Runner to execute the VectorDBRefreshJob end-to-end using real services defined
in config/config.yaml. The script resolves ${VAR} placeholders from environment
variables.

Usage (PowerShell):
  $Env:DW_USER = 'dbuser'
  $Env:DW_PASSWORD = 'secret'
  $Env:METADATA_DB_USER = 'metauser'
  $Env:METADATA_DB_PASSWORD = 'metapass'
  python batch_jobs\run_refresh_job.py

Uses LocalEmbedding (sentence-transformers) from `embeddings.model_name` in config.
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_refresh_job")

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from batch_jobs.refresh_vector_db import VectorDBRefreshJob
from src.utils.config_loader import load_config
from src.vector_store.embeddings import LocalEmbedding
from src.vector_store.vector_db import ChromaVectorStore
from src.vector_store.metadata_store import MetadataStore


def build_embedding_service(cfg: dict) -> LocalEmbedding:
    return LocalEmbedding(model_name=cfg.get("model_name", "all-MiniLM-L6-v2"))


def main():
    logger.info("Loading configuration")
    cfg = load_config()

    # build services
    emb_cfg = cfg.get("embeddings", {})
    embedding_service = build_embedding_service(emb_cfg)

    vector_cfg = cfg.get("vector_store", {})
    vector_store = ChromaVectorStore(config=vector_cfg)

    metadata_cfg = cfg.get("metadata_store", {})
    metadata_store = MetadataStore(config=metadata_cfg)

    # create job and wire services
    job = VectorDBRefreshJob(config={})
    # ensure pipeline config is present
    job.config["datawarehouse"] = cfg.get("datawarehouse")
    job.set_services(embedding_service=embedding_service, vector_store=vector_store, metadata_store=metadata_store)

    logger.info("Running VectorDBRefreshJob")
    result = job.run()
    logger.info("Job result:\n%s", result)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Failed to run refresh job: %s", e)
        sys.exit(2)
