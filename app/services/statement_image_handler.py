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
from collections import Counter
import re

import requests
from openai import OpenAI

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import (
    OPENAI_API_KEY,
    GPT_VISION_MODEL,
    NOTION_TOKEN,
    NOTION_CC_STATEMENT_LINES_DB_ID,
    NOTION_CC_STATEMENTS_DB_ID,
)
from app.gpt.prompts import TAISHIN_STATEMENT_VISION_PROMPT, TAISHIN_STATEMENT_OCR_PROMPT
from app.services.image_handler import compress_image, encode_image_base64

logger = logging.getLogger(__name__)

NOTION_PAGE_VERSION = "2025-09-03"
NOTION_DB_VERSION = "2022-06-28"  # for /v1/databases/* endpoints


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


def build_statement_raw_text(statement_month: str, line: TaishinStatementLine) -> str:
    trans = _normalize_statement_date(statement_month, line.trans_date) if line.trans_date else None
    post = _normalize_statement_date(statement_month, line.post_date) if line.post_date else None
    fx = _normalize_statement_date(statement_month, line.fx_date) if line.fx_date else None

    parts = [
        f"card_hint={line.card_hint or ''}",
        f"trans_date={trans or ''}",
        f"post_date={post or ''}",
        f"twd_amount={line.twd_amount}",
        f"currency={line.currency or ''}",
        f"foreign_amount={line.foreign_amount if line.foreign_amount is not None else ''}",
        f"fx_date={fx or ''}",
        f"country={line.country or ''}",
        f"is_fee={line.is_fee}",
        f"fee_reference_amount={line.fee_reference_amount if line.fee_reference_amount is not None else ''}",
        f"description={line.description}",
    ]
    return " | ".join(parts)


def detect_statement_date_anomaly(statement_month: str, lines: list[TaishinStatementLine]) -> Optional[str]:
    """Detect suspicious date distribution (warning only).

    Heuristic: if many lines share the same trans_date, but post_date varies,
    it often indicates the model latched onto a header date.
    """

    trans_dates = []
    post_dates = []
    for ln in lines:
        td = _normalize_statement_date(statement_month, ln.trans_date) if ln.trans_date else None
        pd = _normalize_statement_date(statement_month, ln.post_date) if ln.post_date else None
        if td:
            trans_dates.append(td)
        if pd:
            post_dates.append(pd)

    if len(trans_dates) < 6:
        return None

    c = Counter(trans_dates)
    top_date, top_count = c.most_common(1)[0]

    # Warn if >= 50% of lines share the same trans_date.
    if top_count / max(len(trans_dates), 1) >= 0.5:
        # Only warn if post_date distribution is not similarly collapsed.
        pc = Counter(post_dates)
        if not pc:
            return "⚠️ 偵測到消費日分布異常（大量集中同一天）。建議檢查消費日欄位是否有錯讀。"
        p_top = pc.most_common(1)[0][1]
        if p_top / max(len(post_dates), 1) < 0.5:
            return (
                f"⚠️ 偵測到消費日分布異常（{top_count} 筆集中在 {top_date}）。"
                "\n這常見於帳單表格欄位錯讀；建議到 Notion 檢查『消費日』是否正確。"
            )

    return None


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


def _token_is_amount(tok: str) -> bool:
    t = tok.replace(",", "")
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", t))


def _parse_amount(tok: str) -> Optional[float]:
    try:
        return float(tok.replace(",", ""))
    except Exception:
        return None


