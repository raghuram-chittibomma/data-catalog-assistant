#!/usr/bin/env python
"""
Simple demo for ChromaVectorStore.
Run this script to create an in-memory Chroma collection, add sample documents, and run a search.

If `chromadb` is not installed, the script will print instructions.
"""
import sys
import os
import json
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vector_store.vector_db import ChromaVectorStore


def main():
    cfg = {
        "collection_name": "demo_collection",
        "backend": {
            "persist_directory": "chroma_data",
            "chroma_impl": "duckdb+parquet",
        }
    }

    store = ChromaVectorStore(config=cfg)

    try:
        store.connect()
    except Exception as e:
        print("chromadb failed to initialize persistent client:", e)
        print("Falling back to in-memory Chroma client for demo.")
        # fallback to in-memory (remove backend persistence settings)
        cfg_fallback = {"collection_name": cfg.get("collection_name", "demo_collection")}
        store = ChromaVectorStore(config=cfg_fallback)
        try:
            store.connect()
        except Exception as e2:
            print("chromadb not available or failed to initialize in-memory client:", e2)
            print("Install: pip install chromadb")
            return

    docs = [
        {"id": "d1", "text": "Customer table stores customer records", "metadata": {"table": "customer"}},
        {"id": "d2", "text": "Orders table stores order rows", "metadata": {"table": "orders"}},
        {"id": "d3", "text": "Products table stores product catalog", "metadata": {"table": "products"}},
    ]

    # simple toy embeddings (dim=3)
    embs = [[0.1, 0.2, 0.3], [0.11, 0.19, 0.25], [0.9, 0.1, 0.05]]

    store.add_documents(docs, embs)

    # If a backup exists, restore it (useful when persistence isn't available)
    def restore_from_backup(path="demo_chroma_backup.json"):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            b_docs = data.get("documents")
            b_embs = data.get("embeddings")
            if b_docs and b_embs and len(b_docs) == len(b_embs):
                store.add_documents(b_docs, b_embs)
                print(f"Restored {len(b_docs)} documents from {path}")
                return True
        except Exception as e:
            print("Failed to restore backup:", e)
        return False

    # Attempt restore (will be a no-op if backup absent)
    restore_from_backup()

    query_emb = [0.1, 0.2, 0.25]
    results = store.search(query_emb, top_k=3)

    print("Search results:")
    for doc, score in results:
        print(f"- id={doc.get('id')} score={score:.4f} metadata={doc.get('metadata')}")

    # Save a simple backup of the demo data as a JSON file for basic persistence
    try:
        backup = {"documents": docs, "embeddings": embs}
        with open("demo_chroma_backup.json", "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2)
        print("Wrote demo backup to demo_chroma_backup.json")
    except Exception as e:
        print("Failed to write demo backup:", e)


if __name__ == '__main__':
    main()
