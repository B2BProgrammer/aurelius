"""
Step 4 of RAG: STORE vectors in ChromaDB, and SEARCH them.

LEARN: ChromaDB runs EMBEDDED here: it's a Python library that saves to a
folder (aurelius\\rag\\chroma-store). No server to install or start. In
production you'd run Chroma as a server, or use a managed service such as
Pinecone, but the code barely changes: add vectors, query vectors.

A "collection" is like a table. Each record holds:
  id         a stable id per chunk (so re-ingesting replaces, not duplicates)
  embedding  the vector
  document   the chunk text
  metadata   source, title, section, doc_type, effective_date...
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import chromadb

from rag.chunker import Chunk


@dataclass
class Hit:
    id: str
    text: str
    metadata: dict
    score: float  # cosine similarity, 0..1


class VectorStore:
    def __init__(self, path: Path, collection: str):
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        # cosine distance: distance = 1 - similarity
        self.col = self.client.get_or_create_collection(
            collection, metadata={"hnsw:space": "cosine"}, embedding_function=None)

    def count(self) -> int:
        return self.col.count()

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        self.col.upsert(ids=[c.id for c in chunks], embeddings=vectors,
                        documents=[c.text for c in chunks], metadatas=[c.metadata for c in chunks])

    def delete_source(self, source: str) -> None:
        self.col.delete(where={"source": source})

    def sources(self) -> dict[str, dict]:
        """{source: {title, doc_type, effective_date, chunks}}"""
        data = self.col.get(include=["metadatas"])
        out: dict[str, dict] = defaultdict(lambda: {"chunks": 0})
        for meta in data["metadatas"] or []:
            entry = out[meta["source"]]
            entry.update(title=meta["title"], doc_type=meta["doc_type"],
                         effective_date=meta["effective_date"])
            entry["chunks"] += 1
        return dict(out)

    def search(self, vector: list[float], k: int, doc_type: str | None = None) -> list[Hit]:
        if self.count() == 0:
            return []
        res = self.col.query(query_embeddings=[vector], n_results=min(k, self.count()),
                             where={"doc_type": doc_type} if doc_type else None,
                             include=["documents", "metadatas", "distances"])
        return [Hit(id=i, text=d, metadata=m, score=round(1 - dist, 4))
                for i, d, m, dist in zip(res["ids"][0], res["documents"][0],
                                         res["metadatas"][0], res["distances"][0])]
