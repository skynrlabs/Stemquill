"""Humanize: small, repeatable changes."""

from stemquill.core.humanize import humanize

NOTES = [(i * 0.25, i * 0.25 + 0.1, 36 + (i % 3), 100) for i in range(64)]


def test_off_means_unchanged():
    assert humanize(NOTES, 120, 0.0, True) == NOTES


def test_same_result_every_time():
    assert humanize(NOTES, 120, 0.5, True) == humanize(NOTES, 120, 0.5, True)


def test_changes_stay_small():
    for amount in (0.2, 0.5, 1.0):
        out = humanize(NOTES, 120, amount, True)
        assert len(out) == len(NOTES)
        for (s0, _, n0, _), (s1, e1, n1, v1) in zip(NOTES, out, strict=True):
            assert n0 == n1
            assert abs(s1 - s0) <= 0.018 * amount + 1e-9
            assert e1 > s1
            assert 1 <= v1 <= 127


def test_it_actually_does_something():
    out = humanize(NOTES, 120, 0.5, True)
    assert out != NOTES
