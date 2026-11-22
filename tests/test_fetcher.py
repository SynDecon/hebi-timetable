from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.fetcher as fetcher

HTML = "semester.id=322&ids=12345"
SPRING = {1: ("08:00", "08:45"), 6: ("15:00", "15:45")}
AUTUMN = {1: ("08:00", "08:45"), 6: ("14:30", "15:15")}


class _Session:
    pass


def _probe(func, max_week=10):
    calls = []
    original = fetcher._fetch_week_periods

    def fake(session, form, week):
        calls.append(week)
        return func(week)

    fetcher._fetch_week_periods = fake
    try:
        probes = fetcher.fetch_week_periods(_Session(), HTML, max_week)
    finally:
        fetcher._fetch_week_periods = original
    return calls, probes


def test_probe_stops_at_first_change():
    calls, probes = _probe(lambda week: SPRING if week < 4 else AUTUMN)
    assert calls == [1, 10, 2, 3, 4]
    assert set(probes) == {1, 2, 3, 4, 10}


def test_probe_stops_when_same():
    calls, probes = _probe(lambda week: AUTUMN)
    assert calls == [1, 10]
    assert set(probes) == {1, 10}


def test_probe_without_last_week():
    calls, probes = _probe(lambda week: {} if week == 10 else (SPRING if week < 4 else AUTUMN))
    assert calls == [1, 10, 2, 3, 4]
    assert 10 not in probes


if __name__ == "__main__":
    failed = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"PASS {name}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failed else 0)