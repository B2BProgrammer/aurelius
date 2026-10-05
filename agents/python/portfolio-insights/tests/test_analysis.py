"""Unit tests for the three checks (pure functions, no MCP, no LLM)."""
from analysis.allocation import check_allocation
from analysis.concentration import check_concentration
from analysis.tax_loss import find_tax_loss_ideas

from conftest import CLIENTS, pos

BUSY = CLIENTS["busy-01"]["positions"]
TARGET = {"equity": 60, "fixed_income": 35, "cash": 5}


def test_drift_and_flags():
    a = check_allocation(BUSY, TARGET, 5.0)
    assert a.current_pct == {"equity": 70.0, "fixed_income": 20.0, "cash": 10.0}
    assert a.drift_pts == {"equity": 10.0, "fixed_income": -15.0, "cash": 5.0}
    assert a.needs_rebalance and len(a.flags) == 2   # cash exactly 5.0 is NOT over the threshold


def test_on_target_needs_nothing():
    assert not check_allocation(CLIENTS["calm-02"]["positions"],
                                {"equity": 40, "fixed_income": 55, "cash": 5}, 5.0).needs_rebalance


def test_concentration_only_counts_stocks():
    flags = check_concentration(BUSY, 10, 15)
    assert [(f.symbol, f.level) for f in flags] == [("BIGCO", "escalate")]  # 50 % fund is NOT flagged


def test_concentration_levels():
    def weight(pct):
        return [pos("A", "taxable", "BIGCO", pct, pct), pos("A", "taxable", "TOTAL", 100 - pct, 100 - pct)]
    assert check_concentration(weight(9), 10, 15) == []
    assert check_concentration(weight(12), 10, 15)[0].level == "review"
    assert check_concentration(weight(16), 10, 15)[0].level == "escalate"


def test_same_stock_in_two_accounts_is_added_up():
    p = [pos("A", "taxable", "BIGCO", 6, 6), pos("B", "ira", "BIGCO", 6, 6), pos("A", "taxable", "TOTAL", 88, 88)]
    assert check_concentration(p, 10, 15)[0].weight_pct == 12.0


def test_tax_loss_only_taxable_and_above_minimum():
    ideas = find_tax_loss_ideas(BUSY, [], {"BOND": ["BOND2"]}, "2026-10-01", 1000, 30)
    assert [(i.symbol, i.account_id, i.unrealized_loss) for i in ideas] == [("BOND", "B-TAX", 5000.0)]
    assert ideas[0].replacements == ["BOND2"] and not ideas[0].wash_sale_risk


def test_wash_sale_detected_across_accounts():
    trades = [{"date": "2026-09-20", "account_id": "B-IRA", "symbol": "BOND", "side": "buy"}]
    idea = find_tax_loss_ideas(BUSY, trades, {}, "2026-10-01", 1000, 30)[0]
    assert idea.wash_sale_risk and "WAIT" in idea.note


def test_old_purchase_is_not_a_wash_sale():
    trades = [{"date": "2026-08-01", "account_id": "B-IRA", "symbol": "BOND", "side": "buy"}]
    assert not find_tax_loss_ideas(BUSY, trades, {}, "2026-10-01", 1000, 30)[0].wash_sale_risk
