"""Scribe settings, read from aurelius\\.env (shared) and meeting-intel\\.env (overrides)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"

_HERE = Path(__file__).resolve()
AGENT_DIR = _HERE.parents[2]
REPO_ROOT = _HERE.parents[5] if len(_HERE.parents) > 5 else AGENT_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", AGENT_DIR / ".env"), extra="ignore")

    agent_name: str = "scribe"
    port: int = Field(default=8003, validation_alias="SCRIBE_PORT")
    service_token: str = ""

    notes_dir: Path = AGENT_DIR / "data" / "meetings"
    max_notes_chars: int = 20000      # per meeting; longer transcripts are rejected
    max_meetings: int = 5             # how many recent meetings summarize_meetings reads

    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_mock: bool = False
    llm_timeout_s: float = 45.0

    @property
    def use_llm(self) -> bool:
        return not self.llm_mock and bool(self.anthropic_api_key) and self.anthropic_api_key != "replace-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
