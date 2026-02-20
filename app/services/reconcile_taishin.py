# -*- coding: utf-8 -*-
"""Taishin credit card statement reconciliation (MVP).

This is a minimal, deterministic matcher intended for LINE "執行對帳".

Scope (MVP):
- Match statement lines to ledger entries by:
  - payment method allowlist (from reconcile lock)
  - transaction date (消費日) ±2 days
  - TWD amount exact match (ledger 原幣別=TWD and 原幣金額)
- If multiple candidates found for a statement line, keep it unmatched.
- Writes relations in Notion:
  - statement_line.對應帳目 + 對帳狀態
  - ledger.對應帳單明細 + 對應帳單
  - statement_line.所屬帳單

Future phases will add batch_id aggregation, FX matching, fees, offsets, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests

from app.config import (
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
    NOTION_CC_STATEMENT_LINES_DB_ID,
    NOTION_CC_STATEMENTS_DB_ID,
)

logger = logging.getLogger(__name__)

NOTION_VERSION = "2025-09-03"


@dataclass(frozen=True)
class ReconcileSummary:
    statement_id: str
    period: str
    statement_lines_total: int
    matched: int
    ambiguous: int
    unmatched: int
    statement_page_id: str


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _notion_query(container_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Query a Notion database or data source.

    NOTE:
    - Legacy Notion API uses /v1/databases/{id}/query.
    - Newer data_sources feature uses /v1/data_sources/{id}/query.

    We try databases first, then fall back to data_sources for compatibility.
    """

    # 1) Try databases
    url_db = f"https://api.notion.com/v1/databases/{container_id}/query"
    resp = requests.post(url_db, headers=_headers(), json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()

    # 2) Fallback to data_sources
    url_ds = f"https://api.notion.com/v1/data_sources/{container_id}/query"
    resp2 = requests.post(url_ds, headers=_headers(), json=payload, timeout=30)
    if resp2.status_code == 200:
        return resp2.json()

    raise RuntimeError(
        "Notion query failed: "
        f"db={resp.status_code} {resp.text} | "
        f"ds={resp2.status_code} {resp2.text}"
    )


def _notion_create_page(database_id: str, properties: dict[str, Any]) -> str:
    url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": database_id}, "properties": properties}
    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Notion create failed: {resp.status_code} {resp.text}")
    return resp.json()["id"]


def _notion_patch_page(page_id: str, properties: dict[str, Any]) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.patch(url, headers=_headers(), json={"properties": properties}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Notion patch failed: {resp.status_code} {resp.text}")


def _rt_plain(prop: dict[str, Any]) -> str:
    rt = (prop or {}).get("rich_text") or []
    if not rt:
        return ""
    t = rt[0].get("plain_text")
    return (t or "").strip()


def _title_plain(prop: dict[str, Any]) -> str:
    t = (prop or {}).get("title") or []
    if not t:
        return ""
    return (t[0].get("plain_text") or "").strip()


def _select_name(prop: dict[str, Any]) -> str:
    s = (prop or {}).get("select")
    return (s or {}).get("name") if isinstance(s, dict) else ""


def _number(prop: dict[str, Any]) -> Optional[float]:
    n = (prop or {}).get("number")
    return float(n) if n is not None else None


def _date(prop: dict[str, Any]) -> Optional[date]:
    d = (prop or {}).get("date")
    if not d or not d.get("start"):
        return None
    return date.fromisoformat(d["start"][:10])


def _eq_amount(a: float, b: float) -> bool:
    # TWD amounts are integers in ledger, statement may be float.
    return round(a, 2) == round(b, 2)


def _ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
    if not NOTION_CC_STATEMENTS_DB_ID:
        raise RuntimeError("NOTION_CC_STATEMENTS_DB_ID not configured")

    # Find existing by 帳單ID
    q = _notion_query(
        NOTION_CC_STATEMENTS_DB_ID,
        {
            "page_size": 5,
            "filter": {"property": "帳單ID", "rich_text": {"equals": statement_id}},
        },
    )
    res = q.get("results") or []
    if res:
        return res[0]["id"]

    # Create
    props = {
        "Name": {"title": [{"text": {"content": f"台新 {period}"}}]},
        "帳單ID": {"rich_text": [{"text": {"content": statement_id}}]},
        "銀行": {"select": {"name": bank}},
    }
    return _notion_create_page(NOTION_CC_STATEMENTS_DB_ID, props)


def _fetch_statement_lines(statement_id: str) -> list[dict[str, Any]]:
    if not NOTION_CC_STATEMENT_LINES_DB_ID:
        raise RuntimeError("NOTION_CC_STATEMENT_LINES_DB_ID not configured")

    all_rows: list[dict[str, Any]] = []
    cursor = None
    while True:
        payload: dict[str, Any] = {
            "page_size": 100,
            "filter": {"property": "帳單ID", "rich_text": {"equals": statement_id}},
        }
        if cursor:
            payload["start_cursor"] = cursor
        data = _notion_query(NOTION_CC_STATEMENT_LINES_DB_ID, payload)
        all_rows.extend(data.get("results") or [])
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return all_rows


def _fetch_ledger_candidates(*, payment_method: str, day: date) -> list[dict[str, Any]]:
    if not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_DATABASE_ID not configured")

    start = (day - timedelta(days=2)).isoformat()
    end = (day + timedelta(days=2)).isoformat()

    # Query by payment method and date window; we'll filter amounts client-side.
    data = _notion_query(
        NOTION_DATABASE_ID,
        {
            "page_size": 100,
            "filter": {
                "and": [
                    {"property": "付款方式", "select": {"equals": payment_method}},
                    {"property": "日期", "date": {"on_or_after": start}},
                    {"property": "日期", "date": {"on_or_before": end}},
                ]
            },
        },
    )
    return data.get("results") or []


def reconcile_taishin_statement(*, statement_id: str, period: str, payment_methods: list[str]) -> ReconcileSummary:
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN not configured")

    statement_page_id = _ensure_statement_page(statement_id=statement_id, period=period, bank="台新")

    lines = _fetch_statement_lines(statement_id)
    matched = 0
    ambiguous = 0

    for row in lines:
        pid = row["id"]
        props = row.get("properties") or {}

        # Skip fee lines for MVP
        is_fee = bool((props.get("是否手續費") or {}).get("checkbox"))
        if is_fee:
            continue

        pay = _select_name(props.get("付款方式") or {})
        if payment_methods and pay and pay not in payment_methods:
            continue

        trans_day = _date(props.get("消費日") or {})
        if not trans_day:
            # fallback: post date
            trans_day = _date(props.get("入帳起息日") or {})
        if not trans_day:
            continue

        twd = _number(props.get("新臺幣金額") or {})
        if twd is None:
            continue

        candidates: list[tuple[str, dict[str, Any]]] = []
        for m in (payment_methods or ([pay] if pay else [])):
            if not m:
                continue
            for led in _fetch_ledger_candidates(payment_method=m, day=trans_day):
                lp = led.get("properties") or {}
                cur = _select_name(lp.get("原幣別") or {})
                amt = _number(lp.get("原幣金額") or {})
                if cur != "TWD" or amt is None:
                    continue
                if _eq_amount(amt, twd):
                    candidates.append((led["id"], led))

        # de-dup
        cand_ids = sorted(set([c[0] for c in candidates]))

        if len(cand_ids) == 1:
            ledger_id = cand_ids[0]

            # Patch statement line
            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對應帳目": {"relation": [{"id": ledger_id}]},
                    "對帳狀態": {"select": {"name": "matched"}},
                },
            )

            # Patch ledger
            _notion_patch_page(
                ledger_id,
                {
                    "對應帳單明細": {"relation": [{"id": pid}]},
                    "對應帳單": {"relation": [{"id": statement_page_id}]},
                },
            )

            matched += 1
        elif len(cand_ids) >= 2:
            ambiguous += 1
            # record statement page relation even if ambiguous
            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對帳狀態": {"select": {"name": "unmatched"}},
                },
            )
        else:
            # no match; still attach statement page
            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對帳狀態": {"select": {"name": "unmatched"}},
                },
            )

    total = len(lines)
    unmatched = max(total - matched - ambiguous, 0)
    return ReconcileSummary(
        statement_id=statement_id,
        period=period,
        statement_lines_total=total,
        matched=matched,
        ambiguous=ambiguous,
        unmatched=unmatched,
        statement_page_id=statement_page_id,
    )


def format_reconcile_summary(summary: ReconcileSummary) -> str:
    return (
        "✅ 對帳完成（MVP）"
        f"\n• 期別：{summary.period}"
        f"\n• 帳單ID：{summary.statement_id}"
        f"\n• 明細總數：{summary.statement_lines_total}"
        f"\n• 已匹配：{summary.matched}"
        f"\n• 需人工確認：{summary.ambiguous}"
        f"\n• 未匹配：{summary.unmatched}"
    )
