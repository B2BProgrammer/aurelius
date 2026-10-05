package com.aurelius.actuary.planning;

import java.util.Map;

/**
 * What the math needs from a portfolio: total value, value per asset class,
 * the largest single stock, and what the firm has on file (risk label, target mix).
 *
 * @param source "mcp" (live, from the advisor-tools MCP server) or "snapshot (...)" (fallback file)
 */
public record Portfolio(String source, String asOf, String riskProfile, Map<String, Double> targetAllocationPct,
                        double totalMarketValue, Map<String, Double> allocationValue, Stock largestSingleStock) {

    public record Stock(String symbol, double marketValue) {}

    public Portfolio {
        targetAllocationPct = targetAllocationPct == null ? Map.of() : Map.copyOf(targetAllocationPct);
        allocationValue = allocationValue == null ? Map.of() : Map.copyOf(allocationValue);
    }

    /** Weight 0..1 of an asset class: "equity", "fixed_income" or "cash". */
    public double weight(String assetClass) {
        return totalMarketValue <= 0 ? 0 : allocationValue.getOrDefault(assetClass, 0.0) / totalMarketValue;
    }

    public Portfolio withSource(String newSource) {
        return new Portfolio(newSource, asOf, riskProfile, targetAllocationPct, totalMarketValue, allocationValue,
                largestSingleStock);
    }
}
