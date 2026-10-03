// Types and loaders for the JSON files written by `investup export`.

export interface Band {
  low: number;
  high: number;
  n: number;
  observed: number;
}

export interface TrackRecord {
  model: string;
  horizon_months: number;
  test_years: string;
  auc: number;
  base_rate: number;
  p_at_100: number;
  lift_at_100: number;
  hit_rate_by_rank: Band[];
}

export interface Summary {
  data_end: string;
  prev_date: string;
  generated_at: string;
  model: string;
  quarter: {
    this: { companies: number; money: number };
    year_ago: { companies: number; money: number };
    new_companies: number;
  };
  typical: { p_step: number; p_ipo: number };
  pulse: { q: string; companies: number; money: number }[];
  sectors: { sector: string; last_12m: number; prior_12m: number; money_12m: number }[];
  states: { state: string; companies: number; money: number }[];
  track_record: Partial<Record<"step_up" | "went_public" | "next_round", TrackRecord>>;
}

export interface Company {
  cik: number;
  name: string;
  state: string;
  sector: string;
  first_filing: string | null;
  last_raise: string | null;
  total_raised: number | null;
  largest_round: number | null;
  rounds: number;
  p_step: number | null;
  p_ipo: number | null;
  pct_step: number | null;
  pct_ipo: number | null;
  hit_step: number | null;
  hit_ipo: number | null;
  repeat_founder: boolean;
  prev_p_step: number | null;
  step_reason: string | null;
  ipo_reason: string | null;
}

export interface Lists {
  step_up: number[];
  ipo_watch: number[];
  movers: number[];
  repeat_founders: number[];
  biggest: { cik: number; new_money: number }[];
  ipo_pipeline: { cik: number; name: string; filed: string }[];
}

export interface SearchEntry {
  cik: number;
  name: string;
  state: string | null;
  last_year: number;
}

export interface Person {
  name: string;
  roles: string;
  other: { cik: number; name: string; public: number | null }[];
}

export interface Detail {
  name: string;
  state: string | null;
  sector: string;
  industry: string | null;
  year_of_inc: number | null;
  first_filing: string | null;
  last_raise: string | null;
  total_raised: number | null;
  rounds: number;
  investors_last: number | null;
  investors_max: number | null;
  revenue_range: string | null;
  went_public: string | null;
  s1_filed: string | null;
  vehicle: boolean;
  // [filed, new money, starts a new round, accession number]
  timeline: [string, number, boolean, string][];
  people: Person[];
}

interface Columnar {
  columns: string[];
  rows: unknown[][];
}

export function fromColumnar<T>(data: Columnar): T[] {
  return data.rows.map((row) => {
    const obj: Record<string, unknown> = {};
    data.columns.forEach((c, i) => (obj[c] = row[i]));
    return obj as T;
  });
}

const cache = new Map<string, Promise<unknown>>();

function load<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(`data/${path}`).then((r) => {
        if (!r.ok) throw new Error(`Couldn't load ${path} (${r.status})`);
        return r.json();
      }),
    );
  }
  return cache.get(path) as Promise<T>;
}

export const loadSummary = () => load<Summary>("summary.json");
export const loadLists = () => load<Lists>("lists.json");

let universeIndex: Promise<Map<number, Company>> | null = null;
export function loadUniverse(): Promise<Map<number, Company>> {
  universeIndex ??= load<Columnar>("universe.json").then(
    (d) => new Map(fromColumnar<Company>(d).map((c) => [c.cik, c])),
  );
  return universeIndex;
}

let searchIndex: Promise<SearchEntry[]> | null = null;
export function loadSearch(): Promise<SearchEntry[]> {
  searchIndex ??= load<Columnar>("search.json").then((d) => fromColumnar<SearchEntry>(d));
  return searchIndex;
}

export function shardOf(cik: number): string {
  return (cik % 256).toString(16).padStart(2, "0");
}

export async function loadDetail(cik: number): Promise<Detail | null> {
  const shard = await load<Record<string, Detail>>(`c/${shardOf(cik)}.json`);
  return shard[String(cik)] ?? null;
}

export function filingUrl(cik: number, accession: string): string {
  return `https://www.sec.gov/Archives/edgar/data/${cik}/${accession.replace(/-/g, "")}/${accession}-index.htm`;
}

export function edgarCompanyUrl(cik: number): string {
  return `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=D`;
}
