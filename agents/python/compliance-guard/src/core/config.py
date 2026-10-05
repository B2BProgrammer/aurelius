"""
Sentinel settings, read from aurelius\\.env (shared) and compliance-guard\\.env (overrides).

LEARN: Sentinel uses the SAME SERVICE_TOKEN as the Conductor. That shared
secret is how Sentinel knows a request really comes from another agent.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"


def _env_files() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    agent_dir = here.parents[2]  # .../compliance-guard
    files = []
    if len(here.parents) > 5:
        files.append(here.parents[5] / ".env")  # .../aurelius/.env
    files.append(agent_dir / ".env")
    return tuple(files)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files(), extra="ignore")

    agent_name: str = "sentinel"
    port: int = Field(default=8004, validation_alias="SENTINEL_PORT")

    # --- Who may call me ------------------------------------------------------
    service_token: str = ""

    # --- LLM classifier (optional second opinion on borderline injections) ----
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_mock: bool = False
    llm_timeout_s: float = 15.0

    # --- Policy knobs ---------------------------------------------------------
    max_text_chars: int = 20000
    injection_block_score: float = 0.8   # >= this: block outright
    injection_review_score: float = 0.4  # >= this: ask the LLM classifier (if available)

    # --- Audit ----------------------------------------------------------------
    audit_log_path: str = "logs/audit.jsonl"  # relative to compliance-guard folder

    @property
    def use_llm(self) -> bool:
        return not self.llm_mock and bool(self.anthropic_api_key) and self.anthropic_api_key != "replace-me"

    @property
    def audit_path(self) -> Path:
        p = Path(self.audit_log_path)
        return p if p.is_absolute() else Path(__file__).resolve().parents[2] / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
