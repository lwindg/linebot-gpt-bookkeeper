# -*- coding: utf-8 -*-
"""
Project list command handling for LINE.
"""

from __future__ import annotations

from datetime import date

from app.services.project_options import get_project_options
from app.shared.project_resolver import filter_recent_project_options


_PROJECT_LIST_COMMAND = "專案清單"


def is_project_list_command(message: str) -> bool:
    return (message or "").strip() == _PROJECT_LIST_COMMAND


def build_project_list_message(
    options: list[str],
    *,
    today: date | None = None,
    lookback_days: int = 30,
) -> str:
    recent_options = filter_recent_project_options(
        options,
        today=today,
        lookback_days=lookback_days,
    )
    if not recent_options:
        return "❌ 找不到近期專案（過去30天~未來）"

    lines = ["📌 近期專案（過去30天~未來）"]
    for idx, option in enumerate(recent_options, start=1):
        lines.append(f"{idx}) {option}")
    return "\n".join(lines)


def handle_project_list_request() -> str:
    options, _error = get_project_options()
    if not options:
        return "❌ 無法取得專案清單，請稍後再試。"
    return build_project_list_message(options)
