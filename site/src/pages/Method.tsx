import { Card, ErrorNote, Loading } from "../components/Bits";
import { type TrackRecord, loadSummary } from "../data";
import { pct } from "../format";
import { useAsync } from "../useAsync";

const LABELS: Record<string, { title: string; text: string }> = {
  step_up: {
    title: "Bigger round",
    text: "A new round of at least $5M and at least 1.5× the company's largest round so far, within 18 months.",
  },
  went_public: {
    title: "IPO",
    text: "A priced IPO prospectus or first periodic SEC report within 36 months.",
  },
  next_round: {
    title: "Any new round",
    text: "Any new offering reporting new money within 18 months.",
  },
};

function Record({ label, tr }: { label: string; tr: TrackRecord }) {
  const l = LABELS[label];
  return (
    <Card title={l.title} note={l.text}>
      <dl className="facts">
        <div>
          <dt>Test years</dt>
          <dd>{tr.test_years}</dd>
        </div>
        <div>
          <dt>Average company</dt>
          <dd>{pct(tr.base_rate, 1)}</dd>
        </div>
        <div>
          <dt>Our top 100</dt>
          <dd>
            {pct(tr.p_at_100)} ({tr.lift_at_100}×)
          </dd>
        </div>
        <div>
          <dt>Ranking quality (AUC)</dt>
          <dd>{tr.auc}</dd>
        </div>
      </dl>
      {tr.hit_rate_by_rank.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Ranked in</th>
              <th className="num">Companies</th>
              <th className="num">Actually did it</th>
            </tr>
          </thead>
          <tbody>
            {[...tr.hit_rate_by_rank].reverse().map((b) => (
              <tr key={b.low}>
                <td>
                  {b.high >= 1 ? `Top ${+(100 * (1 - b.low)).toFixed(1)}%` : `${+(100 * (1 - b.high)).toFixed(1)}–${+(100 * (1 - b.low)).toFixed(1)}% from top`}
                </td>
                <td className="num">{b.n.toLocaleString()}</td>
                <td className="num">{pct(b.observed, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function Method() {
  const state = useAsync(loadSummary, []);
  if (state.error) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading />;
  const s = state.data;
  return (
    <div className="stack prose">
      <h1>How we score</h1>
      <p>
        Investup tracks every US company that reports a private raise to the SEC on{" "}
        <strong>Form D</strong>, and uses EDGAR's filing index to see which ones later went
        public. Everything comes from public filings; no scraped or licensed data.
      </p>
      <p>
        For each company we build features only from filings that were public at the time
        (funding history, recency, round sizes, sector, state, and the track record of the
        people named on filings). A gradient-boosted model ranks companies; it was tested
        <em> walk-forward</em>: for each year 2016–2024, trained only on what was knowable then,
        and scored against what actually happened next.
      </p>
      <p>
        <strong>The percentages we show are historical hit rates</strong>: how often companies
        ranked in the same band actually did it in those backtests. We don't show the model's raw
        probabilities because they're over-confident at the very top, especially for IPOs, where
        hit rates swing with the market (2021 vs 2023).
      </p>

      <div className="grid">
        {(["step_up", "went_public", "next_round"] as const).map((label) => {
          const tr = s.track_record[label];
          return tr ? <Record key={label} label={label} tr={tr} /> : null;
        })}
      </div>

      <h2>What this doesn't see</h2>
      <ul>
        <li>Companies that don't file Form D, or raise through entities under other names.</li>
        <li>Acquisitions: a company that was bought can still appear until it goes quiet.</li>
        <li>Valuations, investor names, revenue (beyond the optional range on Form D).</li>
        <li>"IPO" includes small self-filed listings, not only venture-backed IPOs.</li>
      </ul>
      <p className="muted small">
        Data through {s.data_end} · generated {s.generated_at.slice(0, 10)} · model {s.model} ·
        open source on{" "}
        <a href="https://github.com/nuterian/investup" target="_blank" rel="noreferrer">
          GitHub
        </a>
        . Not investment advice.
      </p>
    </div>
  );
}
