package com.aurelius.actuary.planning;

/**
 * Capital market assumptions: what we ASSUME each asset class returns, after inflation.
 *
 * LEARN: Every projection is only as good as these numbers, which is why they're
 * published at GET /v1/assumptions and returned with every projection. Real firms
 * set them once a year in an investment committee. These are illustrative.
 *
 * Portfolio return  = sum of (weight x mean)
 * Portfolio risk    = sqrt( w'.Cov.w ), with a small equity/bond correlation
 */
public record Assumptions(double equityMean, double equityVol, double bondMean, double bondVol,
                          double cashMean, double cashVol, double equityBondCorrelation) {

    public static final Assumptions DEFAULT = new Assumptions(0.050, 0.160, 0.020, 0.060, 0.005, 0.010, 0.10);

    public double expectedReturn(Portfolio p) {
        return p.weight("equity") * equityMean + p.weight("fixed_income") * bondMean + p.weight("cash") * cashMean;
    }

    public double volatility(Portfolio p) {
        double we = p.weight("equity"), wb = p.weight("fixed_income"), wc = p.weight("cash");
        double variance = sq(we * equityVol) + sq(wb * bondVol) + sq(wc * cashVol)
                + 2 * we * wb * equityVol * bondVol * equityBondCorrelation;
        return Math.sqrt(variance);
    }

    private static double sq(double x) {
        return x * x;
    }
}
