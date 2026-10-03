// The site's only charts: a bar sparkline and labelled horizontal bars.

import { money } from "../format";

export function BarSpark({
  values,
  labels,
  height = 56,
  format = money,
}: {
  values: number[];
  labels: string[];
  height?: number;
  format?: (x: number) => string;
}) {
  const max = Math.max(...values, 1);
  const w = 100 / Math.max(values.length, 1);
  return (
    <svg
      className="spark"
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Bar chart"
    >
      {values.map((v, i) => {
        const h = Math.max((v / max) * (height - 2), v > 0 ? 1 : 0);
        return (
          <rect
            key={labels[i]}
            x={i * w + w * 0.1}
            y={height - h}
            width={w * 0.8}
            height={h}
            className={i === values.length - 1 ? "bar bar-last" : "bar"}
          >
            <title>{`${labels[i]}: ${format(v)}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

export function HBars({
  rows,
}: {
  rows: { label: string; value: number; note?: string; tone?: "up" | "down" }[];
}) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="hbars">
      {rows.map((r) => (
        <div className="hbar-row" key={r.label}>
          <span className="hbar-label">{r.label}</span>
          <span className="hbar-track">
            <span className="hbar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          <span className={`hbar-note ${r.tone ?? ""}`}>{r.note}</span>
        </div>
      ))}
    </div>
  );
}

/** Funding timeline: one bar per filing that reported new money, on a time axis. */
export function Timeline({ points }: { points: { date: string; value: number; label: string }[] }) {
  const pts = points.filter((p) => p.value > 0);
  if (!pts.length) return <p className="muted">No new money reported.</p>;
  const t = (d: string) => new Date(d).getTime();
  const t0 = t(pts[0].date);
  const t1 = Math.max(t(pts[pts.length - 1].date), t0 + 365 * 864e5);
  const max = Math.max(...pts.map((p) => p.value));
  const H = 64;
  const firstYear = new Date(t0).getUTCFullYear();
  const lastYear = new Date(t1).getUTCFullYear();
  return (
    <div className="timeline">
      <svg viewBox={`0 0 100 ${H}`} preserveAspectRatio="none" role="img" aria-label="Funding timeline">
        {pts.map((p) => {
          const x = ((t(p.date) - t0) / (t1 - t0)) * 97 + 1;
          // Square-root scale so small raises stay visible next to big ones.
          const h = Math.max(Math.sqrt(p.value / max) * (H - 2), 2);
          return (
            <rect key={p.label + p.date} x={x - 0.6} y={H - h} width={1.2} height={h} className="bar">
              <title>{`${p.label}: ${money(p.value)}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="timeline-axis">
        <span>{firstYear}</span>
        <span>{lastYear}</span>
      </div>
    </div>
  );
}
