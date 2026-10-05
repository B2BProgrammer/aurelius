"""
Analyst settings, read from aurelius\\.env (shared) and portfolio-insights\\.env (overrides).

LEARN: The policy thresholds below are the same numbers written in the
Librarian's policy documents (rebalancing-policy.md, concentration-policy.md,
tax-loss-harvesting.md). In a real firm they'd come from one rules service so
the documents and the code can never disagree.
"""
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

    agent_name: str = "analyst"
    port: int = Field(default=8002, validation_alias="ANALYST_PORT")
    service_token: str = ""

    # --- MCP server with the portfolio data -----------------------------------
    mcp_advisor_tools_url: str = "http://127.0.0.1:8500/mcp"
    mcp_timeout_s: float = 20.0

    # --- LLM (optional) -------------------------------------------------------
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_mock: bool = False
    llm_timeout_s: float = 30.0
    max_agent_turns: int = 6  # cap for the Claude <-> MCP tool loop

    # --- Policy thresholds (match the policy documents) ----------------------
    drift_threshold_pts: float = 5.0          # rebalancing-policy.md
    concentration_review_pct: float = 10.0    # concentration-policy.md
    concentration_escalate_pct: float = 15.0  # concentration-policy.md
    tlh_min_loss_usd: float = 1000.0          # ignore tiny losses
    wash_sale_days: int = 30                  # tax-loss-harvesting.md

    @property
    def use_llm(self) -> bool:
        return not self.llm_mock and bool(self.anthropic_api_key) and self.anthropic_api_key != "replace-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
