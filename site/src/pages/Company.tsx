import {
  Card,
  ErrorNote,
  Loading,
  type ScoreKind,
  ScorePill,
  StarButton,
  heat,
  scoreParts,
} from "../components/Bits";
import { RankMeter, Timeline } from "../components/Charts";
import {
  type Company,
  type Detail,
  type Summary,
  edgarCompanyUrl,
  filingUrl,
  loadDetail,
  loadSummary,
  loadUniverse,
} from "../data";
import { date, money, pct } from "../format";
import { companyHref } from "../router";
import { useAsync } from "../useAsync";

export function CompanyPage({ cik }: { cik: number }) {
  const state = useAsync(
    () => Promise.all([loadDetail(cik), loadUniverse(), loadSummary()]),
    [cik],
  );
  if (state.error) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading />;
  const [detail, universe, summary] = state.data;
  if (!detail) {
    return (
      <p>
        No Form D raises since 2019 for CIK {cik}.{" "}
        <a href={edgarCompanyUrl(cik)} target="_blank" rel="noreferrer">
          Look it up on SEC EDGAR ↗
        </a>
      </p>
    );
  }
  return (
    <CompanyView
      cik={cik}
      d={detail}
      scored={universe.get(cik)}
      universe={universe}
      summary={summary}
    />
  );
}

function notScoredReason(d: Detail, summary: Summary): string {
  // Mirrors venture_universe() in the pipeline, in the same order.
  if (["Financial Services", "Real Estate", "Extractive & Utilities"].includes(d.sector))
    return `${d.sector} isn't a venture sector we score.`;
  if (!d.state || /\d/.test(d.state)) return "Headquartered outside the US.";
  if (d.went_public) return `Already public (first SEC report or IPO prospectus ${d.went_public}).`;
  if (d.vehicle) return "Looks like a fund, SPV or other investment vehicle.";
  const last = d.last_raise ? new Date(d.last_raise) : null;
  const cutoff = new Date(summary.data_end);
  cutoff.setMonth(cutoff.getMonth() - 36);
  if (!last || last < cutoff) return `No new money reported in the 36 months to ${summary.data_end}.`;
  return "Excluded by our universe filters (for example, a professional-services partnership).";
}

