from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser import parse_weeks, weeks_from_bits


def test_range():
    assert parse_weeks("1-15周") == list(range(1, 16))


def test_odd():
    assert parse_weeks("1-15(单)") == [1, 3, 5, 7, 9, 11, 13, 15]


def test_even():
    assert parse_weeks("2-16(双)") == [2, 4, 6, 8, 10, 12, 14, 16]


def test_list():
    assert parse_weeks("1,3,5周") == [1, 3, 5]


def test_page_gap_format():
    assert parse_weeks("1-6 10-19") == [*range(1, 7), *range(10, 20)]


def test_single_weeks():
    assert parse_weeks("2 12") == [2, 12]


def test_parity_on_list():
    assert parse_weeks("1,4,7(单)") == [1, 7]


def test_empty():
    assert parse_weeks("") == []


def test_invalid():
    try:
        parse_weeks("abc")
    except ValueError:
        return
    raise AssertionError("非法格式应抛 ValueError")


def test_bits():
    assert weeks_from_bits("010011") == [1, 4, 5]


def test_bits_from_one():
    assert weeks_from_bits("010011", week_from=1) == [2, 5, 6]


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