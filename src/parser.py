from __future__ import annotations

import re
from dataclasses import dataclass

ACTIVITY_MARKER = "activity = new TaskActivity("

_TEACHERS_RE = re.compile(r"var teachers\s*=\s*\[(.*?)\];", re.S)
_TEACHER_NAME_RE = re.compile(r'name\s*:\s*"((?:[^"\\]|\\.)*)"')
_COURSE_RE = re.compile(r"^(.*?)\s*\(([\d.]+)\)$")
_UNIT_RE = re.compile(r"var unitCount\s*=\s*(\d+)")
_INDEX_RE = re.compile(r"index\s*=\s*([0-9*+\s]+);")
_SEMESTER_RE = re.compile(r"semester\.id=(\d+)")
_IDS_RE = re.compile(r"[?&]ids=(\d+)")
_MARSHAL_FROM_RE = re.compile(r"marshalTable\(\s*(\d+)\s*,")


@dataclass
class CourseBlock:
    name: str
    code: str
    teacher: str
    room: str
    weekday: int
    start_period: int
    end_period: int
    weeks: list[int]
    uid: str = ""


def parse_weeks(spec: str) -> list[int]:
    text = str(spec).strip()
    if not text:
        return []
    text = (
        text.replace("（", "(")
        .replace("）", ")")
        .replace("，", ",")
        .replace("、", ",")
        .replace("第", "")
    )
    parity = None
    found = re.search(r"\((单|双)\)", text)
    if found:
        parity = found.group(1)
        text = text[: found.start()] + text[found.end() :]
    text = text.replace("周", "").replace("(", "").replace(")", "")
    weeks: set[int] = set()
    for part in re.split(r"[,\s]+", text):
        if not part:
            continue
        found = re.fullmatch(r"(\d+)-(\d+)", part)
        if found:
            first, last = int(found.group(1)), int(found.group(2))
            if first > last:
                raise ValueError(f"周次区间不合法: {part}")
            weeks.update(range(first, last + 1))
            continue
        if re.fullmatch(r"\d+", part):
            weeks.add(int(part))
            continue
        raise ValueError(f"无法解析周次: {part}")
    if parity == "单":
        weeks = {w for w in weeks if w % 2 == 1}
    elif parity == "双":
        weeks = {w for w in weeks if w % 2 == 0}
    return sorted(weeks)


def weeks_from_bits(bits: str, week_from: int = 2) -> list[int]:
    offset = 2 - week_from
    weeks = []
    for position, flag in enumerate(bits):
        if flag != "1":
            continue
        week = position + offset
        if week >= 1:
            weeks.append(week)
    return weeks


def parse_semester_params(html: str) -> tuple[str | None, str | None]:
    semester = _SEMESTER_RE.search(html)
    ids = _IDS_RE.search(html)
    return (
        semester.group(1) if semester else None,
        ids.group(1) if ids else None,
    )


def _find_activity_bodies(html: str) -> list[tuple[int, int, str]]:
    found = []
    cursor = 0
    while True:
        start = html.find(ACTIVITY_MARKER, cursor)
        if start < 0:
            break
        i = start + len(ACTIVITY_MARKER)
        depth = 1
        quote = None
        while i < len(html) and depth:
            char = html[i]
            if quote:
                if char == "\\":
                    i += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            i += 1
        found.append((start, i, html[start + len(ACTIVITY_MARKER) : i - 1]))
        cursor = i
    return found


def _split_args(body: str) -> list[str]:
    args: list[str] = []
    current = ""
    quote = None
    depth = 0
    i = 0
    while i < len(body):
        char = body[i]
        if quote:
            if char == "\\":
                current += body[i : i + 2]
                i += 2
                continue
            current += char
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            current += char
        elif char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += char
        i += 1
    args.append(current.strip())
    return args


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return (
        value.replace("\\\\", "\\")
        .replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\t", "\t")
        .replace("\\n", "\n")
    )


def _eval_index(expr: str) -> int | None:
    compact = expr.replace(" ", "")
    if not compact or not re.fullmatch(r"[0-9*+]+", compact):
        return None
    total = 0
    for term in compact.split("+"):
        if not term:
            continue
        product = 1
        for factor in term.split("*"):
            product *= int(factor)
        total += product
    return total


def _normalize_room(room: str) -> str:
    room = room.replace("\t", " ").replace("鹤壁工程技术学院", " ")
    return re.sub(r"\s+", " ", room).strip()


def _split_course(raw: str) -> tuple[str, str]:
    raw = _unquote(raw)
    found = _COURSE_RE.match(raw)
    if not found:
        return raw, ""
    return found.group(1).strip(), found.group(2)


def parse_course_table(html: str) -> list[CourseBlock]:
    unit_match = _UNIT_RE.search(html)
    if not unit_match:
        raise ValueError("页面中没有找到 unitCount，可能不是课表页面")
    unit_count = int(unit_match.group(1))
    marshal_from = _MARSHAL_FROM_RE.search(html)
    week_from = int(marshal_from.group(1)) if marshal_from else 2

    bodies = _find_activity_bodies(html)
    if not bodies:
        raise ValueError("页面中没有找到 TaskActivity，可能未登录或课表为空")

    blocks: list[CourseBlock] = []
    seen: set[tuple] = set()
    for position, (start, end, body) in enumerate(bodies):
        prefix = html[:start] if position == 0 else html[bodies[position - 1][1] : start]
        teachers = _TEACHERS_RE.findall(prefix)
        names = _TEACHER_NAME_RE.findall(teachers[-1]) if teachers else []

        args = _split_args(body)
        if len(args) < 7:
            continue
        name, code = _split_course(args[3])
        room = _normalize_room(_unquote(args[5]))
        bits = _unquote(args[6])
        if set(bits) <= {"0", "1"} and len(bits) > 10:
            weeks = weeks_from_bits(bits, week_from)
        else:
            weeks = parse_weeks(bits)

        next_marker = bodies[position + 1][0] if position + 1 < len(bodies) else len(html)
        script_end = html.find("</script>", end)
        segment_end = min(next_marker, script_end if script_end >= 0 else len(html))
        segment = html[end:segment_end].replace("unitCount", str(unit_count))
        indexes = [value for value in (_eval_index(m) for m in _INDEX_RE.findall(segment)) if value is not None]
        indexes = [value for value in indexes if 0 <= value < 7 * unit_count]
        if not indexes:
            continue

        days = {value // unit_count for value in indexes}
        weekday = sorted(days)[0]
        periods = sorted(value % unit_count for value in indexes if value // unit_count == weekday)
        if not periods or not weeks:
            continue

        key = (name, code, tuple(names), room, weekday, periods[0], periods[-1], tuple(weeks))
        if key in seen:
            continue
        seen.add(key)
        blocks.append(
            CourseBlock(
                name=name,
                code=code,
                teacher="/".join(names),
                room=room,
                weekday=weekday,
                start_period=periods[0] + 1,
                end_period=periods[-1] + 1,
                weeks=weeks,
            )
        )
    return blocks