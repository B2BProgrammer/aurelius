"""
Step 2 of RAG: CHUNK documents into small passages.

LEARN: Why chunk at all?
  * Embeddings work best on focused text: one topic per vector.
  * We send only the few most relevant passages to the LLM, which is cheaper
    and more accurate than sending whole documents.

How we chunk:
  1. Split on markdown headings, so a chunk never mixes two sections.
  2. Pack paragraphs into chunks of about CHUNK_SIZE characters.
  3. Repeat the last paragraph of a chunk at the start of the next one
     (OVERLAP), so a sentence near a boundary is never cut off from its context.
  4. Prefix each chunk with "Title > Section" so the vector "knows" where it came from.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from rag.loader import Document

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


@dataclass
class Chunk:
    id: str
    text: str            # what gets embedded and shown to the LLM
    metadata: dict


def _sections(text: str) -> list[tuple[str, str]]:
    """[(section heading, section body)] in document order."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [("", text)]
    out = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        out.append(("", text[: matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(2).strip(), text[m.end():end]))
    return out


def _pack(paragraphs: list[str], size: int, overlap: int) -> list[str]:
    chunks, current = [], []
    for para in paragraphs:
        if current and len("\n\n".join(current + [para])) > size:
            chunks.append("\n\n".join(current))
            tail = current[-1] if len(current[-1]) <= overlap else current[-1][-overlap:]
            current = [tail] if overlap else []
        current.append(para)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_document(doc: Document, size: int = 700, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    carried: list[str] = []  # headings with no text of their own, e.g. "## Rating: Hold"
    for section, body in _sections(doc.text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if not paragraphs:
            if section:
                carried.append(section)  # keep it: it often carries the key fact
            continue
        if carried:
            paragraphs.insert(0, ". ".join(carried) + ".")
            carried = []
        for piece in _pack(paragraphs, size, overlap):
            header = f"{doc.title} > {section}" if section else doc.title
            index = len(chunks)
            chunk_id = hashlib.sha1(f"{doc.source}#{index}".encode()).hexdigest()[:16]
            chunks.append(Chunk(
                id=chunk_id,
                text=f"{header}\n{piece}",
                metadata={
                    "source": doc.source,
                    "title": doc.title,
                    "section": section or doc.title,
                    "doc_type": doc.metadata.get("doc_type", "guide"),
                    "effective_date": doc.metadata.get("effective_date", "unknown"),
                    "version": doc.metadata.get("version", ""),
                    "chunk_index": index,
                },
            ))
    return chunks
