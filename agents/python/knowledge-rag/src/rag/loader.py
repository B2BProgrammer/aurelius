"""
Step 1 of RAG: LOAD documents from a folder.

Each .md / .txt file may start with "front matter", a small header of
key: value pairs between --- lines:

    ---
    title: Single-Stock Concentration Policy
    doc_type: policy
    effective_date: 2026-01-15
    ---

LEARN: Metadata is as important as the text. It lets us cite the exact
document and date, filter by type ("only policies"), and later enforce who
may see what.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".md", ".txt"}


@dataclass
class Document:
    source: str                      # file name, e.g. concentration-policy.md
    text: str                        # body without the front matter
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.metadata.get("title", self.source)


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, parts[2].lstrip("\n")


def load_documents(folder: Path) -> list[Document]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Documents folder not found: {folder}")
    docs = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in SUPPORTED or path.name.startswith("."):
            continue
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        meta.setdefault("doc_type", "guide")
        meta.setdefault("effective_date", "unknown")
        docs.append(Document(source=path.name, text=body, metadata=meta))
    return docs
