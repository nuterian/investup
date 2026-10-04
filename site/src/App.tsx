import type { ReactNode } from "react";
import { SearchBox } from "./components/SearchBox";
import { CompanyPage } from "./pages/Company";
import { Explore } from "./pages/Explore";
import { Home } from "./pages/Home";
import { Method } from "./pages/Method";
import { loadSummary } from "./data";
import { date } from "./format";
import { href, useRoute } from "./router";
import { useAsync } from "./useAsync";

export function App() {
  const route = useRoute();
  const [page, arg] = route.path;
  const summary = useAsync(loadSummary, []);

  let content: ReactNode;
  if (page === "c" && arg && /^\d+$/.test(arg)) content = <CompanyPage cik={Number(arg)} />;
  else if (page === "explore") content = <Explore params={route.params} />;
  else if (page === "method") content = <Method />;
  else content = <Home params={route.params} />;

  const nav = (to: string, label: string) => (
    <a href={href(to)} className={(page ?? "") === to ? "active" : ""}>
      {label}
    </a>
  );

  return (
    <>
      <header className="top">
        <div className="top-inner">
          <a href="#/" className="logo">
            investup
          </a>
          <nav>
            {nav("", "Dashboard")}
            {nav("explore", "Explore")}
            {nav("method", "Method")}
          </nav>
          <SearchBox />
          {summary.data && (
            <span className="fresh" title="Newest SEC filing included">
              <i className="fresh-dot" /> {date(summary.data.data_end, true)}
            </span>
          )}
        </div>
      </header>
      <main className="page">{content}</main>
      <footer className="foot muted small">
        Built from public SEC filings. Not investment advice.
      </footer>
    </>
  );
}
