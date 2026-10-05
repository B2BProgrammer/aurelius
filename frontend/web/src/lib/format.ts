/** Formatting helpers: one place, so every screen writes money and dates the same way. */

const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const money = (n: number): string => usd0.format(n);

/** $2.35M, $329k: for headers where space is tight. */
export function moneyShort(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "−" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(abs >= 10_000_000 ? 1 : 2)}M`;
  if (abs >= 1_000) return `${sign}$${Math.round(abs / 1_000)}k`;
  return `${sign}$${Math.round(abs)}`;
}

/** +$11,000 / −$29,610 (a real minus sign, so negatives read clearly). */
export const signedMoney = (n: number): string => (n < 0 ? `−${money(-n)}` : `+${money(n)}`);

const dayFmt = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
const shortFmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** "2026-10-08" -> "Thu, Oct 8" (dates are calendar days, so read them as UTC). */
export const day = (iso: string): string => dayFmt.format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
export const shortDay = (iso: string): string => shortFmt.format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));

/** Never "100%" or "0%" for a projection: it must not sound certain. */
export function chance(pct: number): string {
  if (pct >= 99.5) return "over 99%";
  if (pct < 0.5) return "under 1%";
  return `${Math.round(pct)}%`;
}

export const CLASS_LABEL: Record<string, string> = { equity: "Stocks", fixed_income: "Bonds", cash: "Cash" };
