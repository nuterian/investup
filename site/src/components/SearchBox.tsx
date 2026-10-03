import { useEffect, useRef, useState } from "react";
import { type Company, type SearchEntry, loadSearch, loadUniverse } from "../data";
import { companyHref } from "../router";
import { search } from "../search";

export function SearchBox() {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState<SearchEntry[] | null>(null);
  const [universe, setUniverse] = useState<Map<number, Company> | null>(null);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // ⌘K / Ctrl+K or "/" focuses search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest("input, textarea, select");
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const warm = () => {
    if (!index) loadSearch().then(setIndex);
    if (!universe) loadUniverse().then(setUniverse);
  };

  const results = index
    ? search(index, query, (cik) => universe?.get(cik)?.pct_step ?? 0)
    : [];

  const go = (cik: number) => {
    window.location.hash = companyHref(cik);
    setQuery("");
    setOpen(false);
    input.current?.blur();
  };

  return (
    <div className="search">
      <input
        ref={input}
        type="search"
        placeholder="Search companies or CIK…"
        aria-label="Search companies"
        value={query}
        onFocus={() => {
          warm();
          setOpen(true);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, results.length - 1));
          else if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
          else if (e.key === "Enter" && results[active]) go(results[active].cik);
          else if (e.key === "Escape") input.current?.blur();
          else return;
          e.preventDefault();
        }}
      />
      <kbd className="search-hint">⌘K</kbd>
      {open && query && (
        <ul className="search-results" role="listbox">
          {!index && <li className="muted">Loading…</li>}
          {index && results.length === 0 && <li className="muted">No matches</li>}
          {results.map((r, i) => (
            <li
              key={r.cik}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseDown={() => go(r.cik)}
              onMouseEnter={() => setActive(i)}
            >
              <span>{r.name}</span>
              <span className="muted">
                {r.state ?? ""} · last filed {r.last_year}
                {universe?.has(r.cik) ? " · scored" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
