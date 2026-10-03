import { describe, expect, it } from "vitest";
import type { Company, SearchEntry } from "./data";
import { fromColumnar, shardOf } from "./data";
import { change, money, multiple, pct, quarterLabel, topPct } from "./format";
import { applyFilters } from "./pages/Explore";
import { search, tokens } from "./search";

describe("format", () => {
  it("formats money compactly", () => {
    expect(money(null)).toBe("–");
    expect(money(950)).toBe("$950");
    expect(money(12_500)).toBe("$13K");
    expect(money(5_000_000)).toBe("$5.0M");
    expect(money(208_100_000)).toBe("$208M");
    expect(money(1_100_000_000)).toBe("$1.1B");
  });

  it("formats percentages, ranks and multiples", () => {
    expect(pct(0.178)).toBe("18%");
    expect(pct(0.008)).toBe("0.8%");
    expect(pct(0.008, 1)).toBe("0.8%");
    expect(topPct(0.985)).toBe("top 2%");
    expect(topPct(0.995)).toBe("top 0.5%");
    expect(topPct(0.9995)).toBe("top 0.1%");
    expect(topPct(0.8)).toBe("top 20%");
    expect(topPct(0.2)).toBe("bottom half");
    expect(multiple(0.2, 0.05)).toBe("4.0×");
    expect(multiple(0.2, 0.008)).toBe("25×");
    expect(change(110, 100)).toBe("+10%");
    expect(change(90, 100)).toBe("−10%");
    expect(quarterLabel("2026-06-30")).toBe("Q2 2026");
  });
});

describe("data", () => {
  it("expands columnar files and shards by CIK", () => {
    expect(fromColumnar<{ a: number; b: string }>({ columns: ["a", "b"], rows: [[1, "x"]] })).toEqual([
      { a: 1, b: "x" },
    ]);
    expect(shardOf(1001)).toBe("3e9");
    expect(shardOf(1024)).toBe("000");
  });
});

describe("search", () => {
  const index: SearchEntry[] = [
    { cik: 1, name: "Stripe, Inc.", state: "CA", last_year: 2024 },
    { cik: 2, name: "Greystripe Inc", state: "CA", last_year: 2012 },
    { cik: 3, name: "Stripe Milton LLC", state: "NY", last_year: 2023 },
    { cik: 4, name: "Route 92 Medical, Inc.", state: "CA", last_year: 2026 },
  ];

  it("drops legal suffixes when tokenizing", () => {
    expect(tokens("Route 92 Medical, Inc.")).toEqual(["route", "92", "medical"]);
  });

  it("matches token prefixes and prefers exact names", () => {
    expect(search(index, "stripe").map((e) => e.cik)).toEqual([1, 3]);
    expect(search(index, "rout med").map((e) => e.cik)).toEqual([4]);
  });

  it("finds companies by CIK", () => {
    expect(search(index, "3").map((e) => e.cik)[0]).toBe(3);
  });
});

describe("explore filters", () => {
  const base: Omit<Company, "cik" | "name" | "sector" | "total_raised" | "last_raise" | "p_step"> = {
    state: "CA",
    first_filing: "2020-01-01",
    largest_round: null,
    rounds: 1,
    p_ipo: 0.01,
    pct_step: 0.5,
    pct_ipo: 0.5,
    hit_step: 0.05,
    hit_ipo: 0.01,
    repeat_founder: false,
    prev_p_step: null,
    step_reason: null,
    ipo_reason: null,
  };
  const rows: Company[] = [
    { ...base, cik: 1, name: "A", sector: "Technology", total_raised: 10e6, last_raise: "2026-05-01", p_step: 0.2 },
    { ...base, cik: 2, name: "B", sector: "Health Care", total_raised: 50e6, last_raise: "2025-01-01", p_step: 0.4 },
    { ...base, cik: 3, name: "C", sector: "Technology", total_raised: 1e6, last_raise: "2026-06-01", p_step: 0.1, repeat_founder: true },
  ];
  const f = { sector: "", state: "", min: 0, within: 0, repeat: false, sort: "step" as const };

  it("sorts by bigger-round odds by default", () => {
    expect(applyFilters([...rows], f, "2026-06-30").map((c) => c.cik)).toEqual([2, 1, 3]);
  });

  it("filters by sector, size, recency and repeat founders", () => {
    expect(applyFilters([...rows], { ...f, sector: "Technology" }, "2026-06-30").map((c) => c.cik)).toEqual([1, 3]);
    expect(applyFilters([...rows], { ...f, min: 5e6 }, "2026-06-30").map((c) => c.cik)).toEqual([2, 1]);
    expect(applyFilters([...rows], { ...f, within: 12 }, "2026-06-30").map((c) => c.cik)).toEqual([1, 3]);
    expect(applyFilters([...rows], { ...f, repeat: true }, "2026-06-30").map((c) => c.cik)).toEqual([3]);
  });
});
