import hashlib
import random

from langchain_core.embeddings import Embeddings


DEFAULT_EMBEDDING_DIMENSION = 384


class FakeEmbeddingProvider(Embeddings):
    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        seed = _stable_seed(text)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]


def _stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def get_embedding_provider() -> Embeddings:
    return FakeEmbeddingProvider()
