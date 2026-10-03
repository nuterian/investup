"""Download SEC Form D quarterly data set ZIPs.

We read the SEC's Form D data sets page to find each quarter's link rather
than guessing URLs. The files live under more than one path
(/files/structureddata/... and, since 2026, /files/datastandardsinnovation/...),
and some have suffixes such as 2008q2_d_0.zip.

SEC fair-access rules: identify yourself with a User-Agent that includes a
contact email, and stay under 10 requests/second.
https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets"
_QUARTER_RE = re.compile(r"^(\d{4})[qQ]([1-4])$")
_ZIP_LINK_RE = re.compile(r'href="([^"]*?/(\d{4})q([1-4])_d(?:_\d+)?\.zip)"', re.IGNORECASE)


def parse_quarter(text: str) -> tuple[int, int]:
    m = _QUARTER_RE.match(text.strip())
    if not m:
        raise ValueError(f"Expected a quarter like 2015q1, got {text!r}")
    return int(m.group(1)), int(m.group(2))


def last_complete_quarter(today: dt.date | None = None) -> tuple[int, int]:
    today = today or dt.date.today()
    q = (today.month - 1) // 3 + 1
    return (today.year, q - 1) if q > 1 else (today.year - 1, 4)


def quarter_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out = []
    y, q = start
    while (y, q) <= end:
        out.append((y, q))
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


def quarter_filename(year: int, quarter: int) -> str:
    return f"{year}q{quarter}_d.zip"


def user_agent() -> str:
    ua = os.environ.get("INVESTUP_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError(
            "Set INVESTUP_USER_AGENT to 'Your Name your@email.com'. "
            "The SEC requires a contact email in the User-Agent and rejects requests without one."
        )
    return ua


def _get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    finally:
        time.sleep(0.2)  # well under the SEC's 10 req/s limit


def parse_index(html: str, base_url: str = INDEX_URL) -> dict[tuple[int, int], str]:
    """Map (year, quarter) to an absolute ZIP URL from the data sets page."""
    links: dict[tuple[int, int], str] = {}
    for href, year, quarter in _ZIP_LINK_RE.findall(html):
        links.setdefault((int(year), int(quarter)), urllib.parse.urljoin(base_url, href))
    return links


def available_quarters() -> dict[tuple[int, int], str]:
    index_url = os.environ.get("INVESTUP_FORMD_INDEX_URL", INDEX_URL)
    links = parse_index(_get(index_url).decode("utf-8", "replace"), index_url)
    if not links:
        raise RuntimeError(f"No Form D ZIP links found on {index_url}; has the page moved?")
    return links


def download_range(
    start: tuple[int, int], end: tuple[int, int], dest: Path, *, force: bool = False
) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    links = available_quarters()
    paths = []
    for year, quarter in quarter_range(start, end):
        label = f"{year}q{quarter}"
        target = dest / quarter_filename(year, quarter)
        if target.exists() and not force:
            print(f"{label}: already downloaded")
            paths.append(target)
            continue
        url = links.get((year, quarter))
        if url is None:
            print(f"{label}: not published yet")
            continue
        tmp = target.with_suffix(".part")
        tmp.write_bytes(_get(url))
        tmp.replace(target)
        print(f"{label}: {target} ({target.stat().st_size / 1e6:.1f} MB)")
        paths.append(target)
    return paths
