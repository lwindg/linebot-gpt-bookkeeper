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
from collections import defaultdict

import requests

from app.config import (
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
    NOTION_CC_STATEMENT_LINES_DB_ID,
    NOTION_CC_STATEMENTS_DB_ID,
)

logger = logging.getLogger(__name__)

# Notion API versions:
# - Use legacy version for /v1/databases/* endpoints (query still supported)
# - Use new version for /v1/data_sources/* endpoints
NOTION_DB_VERSION = "2022-06-28"
NOTION_DS_VERSION = "2025-09-03"


@dataclass(frozen=True)
class ReconcileSummary:
    statement_id: str
    period: str
    statement_lines_total: int
    matched: int
    ambiguous: int
    unmatched: int
    statement_page_id: str


def _headers(version: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": version,
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
    resp = requests.post(url_db, headers=_headers(NOTION_DB_VERSION), json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()

    # 2) Fallback to data_sources
    url_ds = f"https://api.notion.com/v1/data_sources/{container_id}/query"
    resp2 = requests.post(url_ds, headers=_headers(NOTION_DS_VERSION), json=payload, timeout=30)
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
    resp = requests.post(url, headers=_headers(NOTION_DB_VERSION), json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Notion create failed: {resp.status_code} {resp.text}")
    return resp.json()["id"]


def _notion_patch_page(page_id: str, properties: dict[str, Any]) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    resp = requests.patch(url, headers=_headers(NOTION_DB_VERSION), json={"properties": properties}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Notion patch failed: {resp.status_code} {resp.text}")


def _rt_plain(prop: dict[str, Any]) -> str:
    rt = (prop or {}).get("rich_text") or []
    if not rt:
        return ""
    t = rt[0].get("plain_text")
    return (t or "").strip()


def _batch_id_from_ledger_props(props: dict[str, Any]) -> Optional[str]:
    # Prefer explicit 批次ID rich_text. Otherwise derive from 交易ID like YYYYMMDD-HHMMSS-XX.
    bid = _rt_plain(props.get("批次ID") or {})
    if bid:
        return bid

    tid = _rt_plain(props.get("交易ID") or {})
    if tid and "-" in tid and len(tid) >= 3 and tid[-3] == "-":
        return tid.rsplit("-", 1)[0]
    return None


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


def _foreign_amount_tolerance(currency: str) -> float:
    cur = (currency or "").upper().strip()
    # Common integer currencies
    if cur in ("JPY",):
        return 1.0
    return 0.05


def _eq_foreign_amount(a: float, b: float, *, currency: str) -> bool:
    tol = _foreign_amount_tolerance(currency)
    return abs(float(a) - float(b)) <= tol


def _rate_close(ledger_rate: float, implied_rate: float, *, tol_ratio: float = 0.03) -> bool:
    if implied_rate <= 0:
        return False
    return abs(float(ledger_rate) - float(implied_rate)) / float(implied_rate) <= tol_ratio


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

    consumed_ledger_ids: set[str] = set()
    consumed_batch_ids: set[str] = set()

    for row in lines:
        pid = row["id"]
        props = row.get("properties") or {}

        # Skip fee lines for MVP
        is_fee = bool((props.get("是否手續費") or {}).get("checkbox"))
        if is_fee:
            continue

        pay = _select_name(props.get("付款方式") or {})
        # If payment method is present, keep it within allowlist.
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

        stmt_currency = _select_name(props.get("幣別") or {})
        stmt_foreign = _number(props.get("外幣金額") or {})
        implied_rate = None
        if stmt_currency and stmt_foreign and stmt_foreign != 0:
            try:
                implied_rate = float(twd) / float(stmt_foreign)
            except Exception:
                implied_rate = None

        # Collect ledger candidates in date window (by payment method allowlist)
        candidate_ledgers: dict[str, dict[str, Any]] = {}
        for m in (payment_methods or ([pay] if pay else [])):
            if not m:
                continue
            for led in _fetch_ledger_candidates(payment_method=m, day=trans_day):
                lid = led["id"]
                if lid in consumed_ledger_ids:
                    continue
                candidate_ledgers[lid] = led

        # Partition into:
        # - foreign exact matches (original currency)
        # - TWD exact matches
        # - batch groups (TWD sum match)
        foreign_single_ids: list[str] = []
        exact_single_ids: list[str] = []
        batch_groups: dict[str, list[str]] = defaultdict(list)

        for lid, led in candidate_ledgers.items():
            lp = led.get("properties") or {}
            cur = _select_name(lp.get("原幣別") or {})
            amt = _number(lp.get("原幣金額") or {})
            if amt is None:
                continue

            # Foreign match path: statement has currency + foreign amount
            if stmt_currency and stmt_foreign is not None and cur and cur.upper() == str(stmt_currency).upper():
                if _eq_foreign_amount(float(amt), float(stmt_foreign), currency=str(stmt_currency)):
                    # Optional rate sanity check when available (prevents wrong matches)
                    led_rate = _number(lp.get("匯率") or {})
                    if implied_rate is not None and led_rate is not None:
                        if not _rate_close(float(led_rate), float(implied_rate)):
                            # Too far off; skip this candidate
                            pass
                        else:
                            foreign_single_ids.append(lid)
                    else:
                        foreign_single_ids.append(lid)

            # TWD-only matching + batch aggregation
            if cur != "TWD":
                continue

            bid = _batch_id_from_ledger_props(lp)
            if bid:
                batch_groups[bid].append(lid)
            if _eq_amount(float(amt), float(twd)):
                exact_single_ids.append(lid)

        # Evaluate batch matches
        batch_match_ids: list[str] = []
        batch_match_bid: Optional[str] = None
        for bid, lids in batch_groups.items():
            if bid in consumed_batch_ids:
                continue
            if len(lids) < 2:
                continue
            total_amt = 0.0
            ok = True
            for lid in lids:
                lp = candidate_ledgers[lid].get("properties") or {}
                amt = _number(lp.get("原幣金額") or {})
                if amt is None:
                    ok = False
                    break
                total_amt += float(amt)
            if ok and _eq_amount(total_amt, twd):
                if batch_match_bid is not None:
                    # multiple batch candidates -> ambiguous
                    batch_match_bid = "__multiple__"
                    break
                batch_match_bid = bid
                batch_match_ids = sorted(set(lids))

        if batch_match_bid == "__multiple__":
            ambiguous += 1
            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對帳狀態": {"select": {"name": "unmatched"}},
                },
            )
            continue

        # Decision priority:
        # 0) Unique foreign exact match (when statement provides foreign currency + amount)
        # 1) Unique batch sum match (TWD)
        # 2) Unique single exact amount match (TWD)
        # Otherwise: unmatched/ambiguous

        unique_foreign = sorted(set(foreign_single_ids))
        if stmt_currency and stmt_foreign is not None and stmt_currency.upper() != "TWD" and len(unique_foreign) == 1:
            ledger_id = unique_foreign[0]

            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對應帳目": {"relation": [{"id": ledger_id}]},
                    "對帳狀態": {"select": {"name": "matched"}},
                },
            )
            _notion_patch_page(
                ledger_id,
                {
                    "對應帳單明細": {"relation": [{"id": pid}]},
                    "對應帳單": {"relation": [{"id": statement_page_id}]},
                },
            )
            consumed_ledger_ids.add(ledger_id)
            matched += 1

        elif stmt_currency and stmt_foreign is not None and stmt_currency.upper() != "TWD" and len(unique_foreign) >= 2:
            ambiguous += 1
            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對帳狀態": {"select": {"name": "unmatched"}},
                },
            )

        elif batch_match_bid and batch_match_ids:
            # Apply batch match
            ledger_ids = batch_match_ids

            _notion_patch_page(
                pid,
                {
                    "所屬帳單": {"relation": [{"id": statement_page_id}]},
                    "對應帳目": {"relation": [{"id": x} for x in ledger_ids]},
                    "對帳狀態": {"select": {"name": "matched"}},
                },
            )

            for ledger_id in ledger_ids:
                _notion_patch_page(
                    ledger_id,
                    {
                        "對應帳單明細": {"relation": [{"id": pid}]},
                        "對應帳單": {"relation": [{"id": statement_page_id}]},
                    },
                )
                consumed_ledger_ids.add(ledger_id)

            consumed_batch_ids.add(batch_match_bid)
            matched += 1

        else:
            unique_exact = sorted(set(exact_single_ids))
            if len(unique_exact) == 1:
                ledger_id = unique_exact[0]

                _notion_patch_page(
                    pid,
                    {
                        "所屬帳單": {"relation": [{"id": statement_page_id}]},
                        "對應帳目": {"relation": [{"id": ledger_id}]},
                        "對帳狀態": {"select": {"name": "matched"}},
                    },
                )
                _notion_patch_page(
                    ledger_id,
                    {
                        "對應帳單明細": {"relation": [{"id": pid}]},
                        "對應帳單": {"relation": [{"id": statement_page_id}]},
                    },
                )
                consumed_ledger_ids.add(ledger_id)
                matched += 1

            elif len(unique_exact) >= 2:
                ambiguous += 1
                _notion_patch_page(
                    pid,
                    {
                        "所屬帳單": {"relation": [{"id": statement_page_id}]},
                        "對帳狀態": {"select": {"name": "unmatched"}},
                    },
                )
            else:
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