def parse_taishin_statement_ocr_text(text: str, *, statement_month: str) -> list[TaishinStatementLine]:
    """Parse Taishin statement rows from OCR text.

    Strategy:
    - Walk line-by-line.
    - Track current card section by keywords.
    - For each row that starts with two date tokens, parse columns from right-to-left.

    Expected row start:
      <trans_date> <post_date> <description...> <twd_amount> [fx_date] [country] [currency] [foreign_amount]

    Dates may be ROC(YYYMMDD), Gregorian(YYYYMMDD), YYMMDD, MM/DD, or MMDD.
    """

    lines: list[TaishinStatementLine] = []
    current_card: Optional[str] = None

    for raw_line in (text or "").splitlines():
        s = raw_line.strip()
        if not s:
            continue

        # Section detection
        s_norm = s.replace(" ", "")
        if "GoGo" in s or "@GoGo" in s or "@GoGoicash" in s_norm:
            current_card = "台新狗卡"
        if "FlyGo" in s:
            current_card = "FlyGo 信用卡"

        parts = s.split()
        if len(parts) < 4:
            continue

        # Row detection: must start with two date-ish tokens (digits or with / or -)
        t0, t1 = parts[0], parts[1]
        if not (re.fullmatch(r"[0-9/\-]+", t0) and re.fullmatch(r"[0-9/\-]+", t1)):
            continue

        trans_date = t0
        post_date = t1

        # Parse from right-to-left
        rest = parts[2:]

        foreign_amount = None
        currency = None
        country = None
        fx_date = None

        # foreign amount at end
        if rest and _token_is_amount(rest[-1]):
            # only treat it as foreign amount if there is a currency code before it
            if len(rest) >= 2 and re.fullmatch(r"[A-Z]{3}", rest[-2]):
                foreign_amount = _parse_amount(rest[-1])
                currency = rest[-2]
                rest = rest[:-2]

        # country code
        if rest and re.fullmatch(r"[A-Z]{2}", rest[-1]):
            country = rest[-1]
            rest = rest[:-1]

        # fx date as MMDD or date-like
        if rest and re.fullmatch(r"\d{4}", rest[-1]):
            fx_date = rest[-1]
            rest = rest[:-1]

        # TWD amount should be the last numeric in rest
        if not rest:
            continue

        twd_amount = None
        twd_idx = None
        for i in range(len(rest) - 1, -1, -1):
            if _token_is_amount(rest[i]):
                twd_amount = _parse_amount(rest[i])
                twd_idx = i
                break

        if twd_amount is None or twd_idx is None:
            continue

        desc_tokens = rest[:twd_idx]
        description = " ".join(desc_tokens).strip()
        if not description:
            description = "(statement line)"

        # Fee line detection
        is_fee = description.startswith("國外交易服務費")
        fee_reference_amount = None
        if is_fee:
            m = re.search(r"服務費[—\-](\d+(?:\.\d+)?)", description)
            if m:
                fee_reference_amount = _parse_float(m.group(1))

        lines.append(
            TaishinStatementLine(
                card_hint=current_card,
                trans_date=trans_date,
                post_date=post_date,
                description=description,
                twd_amount=float(twd_amount),
                fx_date=fx_date,
                country=country,
                currency=currency,
                foreign_amount=foreign_amount,
                is_fee=is_fee,
                fee_reference_amount=fee_reference_amount,
            )
        )

    return lines


def extract_taishin_statement_text(
    image_data: bytes,
    openai_client: Optional[OpenAI] = None,
    enable_compression: bool = True,
) -> str:
    """Extract raw text from a statement image using OpenAI Vision (OCR-like)."""

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
                    {"type": "text", "text": TAISHIN_STATEMENT_OCR_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        max_tokens=3000,
    )

    text = response.choices[0].message.content
    if not text:
        raise StatementVisionError("Empty OCR response")

    return text


def _majority(values: list[Optional[str]]) -> Optional[str]:
    vals = [v for v in values if v]
    if not vals:
        return None
    c = Counter(vals)
    top, cnt = c.most_common(1)[0]
    if cnt >= 2:
        return top
    return vals[0]


