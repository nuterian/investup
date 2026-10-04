// The site's charts. Hand-drawn SVG, no chart library.

import { useState } from "react";
import type { Band } from "../data";
import { date, money, pct } from "../format";

/** Bar chart over time with a hover readout. */
export function BarSpark({
  values,
  labels,
  format = money,
  height = 72,
}: {
  values: number[];
  labels: string[];
  format?: (x: number) => string;
  height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...values, 1);
  const n = Math.max(values.length, 1);
  const w = 100 / n;
  const active = hover ?? values.length - 1;
  return (
    <div className="spark-wrap">
      <div className="spark-readout">
        <strong>{format(values[active] ?? 0)}</strong>
        <span className="muted">{labels[active]}</span>
      </div>
      <svg
        className="spark"
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Bar chart by quarter"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const i = Math.floor(((e.clientX - box.left) / box.width) * n);
          setHover(Math.min(Math.max(i, 0), n - 1));
        }}
      >
        {values.map((v, i) => {
          const h = Math.max((v / max) * (height - 2), v > 0 ? 1 : 0);
          return (
            <rect
              key={labels[i]}
              x={i * w + w * 0.12}
              y={height - h}
              width={w * 0.76}
              height={h}
              className={i === active ? "bar bar-on" : "bar"}
              style={{ animationDelay: `${Math.min(i * 6, 400)}ms` }}
            />
          );
        })}
      </svg>
    </div>
  );
}

/** Labelled horizontal bars; each row can link somewhere. */
export function HBars({
  rows,
}: {
  rows: { label: string; value: number; note?: string; tone?: "up" | "down"; href?: string }[];
}) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="hbars">
      {rows.map((r) => {
        const inner = (
          <>
            <span className="hbar-label">{r.label}</span>
            <span className="hbar-track">
              <span className="hbar-fill" style={{ transform: `scaleX(${r.value / max})` }} />
            </span>
            <span className={`hbar-note ${r.tone ?? ""}`}>{r.note}</span>
          </>
        );
        return r.href ? (
          <a className="hbar-row link-row" href={r.href} key={r.label}>
            {inner}
          </a>
        ) : (
          <div className="hbar-row" key={r.label}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}

/** Funding timeline: one bar per filing that reported new money. */
export function Timeline({
  points,
}: {
  points: { date: string; value: number; isNew: boolean }[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = points.filter((p) => p.value > 0);
  if (!pts.length) return <p className="muted">No new money reported.</p>;
  const t = (d: string) => new Date(d).getTime();
  const t0 = t(pts[0].date);
  const t1 = Math.max(t(pts[pts.length - 1].date), t0 + 365 * 864e5);
  const max = Math.max(...pts.map((p) => p.value));
  const H = 72;
  const x = (d: string) => ((t(d) - t0) / (t1 - t0)) * 96 + 2;
  const shown = hover != null ? pts[hover] : null;
  return (
    <div className="timeline">
      <div className="spark-readout">
        {shown ? (
          <>
            <strong>{money(shown.value)}</strong>
            <span className="muted">
              {date(shown.date, true)} · {shown.isNew ? "new round" : "added to an open round"}
            </span>
          </>
        ) : (
          <span className="muted legend">
            <i className="dot dot-new" /> new round <i className="dot dot-add" /> added to an
            open round
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 100 ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Funding timeline"
        onMouseLeave={() => setHover(null)}
      >
        {pts.map((p, i) => {
          // Square-root scale so small raises stay visible next to big ones.
          const h = Math.max(Math.sqrt(p.value / max) * (H - 2), 2);
          return (
            <g key={`${p.date}-${i}`} onMouseEnter={() => setHover(i)}>
              <rect x={x(p.date) - 2} y={0} width={4} height={H} className="hit" />
              <rect
                x={x(p.date) - 0.7}
                y={H - h}
                width={1.4}
                height={h}
                className={`${p.isNew ? "bar bar-new" : "bar bar-add"}${hover === i ? " bar-on" : ""}`}
              />
            </g>
          );
        })}
      </svg>
      <div className="timeline-axis">
        <span>{new Date(t0).getUTCFullYear()}</span>
        <span>{new Date(t1).getUTCFullYear()}</span>
      </div>
    </div>
  );
}

/**
 * Where a company ranks: the universe split into backtest rank bands, each
 * shaded by how often companies in it actually hit, with a marker at this
 * company's percentile.
 */
export function RankMeter({ bands, rank }: { bands: Band[]; rank: number | null }) {
  if (!bands.length || rank == null) return null;
  const top = Math.max(...bands.map((b) => b.observed), 1e-9);
  return (
    <div className="meter" aria-label={`Ranked at the ${Math.round(rank * 100)}th percentile`}>
      <div className="meter-track">
        {bands.map((b) => (
          <span
            key={b.low}
            className="meter-band"
            style={{
              width: `${(Math.min(b.high, 1) - b.low) * 100}%`,
              opacity: 0.15 + 0.85 * (b.observed / top),
            }}
            title={`${Math.round(b.low * 100)}–${Math.round(Math.min(b.high, 1) * 100)}th percentile: ${pct(b.observed, 1)} did it`}
          />
        ))}
        <span className="meter-mark" style={{ left: `${Math.min(rank, 0.999) * 100}%` }} />
      </div>
      <div className="meter-axis muted">
        <span>lowest ranked</span>
        <span>highest ranked</span>
      </div>
    </div>
  );
}
