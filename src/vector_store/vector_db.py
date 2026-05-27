"""
Vector database interface — ChromaDB implementation.
"""

import logging
from typing import List, Dict, Any, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def connect(self):
        """Connect to vector database."""
        pass

    @abstractmethod
    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]):
        """
        Add documents with their embeddings.

        Args:
            documents: List of documents (with metadata)
            embeddings: List of embedding vectors
        """
        pass

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[Dict, float]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results

        Returns:
            List of (document, similarity_score) tuples
        """
        pass

    @abstractmethod
    def update_document(self, doc_id: str, metadata: Dict[str, Any]):
        """Update document metadata."""
        pass

    @abstractmethod
    def delete_document(self, doc_id: str):
        """Delete document from store."""
        pass

    @abstractmethod
    def clear(self):
        """Clear all documents from store."""
        pass

    @abstractmethod
    def persist(self):
        """Persist the store to durable storage."""
        pass


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store (embedded persistent or in-memory client)."""

    def __init__(self, config=None):
        """Initialize Chroma store."""
        self.config = config or {}
        self.client = None
        self.collection = None
        self.backend = "chroma"
        logger.info("Initialized Chroma VectorStore")

    def connect(self):
        """Connect to Chroma database."""
        try:
            import chromadb

            persist_directory = None
            chroma_impl = None
            # Accept config keys: backend.persist_directory, chroma_impl
            backend_conf = self.config.get("backend", {}) if isinstance(self.config, dict) else {}
            persist_directory = backend_conf.get("persist_directory") or self.config.get("persist_directory")
            chroma_db_impl = backend_conf.get("chroma_db_impl") or self.config.get("chroma_db_impl")
            chroma_api_impl = backend_conf.get("chroma_api_impl") or self.config.get("chroma_api_impl")
            chroma_impl = backend_conf.get("chroma_impl") or self.config.get("chroma_impl")

            if persist_directory:
                if chroma_db_impl or chroma_impl or chroma_api_impl:
                    logger.warning(
                        "Custom Chroma implementation config keys are not supported by the current installed Chroma version. "
                        "Persisting to the specified directory with the default persistent client."
                    )
                self.client = chromadb.PersistentClient(path=persist_directory)
            else:
                # in-memory client
                self.client = chromadb.EphemeralClient()

            collection_name = self.config.get("collection_name", "bdw_rag_collection")
            # create or get collection
            try:
                self.collection = self.client.get_collection(name=collection_name)
            except Exception:
                self.collection = self.client.create_collection(name=collection_name)

            logger.info("Connected to Chroma")
        except Exception as e:
            logger.error(f"Failed to initialize Chroma client: {e}")
            raise

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
        upsert: bool = True,
    ):
        """Add or upsert documents in Chroma (upsert avoids duplicate ID errors on refresh)."""
        if not self.client or not self.collection:
            self.connect()

        if not documents:
            return

        ids = []
        docs = []
        metadatas = []

        for i, doc in enumerate(documents):
            doc_id = doc.get("id") or doc.get("doc_id") or f"doc-{i}"
            ids.append(str(doc_id))
            docs.append(doc.get("text") or doc.get("content") or "")
            md = doc.get("metadata") or {
                k: v for k, v in doc.items() if k not in ("id", "doc_id", "text", "content")
            }
            metadatas.append(self._sanitize_metadata(md))

        try:
            write_kwargs = {
                "ids": ids,
                "documents": docs,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }
            if upsert and hasattr(self.collection, "upsert"):
                self.collection.upsert(**write_kwargs)
                logger.debug(f"Upserted {len(documents)} documents into Chroma")
            else:
                self.collection.add(**write_kwargs)
                logger.debug(f"Added {len(documents)} documents to Chroma")
            self.persist()
        except Exception as e:
            logger.error(f"Error writing documents to Chroma: {e}")
            raise

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Chroma metadata values must be str, int, float, or bool."""
        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                sanitized[key] = str(value)
            else:
                sanitized[key] = str(value)
        return sanitized

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search Chroma for similar documents."""
        if not self.client or not self.collection:
            self.connect()

        try:
            result = self.collection.query(query_embeddings=[query_embedding], n_results=top_k, include=["metadatas", "documents", "distances"])
            results = []
            # result is a dict with lists
            distances_list = result.get("distances", [[]])[0]
            docs_list = result.get("documents", [[]])[0]
            metas_list = result.get("metadatas", [[]])[0]
            ids_list = result.get("ids", [[]])[0]

            for idx, d in enumerate(distances_list):
                # convert distance to a similarity-like score in (0,1]
                try:
                    dist = float(d)
                except Exception:
                    dist = d
                if isinstance(dist, float) and 0.0 <= dist <= 1.0:
                    score = 1.0 - dist
                else:
                    try:
                        score = 1.0 / (1.0 + float(dist))
                    except Exception:
                        score = 0.0

                doc = {
                    "id": ids_list[idx] if idx < len(ids_list) else None,
                    "text": docs_list[idx] if idx < len(docs_list) else None,
                    "metadata": metas_list[idx] if idx < len(metas_list) else None,
                }
                results.append((doc, score))

            return results
        except Exception as e:
            logger.error(f"Error searching Chroma: {e}")
            return []

    def update_document(self, doc_id: str, metadata: Dict[str, Any]):
        """Update document in Chroma."""
        if not self.client or not self.collection:
            self.connect()

        try:
            # chroma collection supports update(ids=..., metadatas=..., documents=...)
            self.collection.update(ids=[str(doc_id)], metadatas=[metadata])
            logger.debug(f"Updated document: {doc_id}")
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {e}")

    def delete_document(self, doc_id: str):
        """Delete document from Chroma."""
        if not self.client or not self.collection:
            self.connect()

        try:
            self.collection.delete(ids=[str(doc_id)])
            logger.debug(f"Deleted document: {doc_id}")
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")

    def clear(self):
        """Clear all documents from Chroma."""
        if not self.client:
            self.connect()

        try:
            # reset will clear all collections for this client
            self.client.reset()
            logger.warning("Cleared all documents from Chroma (client.reset())")
        except Exception as e:
            logger.error(f"Error clearing Chroma: {e}")

    def persist(self):
        """Persist the Chroma client state to disk."""
        if not self.client:
            return

        try:
            if hasattr(self.client, "persist"):
                self.client.persist()
                logger.debug("Persisted Chroma client state")
        except Exception as e:
            logger.warning(f"Could not persist Chroma client state: {e}")

    def close(self):
        """Close the Chroma client and release resources."""
        if self.client:
            self.persist()
            if hasattr(self.client, "reset_state"):
                try:
                    self.client.reset_state()
                except Exception as e:
                    logger.warning(f"Error resetting Chroma client state: {e}")
            if hasattr(self.client, "stop"):
                try:
                    self.client.stop()
                    logger.info("Stopped Chroma client")
                except Exception as e:
                    logger.error(f"Error stopping Chroma client: {e}")
        self.client = None
        self.collection = None
