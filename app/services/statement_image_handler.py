"""Statement image (Taishin credit card) processing.

- Extract statement lines from an image via OpenAI Vision
- Normalize to structured records
- Insert into Notion database (cc_statement_lines)

Notes:
- Spec/plan live at specs/010-credit-card-reconciliation/*
- We keep changes minimal and isolated.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional, Any

import requests
from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_VISION_MODEL, NOTION_TOKEN, NOTION_CC_STATEMENT_LINES_DB_ID
from app.gpt.prompts import TAISHIN_STATEMENT_VISION_PROMPT
from app.services.image_handler import compress_image, encode_image_base64

logger = logging.getLogger(__name__)

NOTION_VERSION = "2025-09-03"


@dataclass
class TaishinStatementLine:
    card_hint: Optional[str]
    trans_date: Optional[str]
    post_date: Optional[str]
    description: str
    twd_amount: float
    fx_date: Optional[str]
    country: Optional[str]
    currency: Optional[str]
    foreign_amount: Optional[float]
    is_fee: bool
    fee_reference_amount: Optional[float]


class StatementVisionError(Exception):
    pass


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).replace(",", "").strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def extract_taishin_statement_lines(
    image_data: bytes,
    openai_client: Optional[OpenAI] = None,
    enable_compression: bool = True,
) -> list[TaishinStatementLine]:
    """Extract statement lines from an image using OpenAI Vision."""

    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)

    if enable_compression:
        image_data = compress_image(image_data)

    base64_image = encode_image_base64(image_data)

    response = openai_client.chat.completions.create(
        model=GPT_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TAISHIN_STATEMENT_VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        max_tokens=3000,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content
    if not text:
        raise StatementVisionError("Empty vision response")

    data = json.loads(text)
    status = data.get("status")
    if status != "success":
        message = data.get("message") or "Vision extraction failed"
        raise StatementVisionError(f"{status}: {message}")

    lines: list[TaishinStatementLine] = []
    for raw in data.get("lines", []):
        twd = _parse_float(raw.get("twd_amount"))
        if twd is None:
            # skip incomplete
            continue
        lines.append(
            TaishinStatementLine(
                card_hint=raw.get("card_hint"),
                trans_date=raw.get("trans_date"),
                post_date=raw.get("post_date"),
                description=(raw.get("description") or "").strip(),
                twd_amount=twd,
                fx_date=raw.get("fx_date"),
                country=raw.get("country"),
                currency=raw.get("currency"),
                foreign_amount=_parse_float(raw.get("foreign_amount")),
                is_fee=bool(raw.get("is_fee")),
                fee_reference_amount=_parse_float(raw.get("fee_reference_amount")),
            )
        )

    return lines


def _normalize_statement_date(statement_month: str, mmdd_or_iso: Optional[str]) -> Optional[str]:
    """Normalize statement date.

    Vision output may omit year (e.g. "12/22"). We infer year from statement_month (YYYY-MM).

    Rules:
    - If input already looks like YYYY-MM-DD, keep it.
    - If input is MM/DD or MM-DD:
      - year defaults to statement_month.year
      - if month < statement_month.month: assume it belongs to next year (cross-year cycle)
    """
    if not mmdd_or_iso:
        return None

    s = str(mmdd_or_iso).strip()
    if not s:
        return None

    # Already ISO
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]

    # Try MM/DD or MM-DD
    sep = "/" if "/" in s else ("-" if "-" in s else None)
    if not sep:
        return None

    try:
        mm_s, dd_s = [x.strip() for x in s.split(sep, 1)]
        mm = int(mm_s)
        dd = int(dd_s)
        y, m = [int(x) for x in statement_month.split("-", 1)]
        year = y + (1 if mm < m else 0)
        return f"{year:04d}-{mm:02d}-{dd:02d}"
    except Exception:
        return None


def notion_create_cc_statement_lines(
    *,
    database_id: Optional[str] = None,
    statement_month: str,
    statement_id: str,
    lines: list[TaishinStatementLine],
    account_page_id_by_card_hint: Optional[dict[str, str]] = None,
) -> list[str]:
    """Insert statement lines into Notion cc_statement_lines database.

    Returns created page ids.
    """

    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN not configured")

    if not database_id:
        database_id = NOTION_CC_STATEMENT_LINES_DB_ID

    if not database_id:
        raise RuntimeError("NOTION_CC_STATEMENT_LINES_DB_ID not configured")

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    created: list[str] = []
    for line in lines:
        account_rel = None
        if account_page_id_by_card_hint and line.card_hint:
            account_page_id = account_page_id_by_card_hint.get(line.card_hint)
            if account_page_id:
                account_rel = {"relation": [{"id": account_page_id}]}

        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": line.description[:80] or "(statement line)"}}]},
            "帳單月份": {"select": {"name": statement_month}},
            "帳單ID": {"rich_text": [{"text": {"content": statement_id}}]},
            "付款方式": {"select": {"name": line.card_hint}} if line.card_hint else None,
            "連結帳戶": account_rel,
            "消費日": {"date": {"start": _normalize_statement_date(statement_month, line.trans_date)}}
            if line.trans_date
            else None,
            "入帳起息日": {"date": {"start": _normalize_statement_date(statement_month, line.post_date)}}
            if line.post_date
            else None,
            "新臺幣金額": {"number": line.twd_amount},
            "外幣折算日": {"date": {"start": _normalize_statement_date(statement_month, line.fx_date)}}
            if line.fx_date
            else None,
            "消費地": {"select": {"name": line.country}} if line.country else None,
            "幣別": {"select": {"name": line.currency}} if line.currency else None,
            "外幣金額": {"number": line.foreign_amount} if line.foreign_amount is not None else None,
            "消費明細": {"rich_text": [{"text": {"content": line.description}}]},
            "是否手續費": {"checkbox": line.is_fee},
            "手續費參考金額": {"number": line.fee_reference_amount}
            if line.fee_reference_amount is not None
            else None,
            "對帳狀態": {"select": {"name": "unmatched"}},
        }

        props = {k: v for k, v in props.items() if v is not None}

        payload = {"parent": {"database_id": database_id}, "properties": props}
        resp = requests.post(
            "https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=20
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Notion create page failed: {resp.status_code} {resp.text}")
        created.append(resp.json()["id"])

    return created
