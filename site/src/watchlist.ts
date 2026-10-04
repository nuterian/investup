import { useEffect, useState } from "react";

// Personal watchlist, stored only in this browser.
const KEY = "investup.watchlist";
const EVENT = "investup-watchlist";

function read(): number[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

export function useWatchlist(): [number[], (cik: number) => void] {
  const [list, setList] = useState<number[]>(read);
  useEffect(() => {
    const sync = () => setList(read());
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const toggle = (cik: number) => {
    const next = list.includes(cik) ? list.filter((c) => c !== cik) : [cik, ...list];
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Storage unavailable (private mode): keep it for this page view only.
    }
    setList(next);
    window.dispatchEvent(new Event(EVENT));
  };
  return [list, toggle];
}
