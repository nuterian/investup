import { type ReactNode, useMemo, useState } from "react";
import {
  Card,
  CompanyLink,
  ErrorNote,
  Loading,
  ScorePill,
  StarButton,
  Stat,
  baseRate,
} from "../components/Bits";
import { BarSpark, HBars } from "../components/Charts";
import { type Company, type Lists, type Summary, loadLists, loadSummary, loadUniverse } from "../data";
import { change, date, money, pct, quarterLabel } from "../format";
import { computeLists } from "../lists";
import { href, replaceParams } from "../router";
import { useAsync } from "../useAsync";
import { useWatchlist } from "../watchlist";

export function Home({ params }: { params: URLSearchParams }) {
  const state = useAsync(() => Promise.all([loadSummary(), loadLists(), loadUniverse()]), []);
  if (state.error) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading rows={10} />;
  const [summary, lists, universe] = state.data;
  return (
    <Dashboard
      summary={summary}
      lists={lists}
      universe={universe}
      initialSector={params.get("sector") ?? ""}
    />
  );
}

function Row({ c, right }: { c: Company; right: ReactNode }) {
  return (
    <li className="row">
      <div className="row-main">
        <CompanyLink cik={c.cik} name={c.name} />
        <span className="muted small">
          {c.sector} · {c.state}
          {c.total_raised ? ` · ${money(c.total_raised)} raised` : ""}
        </span>
      </div>
      <div className="row-right">
        {right}
        <StarButton cik={c.cik} />
      </div>
    </li>
  );
}

function Delta({ now, before }: { now: number; before: number }) {
  const up = now >= before;
  return (
    <span className={up ? "up" : "down"}>
      {up ? "▲" : "▼"} {change(now, before).replace(/^[+−]/, "")} vs a year ago
    </span>
  );
}

function Empty() {
  return <p className="muted small">Nothing in this sector right now.</p>;
}

