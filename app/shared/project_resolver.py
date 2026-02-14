from __future__ import annotations

from datetime import date, timedelta
from difflib import SequenceMatcher
import re


_LONG_TERM_PROJECTS = [
    "日常",
    "家庭年度支出",
    "個人年度支出",
    "子女年度支出",
    "健康檢查",
    "登山行程",
    "紀念日／送禮",
    "旅遊",
    "原生家庭",
    "折扣/優惠",
]

_PROJECT_DATE_PREFIX_RE = re.compile(
    r"^(?P<start>\d{8})(?:[-–—](?P<end>\d{8}|\d{4}|\d{2}))?(?P<name>.*)$"
)


def normalize_project_name(value: str) -> str:
    text = (value or "").strip().replace("／", "/").replace("　", " ")
    # Replace various dashes with standard hyphen
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def get_long_term_project(value: str) -> str | None:
    normalized = normalize_project_name(value)
    if not normalized:
        return None
    for project in _LONG_TERM_PROJECTS:
        if normalize_project_name(project) == normalized:
            return project
    return None


def extract_project_date_range(value: str) -> tuple[date, date] | None:
    text = (value or "").strip()
    if not text:
        return None
    match = _PROJECT_DATE_PREFIX_RE.match(text)
    if not match:
        return None
    start_raw = match.group("start")
    end_raw = match.group("end")
    start_date = _parse_yyyymmdd(start_raw)
    if not start_date:
        return None
    end_date = _parse_project_end_date(start_date, end_raw)
    if not end_date:
        return None
    if end_date < start_date:
        return None
    return (start_date, end_date)


def strip_project_date_prefix(value: str) -> tuple[str, tuple[date, date] | None]:
    text = (value or "").strip()
    if not text:
        return ("", None)
    match = _PROJECT_DATE_PREFIX_RE.match(text)
    if not match:
        return (text, None)
    date_range = extract_project_date_range(text)
    if not date_range:
        return (text, None)
    name = (match.group("name") or "").strip()
    return (name, date_range)


def match_short_term_project(
    value: str,
    options: list[str],
    *,
    today: date | None = None,
    min_ratio: float = 0.6,
    lookback_days: int = 30,
) -> tuple[str | None, list[str]]:
    if not options:
        return (None, [])
    today = today or date.today()
    cutoff = today - timedelta(days=lookback_days)
    input_name, _ = strip_project_date_prefix(value)
    normalized_input = normalize_project_name(input_name)
    if not normalized_input:
        return (None, [])

    candidates: list[tuple[float, date, str]] = []
    for option in options:
        option_name, date_range = strip_project_date_prefix(option)
        if not date_range:
            continue
        if date_range[1] < cutoff:
            continue
        normalized_option = normalize_project_name(option_name)
        if not normalized_option:
            continue
        ratio = SequenceMatcher(None, normalized_input, normalized_option).ratio()
        if ratio < min_ratio:
            continue
        candidates.append((ratio, date_range[0], option))

    if not candidates:
        return (None, [])

    candidates.sort(
        key=lambda item: (
            -item[0],
            abs((item[1] - today).days),
        )
    )
    sorted_options = [item[2] for item in candidates]
    if len(sorted_options) == 1:
        return (sorted_options[0], sorted_options)
    return (None, sorted_options[:3])


def filter_recent_project_options(
    options: list[str],
    *,
    today: date | None = None,
    lookback_days: int = 30,
) -> list[str]:
    if not options:
        return []
    today = today or date.today()
    cutoff = today - timedelta(days=lookback_days)
    filtered: list[tuple[date, str]] = []
    for option in options:
        _, date_range = strip_project_date_prefix(option)
        if not date_range:
            continue
        if date_range[1] < cutoff:
            continue
        filtered.append((date_range[0], option))
    filtered.sort(key=lambda item: (item[0], item[1]))
    return [item[1] for item in filtered]


def _parse_yyyymmdd(raw: str) -> date | None:
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None


def _parse_project_end_date(start: date, end_raw: str | None) -> date | None:
    if not end_raw:
        return start
    if len(end_raw) == 2:
        return _safe_date(start.year, start.month, int(end_raw))
    if len(end_raw) == 4:
        return _safe_date(start.year, int(end_raw[:2]), int(end_raw[2:]))
    if len(end_raw) == 8:
        return _parse_yyyymmdd(end_raw)
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def infer_project(category: str) -> str:
    """
    Infer project name from category path.

    Rules (3A):
    - 健康/* -> 健康檢查
    - 行程/* -> 登山行程
    - 禮物/* -> 紀念日／送禮
    - otherwise -> 日常
    """
    if not category:
        return "日常"

    normalized = category.strip().replace("／", "/")
    if not normalized:
        return "日常"

    if normalized.startswith("健康/"):
        return "健康檢查"
    if normalized.startswith("行程/"):
        return "登山行程"
    if normalized.startswith("禮物/"):
        return "紀念日／送禮"

    return "日常"
