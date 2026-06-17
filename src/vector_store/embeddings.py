"""
Local embedding service — sentence-transformers (ChromaDB stack).
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Abstract base class for embedding services."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Convert text to embedding vector."""
        pass

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Convert multiple texts to embedding vectors."""
        pass


class LocalEmbedding(EmbeddingService):
    """
    Local embedding service using sentence-transformers.
    Good for privacy and offline usage.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize local embedding service.

        Args:
            model_name: HuggingFace model name
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"Initialized Local Embedding Service with model: {model_name}")

    def _load_model(self):
        if self.model is None:
            # Prefer sentence-transformers for convenience API
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                self._use_sentence_transformers = True
                return self.model
            except Exception:
                self._use_sentence_transformers = False

            # Fallback: use Hugging Face transformers directly (mean pooling)
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer

                tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                model = AutoModel.from_pretrained(self.model_name)
                model.eval()
                self.model = (tokenizer, model)
                self._use_transformers = True
                self._torch = torch
                return self.model
            except Exception as e:
                raise ImportError(
                    "No local embedding backend available. Install sentence-transformers or transformers."
                ) from e
        return self.model

    def embed_text(self, text: str) -> list[float]:
        """Convert text to embedding."""
        logger.debug(f"Embedding text: {text[:50]}...")
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Convert multiple texts to embeddings."""
        if not texts:
            return []
        logger.debug(f"Embedding {len(texts)} texts")
        model = self._load_model()

        # If sentence-transformers model is available, use its encode
        if getattr(self, "_use_sentence_transformers", False):
            embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
            if hasattr(embeddings, "tolist"):
                return [emb.tolist() for emb in embeddings]
            return [list(vector) for vector in embeddings]

        # If Transformers fallback is available, compute embeddings via mean pooling
        if getattr(self, "_use_transformers", False):
            tokenizer, hf_model = model
            torch = self._torch
            all_embeddings = []
            batch_size = 16
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                inputs = tokenizer(batch, padding=True, truncation=True, return_tensors="pt")
                with torch.no_grad():
                    outputs = hf_model(
                        **{
                            k: v.to(hf_model.device) if hasattr(hf_model, "device") else v
                            for k, v in inputs.items()
                        }
                    )
                    last_hidden = outputs.last_hidden_state
                    # mean pooling excluding padding tokens
                    attention_mask = inputs.get("attention_mask")
                    if attention_mask is None:
                        pooled = last_hidden.mean(dim=1)
                    else:
                        mask = attention_mask.unsqueeze(-1).expand(last_hidden.size()).float()
                        summed = (last_hidden * mask).sum(1)
                        counted = mask.sum(1).clamp(min=1e-9)
                        pooled = summed / counted
                    # convert to CPU numpy and extend
                    vecs = pooled.cpu().numpy()
                    for v in vecs:
                        all_embeddings.append(v.tolist())
            return all_embeddings

        raise RuntimeError("No local embedding backend available")
