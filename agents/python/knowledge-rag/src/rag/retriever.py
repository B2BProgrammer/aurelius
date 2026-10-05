"""
Step 5 of RAG: RETRIEVE the best passages for a question.

  question -> embed -> nearest chunks in Chroma -> drop weak matches -> top K

LEARN: The minimum-score cut-off is an anti-hallucination tool. If nothing in
the documents is close enough, we return NOTHING, and the answer says "not
found in the firm's documents" instead of letting the LLM guess.
"""
from __future__ import annotations

from rag.embeddings import Embedder
from rag.store import Hit, VectorStore


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder, min_score: float):
        self.store, self.embedder, self.min_score = store, embedder, min_score

    def retrieve(self, query: str, top_k: int, doc_type: str | None = None) -> list[Hit]:
        vector = self.embedder.embed([query])[0]
        candidates = self.store.search(vector, k=top_k * 3, doc_type=doc_type)
        best: dict[tuple[str, str], Hit] = {}
        for hit in candidates:
            if hit.score < self.min_score:
                continue
            key = (hit.metadata["source"], hit.metadata["section"])  # one passage per section
            if key not in best or hit.score > best[key].score:
                best[key] = hit
        return sorted(best.values(), key=lambda h: h.score, reverse=True)[:top_k]
