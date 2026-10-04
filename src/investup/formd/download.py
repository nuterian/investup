"""Download SEC Form D quarterly data set ZIPs.

We read the SEC's Form D data sets page to find each quarter's link rather
than guessing URLs. The files live under more than one path
(/files/structureddata/... and, since 2026, /files/datastandardsinnovation/...),
and some have suffixes such as 2008q2_d_0.zip.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

from investup.sec import get, quarter_range

INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets"
_ZIP_LINK_RE = re.compile(r'href="([^"]*?/(\d{4})q([1-4])_d(?:_\d+)?\.zip)"', re.IGNORECASE)


def quarter_filename(year: int, quarter: int) -> str:
    return f"{year}q{quarter}_d.zip"


def parse_index(html: str, base_url: str = INDEX_URL) -> dict[tuple[int, int], str]:
    """Map (year, quarter) to an absolute ZIP URL from the data sets page."""
    links: dict[tuple[int, int], str] = {}
    for href, year, quarter in _ZIP_LINK_RE.findall(html):
        links.setdefault((int(year), int(quarter)), urllib.parse.urljoin(base_url, href))
    return links


def available_quarters() -> dict[tuple[int, int], str]:
    index_url = os.environ.get("INVESTUP_FORMD_INDEX_URL", INDEX_URL)
    links = parse_index(get(index_url).decode("utf-8", "replace"), index_url)
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
        tmp.write_bytes(get(url))
        tmp.replace(target)
        print(f"{label}: {target} ({target.stat().st_size / 1e6:.1f} MB)")
        paths.append(target)
    return paths
