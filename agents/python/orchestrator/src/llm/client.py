"""
LLM client: the ONLY file in the Conductor that talks to Claude.

LEARN: Wrapping the SDK in one small class (an "LLM gateway") means:
  * switching model = change one env var
  * cost and token usage are logged in one place
  * tests run with the fake LLM, no API key or money needed
  * security rules (timeouts, retries, no secrets in logs) live in one spot
"""
from __future__ import annotations

import logging
from typing import Any

from core.config import Settings

log = logging.getLogger("conductor.llm")

# USD per million tokens (input, output). Used only to log estimated cost.
_PRICES = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    for prefix, (p_in, p_out) in _PRICES.items():
        if model.startswith(prefix):
            return (input_tokens * p_in + output_tokens * p_out) / 1_000_000
    return 0.0


class LLMError(RuntimeError):
    """Raised when the LLM call fails; callers fall back to rule-based logic."""


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mock = settings.use_mock_llm
        self._client = None
        if self.mock:
            log.warning("LLM is in MOCK mode (no API key or LLM_MOCK=true). No real Claude calls.")
        else:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.llm_timeout_s,
                max_retries=2,  # SDK retries rate limits and 5xx with backoff
            )

    @staticmethod
    def _system_blocks(system: str) -> list[dict[str, Any]]:
        # LEARN: cache_control marks the system prompt for prompt caching.
        # Repeated calls with the same prompt are billed at ~10% for that part.
        # (Very short prompts are below the cache minimum and simply aren't cached.)
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _log_usage(self, model: str, usage: Any, purpose: str) -> None:
        cost = _estimate_cost(model, usage.input_tokens, usage.output_tokens)
        log.info(
            "llm_call purpose=%s model=%s in_tokens=%s out_tokens=%s est_cost_usd=%.5f",
            purpose, model, usage.input_tokens, usage.output_tokens, cost,
        )

    async def complete(self, system: str, user: str, *, purpose: str, model: str | None = None,
                       max_tokens: int | None = None) -> str:
        """Plain text in, plain text out."""
        if self.mock:
            raise LLMError("mock mode")  # callers use their own fallback text
        model = model or self.settings.llm_model
        try:
            resp = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens or self.settings.llm_max_tokens,
                system=self._system_blocks(system),
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # network, auth, rate limit after retries...
            log.error("llm_call_failed purpose=%s error=%s", purpose, type(exc).__name__)
            raise LLMError(str(exc)) from exc
        self._log_usage(model, resp.usage, purpose)
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    async def complete_with_tool(self, system: str, user: str, tool: dict[str, Any], *,
                                 purpose: str, model: str | None = None) -> dict[str, Any]:
        """
        Structured output: force Claude to answer by "calling" one tool.

        LEARN: tool_choice={"type": "tool", ...} makes Claude return arguments
        that follow the tool's JSON schema, which is far more reliable than
        asking for JSON in plain text and parsing it.
        """
        if self.mock:
            raise LLMError("mock mode")
        model = model or self.settings.llm_model
        try:
            resp = await self._client.messages.create(
                model=model,
                max_tokens=self.settings.llm_max_tokens,
                system=self._system_blocks(system),
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            )
        except Exception as exc:
            log.error("llm_call_failed purpose=%s error=%s", purpose, type(exc).__name__)
            raise LLMError(str(exc)) from exc
        self._log_usage(model, resp.usage, purpose)
        for block in resp.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise LLMError("model did not return the expected tool call")
