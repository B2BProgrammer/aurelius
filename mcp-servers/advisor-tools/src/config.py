"""Settings for the advisor-tools MCP server (reads aurelius\\.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"

_HERE = Path(__file__).resolve()
SERVER_DIR = _HERE.parents[1]                                          # ...\advisor-tools
REPO_ROOT = _HERE.parents[3] if len(_HERE.parents) > 3 else SERVER_DIR  # ...\aurelius


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", SERVER_DIR / ".env"), extra="ignore")

    port: int = Field(default=8500, validation_alias="MCP_PORT")
    host: str = "127.0.0.1"
    service_token: str = ""  # same shared secret the agents use
    data_dir: Path = SERVER_DIR / "data"
    max_trade_lookback_days: int = 365


@lru_cache
def get_settings() -> Settings:
    return Settings()
