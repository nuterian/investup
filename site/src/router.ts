import { useEffect, useState } from "react";

// Hash routes (#/c/123, #/explore?sector=…) work on GitHub Pages with no server.
export interface Route {
  path: string[];
  params: URLSearchParams;
}

function parse(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const [p, q = ""] = hash.split("?");
  return { path: p.split("/").filter(Boolean), params: new URLSearchParams(q) };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onChange = () => {
      setRoute(parse());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function href(path: string, params?: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== "") q.set(k, String(v));
  }
  const qs = q.toString();
  return `#/${path}${qs ? `?${qs}` : ""}`;
}

/** Update query params without adding a history entry or scrolling. */
export function replaceParams(path: string, params: Record<string, string | number | undefined>) {
  window.history.replaceState(null, "", href(path, params));
}

export const companyHref = (cik: number) => href(`c/${cik}`);
