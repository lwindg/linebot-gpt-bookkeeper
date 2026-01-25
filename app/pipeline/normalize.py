# -*- coding: utf-8 -*-
"""
Shared normalization helpers for pipeline outputs.

集中交易ID/批次ID邏輯，避免 GPT/Parser 雙路徑重複實作。
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from app.pipeline.transaction_id import generate_transaction_id


def build_batch_id(
    date_str: Optional[str],
    *,
    item: Optional[str] = None,
    use_current_time: bool = False,
) -> str:
    """Build a batch id using the shared transaction id generator."""
    if not date_str:
        date_str = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    return generate_transaction_id(
        date_str,
        None,
        item,
        use_current_time=use_current_time,
    )


def assign_transaction_ids(entries: Iterable, batch_id: str) -> None:
    """Assign transaction IDs to entries (single -> base, multi -> base-01...)."""
    entries_list = list(entries)
    if not entries_list:
        return
    if len(entries_list) == 1:
        entries_list[0].交易ID = batch_id
        return
    for idx, entry in enumerate(entries_list, start=1):
        entry.交易ID = f"{batch_id}-{idx:02d}"
