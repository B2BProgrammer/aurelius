"""
analyze_portfolio: the deterministic pipeline.

    MCP get_client_profile ─┐
    MCP get_holdings ───────┼─> allocation drift ─┐
    MCP get_recent_trades ──┤   concentration ────┼─> actions ─> summary (template or Claude)
    MCP get_security_info ──┘   tax-loss ideas ───┘

LEARN: CODE decides which tools to call here, always in the same order. It's
predictable, cheap and auditable: the right shape for a standard report.
Compare with llm/tool_agent.py, where CLAUDE decides which tools to call.
"""
from __future__ import annotations

from analysis.allocation import check_allocation
from analysis.concentration import check_concentration
from analysis.tax_loss import find_tax_loss_ideas
from core.config import Settings
from llm.narrator import Narrator
from mcp_client.client import PortfolioTools, ToolCallError
from schemas.models import AnalysisResult


async def analyze(tools: PortfolioTools, client_id: str, settings: Settings, narrator: Narrator) -> AnalysisResult:
    profile = await tools.call("get_client_profile", client_id=client_id)
    holdings = await tools.call("get_holdings", client_id=client_id)
    trades = await tools.call("get_recent_trades", client_id=client_id, days=settings.wash_sale_days)
    positions = holdings["positions"]

    allocation = check_allocation(positions, profile["target_allocation_pct"], settings.drift_threshold_pts)
    concentration = check_concentration(positions, settings.concentration_review_pct,
                                        settings.concentration_escalate_pct)

    # look up replacement funds only for securities that could be harvested
    replacements: dict[str, list[str]] = {}
    for p in positions:
        if p["account_type"] == "taxable" and -p["unrealized_gain_loss"] >= settings.tlh_min_loss_usd:
            try:
                info = await tools.call("get_security_info", symbol=p["symbol"])
                replacements[p["symbol"]] = info.get("replacements", [])
            except ToolCallError:
                replacements[p["symbol"]] = []
    ideas = find_tax_loss_ideas(positions, trades["trades"], replacements, holdings["as_of"],
                                settings.tlh_min_loss_usd, settings.wash_sale_days)

    actions = list(allocation.flags and [f"Rebalance: {'; '.join(allocation.flags)}. Prefer trades in IRAs "
                                         f"first to avoid realizing gains."])
    actions += [c.message for c in concentration]
    actions += [f"Tax-loss: {i.symbol} in {i.account_id} (${i.unrealized_loss:,.0f}). {i.note}" for i in ideas]
    if not actions:
        actions = ["No action needed: allocation within tolerance, no concentrated stock, no harvestable losses."]

    facts = {
        "household": profile["household"], "risk_profile": profile["risk_profile"],
        "as_of": holdings["as_of"], "total_value": holdings["total_market_value"],
        "allocation": allocation.model_dump(), "concentration": [c.model_dump() for c in concentration],
        "tax_loss_ideas": [i.model_dump() for i in ideas], "actions": actions,
    }
    summary, answered_by = await narrator.summarize(facts)

    return AnalysisResult(
        client_id=client_id, household=profile["household"], as_of=holdings["as_of"],
        total_value=holdings["total_market_value"], allocation=allocation, concentration=concentration,
        tax_loss_ideas=ideas, actions=actions, summary=summary, answered_by=answered_by,
        mcp_tools_used=[c["tool"] for c in tools.calls],
    )
