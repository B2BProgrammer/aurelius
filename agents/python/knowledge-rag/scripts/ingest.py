"""
Rebuild the knowledge index from the command line (no server needed).

Usage (knowledge-rag folder, venv active):
    python scripts\\ingest.py

Add or edit files in aurelius\\rag\\data\\sample-docs, then run this again.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import get_settings  # noqa: E402
from core.log_setup import setup_logging  # noqa: E402
from rag.embeddings import build_embedder  # noqa: E402
from rag.ingest import run_ingest  # noqa: E402
from rag.store import VectorStore  # noqa: E402

setup_logging()
s = get_settings()
print(f"Docs folder : {s.docs_dir}")
print(f"Index folder: {s.chroma_dir}  (collection {s.collection_name})")
report = run_ingest(s, VectorStore(s.chroma_dir, s.collection_name), build_embedder(s.embedding_provider))
print(json.dumps(report.model_dump(), indent=2))
