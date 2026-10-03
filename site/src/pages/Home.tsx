import type { ReactNode } from "react";
import { BarSpark, HBars } from "../components/Charts";
import {
  Card,
  CompanyLink,
  ErrorNote,
  Loading,
  ScorePill,
  Stat,
  baseRate,
} from "../components/Bits";
import { type Company, type Lists, type Summary, loadLists, loadSummary, loadUniverse } from "../data";
import { change, date, money, pct, quarterLabel } from "../format";
import { href } from "../router";
import { useAsync } from "../useAsync";
import { useWatchlist } from "../watchlist";

export function Home() {
  const state = useAsync(
    () => Promise.all([loadSummary(), loadLists(), loadUniverse()]),
    [],
  );
  if (state.error) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading />;
  const [summary, lists, universe] = state.data;
  return <Dashboard summary={summary} lists={lists} universe={universe} />;
}

function Row({ c, summary, right }: { c: Company; summary: Summary; right?: ReactNode }) {
  return (
    <li className="row">
      <div className="row-main">
        <CompanyLink cik={c.cik} name={c.name} />
        <span className="muted small">
          {c.sector} · {c.state}
          {c.total_raised ? ` · ${money(c.total_raised)} raised` : ""}
        </span>
      </div>
      <div className="row-right">{right ?? <ScorePill c={c} kind="step" summary={summary} />}</div>
    </li>
  );
}

function Dashboard({
  summary,
  lists,
  universe,
}: {
  summary: Summary;
  lists: Lists;
  universe: Map<number, Company>;
}) {
  const [watch] = useWatchlist();
  const pick = (ciks: number[]) => ciks.map((c) => universe.get(c)).filter(Boolean) as Company[];
  const q = summary.quarter;
  const pulse = summary.pulse;
  const sectors = summary.sectors.filter((s) => s.last_12m >= 50);
  const step = summary.track_record.step_up;
  const ipo = summary.track_record.went_public;

  return (
    <div className="stack">
      <section className="hero">
        <p className="muted">
          Last 3 months · SEC filings through {date(summary.data_end, true)}
        </p>
        <div className="stats">
          <Stat
            label="private US startups reported a raise"
            value={q.this.companies.toLocaleString()}
            sub={`${change(q.this.companies, q.year_ago.companies)} vs a year ago`}
          />
          <Stat
            label="new money reported"
            value={money(q.this.money)}
            sub={`${change(q.this.money, q.year_ago.money)} vs a year ago`}
          />
          <Stat label="first-time filers" value={q.new_companies.toLocaleString()} />
        </div>
        <div className="pulse">
          <BarSpark values={pulse.map((p) => p.money)} labels={pulse.map((p) => quarterLabel(p.q))} />
          <div className="pulse-axis muted small">
            <span>{pulse[0] && quarterLabel(pulse[0].q)}</span>
            <span>New money per quarter</span>
            <span>{pulse.length > 0 && quarterLabel(pulse[pulse.length - 1].q)}</span>
          </div>
        </div>
      </section>

      {watch.length > 0 && (
        <Card title="Your watchlist" note="Saved in this browser only.">
          <ul className="rows">
            {pick(watch).map((c) => (
              <Row key={c.cik} c={c} summary={summary} />
            ))}
          </ul>
        </Card>
      )}

      <div className="grid">
        <Card
          title="Likely to raise a bigger round"
          note={
            <>
              Next 18 months: a round of $5M+ and at least 1.5× their largest so far. Typical
              company: {pct(baseRate(summary, "step"))}.
            </>
          }
        >
          <ul className="rows">
            {pick(lists.step_up).slice(0, 10).map((c) => (
              <Row key={c.cik} c={c} summary={summary} />
            ))}
          </ul>
          <a className="more" href={href("explore", { sort: "step" })}>
            See all →
          </a>
        </Card>

        <Card
          title="IPO watch"
          note={<>Next 36 months. Typical company: {pct(baseRate(summary, "ipo"), 1)}.</>}
        >
          <ul className="rows">
            {pick(lists.ipo_watch).slice(0, 10).map((c) => (
              <Row key={c.cik} c={c} summary={summary} right={<ScorePill c={c} kind="ipo" summary={summary} />} />
            ))}
          </ul>
          <a className="more" href={href("explore", { sort: "ipo" })}>
            See all →
          </a>
        </Card>

        <Card title="Movers" note="Biggest rise in bigger-round odds over the last 3 months.">
          <ul className="rows">
            {pick(lists.movers).slice(0, 8).map((c) => (
              <Row
                key={c.cik}
                c={c}
                summary={summary}
                right={
                  <>
                    <span className="up" title="Odds rose since last quarter">
                      ▲
                    </span>{" "}
                    <ScorePill c={c} kind="step" summary={summary} />
                  </>
                }
              />
            ))}
          </ul>
        </Card>

        <Card title="Repeat founders" note="First filing in the last year; team includes people from an earlier IPO company.">
          <ul className="rows">
            {pick(lists.repeat_founders).slice(0, 8).map((c) => (
              <Row key={c.cik} c={c} summary={summary} />
            ))}
          </ul>
          <a className="more" href={href("explore", { repeat: 1, sort: "step" })}>
            See all →
          </a>
        </Card>

        <Card title="Biggest raises, last 3 months">
          <ul className="rows">
            {lists.biggest.slice(0, 8).map(({ cik, new_money }) => {
              const c = universe.get(cik);
              return c ? (
                <Row key={cik} c={c} summary={summary} right={<strong>{money(new_money)}</strong>} />
              ) : null;
            })}
          </ul>
        </Card>

        <Card title="New IPO filings" note="Private companies that filed an S-1/F-1 in the last 3 months.">
          {lists.ipo_pipeline.length === 0 ? (
            <p className="muted">None in the last 3 months.</p>
          ) : (
            <ul className="rows">
              {lists.ipo_pipeline.slice(0, 8).map((r) => (
                <li className="row" key={r.cik}>
                  <div className="row-main">
                    <CompanyLink cik={r.cik} name={r.name} />
                  </div>
                  <div className="row-right muted small">{r.filed}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Sector momentum" note="Companies raising in the last 12 months, and change vs the 12 months before.">
        <HBars
          rows={sectors.map((s) => ({
            label: s.sector,
            value: s.last_12m,
            note: `${s.last_12m.toLocaleString()} · ${change(s.last_12m, s.prior_12m)}`,
            tone: s.last_12m >= s.prior_12m ? "up" : "down",
          }))}
        />
      </Card>

      {step && ipo && (
        <p className="track muted small">
          Track record ({step.test_years} backtests): companies in our top 100 for a bigger round
          hit it {pct(step.p_at_100)} of the time, vs {pct(step.base_rate)} for the average
          company. For IPOs: {pct(ipo.p_at_100)} vs {pct(ipo.base_rate, 1)}.{" "}
          <a href={href("method")}>How we score →</a>
        </p>
      )}
    </div>
  );
}
