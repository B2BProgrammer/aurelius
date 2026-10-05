import { useState, type FormEvent } from "react";

import { useRetirement, useStressTest } from "../api/hooks";
import { chance, money, moneyShort } from "../lib/format";
import { ErrorNote, Skeleton } from "./ErrorNote";

/**
 * "What if they retire a year later, or spend less?"
 * Each change asks the Actuary (Java) to rerun its Monte Carlo simulation.
 */
export function RetirementSection({ clientId }: { clientId: string }) {
  const [ages, setAges] = useState<number[]>([]);
  const [spending, setSpending] = useState<number | null>(null);
  const [spendingText, setSpendingText] = useState("");
  const [showStress, setShowStress] = useState(false);
  const q = useRetirement(clientId, ages, spending);
  const stress = useStressTest(clientId, showStress);

  if (q.isPending) return <Skeleton />;
  if (q.isError) return <ErrorNote error={q.error} what="the retirement projection" />;
  if (q.data.status !== "ok") return <div className="note error">Actuary couldn't run it: {q.data.error}</div>;

  const r = q.data.output;
  const shown = r.scenarios.map((s) => s.retire_age);
  const planned = shown[0] ?? 65;
  const candidates = r.already_retired
    ? []
    : Array.from({ length: 5 }, (_, i) => planned - 1 + i).filter((a) => a >= 50 && a <= 80);
  const selected = ages.length ? ages : shown;

  function toggle(age: number) {
    const next = selected.includes(age) ? selected.filter((a) => a !== age) : [...selected, age].sort((a, b) => a - b);
    if (next.length === 0 || next.length > 3) return; // compare one to three ages
    setAges(next);
  }

  function applySpending(e: FormEvent) {
    e.preventDefault();
    const n = Number(spendingText.replace(/[$,\s]/g, ""));
    setSpending(Number.isFinite(n) && n >= 10_000 ? n : null);
  }

  return (
    <>
      <p className="lede">{r.headline}</p>

      <div className="whatif">
        {candidates.length > 0 && (
          <div className="field">
            <span id="ages-label" className="hint">
              Retirement age for {r.ages_are_of} (compare up to three)
            </span>
            <div className="ages" role="group" aria-labelledby="ages-label">
              {candidates.map((a) => (
                <button
                  key={a}
                  type="button"
                  className="age-toggle"
                  aria-pressed={selected.includes(a)}
                  onClick={() => toggle(a)}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>
        )}
        <form className="field" onSubmit={applySpending}>
          <label htmlFor="spending">Yearly spending in retirement</label>
          <div className="ages">
            <input
              id="spending"
              inputMode="numeric"
              placeholder={money(r.inputs.annual_spending)}
              value={spendingText}
              onChange={(e) => setSpendingText(e.target.value)}
              style={{ width: "9rem" }}
            />
            <button className="btn quiet" type="submit">
              Rerun
            </button>
          </div>
        </form>
      </div>

      <div className={`odds ${q.isFetching ? "computing" : ""}`} aria-live="polite" aria-busy={q.isFetching}>
        {r.scenarios.map((s) => (
          <div className="odds-item" key={s.retire_age}>
            <div className={`pct ${s.probability_of_success_pct < 80 ? "weak" : ""}`}>
              {chance(s.probability_of_success_pct)}
            </div>
            <div className="cap">
              chance the money lasts, retiring at {s.retire_age}
              <br />
              {moneyShort(s.median_at_retirement)} expected at retirement. In a bad run it lasts to{" "}
              {s.worst_case_age_money_lasts}.
            </div>
          </div>
        ))}
      </div>

      <div>
        {!showStress ? (
          <button className="linkish" type="button" onClick={() => setShowStress(true)}>
            Show how a market crash would hit this portfolio
          </button>
        ) : stress.isPending ? (
          <Skeleton />
        ) : stress.isError ? (
          <ErrorNote error={stress.error} what="the stress test" />
        ) : stress.data.status === "ok" ? (
          <>
            <h3>If history repeated</h3>
            <table className="ledger">
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col" className="r">
                    Loss
                  </th>
                  <th scope="col" className="r">
                    Years of spending
                  </th>
                </tr>
              </thead>
              <tbody>
                {stress.data.output.scenarios.map((s) => (
                  <tr key={s.scenario}>
                    <td>
                      {s.name}
                      <div className="hint">{s.note}</div>
                    </td>
                    <td className="r neg">
                      {money(-s.loss)} ({s.loss_pct}%)
                    </td>
                    <td className="r">{s.years_of_spending ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <div className="note error">Actuary couldn't run the stress test: {stress.data.error}</div>
        )}
      </div>

      <p className="fine">{r.disclosure}</p>
    </>
  );
}
