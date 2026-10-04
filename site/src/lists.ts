// Dashboard lists, computed in the browser so they can be filtered by sector.
// Mirrors investup.export.build_lists for the unfiltered view.

import type { Company, Lists } from "./data";

export interface DashboardLists {
  step_up: Company[];
  ipo_watch: Company[];
  movers: Company[];
  repeat_founders: Company[];
  biggest: { c: Company; new_money: number }[];
  ipo_pipeline: { cik: number; name: string; filed: string; c?: Company }[];
}

function monthsBefore(isoDate: string, months: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

const by =
  (key: (c: Company) => number) =>
  (a: Company, b: Company) =>
    key(b) - key(a) || a.cik - b.cik;

export function computeLists(
  universe: Map<number, Company>,
  exported: Lists,
  dataEnd: string,
  sector = "",
  n = 10,
): DashboardLists {
  const yearAgo = monthsBefore(dataEnd, 12);
  const all = [...universe.values()].filter((c) => !sector || c.sector === sector);
  const active = all.filter((c) => (c.last_raise ?? "") >= yearAgo);
  const inSector = (cik: number) => {
    const c = universe.get(cik);
    return c && (!sector || c.sector === sector) ? c : undefined;
  };

  return {
    step_up: [...active].sort(by((c) => c.p_step ?? 0)).slice(0, n),
    ipo_watch: all
      .filter((c) => (c.total_raised ?? 0) >= 5_000_000)
      .sort(by((c) => c.p_ipo ?? 0))
      .slice(0, n),
    movers: active
      .filter((c) => c.prev_p_step != null)
      .sort(by((c) => (c.p_step ?? 0) - (c.prev_p_step ?? 0)))
      .slice(0, n),
    repeat_founders: all
      .filter((c) => c.repeat_founder && (c.first_filing ?? "") >= yearAgo)
      .sort(by((c) => c.p_step ?? 0))
      .slice(0, n),
    biggest: exported.biggest
      .map((b) => ({ c: inSector(b.cik), new_money: b.new_money }))
      .filter((b): b is { c: Company; new_money: number } => !!b.c)
      .slice(0, n),
    ipo_pipeline: exported.ipo_pipeline
      .map((p) => ({ ...p, c: universe.get(p.cik) }))
      .filter((p) => !sector || p.c?.sector === sector)
      .slice(0, n),
  };
}
