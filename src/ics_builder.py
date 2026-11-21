from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from hashlib import sha1
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, Timezone, TimezoneStandard

from .parser import CourseBlock


def _compress(weeks: list[int]) -> str:
    parts: list[str] = []
    i = 0
    while i < len(weeks):
        j = i
        while j + 1 < len(weeks) and weeks[j + 1] == weeks[j] + 1:
            j += 1
        parts.append(str(weeks[i]) if i == j else f"{weeks[i]}-{weeks[j]}")
        i = j + 1
    return ",".join(parts)


def _at(day: date, hhmm: str, tz: ZoneInfo) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def _normalize_overrides(raw) -> list[dict]:
    result: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        course = str(item.get("course", "")).strip()
        action = str(item.get("action", "")).strip().lower()
        if not course or action not in {"cancel", "modify"} or item.get("week") is None:
            continue
        result.append({**item, "course": course, "action": action, "week": int(item["week"])})
    return result


def _assign_uids(blocks: list[CourseBlock]) -> None:
    groups: dict[tuple, list[CourseBlock]] = {}
    for block in blocks:
        key = (block.name, block.teacher, block.weekday, block.start_period)
        groups.setdefault(key, []).append(block)
    for key, group in groups.items():
        group.sort(key=lambda b: (b.weeks[0], b.room, b.code))
        for index, block in enumerate(group):
            raw = "|".join([*map(str, key), str(index)])
            block.uid = sha1(raw.encode("utf-8")).hexdigest()[:24] + "@hebi-timetable"


def _timezone_component(tzid: str, tz: ZoneInfo) -> Timezone:
    offset = datetime(2026, 1, 1, tzinfo=tz).utcoffset() or timedelta(0)
    component = Timezone()
    component.add("tzid", tzid)
    standard = TimezoneStandard()
    standard.add("dtstart", datetime(1970, 1, 1))
    standard.add("tzoffsetfrom", offset)
    standard.add("tzoffsetto", offset)
    standard.add("tzname", "CST")
    component.add_component(standard)
    return component


def _event(block: CourseBlock, dtstart: datetime, dtend: datetime, room: str, weeks: list[int], now: datetime) -> Event:
    event = Event()
    event.add("summary", block.name)
    event.add("dtstart", dtstart)
    event.add("dtend", dtend)
    event.add("location", room)
    event.add("description", f"教师：{block.teacher}\n周次：{_compress(weeks)}")
    event.add("uid", block.uid)
    event.add("dtstamp", now)
    event.add("last-modified", now)
    event.add("sequence", 0)
    return event


def _series(block: CourseBlock, weeks: list[int], semester_start: date, periods: dict, tz: ZoneInfo, now: datetime) -> Event:
    start_hhmm = periods[block.start_period][0]
    end_hhmm = periods[block.end_period][1]
    first, last = weeks[0], weeks[-1]
    first_day = semester_start + timedelta(days=(first - 1) * 7 + block.weekday)
    last_day = semester_start + timedelta(days=(last - 1) * 7 + block.weekday)
    event = _event(block, _at(first_day, start_hhmm, tz), _at(first_day, end_hhmm, tz), block.room, weeks, now)
    until = _at(last_day, start_hhmm, tz).astimezone(dt_timezone.utc)
    event.add("rrule", {"freq": "WEEKLY", "until": until})
    present = set(weeks)
    skipped = [
        _at(semester_start + timedelta(days=(week - 1) * 7 + block.weekday), start_hhmm, tz)
        for week in range(first, last + 1)
        if week not in present
    ]
    if skipped:
        event.add("exdate", skipped)
    return event


def _modified(block: CourseBlock, week: int, override: dict, semester_start: date, periods: dict, tz: ZoneInfo, now: datetime) -> Event:
    start_period, end_period = block.start_period, block.end_period
    if override.get("periods"):
        sequence = [int(value) for value in override["periods"]]
        start_period, end_period = sequence[0], sequence[-1]
    elif override.get("period"):
        start_period = int(override["period"])
        end_period = int(override.get("end_period") or start_period)
    start_hhmm = periods[start_period][0]
    end_hhmm = periods[end_period][1]
    room = str(override.get("room") or block.room).strip()
    day = semester_start + timedelta(days=(week - 1) * 7 + block.weekday)
    event = _event(block, _at(day, start_hhmm, tz), _at(day, end_hhmm, tz), room, [week], now)
    event["uid"] = f"{block.uid}-w{week}"
    return event


def build_calendar(blocks: list[CourseBlock], semester: dict, raw_overrides) -> Calendar:
    tzid = str(semester.get("timezone") or "Asia/Shanghai")
    tz = ZoneInfo(tzid)
    semester_start = date.fromisoformat(str(semester["semester_start"]))
    periods = {int(item["index"]): (str(item["start"]), str(item["end"])) for item in semester["periods"]}
    overrides = _normalize_overrides(raw_overrides)
    now = datetime.now(dt_timezone.utc)

    _assign_uids(blocks)

    calendar = Calendar()
    calendar.add("prodid", "-//hebi-timetable//CN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", "课表")
    calendar.add("x-wr-timezone", tzid)
    calendar.add_component(_timezone_component(tzid, tz))

    matched: set[int] = set()
    emitted: set[tuple] = set()
    for block in blocks:
        applicable = [item for item in overrides if item["course"] in (block.name, block.code)]
        removed = {item["week"] for item in applicable}
        weeks = [week for week in block.weeks if week not in removed]
        if weeks:
            calendar.add_component(_series(block, weeks, semester_start, periods, tz, now))
        for item in applicable:
            matched.add(id(item))
            week = item["week"]
            key = (block.uid, week)
            if item["action"] != "modify" or week not in block.weeks or key in emitted:
                continue
            emitted.add(key)
            calendar.add_component(_modified(block, week, item, semester_start, periods, tz, now))

    for item in overrides:
        if id(item) not in matched:
            print(f"警告: 调课规则未命中任何课程: {item['course']} 第{item['week']}周")

    return calendar