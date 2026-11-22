from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

import yaml

from .fetcher import FetchError, LoginError, create_session, fetch_course_table
from .ics_builder import build_calendar
from .parser import parse_course_table

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OUTPUT_FILE = ROOT / "output" / "课表.ics"


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _set_output(**values: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={str(value).replace(chr(10), ' ')}\n")


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def run(html_path: str | None, half: bool = False) -> int:
    if html_path:
        html = Path(html_path).read_text(encoding="utf-8", errors="replace")
    else:
        user = os.environ.get("SCHOOL_USER", "")
        password = os.environ.get("SCHOOL_PASS", "")
        if not user or not password:
            raise LoginError("缺少 SCHOOL_USER / SCHOOL_PASS")
        html = fetch_course_table(create_session(user, password))

    blocks = parse_course_table(html)
    courses = {block.name for block in blocks}
    if len(courses) < 3:
        raise FetchError(f"仅解析到 {len(courses)} 门课程，判定为登录失败，未写入文件")

    if half:
        keep = set(sorted(courses)[: max(1, len(courses) // 2)])
        blocks = [block for block in blocks if block.name in keep]
        courses = keep

    semester = _read_yaml(CONFIG_DIR / "semester.yaml")
    overrides = _read_yaml(CONFIG_DIR / "overrides.yaml").get("overrides", [])
    calendar = build_calendar(blocks, semester, overrides)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = OUTPUT_FILE.with_name(OUTPUT_FILE.name + ".tmp")
    temp_file.write_bytes(calendar.to_ical())
    temp_file.replace(OUTPUT_FILE)
    return len(courses)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", help="本地课表 HTML 路径，跳过抓取")
    parser.add_argument("--half", action="store_true", help="只发布一半课程，用于测试日历刷新")
    args = parser.parse_args()
    _load_dotenv()
    half = args.half or os.environ.get("PUBLISH_HALF", "").lower() in {"1", "true", "yes"}
    try:
        count = run(args.html, half)
        if half:
            print(f"测试模式：已生成 {OUTPUT_FILE}，只含 {count} 门课程。测完请重跑完整模式恢复")
        else:
            print(f"已生成 {OUTPUT_FILE}，共 {count} 门课程")
        _set_output(valid="true", error="", courses=str(count))
    except Exception as exc:
        _set_output(valid="false", error=str(exc))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()