def reconcile_ocr_parses(
    parses: list[list[TaishinStatementLine]],
    *,
    statement_month: str,
) -> list[TaishinStatementLine]:
    """Combine multiple OCR parses to reduce single-character OCR errors.

    - Choose a baseline parse (most lines).
    - For each baseline line, find matching lines in other parses by (twd_amount, normalized post_date).
    - Vote on trans_date/post_date/fx_date tokens.

    This is best-effort and intentionally conservative.
    """

    if not parses:
        return []

    baseline = max(parses, key=lambda x: len(x))

    # Build lookup for other parses
    lookups = []
    for p in parses:
        d = {}
        for ln in p:
            post_norm = _normalize_statement_date(statement_month, ln.post_date) if ln.post_date else None
            key = (round(float(ln.twd_amount), 2), post_norm)
            # keep first
            d.setdefault(key, ln)
        lookups.append(d)

    merged: list[TaishinStatementLine] = []
    for base in baseline:
        post_norm = _normalize_statement_date(statement_month, base.post_date) if base.post_date else None
        key = (round(float(base.twd_amount), 2), post_norm)

        candidates: list[TaishinStatementLine] = []
        for d in lookups:
            if key in d:
                candidates.append(d[key])

        trans_vote = _majority([c.trans_date for c in candidates])
        post_vote = _majority([c.post_date for c in candidates])
        fx_vote = _majority([c.fx_date for c in candidates])

        # Prefer non-empty card_hint/desc/currency from baseline
        merged.append(
            TaishinStatementLine(
                card_hint=base.card_hint,
                trans_date=trans_vote or base.trans_date,
                post_date=post_vote or base.post_date,
                description=base.description,
                twd_amount=base.twd_amount,
                fx_date=fx_vote or base.fx_date,
                country=base.country,
                currency=base.currency,
                foreign_amount=base.foreign_amount,
                is_fee=base.is_fee,
                fee_reference_amount=base.fee_reference_amount,
            )
        )

    return merged


def build_ocr_preview(text: str, *, max_lines: int = 30, max_chars: int = 1800) -> str:
    lines = (text or "").splitlines()
    chunk = "\n".join(lines[:max_lines]).strip()
    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "…"
    return chunk


def append_statement_note(*, statement_page_id: str, note: str) -> None:
    """Append note text into statement page 備註 (best-effort)."""

    if not note:
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_PAGE_VERSION,
    }

    # Fetch existing note
    resp = requests.get(f"https://api.notion.com/v1/pages/{statement_page_id}", headers=headers, timeout=30)
    if resp.status_code != 200:
        return

    props = (resp.json().get("properties") or {})
    rt = (props.get("備註") or {}).get("rich_text") or []
    existing = rt[0].get("plain_text") if rt else ""

    combined = (existing + "\n\n" + note).strip() if existing else note.strip()
    if len(combined) > 2000:
        combined = combined[-2000:]

    payload = {
        "properties": {
            "備註": {"rich_text": [{"text": {"content": combined}}]},
        }
    }

    requests.patch(
        f"https://api.notion.com/v1/pages/{statement_page_id}",
        headers=headers,
        json=payload,
        timeout=30,
    )


