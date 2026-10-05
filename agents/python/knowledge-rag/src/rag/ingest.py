"""
The INGESTION pipeline: folder of documents -> searchable index.

    load  ->  chunk  ->  safety check  ->  embed  ->  store
   (loader)  (chunker)    (safety)      (embeddings)  (store)

LEARN: Ingestion is idempotent: run it as often as you like.
  * Each document's old chunks are deleted before its new ones are added,
    so an edited policy never leaves stale passages behind.
  * Documents deleted from the folder are removed from the index.
"""
from __future__ import annotations

import logging
import time

from core.config import Settings
from rag.chunker import chunk_document
from rag.embeddings import Embedder
from rag.loader import load_documents
from rag.safety import check_chunk
from rag.store import VectorStore
from schemas.models import IngestReport

log = logging.getLogger("librarian.ingest")


def run_ingest(settings: Settings, store: VectorStore, embedder: Embedder) -> IngestReport:
    start = time.perf_counter()
    docs = load_documents(settings.docs_dir)
    quarantined: list[dict[str, str]] = []
    total_chunks = 0

    for doc in docs:
        chunks = chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
        safe = []
        for c in chunks:
            reason = check_chunk(c.text)
            if reason:
                quarantined.append({"source": doc.source, "section": c.metadata["section"], "reason": reason})
                log.warning("chunk_quarantined source=%s section=%s reason=%s",
                            doc.source, c.metadata["section"], reason)
            else:
                safe.append(c)
        store.delete_source(doc.source)
        store.upsert(safe, embedder.embed([c.text for c in safe]) if safe else [])
        total_chunks += len(safe)
        log.info("ingested source=%s chunks=%d quarantined=%d",
                 doc.source, len(safe), len(chunks) - len(safe))

    on_disk = {d.source for d in docs}
    removed = [s for s in store.sources() if s not in on_disk]
    for source in removed:
        store.delete_source(source)
        log.info("removed source=%s (no longer in docs folder)", source)

    report = IngestReport(documents=len(docs), chunks=total_chunks, quarantined=quarantined,
                          removed_sources=removed, embedding_provider=embedder.name,
                          duration_ms=int((time.perf_counter() - start) * 1000))
    log.info("ingest_done documents=%d chunks=%d quarantined=%d ms=%d",
             report.documents, report.chunks, len(quarantined), report.duration_ms)
    return report
