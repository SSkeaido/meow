import hashlib
import math
import os
import re

from langchain_core.embeddings import Embeddings

from app.integrations.siliconflow import SiliconFlowEmbeddings


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


class HashEmbeddings(Embeddings):
    """Deterministic local embeddings for no-key development.

    This is only a bootstrap embedding provider. It gives us a real vector-store
    flow without sending PDF content to any third-party model.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def get_embeddings() -> Embeddings:
    provider = os.getenv("EMBEDDING_PROVIDER", "hash").lower()
    if provider == "hash":
        dimensions = int(os.getenv("HASH_EMBEDDING_DIMENSIONS", "256"))
        return HashEmbeddings(dimensions=dimensions)
    if provider == "siliconflow":
        return SiliconFlowEmbeddings()
    raise ValueError("EMBEDDING_PROVIDER must be 'hash' or 'siliconflow'")
