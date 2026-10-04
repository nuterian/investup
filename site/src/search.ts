import type { SearchEntry } from "./data";

const STOP = new Set(["inc", "llc", "corp", "co", "ltd", "lp", "the", "corporation", "company"]);

export function tokens(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .filter((t) => t && !STOP.has(t));
}

/**
 * Every query token must be a prefix of some name token. Ranked by: name starts
 * with the query, then scored companies (by `boost`), then most recent filer.
 * A numeric query also matches CIKs.
 */
export function search(
  index: SearchEntry[],
  query: string,
  boost: (cik: number) => number = () => 0,
  limit = 8,
): SearchEntry[] {
  const q = tokens(query);
  if (!q.length) return [];
  const asCik = /^\d+$/.test(query.trim()) ? Number(query.trim()) : null;
  const lowered = query.trim().toLowerCase();

  const hits: { e: SearchEntry; score: number }[] = [];
  for (const e of index) {
    if (asCik !== null && e.cik === asCik) {
      hits.push({ e, score: 1e9 });
      continue;
    }
    const name = e.name.toLowerCase();
    const nameTokens = tokens(e.name);
    if (!q.every((t) => nameTokens.some((n) => n.startsWith(t)))) continue;
    let score = e.last_year;
    if (name.startsWith(lowered)) score += 1e6;
    if (nameTokens.length === q.length) score += 1e5;
    score += boost(e.cik) * 1e4;
    hits.push({ e, score });
  }
  hits.sort((a, b) => b.score - a.score || a.e.name.localeCompare(b.e.name));
  return hits.slice(0, limit).map((h) => h.e);
}
