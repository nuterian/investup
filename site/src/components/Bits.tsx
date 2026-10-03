import type { ReactNode } from "react";
import type { Company, Summary } from "../data";
import { multiple, pct, topPct } from "../format";
import { companyHref } from "../router";

export function CompanyLink({ cik, name }: { cik: number; name: string }) {
  return <a href={companyHref(cik)}>{name}</a>;
}

export function Card({
  title,
  note,
  children,
}: {
  title: string;
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      <header>
        <h2>{title}</h2>
        {note && <p className="muted small">{note}</p>}
      </header>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export type ScoreKind = "step" | "ipo";

/** Base rate (historical share with the outcome) for a score kind. */
export function baseRate(summary: Summary, kind: ScoreKind): number | null {
  const tr = summary.track_record[kind === "step" ? "step_up" : "went_public"];
  return tr?.base_rate ?? null;
}

/**
 * The number we show for a score: the historical hit rate of the company's rank
 * band, with its multiple of the base rate. Raw model probabilities are
 * over-confident at the top, so they're never shown on their own.
 */
export function scoreParts(c: Company, kind: ScoreKind, summary: Summary) {
  const hit = kind === "step" ? c.hit_step : c.hit_ipo;
  const rank = kind === "step" ? c.pct_step : c.pct_ipo;
  const base = baseRate(summary, kind);
  return { hit, rank, base, text: pct(hit), times: multiple(hit, base), top: topPct(rank) };
}

export function ScorePill({ c, kind, summary }: { c: Company; kind: ScoreKind; summary: Summary }) {
  const s = scoreParts(c, kind, summary);
  if (s.hit == null) return <span className="muted">–</span>;
  return (
    <span className="pill" title={`${s.top} · ${s.text} of companies ranked here historically`}>
      {s.text}
      <span className="pill-sub">{s.times}</span>
    </span>
  );
}

export function Loading() {
  return <p className="muted">Loading…</p>;
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p className="error">
      {error instanceof Error ? error.message : "Something went wrong loading the data."}
    </p>
  );
}
