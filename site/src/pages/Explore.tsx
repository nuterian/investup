import { useMemo, useState } from "react";
import { CompanyLink, ErrorNote, Loading, ScorePill } from "../components/Bits";
import { type Company, type Summary, loadSummary, loadUniverse } from "../data";
import { date, money } from "../format";
import { replaceParams } from "../router";
import { useAsync } from "../useAsync";

type Sort = "step" | "ipo" | "raised" | "recent";

interface Filters {
  sector: string;
  state: string;
  min: number; // minimum total raised, $
  within: number; // last raise within N months (0 = any)
  repeat: boolean;
  sort: Sort;
}

const MIN_OPTIONS = [0, 1e6, 5e6, 20e6, 100e6];
const WITHIN_OPTIONS = [0, 6, 12, 24];

function readFilters(params: URLSearchParams): Filters {
  const sort = params.get("sort");
  return {
    sector: params.get("sector") ?? "",
    state: params.get("state") ?? "",
    min: Number(params.get("min") ?? 0) || 0,
    within: Number(params.get("within") ?? 0) || 0,
    repeat: params.get("repeat") === "1",
    sort: sort === "ipo" || sort === "raised" || sort === "recent" ? sort : "step",
  };
}

export function applyFilters(rows: Company[], f: Filters, dataEnd: string): Company[] {
  let cutoff = "";
  if (f.within) {
    const d = new Date(dataEnd);
    d.setMonth(d.getMonth() - f.within);
    cutoff = d.toISOString().slice(0, 10);
  }
  const out = rows.filter(
    (c) =>
      (!f.sector || c.sector === f.sector) &&
      (!f.state || c.state === f.state) &&
      (c.total_raised ?? 0) >= f.min &&
      (!cutoff || (c.last_raise ?? "") >= cutoff) &&
      (!f.repeat || c.repeat_founder),
  );
  const key: Record<Sort, (c: Company) => number | string> = {
    step: (c) => c.p_step ?? 0,
    ipo: (c) => c.p_ipo ?? 0,
    raised: (c) => c.total_raised ?? 0,
    recent: (c) => c.last_raise ?? "",
  };
  const k = key[f.sort];
  return out.sort((a, b) => (k(b) > k(a) ? 1 : k(b) < k(a) ? -1 : a.cik - b.cik));
}

function toCsv(rows: Company[]): string {
  const cols = [
    "cik", "name", "state", "sector", "first_filing", "last_raise", "total_raised",
    "largest_round", "rounds", "hit_step", "pct_step", "hit_ipo", "pct_ipo", "repeat_founder",
  ] as const;
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

function download(rows: Company[]) {
  const url = URL.createObjectURL(new Blob([toCsv(rows)], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "investup-companies.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function Explore({ params }: { params: URLSearchParams }) {
  const state = useAsync(() => Promise.all([loadUniverse(), loadSummary()]), []);
  if (state.error) return <ErrorNote error={state.error} />;
  if (!state.data) return <Loading />;
  const [universe, summary] = state.data;
  return <Screener universe={universe} summary={summary} initial={readFilters(params)} />;
}

function Screener({
  universe,
  summary,
  initial,
}: {
  universe: Map<number, Company>;
  summary: Summary;
  initial: Filters;
}) {
  const [f, setF] = useState<Filters>(initial);
  const [shown, setShown] = useState(100);
  const all = useMemo(() => [...universe.values()], [universe]);
  const sectors = useMemo(() => [...new Set(all.map((c) => c.sector))].sort(), [all]);
  const states = useMemo(() => [...new Set(all.map((c) => c.state))].sort(), [all]);
  const rows = useMemo(() => applyFilters(all, f, summary.data_end), [all, f, summary]);

  const update = (patch: Partial<Filters>) => {
    const next = { ...f, ...patch };
    setF(next);
    setShown(100);
    replaceParams("explore", {
      sector: next.sector,
      state: next.state,
      min: next.min || undefined,
      within: next.within || undefined,
      repeat: next.repeat ? 1 : undefined,
      sort: next.sort === "step" ? undefined : next.sort,
    });
  };

  return (
    <div className="stack">
      <h1>Explore</h1>
      <div className="filters">
        <select value={f.sector} onChange={(e) => update({ sector: e.target.value })} aria-label="Sector">
          <option value="">All sectors</option>
          {sectors.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={f.state} onChange={(e) => update({ state: e.target.value })} aria-label="State">
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={f.min} onChange={(e) => update({ min: Number(e.target.value) })} aria-label="Total raised">
          {MIN_OPTIONS.map((m) => (
            <option key={m} value={m}>
              {m ? `Raised ${money(m)}+` : "Any amount raised"}
            </option>
          ))}
        </select>
        <select
          value={f.within}
          onChange={(e) => update({ within: Number(e.target.value) })}
          aria-label="Last raise"
        >
          {WITHIN_OPTIONS.map((m) => (
            <option key={m} value={m}>
              {m ? `Raised in last ${m} months` : "Raised in last 36 months"}
            </option>
          ))}
        </select>
        <label className="check">
          <input type="checkbox" checked={f.repeat} onChange={(e) => update({ repeat: e.target.checked })} />
          Repeat founders
        </label>
        <select value={f.sort} onChange={(e) => update({ sort: e.target.value as Sort })} aria-label="Sort">
          <option value="step">Sort: bigger-round odds</option>
          <option value="ipo">Sort: IPO odds</option>
          <option value="raised">Sort: total raised</option>
          <option value="recent">Sort: most recent raise</option>
        </select>
      </div>
      <p className="muted small">
        {rows.length.toLocaleString()} companies ·{" "}
        <button type="button" className="link" onClick={() => download(rows)}>
          Download CSV
        </button>
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Sector</th>
              <th>State</th>
              <th>Last raise</th>
              <th className="num">Total raised</th>
              <th className="num">Bigger round</th>
              <th className="num">IPO</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map((c) => (
              <tr key={c.cik}>
                <td>
                  <CompanyLink cik={c.cik} name={c.name} />
                  {c.repeat_founder && <span className="tag">repeat</span>}
                </td>
                <td>{c.sector}</td>
                <td>{c.state}</td>
                <td>{date(c.last_raise)}</td>
                <td className="num">{money(c.total_raised)}</td>
                <td className="num">
                  <ScorePill c={c} kind="step" summary={summary} />
                </td>
                <td className="num">
                  <ScorePill c={c} kind="ipo" summary={summary} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {shown < rows.length && (
        <button type="button" className="more-btn" onClick={() => setShown(shown + 100)}>
          Show more
        </button>
      )}
    </div>
  );
}
