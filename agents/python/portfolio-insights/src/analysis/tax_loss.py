"""
Check 3: TAX-LOSS HARVESTING ideas (tax-loss-harvesting.md).

Rules applied:
  * Only TAXABLE accounts. A loss inside an IRA can't be deducted, so it's ignored.
  * Only losses of at least TLH_MIN_LOSS_USD (default $1,000).
  * WASH-SALE check: if the same security was BOUGHT in ANY household account
    (IRAs included) within 30 days, selling now would have the loss disallowed.
    Those ideas are kept but flagged, so the advisor knows why to wait.
  * Suggest replacements that are similar but not substantially identical
    (from get_security_info), to stay invested.
"""
from __future__ import annotations

from datetime import date, timedelta

from schemas.models import TaxLossIdea


def find_tax_loss_ideas(positions: list[dict], trades: list[dict], replacements: dict[str, list[str]],
                        as_of: str, min_loss: float, wash_days: int) -> list[TaxLossIdea]:
    cutoff = date.fromisoformat(as_of) - timedelta(days=wash_days)
    recent_buys: dict[str, list[dict]] = {}
    for t in trades:
        if t["side"] == "buy" and date.fromisoformat(t["date"]) >= cutoff:
            recent_buys.setdefault(t["symbol"], []).append(t)

    ideas = []
    for p in positions:
        loss = -p["unrealized_gain_loss"]
        if p["account_type"] != "taxable" or loss < min_loss:
            continue
        buys = recent_buys.get(p["symbol"], [])
        if buys:
            b = buys[0]
            note = (f"WAIT: {p['symbol']} was bought in {b['account_id']} on {b['date']}. Selling within "
                    f"{wash_days} days of a purchase triggers the wash-sale rule and the loss is disallowed.")
        else:
            alt = ", ".join(replacements.get(p["symbol"], [])) or "a similar, not substantially identical fund"
            note = (f"Sell to realize a ${loss:,.0f} loss; buy {alt} to stay invested. Avoid buying "
                    f"{p['symbol']} in any household account for {wash_days} days.")
        ideas.append(TaxLossIdea(symbol=p["symbol"], name=p["name"], account_id=p["account_id"],
                                 unrealized_loss=round(loss, 2),
                                 replacements=replacements.get(p["symbol"], []),
                                 wash_sale_risk=bool(buys), note=note))
    return sorted(ideas, key=lambda i: -i.unrealized_loss)
