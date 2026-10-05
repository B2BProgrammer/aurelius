import type { AssetClass, Portfolio, Risk, Section } from "../api/types";
import { CLASS_LABEL, money } from "../lib/format";

const CLASSES: AssetClass[] = ["equity", "fixed_income", "cash"];

export function Allocation({ p }: { p: Portfolio }) {
  const a = p.allocation;
  return (
    <div className="alloc">
      {CLASSES.map((c) => {
        const drift = a.drift_pts[c];
        const off = Math.abs(drift) >= 5;
        return (
          <div className="alloc-row" key={c}>
            <span>{CLASS_LABEL[c]}</span>
            <div
              className="alloc-bars"
              role="img"
              aria-label={`${CLASS_LABEL[c]}: ${a.current_pct[c]}% now, target ${a.target_pct[c]}%`}
            >
              <div className="bar" style={{ width: `${a.current_pct[c]}%` }} />
              <div className="bar target" style={{ width: `${a.target_pct[c]}%` }} />
            </div>
            <span className="num">
              {a.current_pct[c]}%{" "}
              <span className={`drift ${off ? "off" : ""}`}>
                {drift === 0 ? "on target" : `${drift > 0 ? "+" : "−"}${Math.abs(drift)} pts`}
              </span>
            </span>
          </div>
        );
      })}
      <div className="legend" aria-hidden="true">
        <span>Now</span>
        <span className="t">Target</span>
      </div>
    </div>
  );
}

export function PortfolioBody({ p, risk }: { p: Portfolio; risk: Section<Risk> }) {
  return (
    <>
      <p className="lede">{p.summary}</p>
      <Allocation p={p} />
      {risk.status === "ok" && (
        <p className="prose">
          Risk score {risk.output.risk_score} of 100, {risk.output.band.toLowerCase()}, set by{" "}
          {risk.output.limiting_factor === "capacity" ? "their capacity to take losses" : "their stated willingness"}.
          The profile suggests about {risk.output.suggested_equity_pct}% in stocks; they hold{" "}
          {risk.output.current_equity_pct}%.
        </p>
      )}
      {p.tax_loss_ideas.length > 0 && (
        <div>
          <h3>Tax-loss ideas</h3>
          <table className="ledger">
            <thead>
              <tr>
                <th scope="col">Holding</th>
                <th scope="col" className="r">
                  Unrealized loss
                </th>
                <th scope="col">Could swap to</th>
              </tr>
            </thead>
            <tbody>
              {p.tax_loss_ideas.map((t) => (
                <tr key={t.symbol}>
                  <td>
                    {t.name}
                    <div className="hint">{t.note}</div>
                  </td>
                  <td className="r neg">{money(-Math.abs(t.unrealized_loss))}</td>
                  <td>{t.replacements.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
