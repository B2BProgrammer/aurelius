"""
Settings for the Conductor.

LEARN: Never hard-code secrets or URLs. pydantic-settings reads every field
below from environment variables or .env files (field `llm_model` <- env var
`LLM_MODEL`). Values are type-checked, so `AUTH_REQUIRED=yes` fails at startup
instead of causing a strange bug later.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"


def _env_files() -> tuple[Path, ...]:
    """Root aurelius/.env first, then the agent's own .env (which wins)."""
    here = Path(__file__).resolve()
    agent_dir = here.parents[2]  # .../orchestrator
    files = []
    if len(here.parents) > 5:
        files.append(here.parents[5] / ".env")  # .../aurelius/.env
    files.append(agent_dir / ".env")
    return tuple(files)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files(), extra="ignore")

    # --- Identity -------------------------------------------------------------
    agent_name: str = "conductor"
    port: int = 8000
    # 127.0.0.1 = this computer only (safe default). 0.0.0.0 = also your Wi-Fi network,
    # needed only to test the Flutter app on a real phone. Every other agent stays private.
    conductor_host: str = "127.0.0.1"

    # --- LLM ------------------------------------------------------------------
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    conductor_model: str = ""  # optional: a stronger model just for planning
    llm_max_tokens: int = 1500
    llm_timeout_s: float = 60.0
    llm_mock: bool = False

    # --- Other agents ---------------------------------------------------------
    mock_agents: bool = True
    real_agents: str = ""  # e.g. "sentinel,librarian": these are called for real even when MOCK_AGENTS=true
    agent_timeout_s: float = 20.0
    service_token: str = ""
    sentinel_fail_mode: Literal["closed", "open"] = "closed"

    sentinel_url: str = "http://127.0.0.1:8004"
    librarian_url: str = "http://127.0.0.1:8001"
    analyst_url: str = "http://127.0.0.1:8002"
    scribe_url: str = "http://127.0.0.1:8003"
    herald_url: str = "http://127.0.0.1:8101"
    liaison_url: str = "http://127.0.0.1:8102"
    notary_url: str = "http://127.0.0.1:8201"
    actuary_url: str = "http://127.0.0.1:8202"
    pulse_url: str = "http://127.0.0.1:8301"

    # --- Security -------------------------------------------------------------
    auth_required: bool = True
    jwt_signing_key: str = ""
    jwt_issuer: str = "aurelius-dev"
    jwt_audience: str = "aurelius"
    # Which web pages may call this API from a browser: the Atrium web app (Vite dev server).
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Dev sign-in for the apps (stand-in for company SSO). Empty = disabled.
    dev_login_password: str = ""
    login_token_minutes: int = Field(default=480, ge=5, le=1440)
    max_message_chars: int = Field(default=4000, ge=100, le=20000)

    # --- Limits (protect cost and latency) ------------------------------------
    max_plan_stages: int = 4
    max_plan_steps: int = 8

    @property
    def use_mock_llm(self) -> bool:
        """Fall back to the fake LLM when there is no API key."""
        return self.llm_mock or not self.anthropic_api_key or self.anthropic_api_key == "replace-me"

    @property
    def real_agent_set(self) -> set[str]:
        return {a.strip().lower() for a in self.real_agents.split(",") if a.strip()}

    def is_mocked(self, agent: str) -> bool:
        return self.mock_agents and agent not in self.real_agent_set

    @property
    def planner_model(self) -> str:
        return self.conductor_model or self.llm_model

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
