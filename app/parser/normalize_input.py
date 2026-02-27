# -*- coding: utf-8 -*-
"""Parser-first input normalization.

Goal:
- Keep parser-first text handling consistent with historical GPT-first spacing normalization.
- Be conservative: only normalize patterns that are known to cause parse failures.

This is applied only for parser-first bookkeeping messages (not images, not reconcile).
"""

from __future__ import annotations

import re


# Known payment tokens that often get glued to amounts.
_PAYMENT_TOKENS = (
    "現金",
    "Line Pay",
    "line",
    "linepay",
    "line pay",
    "狗卡",
    "灰狗",
    "FlyGo",
    "richart",
)


def normalize_parser_input(text: str) -> str:
    s = text or ""

    # 1) Insert space before '$' when glued to Chinese: 花菜$150 -> 花菜 $150
    s = re.sub(r"([\u4e00-\u9fff])\$", r"\1 $", s)

    # 2) Insert space between digits and common payment tokens when glued: 250現金 -> 250 現金
    # Only for known tokens to avoid over-splitting.
    for tok in _PAYMENT_TOKENS:
        # word-ish token (ascii): use case-insensitive boundary
        if re.fullmatch(r"[A-Za-z ]+", tok):
            s = re.sub(rf"(\d)({re.escape(tok)})\b", r"\1 \2", s, flags=re.IGNORECASE)
        else:
            s = re.sub(rf"(\d)({re.escape(tok)})", r"\1 \2", s)

    # 3) Collapse excessive spaces
    s = re.sub(r"[ \t]+", " ", s)

    return s.strip()
