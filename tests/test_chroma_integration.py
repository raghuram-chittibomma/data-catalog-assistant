"""Integration tests for ChromaVectorStore.

These tests will be skipped if `chromadb` is not installed in the environment.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import chromadb  # noqa: F401

    CHROMADB_AVAILABLE = True
except Exception:
    CHROMADB_AVAILABLE = False

from src.vector_store.vector_db import ChromaVectorStore


@unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb not installed - skipping integration tests")
class TestChromaIntegration(unittest.TestCase):
    def test_add_and_search(self):
        cfg = {"collection_name": "test_collection_integration"}
        vs = ChromaVectorStore(config=cfg)
        vs.connect()

        docs = [
            {"id": "t1", "text": "Alice from customer table", "metadata": {"table": "customer"}},
            {"id": "t2", "text": "Order row with amount", "metadata": {"table": "orders"}},
        ]
        embs = [[0.01, 0.02, 0.03], [0.5, 0.4, 0.3]]

        vs.add_documents(docs, embs)

        results = vs.search([0.01, 0.02, 0.03], top_k=2)
        self.assertTrue(len(results) >= 1)
        top_doc, top_score = results[0]
        self.assertIn(top_doc.get("id"), {"t1", "t2"})


if __name__ == "__main__":
    unittest.main()
