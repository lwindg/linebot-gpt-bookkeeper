from datetime import date

from app.shared.project_resolver import (
    extract_project_date_range,
    get_long_term_project,
    infer_project,
    match_short_term_project,
    normalize_project_name,
    strip_project_date_prefix,
)


def test_infer_project_default_daily() -> None:
    assert infer_project("") == "日常"
    assert infer_project("家庭/餐飲/午餐") == "日常"


def test_infer_project_health_mapping() -> None:
    assert infer_project("健康/醫療") == "健康檢查"
    assert infer_project("健康/運動") == "健康檢查"


def test_infer_project_trip_mapping() -> None:
    assert infer_project("行程/登山") == "登山行程"
    assert infer_project("行程/交通") == "登山行程"


def test_infer_project_gift_mapping() -> None:
    assert infer_project("禮物/節慶") == "紀念日／送禮"
    assert infer_project("禮物/生日") == "紀念日／送禮"


def test_infer_project_normalize_fullwidth_separator() -> None:
    assert infer_project("健康／醫療") == "健康檢查"


def test_normalize_project_name_handles_slash_and_space() -> None:
    assert normalize_project_name(" 紀念日／送禮 ") == "紀念日/送禮"
    assert normalize_project_name(" 家庭 年度支出 ") == "家庭年度支出"


def test_get_long_term_project_matches_normalized() -> None:
    assert get_long_term_project("紀念日/送禮") == "紀念日／送禮"
    assert get_long_term_project(" 旅遊 ") == "旅遊"
    assert get_long_term_project("不存在") is None


def test_extract_project_date_range_single_day() -> None:
    assert extract_project_date_range("20260206 日本玩雪") == (
        date(2026, 2, 6),
        date(2026, 2, 6),
    )


def test_extract_project_date_range_same_month() -> None:
    assert extract_project_date_range("20260206-14 日本玩雪") == (
        date(2026, 2, 6),
        date(2026, 2, 14),
    )


def test_extract_project_date_range_cross_month() -> None:
    assert extract_project_date_range("20260130-0202 日本玩雪") == (
        date(2026, 1, 30),
        date(2026, 2, 2),
    )


def test_extract_project_date_range_cross_year() -> None:
    assert extract_project_date_range("20251230-20260102 日本玩雪") == (
        date(2025, 12, 30),
        date(2026, 1, 2),
    )


def test_extract_project_date_range_invalid() -> None:
    assert extract_project_date_range("20260230 日本玩雪") is None
    assert extract_project_date_range("日本玩雪") is None


def test_strip_project_date_prefix() -> None:
    name, date_range = strip_project_date_prefix("20260206-14 日本玩雪")
    assert name == "日本玩雪"
    assert date_range == (date(2026, 2, 6), date(2026, 2, 14))

    name, date_range = strip_project_date_prefix("日本玩雪")
    assert name == "日本玩雪"
    assert date_range is None


def test_match_short_term_project_unique_candidate() -> None:
    today = date(2026, 2, 1)
    options = [
        "20251206-07 雪東行程",
        "20260206-14 日本玩雪",
        "旅遊",
    ]
    resolved, candidates = match_short_term_project(
        "日本玩雪",
        options,
        today=today,
    )
    assert resolved == "20260206-14 日本玩雪"
    assert candidates == ["20260206-14 日本玩雪"]


def test_match_short_term_project_non_unique_candidate() -> None:
    today = date(2026, 2, 1)
    options = [
        "20260206-14 日本玩雪",
        "20260115 日本滑雪",
    ]
    resolved, candidates = match_short_term_project(
        "日本玩雪",
        options,
        today=today,
    )
    assert resolved is None
    assert candidates == ["20260206-14 日本玩雪", "20260115 日本滑雪"]


def test_match_short_term_project_sorts_by_date_when_tied() -> None:
    today = date(2026, 2, 1)
    options = [
        "20260306 日本玩雪",
        "20260206 日本玩雪",
    ]
    resolved, candidates = match_short_term_project(
        "日本玩雪",
        options,
        today=today,
    )
    assert resolved is None
    assert candidates == ["20260206 日本玩雪", "20260306 日本玩雪"]
