"""
Librarian settings, read from aurelius\\.env (shared) and knowledge-rag\\.env (overrides).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"

_HERE = Path(__file__).resolve()
AGENT_DIR = _HERE.parents[2]                                     # ...\knowledge-rag
REPO_ROOT = _HERE.parents[5] if len(_HERE.parents) > 5 else AGENT_DIR  # ...\aurelius


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", AGENT_DIR / ".env"), extra="ignore")

    agent_name: str = "librarian"
    port: int = Field(default=8001, validation_alias="LIBRARIAN_PORT")
    service_token: str = ""

    # --- LLM (writes the answer from the retrieved passages) -----------------
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_mock: bool = False
    llm_timeout_s: float = 30.0
    llm_max_tokens: int = 600

    # --- RAG -------------------------------------------------------------------
    # minilm = real semantic embeddings (all-MiniLM-L6-v2, ~80 MB download on first run)
    # hash   = offline keyword-style embeddings (tests, or no internet)
    embedding_provider: Literal["minilm", "hash"] = "minilm"
    docs_dir: Path = REPO_ROOT / "rag" / "data" / "sample-docs"
    chroma_dir: Path = REPO_ROOT / "rag" / "chroma-store"
    collection_prefix: str = "aurelius-knowledge"
    chunk_size: int = 700        # characters per chunk (about 150 words)
    chunk_overlap: int = 120     # characters repeated between neighbouring chunks
    top_k: int = 4               # passages given to the LLM
    min_score: float | None = None  # similarity cut-off; None = provider default
    auto_ingest: bool = True     # index the docs folder at startup if the index is empty
    max_query_chars: int = 2000

    @property
    def use_llm(self) -> bool:
        return not self.llm_mock and bool(self.anthropic_api_key) and self.anthropic_api_key != "replace-me"

    @property
    def collection_name(self) -> str:
        # one collection per embedding model: vectors from different models can't be mixed
        return f"{self.collection_prefix}-{self.embedding_provider}"

    @property
    def effective_min_score(self) -> float:
        if self.min_score is not None:
            return self.min_score
        return 0.30 if self.embedding_provider == "minilm" else 0.12


@lru_cache
def get_settings() -> Settings:
    return Settings()
