from __future__ import annotations

import datetime as dt

from investup import digest
from investup.formd import load


def test_digest_lists_recent_filers(con, sample_quarters):
    load.load_dir(con, sample_quarters)
    d = digest.build(con, since=dt.date(2019, 1, 1), model="cell")
    assert d.end == dt.date(2019, 6, 1)
    # Only Acme filed in the window; its 2019 round is $5M of new money.
    assert [r[1] for r in d.step_up] == ["Acme Robotics, Inc."]
    assert d.step_up[0][5] == 5_000_000
    text = digest.render_markdown(d)
    assert "Acme Robotics, Inc." in text
    assert "CIK=1001" in text
