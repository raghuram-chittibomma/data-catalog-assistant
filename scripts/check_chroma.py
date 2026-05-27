#!/usr/bin/env python
"""Quick Chroma diagnostic — document count and sample search."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.utils.config_loader import load_config
from src.vector_store.embeddings import LocalEmbedding
from src.vector_store.vector_db import ChromaVectorStore


def main() -> int:
    cfg = load_config()
    persist = cfg["vector_store"]["backend"]["persist_directory"]
    path = ROOT / persist
    print(f"persist_directory: {persist} -> {path} (exists={path.exists()})")

    vs = ChromaVectorStore(config=cfg["vector_store"])
    vs.connect()
    count = vs.collection.count()
    print(f"collection: {cfg['vector_store'].get('collection_name')} count={count}")

    if count == 0:
        print("EMPTY — run: python batch_jobs/run_refresh_job.py")
        return 1

    emb = LocalEmbedding(model_name=cfg["embeddings"]["model_name"])
    q = emb.embed_texts(["customer orders"])[0]
    hits = vs.search(q, top_k=3)
    print(f"search hits: {len(hits)}")
    for doc, score in hits:
        print(f"  {doc.get('id')} score={score:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
