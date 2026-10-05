"""
Step 3 of RAG: EMBED text into vectors (lists of numbers).

LEARN: An embedding model turns text into a vector so that texts with similar
MEANING end up close together. "When must clients start withdrawals from
their IRA?" lands near the RMD guide even though it shares few words with it.
We compare vectors with COSINE SIMILARITY: 1.0 = same direction, 0 = unrelated.

Two providers:
  minilm  all-MiniLM-L6-v2 through ChromaDB's built-in ONNX runtime.
          384 numbers per text, runs on your CPU, free. Downloads ~80 MB the
          first time and caches it (in your user folder under .cache\\chroma).
  hash    "feature hashing": each word and word pair is hashed into one of
          512 slots. It only matches shared WORDS, not meaning, but needs no
          download. Used by the tests and as an offline fallback.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_STOP = set("a an and are as at be by for from has have how i in is it its of on or that the this "
            "to was what when where which who why will with do does can should my our your their "
            "me we you they".split())


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    name = "hash"

    def __init__(self, dims: int = 512):
        self.dims = dims

    @staticmethod
    def _tokens(text: str) -> list[str]:
        words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]
        return [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words]  # tiny stemmer

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        tokens = self._tokens(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feat in features:
            h = int(hashlib.md5(feat.encode()).hexdigest(), 16)
            vec[h % self.dims] += 1.0 if (h >> 64) & 1 else -1.0
        vec = [math.copysign(math.log1p(abs(v)), v) for v in vec]  # dampen repeated words
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class MiniLMEmbedder:
    name = "minilm"

    def __init__(self):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._fn = DefaultEmbeddingFunction()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._fn(texts)]


def build_embedder(provider: str) -> Embedder:
    return MiniLMEmbedder() if provider == "minilm" else HashEmbedder()
