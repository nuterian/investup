"""Download SEC Form D quarterly data set ZIPs.

SEC fair-access rules: identify yourself with a User-Agent containing a name and
contact email, and stay under 10 requests/second.
https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

# SEC moved its structured data sets from /files/structureddata/ to
# /files/datastandardsinnovation/ in 2026. We try the new location first and fall back to
# the old one. Override with INVESTUP_FORMD_URL_TEMPLATE if the SEC moves them again
# (the template gets {year} and {quarter}).
URL_TEMPLATES = (
    "https://www.sec.gov/files/datastandardsinnovation/data/form-d-data-sets/{year}q{quarter}_d.zip",
    "https://www.sec.gov/files/structureddata/data/form-d-data-sets/{year}q{quarter}_d.zip",
)

FIRST_QUARTER = (2008, 1)
_QUARTER_RE = re.compile(r"^(\d{4})[qQ]([1-4])$")


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


def _user_agent() -> str:
    ua = os.environ.get("INVESTUP_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError(
            "Set INVESTUP_USER_AGENT to 'Your Name your@email.com'. "
            "The SEC requires a contact in the User-Agent for automated downloads."
        )
    return ua


def _templates() -> tuple[str, ...]:
    override = os.environ.get("INVESTUP_FORMD_URL_TEMPLATE")
    return (override,) if override else URL_TEMPLATES


def download_quarter(year: int, quarter: int, dest: Path, *, force: bool = False) -> Path | None:
    """Download one quarter. Returns the path, or None if no URL template had it."""
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / quarter_filename(year, quarter)
    if target.exists() and not force:
        return target

    headers = {"User-Agent": _user_agent(), "Accept-Encoding": "identity"}
    for template in _templates():
        url = template.format(year=year, quarter=quarter)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                tmp = target.with_suffix(".part")
                tmp.write_bytes(resp.read())
                tmp.replace(target)
                return target
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        finally:
            time.sleep(0.2)  # well under the SEC's 10 req/s limit
    return None


def download_range(
    start: tuple[int, int], end: tuple[int, int], dest: Path, *, force: bool = False
) -> list[Path]:
    paths = []
    for year, quarter in quarter_range(start, end):
        path = download_quarter(year, quarter, dest, force=force)
        label = f"{year}q{quarter}"
        if path is None:
            print(f"{label}: not found at any known URL (set INVESTUP_FORMD_URL_TEMPLATE?)")
        else:
            print(f"{label}: {path}")
            paths.append(path)
    return paths
