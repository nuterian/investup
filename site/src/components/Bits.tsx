import type { ReactNode } from "react";
import type { Company, Summary } from "../data";
import { multiple, pct, topPct } from "../format";
import { companyHref } from "../router";
import { useWatchlist } from "../watchlist";

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

/** 0–4 tint level from rank: top 1% → 4, top 5% → 3, top 10% → 2, top 25% → 1. */
export function heat(rank: number | null | undefined): number {
  if (rank == null) return 0;
  if (rank >= 0.99) return 4;
  if (rank >= 0.95) return 3;
  if (rank >= 0.9) return 2;
  if (rank >= 0.75) return 1;
  return 0;
}

export function ScorePill({ c, kind, summary }: { c: Company; kind: ScoreKind; summary: Summary }) {
  const s = scoreParts(c, kind, summary);
  if (s.hit == null) return <span className="muted">–</span>;
  return (
    <span
      className={`score-pill heat-${heat(s.rank)}`}
      title={`${s.text} of companies ranked here did it historically (${s.times} the average)`}
    >
      <span className="score-num">{s.text}</span>
      <span className="score-rank">
        <i className="heat-bar" aria-hidden="true">
          <b />
          <b />
          <b />
          <b />
        </i>
        {s.top}
      </span>
    </span>
  );
}

export function StarButton({ cik, label = false }: { cik: number; label?: boolean }) {
  const [watch, toggle] = useWatchlist();
  const on = watch.includes(cik);
  return (
    <button
      type="button"
      className={on ? "star on" : "star"}
      aria-pressed={on}
      aria-label={on ? "Remove from watchlist" : "Add to watchlist"}
      title={on ? "Remove from watchlist" : "Add to watchlist"}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle(cik);
      }}
    >
      {on ? "★" : "☆"}
      {label && <span>{on ? " Watching" : " Watch"}</span>}
    </button>
  );
}

/** Placeholder rows shown while data loads. */
export function Loading({ rows = 6 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      <span className="sk sk-title" />
      {Array.from({ length: rows }, (_, i) => (
        <span className="sk" key={i} style={{ width: `${92 - ((i * 13) % 30)}%` }} />
      ))}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p className="error">
      {error instanceof Error ? error.message : "Something went wrong loading the data."}
    </p>
  );
}