def extract_taishin_statement_lines(
    image_data: bytes,
    openai_client: Optional[OpenAI] = None,
    enable_compression: bool = True,
    *,
    statement_month: Optional[str] = None,
) -> list[TaishinStatementLine]:
    """Extract statement lines from an image.

    Primary: OCR text extraction + deterministic parsing (more stable than direct JSON extraction).
    Fallback: legacy JSON extraction prompt.
    """

    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Primary: OCR text -> deterministic parse
    if statement_month:
        # Run OCR multiple times (with/without compression) and vote to reduce single-character OCR errors.
        ocr_texts = [
            extract_taishin_statement_text(
                image_data,
                openai_client=openai_client,
                enable_compression=True,
            ),
            extract_taishin_statement_text(
                image_data,
                openai_client=openai_client,
                enable_compression=False,
            ),
            extract_taishin_statement_text(
                image_data,
                openai_client=openai_client,
                enable_compression=True,
            ),
        ]

        parses = [parse_taishin_statement_ocr_text(t, statement_month=statement_month) for t in ocr_texts]
        parsed = reconcile_ocr_parses(parses, statement_month=statement_month)

        if not parsed:
            raise StatementVisionError("not_statement: no parseable statement rows found")

        return parsed

    # Fallback (only when statement_month is not provided): legacy JSON extraction
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

    # ROC date formats from Taishin statement, e.g. 1141202 (YYYMMDD)
    if s.isdigit():
        # YYYYMMDD (8 digits) - Gregorian year
        if len(s) == 8:
            try:
                year = int(s[:4])
                mm = int(s[4:6])
                dd = int(s[6:8])
                return f"{year:04d}-{mm:02d}-{dd:02d}"
            except Exception:
                return None

        # YYYMMDD (7 digits) - ROC year
        if len(s) == 7:
            try:
                roc_y = int(s[:3])
                mm = int(s[3:5])
                dd = int(s[5:7])
                year = roc_y + 1911
                return f"{year:04d}-{mm:02d}-{dd:02d}"
            except Exception:
                return None

        # YYMMDD (6 digits) - Gregorian short year (assume 2000+YY, then sanity-check by statement period)
        if len(s) == 6:
            try:
                yy = int(s[:2])
                mm = int(s[2:4])
                dd = int(s[4:6])
                year = 2000 + yy

                # If far from statement period year, shift to 1900s as a fallback.
                y, _m = [int(x) for x in statement_month.split("-", 1)]
                if abs(year - y) >= 50:
                    year = 1900 + yy

                return f"{year:04d}-{mm:02d}-{dd:02d}"
            except Exception:
                return None

        # MMDD (4 digits), often used in FX date column (e.g. 1208)
        if len(s) == 4:
            try:
                mm = int(s[:2])
                dd = int(s[2:4])
                y, m = [int(x) for x in statement_month.split("-", 1)]
                year = y + (1 if mm < m else 0)
                return f"{year:04d}-{mm:02d}-{dd:02d}"
            except Exception:
                return None

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


def ensure_cc_statement_page(
    *,
    statement_id: str,
    period: str,
    bank: str = "台新",
    source_note: Optional[str] = None,
) -> str:
    """Create/find a statement page.

    Uses 帳單ID as the unique key.

    We intentionally keep the required metadata minimal in MVP.
    """

    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN not configured")
    if not NOTION_CC_STATEMENTS_DB_ID:
        raise RuntimeError("NOTION_CC_STATEMENTS_DB_ID not configured")

    headers_db = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_DB_VERSION,
    }

    # 1) Find existing
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_CC_STATEMENTS_DB_ID}/query",
        headers=headers_db,
        json={
            "page_size": 5,
            "filter": {"property": "帳單ID", "rich_text": {"equals": statement_id}},
        },
        timeout=30,
    )
    if resp.status_code == 200:
        results = resp.json().get("results") or []
        if results:
            return results[0]["id"]
    else:
        raise RuntimeError(f"Notion query(statement) failed: {resp.status_code} {resp.text}")

    # 2) Create
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz).isoformat()

    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": f"{bank} {period}"}}]},
        "帳單ID": {"rich_text": [{"text": {"content": statement_id}}]},
        "銀行": {"select": {"name": bank}},
        "匯入時間": {"date": {"start": now}},
    }
    if source_note:
        props["備註"] = {"rich_text": [{"text": {"content": source_note[:2000]}}]}

    headers_page = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_PAGE_VERSION,
    }

    resp2 = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers_page,
        json={"parent": {"database_id": NOTION_CC_STATEMENTS_DB_ID}, "properties": props},
        timeout=30,
    )
    if resp2.status_code != 200:
        raise RuntimeError(f"Notion create(statement) failed: {resp2.status_code} {resp2.text}")
    return resp2.json()["id"]


def notion_create_cc_statement_lines(
    *,
    database_id: Optional[str] = None,
    statement_month: str,
    statement_id: str,
    lines: list[TaishinStatementLine],
    statement_page_id: Optional[str] = None,
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
        "Notion-Version": NOTION_PAGE_VERSION,
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
            "帳單ID": {"rich_text": [{"text": {"content": statement_id}}]},
            "所屬帳單": {"relation": [{"id": statement_page_id}]} if statement_page_id else None,
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
            "raw_text": {
                "rich_text": [
                    {
                        "text": {
                            "content": build_statement_raw_text(statement_month, line)[:2000]
                        }
                    }
                ]
            },
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
