"""
Check 2: SINGLE-STOCK CONCENTRATION (concentration-policy.md).
  > 10 %  of household assets in one stock  -> review with client
  > 15 %                                     -> escalate to branch manager

LEARN: The rule applies to individual STOCKS, not diversified funds. A 40 %
position in a total-market index fund is not "concentrated" in the policy's
sense, so we filter on security_type. Getting the rule's scope right matters
as much as getting the arithmetic right.
"""
from __future__ import annotations

from collections import defaultdict

from schemas.models import ConcentrationFlag


def check_concentration(positions: list[dict], review_pct: float, escalate_pct: float) -> list[ConcentrationFlag]:
    total = sum(p["market_value"] for p in positions) or 1.0
    stock_value: dict[str, float] = defaultdict(float)
    names: dict[str, str] = {}
    for p in positions:
        if p["security_type"] == "stock":      # same stock across accounts counts together
            stock_value[p["symbol"]] += p["market_value"]
            names[p["symbol"]] = p["name"]

    flags = []
    for symbol, value in sorted(stock_value.items(), key=lambda kv: -kv[1]):
        weight = round(value / total * 100, 1)
        if weight > escalate_pct:
            flags.append(ConcentrationFlag(
                symbol=symbol, name=names[symbol], weight_pct=weight, level="escalate",
                message=f"{names[symbol]} is {weight:.1f}% of assets (above {escalate_pct:.0f}%): escalate to "
                        f"branch manager within 30 days with a diversification plan or signed acknowledgment."))
        elif weight > review_pct:
            flags.append(ConcentrationFlag(
                symbol=symbol, name=names[symbol], weight_pct=weight, level="review",
                message=f"{names[symbol]} is {weight:.1f}% of assets (above {review_pct:.0f}%): document a "
                        f"conversation with the client at the next review."))
    return flags
