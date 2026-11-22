from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ics_builder import build_calendar
from src.parser import CourseBlock

PERIODS = [
    (1, "08:00", "08:45"),
    (2, "08:55", "09:40"),
    (3, "10:00", "10:45"),
    (4, "10:55", "11:40"),
    (5, "11:50", "12:35"),
    (6, "14:30", "15:15"),
    (7, "15:25", "16:10"),
    (8, "16:30", "17:15"),
    (9, "17:25", "18:10"),
    (10, "19:00", "19:45"),
    (11, "19:55", "20:40"),
]
SPRING = {6: ("15:00", "15:45")}
AUTUMN = {6: ("14:30", "15:15")}


def _semester():
    return {
        "semester_start": "2026-08-31",
        "timezone": "Asia/Shanghai",
        "periods": [{"index": index, "start": start, "end": end} for index, start, end in PERIODS],
    }


def _block(weeks, start_period=6, end_period=6):
    return CourseBlock(
        name="测试课",
        code="T001",
        teacher="老师",
        room="A101",
        weekday=0,
        start_period=start_period,
        end_period=end_period,
        weeks=weeks,
    )


def test_split_at_switch():
    week_periods = {1: SPRING, 2: SPRING, 3: AUTUMN, 4: AUTUMN}
    text = build_calendar([_block([1, 2, 3, 4])], _semester(), [], week_periods).to_ical().decode()
    assert text.count("BEGIN:VEVENT") == 2
    assert "20260831T150000" in text
    assert "20260914T143000" in text
    assert text.count("RRULE:FREQ=WEEKLY;COUNT=2") == 2
    uids = [line for line in text.splitlines() if line.startswith("UID:")]
    assert len(uids) == 2 and len(set(uids)) == 2


def test_no_split_when_times_same():
    week_periods = {1: SPRING, 2: SPRING, 3: AUTUMN, 4: AUTUMN}
    text = build_calendar([_block([1, 2, 3, 4], 1, 1)], _semester(), [], week_periods).to_ical().decode()
    assert text.count("BEGIN:VEVENT") == 1
    assert "20260831T080000" in text


def test_fallback_without_week_periods():
    text = build_calendar([_block([1, 2])], _semester(), []).to_ical().decode()
    assert text.count("BEGIN:VEVENT") == 1
    assert "20260831T143000" in text


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