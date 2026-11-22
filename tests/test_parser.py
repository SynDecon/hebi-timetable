from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser import expand_week_periods, parse_periods, parse_weeks, weeks_from_bits


SPRING = {1: ("08:00", "08:45"), 6: ("15:00", "15:45")}
AUTUMN = {1: ("08:00", "08:45"), 6: ("14:30", "15:15")}


PERIOD_LABELS = [
    ("一", "08:00", "08:45"),
    ("二", "08:55", "09:40"),
    ("三", "10:00", "10:45"),
    ("四", "10:55", "11:40"),
    ("五", "11:50", "12:35"),
    ("六", "14:30", "15:15"),
    ("七", "15:25", "16:10"),
    ("八", "16:30", "17:15"),
    ("九", "17:25", "18:10"),
    ("十", "19:00", "19:45"),
    ("十一", "19:55", "20:40"),
]


def _periods_html(items):
    return "".join(
        f'<font size="2px"> 第{name}节<br>{start}<br>-<br>{end}</font>'
        for name, start, end in items
    )


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


def test_periods_from_page():
    expected = {index + 1: (start, end) for index, (_, start, end) in enumerate(PERIOD_LABELS)}
    assert parse_periods(_periods_html(PERIOD_LABELS)) == expected


def test_periods_single_digit_hour():
    assert parse_periods(_periods_html([("一", "8:00", "8:45")])) == {1: ("08:00", "08:45")}


def test_periods_missing_index():
    assert parse_periods(_periods_html([("一", "08:00", "08:45"), ("三", "10:00", "10:45")])) == {}


def test_periods_bad_range():
    assert parse_periods(_periods_html([("一", "08:00", "08:00")])) == {}
    assert parse_periods(_periods_html([("一", "24:00", "25:00")])) == {}


def test_periods_not_found():
    assert parse_periods("<html></html>") == {}


def test_week_periods_same():
    assert expand_week_periods({1: AUTUMN, 4: AUTUMN}, 4) == {week: AUTUMN for week in range(1, 5)}


def test_week_periods_switch():
    assert expand_week_periods({1: SPRING, 3: AUTUMN, 4: AUTUMN}, 4) == {
        1: SPRING,
        2: SPRING,
        3: AUTUMN,
        4: AUTUMN,
    }


def test_week_periods_missing_middle():
    assert expand_week_periods({1: SPRING, 4: AUTUMN}, 4) == {
        1: SPRING,
        2: SPRING,
        3: SPRING,
        4: AUTUMN,
    }


def test_week_periods_missing_first():
    assert expand_week_periods({2: AUTUMN}, 4) == {}


def test_week_periods_single_week():
    assert expand_week_periods({1: SPRING}, 1) == {1: SPRING}


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