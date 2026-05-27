import gc
import os
import shutil
import tempfile
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vector_store.vector_db import ChromaVectorStore


def test_chroma_persistence_across_reconnects():
    tmpdir = tempfile.mkdtemp()
    store1 = None
    store2 = None
    try:
        cfg = {
            "collection_name": "persist_test_collection",
            "backend": {
                "persist_directory": tmpdir,
                "chroma_impl": "duckdb+parquet",
            },
        }

        store1 = ChromaVectorStore(config=cfg)
        store1.connect()
        docs = [
            {"id": "d1", "text": "Customer table stores customer data", "metadata": {"table": "customer"}},
        ]
        embeddings = [[0.1, 0.2, 0.3]]
        store1.add_documents(docs, embeddings)
        store1.close()

        # Create a second client pointing at the same persistent directory
        store2 = ChromaVectorStore(config=cfg)
        store2.connect()
        query_embedding = [0.1, 0.2, 0.3]
        results = store2.search(query_embedding, top_k=1)
        store2.close()

        assert len(results) == 1
        assert results[0][0]["id"] == "d1"
        assert results[0][0]["metadata"]["table"] == "customer"
    finally:
        if store1 is not None:
            store1.close()
        if store2 is not None:
            store2.close()
        gc.collect()
        shutil.rmtree(tmpdir, ignore_errors=True)