function Dashboard({
  summary,
  lists,
  universe,
  initialSector,
}: {
  summary: Summary;
  lists: Lists;
  universe: Map<number, Company>;
  initialSector: string;
}) {
  const [watch] = useWatchlist();
  const [sector, setSector] = useState(initialSector);
  const [metric, setMetric] = useState<"money" | "companies">("money");
  const view = useMemo(
    () => computeLists(universe, lists, summary.data_end, sector),
    [universe, lists, summary.data_end, sector],
  );
  const q = summary.quarter;
  const pulse = summary.pulse;
  const sectors = summary.sectors.filter((s) => s.last_12m >= 50);
  const step = summary.track_record.step_up;
  const ipo = summary.track_record.went_public;
  const watched = watch.map((c) => universe.get(c)).filter(Boolean) as Company[];
  const pick = (s: string) => {
    setSector(s);
    replaceParams("", { sector: s || undefined });
  };
  const exploreHref = (sort: string, extra: Record<string, string | number> = {}) =>
    href("explore", { sort, sector: sector || undefined, ...extra });

  return (
    <div className="stack fade-in">
      <section className="hero">
        <p className="hero-date muted small">SEC filings through {date(summary.data_end, true)}</p>
        <div className="stats">
          <Stat
            label="startups reported a raise, last 3 months"
            value={q.this.companies.toLocaleString()}
            sub={<Delta now={q.this.companies} before={q.year_ago.companies} />}
          />
          <Stat
            label="new money reported"
            value={money(q.this.money)}
            sub={<Delta now={q.this.money} before={q.year_ago.money} />}
          />
          <Stat label="first-time filers" value={q.new_companies.toLocaleString()} />
        </div>
        <div className="pulse">
          <div className="pulse-head">
            <span className="muted small">
              {metric === "money" ? "New money" : "Companies raising"} per quarter since{" "}
              {pulse[0] && quarterLabel(pulse[0].q)}
            </span>
            <div className="seg" role="group" aria-label="Chart metric">
              <button type="button" aria-pressed={metric === "money"} onClick={() => setMetric("money")}>
                $
              </button>
              <button
                type="button"
                aria-pressed={metric === "companies"}
                onClick={() => setMetric("companies")}
              >
                Companies
              </button>
            </div>
          </div>
          <BarSpark
            values={pulse.map((p) => (metric === "money" ? p.money : p.companies))}
            labels={pulse.map((p, i) =>
              i === pulse.length - 1
                ? `${quarterLabel(p.q)} so far (through ${date(summary.data_end, true)})`
                : quarterLabel(p.q),
            )}
            format={metric === "money" ? money : (x) => `${x.toLocaleString()} companies`}
          />
        </div>
      </section>

      <div className="chips" role="group" aria-label="Filter by sector">
        <button type="button" className="chip" aria-pressed={!sector} onClick={() => pick("")}>
          All sectors
        </button>
        {sectors.map((s) => (
          <button
            type="button"
            key={s.sector}
            className="chip"
            aria-pressed={sector === s.sector}
            onClick={() => pick(s.sector)}
          >
            {s.sector}
          </button>
        ))}
      </div>

      {watched.length > 0 && (
        <Card title="Your watchlist" note="Saved in this browser only.">
          <ul className="rows">
            {watched.map((c) => (
              <Row key={c.cik} c={c} right={<ScorePill c={c} kind="step" summary={summary} />} />
            ))}
          </ul>
        </Card>
      )}

      <div className="grid">
        <Card
          title="Likely to raise a bigger round"
          note={
            <>
              Next 18 months: $5M+ and at least 1.5× their largest round. Average company:{" "}
              {pct(baseRate(summary, "step"))}.
            </>
          }
        >
          {view.step_up.length ? (
            <ul className="rows">
              {view.step_up.map((c) => (
                <Row key={c.cik} c={c} right={<ScorePill c={c} kind="step" summary={summary} />} />
              ))}
            </ul>
          ) : (
            <Empty />
          )}
          <a className="more" href={exploreHref("step", { within: 12 })}>
            See all →
          </a>
        </Card>

        <Card
          title="IPO watch"
          note={<>Next 36 months. Average company: {pct(baseRate(summary, "ipo"), 1)}.</>}
        >
          {view.ipo_watch.length ? (
            <ul className="rows">
              {view.ipo_watch.map((c) => (
                <Row key={c.cik} c={c} right={<ScorePill c={c} kind="ipo" summary={summary} />} />
              ))}
            </ul>
          ) : (
            <Empty />
          )}
          <a className="more" href={exploreHref("ipo")}>
            See all →
          </a>
        </Card>

        <Card title="Movers" note="Biggest rise in bigger-round odds over the last 3 months.">
          {view.movers.length ? (
            <ul className="rows">
              {view.movers.slice(0, 8).map((c) => (
                <Row
                  key={c.cik}
                  c={c}
                  right={
                    <>
                      <span className="up" title="Odds rose over the last 3 months">
                        ▲
                      </span>
                      <ScorePill c={c} kind="step" summary={summary} />
                    </>
                  }
                />
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Card>

        <Card
          title="Repeat founders"
          note="First filing in the last year; the team includes people from an earlier IPO company."
        >
          {view.repeat_founders.length ? (
            <ul className="rows">
              {view.repeat_founders.slice(0, 8).map((c) => (
                <Row key={c.cik} c={c} right={<ScorePill c={c} kind="step" summary={summary} />} />
              ))}
            </ul>
          ) : (
            <Empty />
          )}
          <a className="more" href={exploreHref("step", { repeat: 1 })}>
            See all →
          </a>
        </Card>

        <Card title="Biggest raises, last 3 months">
          {view.biggest.length ? (
            <ul className="rows">
              {view.biggest.slice(0, 8).map(({ c, new_money }) => (
                <Row key={c.cik} c={c} right={<strong className="num">{money(new_money)}</strong>} />
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Card>

        <Card title="New IPO filings" note="Private companies that filed an S-1/F-1 in the last 3 months.">
          {view.ipo_pipeline.length ? (
            <ul className="rows">
              {view.ipo_pipeline.slice(0, 8).map((r) => (
                <li className="row" key={r.cik}>
                  <div className="row-main">
                    <CompanyLink cik={r.cik} name={r.name} />
                    {r.c && <span className="muted small">{r.c.sector} · {r.c.state}</span>}
                  </div>
                  <div className="row-right muted small">{date(r.filed, true)}</div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Card>
      </div>

      <Card
        title="Sector momentum"
        note="Companies raising in the last 12 months, and the change from the 12 months before. Click a sector to explore it."
      >
        <HBars
          rows={sectors.map((s) => ({
            label: s.sector,
            value: s.last_12m,
            note: `${s.last_12m.toLocaleString()} · ${change(s.last_12m, s.prior_12m)}`,
            tone: s.last_12m >= s.prior_12m ? "up" : "down",
            href: href("explore", { sector: s.sector }),
          }))}
        />
      </Card>

      {step && ipo && (
        <p className="track muted small">
          Track record ({step.test_years} backtests): our top 100 for a bigger round did it{" "}
          {pct(step.p_at_100)} of the time, vs {pct(step.base_rate)} for the average company. For
          IPOs: {pct(ipo.p_at_100)} vs {pct(ipo.base_rate, 1)}. <a href={href("method")}>How we score →</a>
        </p>
      )}
    </div>
  );
}
