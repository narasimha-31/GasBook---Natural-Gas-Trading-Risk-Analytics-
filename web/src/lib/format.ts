/** $26.9M, $348K, $980 */
export function money(value: number, digits = 1): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(digits)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(digits)}M`;
  if (abs >= 1e3) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

/** 1.36 -> "136%" */
export function pct(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** "2026-01-23" -> "Jan 23, 2026" */
export function day(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** "2026-01-23" -> "Jan 2026" */
export function month(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
