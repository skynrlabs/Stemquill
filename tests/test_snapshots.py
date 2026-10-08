"""Results don't drift: the fixed synthetic stems must keep producing the same notes.

If a change to the engine is meant to change results, rerun with --update-snapshots and
review the diff of tests/snapshots/ in the pull request.
"""

import json
from pathlib import Path

import pytest

SNAPSHOTS = Path(__file__).parent / "snapshots"
CASES = {
    "kit": dict(stem_type="drums"),
    "beat": dict(stem_type="drums"),
    "beat_grid_humanized": dict(stem_type="drums", grid=4, humanize_amount=0.3, key="beat"),
    "bass": dict(stem_type="bass"),
    "vocal": dict(stem_type="vocal"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_snapshot(case, stems, run, request):
    opts = dict(CASES[case])
    path = stems[opts.pop("key", case)][0]
    result = run(path, **opts)
    got = [[round(s, 4), round(e, 4), int(n), int(v)] for s, e, n, v in result["notes"]]
    file = SNAPSHOTS / f"{case}.json"
    if request.config.getoption("--update-snapshots") or not file.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        file.write_text(json.dumps(got, indent=0))
        if not request.config.getoption("--update-snapshots"):
            pytest.skip(f"created {file.name}; commit it")
        return
    expected = json.loads(file.read_text())
    assert len(got) == len(expected), "number of notes changed"
    for g, x in zip(got, expected, strict=True):
        assert g[2] == x[2], f"pitch changed at {x[0]}s"
        assert g[0] == pytest.approx(x[0], abs=0.005), f"timing changed at {x[0]}s"
        assert g[3] == pytest.approx(x[3], abs=3), f"velocity changed at {x[0]}s"
