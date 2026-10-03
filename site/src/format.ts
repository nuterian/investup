// Number formatting. Every score is shown with a reference point.

export function money(x: number | null | undefined): string {
  if (x == null || x === 0) return "–";
  const abs = Math.abs(x);
  if (abs >= 1e9) return `$${(x / 1e9).toFixed(abs >= 1e10 ? 0 : 1)}B`;
  if (abs >= 1e6) return `$${(x / 1e6).toFixed(abs >= 1e8 ? 0 : 1)}M`;
  if (abs >= 1e3) return `$${Math.round(x / 1e3)}K`;
  return `$${Math.round(x)}`;
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x == null) return "–";
  const v = x * 100;
  if (v > 0 && v < 1 && digits === 0) return `${v.toFixed(1)}%`;
  return `${v.toFixed(digits)}%`;
}

export function change(now: number, before: number): string {
  if (!before) return "–";
  const d = (now - before) / before;
  return `${d >= 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(0)}%`;
}

/** "top 2%" for a percentile in [0, 1]. */
export function topPct(p: number | null | undefined): string {
  if (p == null) return "–";
  const top = (1 - p) * 100;
  if (top < 0.1) return "top 0.1%";
  if (top < 1) return `top ${top.toFixed(1)}%`;
  if (top <= 50) return `top ${Math.max(1, Math.round(top))}%`;
  return "bottom half";
}

/** "3.4×" multiple of a base rate. */
export function multiple(x: number | null | undefined, base: number | null | undefined): string {
  if (x == null || !base) return "–";
  const m = x / base;
  return m >= 10 ? `${Math.round(m)}×` : `${m.toFixed(1)}×`;
}

export function date(d: string | null | undefined): string {
  if (!d) return "–";
  const [y, m] = d.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[Number(m) - 1]} ${y}`;
}

export function quarterLabel(d: string): string {
  const [y, m] = d.split("-").map(Number);
  return `Q${Math.floor((m - 1) / 3) + 1} ${y}`;
}
