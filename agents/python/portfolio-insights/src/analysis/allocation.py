"""
Check 1: ALLOCATION DRIFT (rebalancing-policy.md: rebalance when an asset class
is more than 5 percentage points away from target).

LEARN: All numbers in the Analyst are computed in CODE, not by the LLM.
LLMs are unreliable at arithmetic; code is exact and testable. The LLM's job
(llm/narrator.py) is only to explain the results in plain English.
"""
from __future__ import annotations

from schemas.models import AllocationCheck

ASSET_CLASSES = ("equity", "fixed_income", "cash")
LABEL = {"equity": "Equity", "fixed_income": "Fixed income", "cash": "Cash"}


def check_allocation(positions: list[dict], target_pct: dict[str, float], threshold_pts: float) -> AllocationCheck:
    total = sum(p["market_value"] for p in positions) or 1.0
    by_class = {ac: 0.0 for ac in ASSET_CLASSES}
    for p in positions:
        by_class[p["asset_class"]] = by_class.get(p["asset_class"], 0.0) + p["market_value"]

    current = {ac: round(v / total * 100, 1) for ac, v in by_class.items()}
    target = {ac: float(target_pct.get(ac, 0)) for ac in by_class}
    drift = {ac: round(current[ac] - target[ac], 1) for ac in by_class}

    flags = []
    for ac, d in drift.items():
        if abs(d) > threshold_pts:
            direction = "over" if d > 0 else "under"
            flags.append(f"{LABEL.get(ac, ac)} is {abs(d):.1f} points {direction} target "
                         f"({current[ac]:.1f}% vs {target[ac]:.0f}%)")
    return AllocationCheck(target_pct=target, current_pct=current, drift_pts=drift,
                           needs_rebalance=bool(flags), flags=flags)
