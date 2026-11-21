from __future__ import annotations

import base64
from urllib.parse import quote

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .parser import parse_semester_params

AUTH_BASE = "http://39.164.230.243:9527"
EAMS_BASE = "http://39.164.230.243:91"
SERVICE_URL = f"{EAMS_BASE}/eams/login.action"
AES_KEY = b"jsmituluzhou2024"
TIMEOUT = 30


class LoginError(RuntimeError):
    pass


class FetchError(RuntimeError):
    pass


def _request(session: requests.Session, method: str, url: str, **kwargs):
    try:
        return session.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        # 公开仓库的 Actions 日志会公开，URL 里的 ids 参数是学号，不能带进异常信息
        raise FetchError(f"请求失败 {method} {url.split('?')[0]}: {type(exc).__name__}") from None


def _encrypt_password(password: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("ascii")


def _headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }
    if referer:
        headers["Referer"] = referer
        headers["Origin"] = AUTH_BASE
    return headers


def create_session(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_headers())

    captcha = _request(session, "GET", f"{AUTH_BASE}/authserver/captcha")
    try:
        state = captcha.json().get("data", {}).get("state", "")
    except ValueError as exc:
        raise LoginError(f"获取登录 state 失败，HTTP {captcha.status_code}") from exc

    payload = {
        "username": username,
        "password": _encrypt_password(password),
        "captcha": "",
        "authType": "normal",
        "state": state,
        "remeberMe": "0",
        "serviceUrl": SERVICE_URL,
    }
    response = _request(
        session,
        "POST",
        f"{AUTH_BASE}/authserver/login/signin",
        json=payload,
        headers=_headers(f"{AUTH_BASE}/#/authserver/login"),
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise LoginError(f"登录接口返回非 JSON，HTTP {response.status_code}") from exc
    if body.get("code") != 0:
        raise LoginError(f"登录失败: {body.get('message') or body}")

    token = (body.get("data") or {}).get("token") or ""
    if token:
        for name in ("congress", "token"):
            session.cookies.set(name, quote(token, safe=""), domain="39.164.230.243", path="/")
        session.cookies.set(
            "user", quote('{"username":"%s"}' % username, safe=""), domain="39.164.230.243", path="/"
        )

    _request(session, "GET", SERVICE_URL, headers=_headers(f"{AUTH_BASE}/authserver/login"))
    return session


def _looks_like_login(text: str) -> bool:
    return "统一身份认证" in text or "authserver/login" in text


def fetch_course_table(session: requests.Session) -> str:
    page = _request(session, "GET", f"{EAMS_BASE}/eams/courseTableForStd.action")
    page.encoding = "utf-8"
    if _looks_like_login(page.text):
        raise LoginError("未获得教务系统会话，登录流程未生效")

    semester_id, ids = parse_semester_params(page.text)
    params = {"ignoreHead": "1", "setting.kind": "std", "startWeek": ""}
    if semester_id:
        params["semester.id"] = semester_id
    if ids:
        params["ids"] = ids

    table = _request(
        session,
        "GET",
        f"{EAMS_BASE}/eams/courseTableForStd!courseTable.action",
        params=params,
    )
    table.encoding = "utf-8"
    if _looks_like_login(table.text):
        raise LoginError("课表页要求重新登录")
    if "TaskActivity" not in table.text:
        raise FetchError("课表页中没有 TaskActivity 数据")
    return table.text