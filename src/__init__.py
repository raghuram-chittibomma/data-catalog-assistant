"""
Data Catalog Assistant — RAG-based warehouse catalog POC
An AI-powered assistant for data lineage analysis and query generation.
"""

__version__ = "0.1.0"
__author__ = "Your Team"

from src.core.rag_engine import RAGEngine
from src.vector_store.vector_db import ChromaVectorStore

__all__ = ["RAGEngine", "ChromaVectorStore"]
