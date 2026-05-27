"""Tests for Chroma document upsert behavior."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vector_store.vector_db import ChromaVectorStore


class FakeCollection:
    def __init__(self):
        self.upsert_calls = 0
        self.add_calls = 0

    def upsert(self, **kwargs):
        self.upsert_calls += 1
        self.last_kwargs = kwargs

    def add(self, **kwargs):
        self.add_calls += 1


class FakeClient:
    def persist(self):
        pass


def test_add_documents_uses_upsert_by_default():
    store = ChromaVectorStore(config={"collection_name": "test"})
    store.client = FakeClient()
    store.collection = FakeCollection()

    docs = [{"id": "public.orders", "text": "orders table", "metadata": {"asset_type": "table", "primary_keys": ["id"]}}]
    embeddings = [[0.1] * 384]

    store.add_documents(docs, embeddings)

    assert store.collection.upsert_calls == 1
    assert store.collection.add_calls == 0
    assert store.collection.last_kwargs["ids"] == ["public.orders"]


def test_sanitize_metadata_converts_lists():
    md = ChromaVectorStore._sanitize_metadata({"primary_keys": ["id", "name"], "count": 2})
    assert isinstance(md["primary_keys"], str)
    assert md["count"] == 2
