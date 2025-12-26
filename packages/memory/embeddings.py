from __future__ import annotations

import hashlib
import os
import random
from typing import Protocol

EMBEDDING_DIM = 384


class EmbeddingProvider(Protocol):
    def is_available(self) -> bool:
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class OffEmbeddingProvider:
    def is_available(self) -> bool:
        return False

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return []


class FakeEmbeddingProvider:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def is_available(self) -> bool:
        return True

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]


class SentenceTransformerProvider:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def is_available(self) -> bool:
        return True

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def get_embedding_provider() -> EmbeddingProvider:
    mode = os.getenv("EMBEDDINGS_MODE", "off").lower()
    if mode == "fake":
        return FakeEmbeddingProvider()
    if mode == "local":
        model_name = os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
        try:
            return SentenceTransformerProvider(model_name)
        except Exception:
            return OffEmbeddingProvider()
    return OffEmbeddingProvider()