function ScoreBlock({
  c,
  kind,
  summary,
  title,
  horizon,
}: {
  c: Company;
  kind: ScoreKind;
  summary: Summary;
  title: string;
  horizon: string;
}) {
  const s = scoreParts(c, kind, summary);
  const reason = kind === "step" ? c.step_reason : c.ipo_reason;
  const bands = summary.track_record[kind === "step" ? "step_up" : "went_public"]?.hit_rate_by_rank;
  return (
    <div className={`score heat-edge-${heat(s.rank)}`}>
      <div className="score-head">
        <span className="score-title">{title}</span>
        <span className="muted small">{horizon}</span>
      </div>
      <div className="score-value">
        {s.text}
        <span className="score-times">{s.times} the average</span>
      </div>
      <RankMeter bands={bands ?? []} rank={s.rank} />
      <p className="small">
        Ranked <strong>{s.top}</strong>. In backtests, {s.text} of companies ranked this high did
        it, vs {pct(s.base, kind === "ipo" ? 1 : 0)} for the average company.
      </p>
      {reason && (
        <ul className="reasons small">
          {reason.split(" · ").map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Peers({
  c,
  universe,
  summary,
}: {
  c: Company;
  universe: Map<number, Company>;
  summary: Summary;
}) {
  const size = Math.log1p(c.total_raised ?? 0);
  const peers = [...universe.values()]
    .filter((u) => u.cik !== c.cik && u.sector === c.sector && u.state === c.state)
    .sort(
      (a, b) =>
        Math.abs(Math.log1p(a.total_raised ?? 0) - size) -
        Math.abs(Math.log1p(b.total_raised ?? 0) - size),
    )
    .slice(0, 5);
  if (!peers.length) return null;
  return (
    <Card
      title="Similar companies"
      note={`${c.sector} in ${c.state}, closest in total raised. Bigger-round and IPO odds.`}
    >
      <ul className="rows">
        {peers.map((p) => (
          <li className="row" key={p.cik}>
            <div className="row-main">
              <a href={companyHref(p.cik)}>{p.name}</a>
              <span className="muted small">{money(p.total_raised)} raised</span>
            </div>
            <div className="row-right">
              <ScorePill c={p} kind="step" summary={summary} />
              <ScorePill c={p} kind="ipo" summary={summary} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function CompanyView({
  cik,
  d,
  scored,
  universe,
  summary,
}: {
  cik: number;
  d: Detail;
  scored: Company | undefined;
  universe: Map<number, Company>;
  summary: Summary;
}) {
  const filings = [...d.timeline].reverse();
  const largest = scored?.largest_round;

  return (
    <div className="stack fade-in">
      <header className="company-head">
        <div>
          <h1>{d.name}</h1>
          <p className="muted">
            {[d.sector, d.industry !== d.sector ? d.industry : null, d.state]
              .filter(Boolean)
              .join(" · ")}{" "}
            ·{" "}
            <a href={edgarCompanyUrl(cik)} target="_blank" rel="noreferrer">
              CIK {cik} ↗
            </a>
          </p>
        </div>
        <StarButton cik={cik} label />
      </header>

      {scored ? (
        <div className="grid">
          <ScoreBlock
            c={scored}
            kind="step"
            summary={summary}
            title="Bigger round"
            horizon="next 18 months · $5M+ and 1.5× largest round"
          />
          <ScoreBlock c={scored} kind="ipo" summary={summary} title="IPO" horizon="next 36 months" />
        </div>
      ) : (
        <p className="note">Not scored: {notScoredReason(d, summary)}</p>
      )}

      <Card title="Funding">
        <Timeline
          points={d.timeline.map(([filed, value, isNew]) => ({ date: filed, value, isNew }))}
        />
        <dl className="facts">
          <div>
            <dt>Total raised</dt>
            <dd>{money(d.total_raised)}</dd>
          </div>
          <div>
            <dt>Largest round</dt>
            <dd>{money(largest)}</dd>
          </div>
          <div>
            <dt>Rounds</dt>
            <dd>{d.rounds}</dd>
          </div>
          <div>
            <dt>First filing</dt>
            <dd>{date(d.first_filing)}</dd>
          </div>
          <div>
            <dt>Last raise</dt>
            <dd>{date(d.last_raise)}</dd>
          </div>
          <div>
            <dt>Investors (last raise)</dt>
            <dd>{d.investors_last ?? "–"}</dd>
          </div>
          <div>
            <dt>Revenue range</dt>
            <dd>{d.revenue_range ?? "–"}</dd>
          </div>
          {d.year_of_inc && (
            <div>
              <dt>Incorporated</dt>
              <dd>{d.year_of_inc}</dd>
            </div>
          )}
          {d.s1_filed && (
            <div>
              <dt>S-1/F-1 filed</dt>
              <dd>{d.s1_filed}</dd>
            </div>
          )}
        </dl>
      </Card>

      {d.people.length > 0 && (
        <Card title="People on filings" note="As named in the company's most recent Form D.">
          <ul className="rows">
            {d.people.map((p) => (
              <li className="row person" key={p.name + p.roles}>
                <div className="row-main">
                  <span>{p.name}</span>
                  <span className="muted small">{p.roles}</span>
                </div>
                {p.other.length > 0 && (
                  <div className="small">
                    Also:{" "}
                    {p.other.map((o, i) => (
                      <span key={o.cik}>
                        {i > 0 && ", "}
                        <a href={companyHref(o.cik)}>{o.name}</a>
                        {o.public && <span className="tag">IPO {o.public}</span>}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {scored && <Peers c={scored} universe={universe} summary={summary} />}

      <Card title="Form D filings">
        <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Filed</th>
              <th>Type</th>
              <th className="num">New money</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filings.map(([filed, value, isNew, acc]) => (
              <tr key={acc}>
                <td>{filed}</td>
                <td>{isNew ? "New offering" : "Amendment"}</td>
                <td className="num">{money(value)}</td>
                <td className="num">
                  <a href={filingUrl(cik, acc)} target="_blank" rel="noreferrer">
                    SEC ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Card>
    </div>
  );
}
