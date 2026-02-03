from datetime import date
from unittest.mock import patch

from app.line.project_list import (
    build_project_list_message,
    handle_project_list_request,
    is_project_list_command,
)


def test_is_project_list_command_matches_exact() -> None:
    assert is_project_list_command("專案清單") is True
    assert is_project_list_command("  專案清單 ") is True
    assert is_project_list_command("專案清單1") is False
    assert is_project_list_command("") is False


def test_build_project_list_message_filters_recent() -> None:
    today = date(2026, 2, 1)
    options = [
        "20251206-07 雪東行程",
        "20260206-14 日本玩雪",
        "旅遊",
    ]
    message = build_project_list_message(options, today=today)
    assert "20260206-14 日本玩雪" in message
    assert "20251206-07 雪東行程" not in message
    assert "旅遊" not in message


def test_build_project_list_message_empty() -> None:
    today = date(2026, 2, 1)
    message = build_project_list_message([], today=today)
    assert "找不到近期專案" in message


@patch("app.line.project_list.get_project_options")
def test_handle_project_list_request_error(mock_get_options) -> None:
    mock_get_options.return_value = (None, "request_failed")
    message = handle_project_list_request()
    assert "無法取得專案清單" in message
