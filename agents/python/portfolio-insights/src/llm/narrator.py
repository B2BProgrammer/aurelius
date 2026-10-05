"""
Turns the computed facts into a short summary for the advisor.

LEARN: Claude gets FACTS (already computed, as JSON) and only writes prose.
It's told never to introduce numbers that aren't in the facts. Without an API
key, a template writes the same summary deterministically, for free.
"""
from __future__ import annotations

import json
import logging

from core.config import Settings

log = logging.getLogger("analyst.narrator")

SYSTEM = """You write portfolio review notes for a financial advisor at Aurelius Wealth.
You receive pre-computed facts as JSON inside <facts> tags. Write 3 to 5 plain sentences:
the headline issue first, then what to do. Use ONLY numbers that appear in the facts.
Never compute new numbers, never promise returns, never give tax advice beyond what the facts say.
If the facts show no issues, say so in one sentence."""


def template_summary(f: dict) -> str:
    parts = [f"{f['household']} (${f['total_value']:,.0f}, {f['risk_profile']} profile, data as of {f['as_of']})."]
    alloc = f["allocation"]
    parts.append("; ".join(alloc["flags"]) + ". Rebalance." if alloc["needs_rebalance"]
                 else "Allocation is within the 5-point tolerance.")
    for c in f["concentration"]:
        parts.append(f"{c['name']} is {c['weight_pct']:.1f}% of assets ({c['level']}).")
    for i in f["tax_loss_ideas"]:
        status = "is blocked for now by the wash-sale rule" if i["wash_sale_risk"] else "can be harvested"
        parts.append(f"{i['symbol']} has a ${i['unrealized_loss']:,.0f} loss in a taxable account that {status}.")
    if not alloc["needs_rebalance"] and not f["concentration"] and not f["tax_loss_ideas"]:
        parts.append("No action needed.")
    return " ".join(parts)


class Narrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        if settings.use_llm:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key,
                                         timeout=settings.llm_timeout_s, max_retries=2)

    async def summarize(self, facts: dict) -> tuple[str, str]:
        if self.client is None:
            return template_summary(facts), "template"
        try:
            resp = await self.client.messages.create(
                model=self.settings.llm_model, max_tokens=400,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": f"<facts>\n{json.dumps(facts, indent=1)}\n</facts>"}])
            log.info("llm_call purpose=summary model=%s in_tokens=%s out_tokens=%s",
                     self.settings.llm_model, resp.usage.input_tokens, resp.usage.output_tokens)
            return "".join(b.text for b in resp.content if b.type == "text").strip(), self.settings.llm_model
        except Exception as exc:
            log.warning("llm_failed error=%s, using template", type(exc).__name__)
            return template_summary(facts), "template"
