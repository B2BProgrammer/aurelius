package com.aurelius.actuary.risk;

import com.aurelius.actuary.planning.Portfolio;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * Stress test: "what would this portfolio lose if <bad period> happened again?"
 *
 * LEARN: Monte Carlo answers "how likely?"; a stress test answers "how bad?".
 * Advisors use it to check a client could live with the worst case. We apply
 * APPROXIMATE historical asset-class returns to today's mix, plus a
 * single-stock shock when the client holds one large stock.
 */
public final class StressTester {
    private StressTester() {}

    public record Scenario(String id, String name, double equity, double fixedIncome, double cash, String note) {}

    public record Row(String scenario, String name, long loss, double lossPct, long valueAfter,
                      Double yearsOfSpending, String note) {}

    /** Approximate peak-to-trough / calendar figures for broad US indexes. Illustrative, not exact. */
    public static final List<Scenario> SCENARIOS = List.of(
            new Scenario("gfc_2008", "2008 global financial crisis", -0.37, 0.05, 0.02,
                    "Stocks about -37% in 2008; high-quality bonds rose."),
            new Scenario("dotcom_2000", "2000-2002 dot-com bust", -0.45, 0.30, 0.10,
                    "Stocks fell about 45% over three years; bonds rallied."),
            new Scenario("covid_2020", "2020 COVID crash (Feb-Mar)", -0.34, 0.01, 0.00,
                    "Fast 34% stock drop in five weeks; recovered within months."),
            new Scenario("rates_2022", "2022 rate shock", -0.18, -0.13, 0.015,
                    "Stocks AND bonds fell together: diversification helped less."));

    public static final String SINGLE_STOCK = "single_stock_halved";

    public static List<String> ids() {
        List<String> ids = new ArrayList<>(SCENARIOS.stream().map(Scenario::id).toList());
        ids.add(SINGLE_STOCK);
        return ids;
    }

    public static List<Row> run(Portfolio p, double annualSpending, String onlyScenario) {
        double total = p.totalMarketValue();
        Map<String, Double> v = p.allocationValue();
        List<Row> rows = new ArrayList<>();
        for (Scenario s : SCENARIOS) {
            if (onlyScenario != null && !onlyScenario.equals(s.id())) continue;
            double change = v.getOrDefault("equity", 0.0) * s.equity() + v.getOrDefault("fixed_income", 0.0) * s.fixedIncome()
                    + v.getOrDefault("cash", 0.0) * s.cash();
            rows.add(row(s.id(), s.name(), -change, total, annualSpending, s.note()));
        }
        if (p.largestSingleStock() != null && (onlyScenario == null || SINGLE_STOCK.equals(onlyScenario))) {
            Portfolio.Stock st = p.largestSingleStock();
            rows.add(row(SINGLE_STOCK, st.symbol() + " falls 50% (company-specific)", st.marketValue() * 0.5, total,
                    annualSpending, "Only " + st.symbol() + " falls; the rest of the market is flat."));
        }
        rows.sort(Comparator.comparingLong(Row::loss).reversed());
        return rows;
    }

    private static Row row(String id, String name, double loss, double total, double spending, String note) {
        return new Row(id, name, Math.round(loss / 1000.0) * 1000L, Math.round(1000 * loss / total) / 10.0,
                Math.round((total - loss) / 1000.0) * 1000L,
                spending > 0 ? Math.round(10 * loss / spending) / 10.0 : null, note);
    }
}
