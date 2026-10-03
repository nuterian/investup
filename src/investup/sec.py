"""Shared helpers for SEC downloads.

SEC fair-access rules: identify yourself with a User-Agent that includes a
contact email, and stay under 10 requests/second.
https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
import urllib.request

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


def user_agent() -> str:
    ua = os.environ.get("INVESTUP_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError(
            "Set INVESTUP_USER_AGENT to 'Your Name your@email.com'. "
            "The SEC requires a contact email in the User-Agent and rejects requests without one."
        )
    return ua


def get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    finally:
        time.sleep(0.2)  # well under the SEC's 10 req/s limit
