# -*- coding: utf-8 -*-
"""
Pipeline Router

Explicit entrypoints for GPT-first / Parser-first modes.
"""

from __future__ import annotations

from typing import Literal

from app.gpt_processor import (
    process_multi_expense,
    process_multi_expense_gpt_only,
    _detect_update_intent,
)
from app.processor import process_with_parser


Mode = Literal["auto", "parser", "gpt"]


def process_message(user_message: str, *, mode: Mode = "auto", debug: bool = False):
    """Route message to the selected pipeline."""
    if _detect_update_intent(user_message):
        # Update intent always goes through GPT path.
        return process_multi_expense_gpt_only(user_message, debug=debug)

    if mode == "parser":
        return process_with_parser(user_message)
    if mode == "gpt":
        return process_multi_expense_gpt_only(user_message, debug=debug)
    return process_multi_expense(user_message, debug=debug)
