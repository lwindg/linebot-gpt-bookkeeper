# -*- coding: utf-8 -*-
"""OpenClaw assistant CLI.

This CLI is intended for local, deterministic-first bookkeeping flows triggered
by OpenClaw chat (e.g. `/bk ...`).

Design goals:
- Reuse the repo's parser/enricher/converter and Notion write path.
- Support a `--no-llm` mode that never calls OpenAI.
- When deterministic resolution is insufficient, emit `needs_llm` with a draft
  payload for OpenClaw to fill, then call `apply` to write via the repo.

NOTE: LINE bot routing remains unchanged. This CLI is a separate local entry.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from app.gpt.types import BookkeepingEntry
from app.processor import process_with_parser
from app.services.webhook_sender import send_multiple_webhooks, send_to_webhook
from app.services.kv_store import KVStore
from app.services.notion_service import NotionService
from app.services.lock_service import LockService
from app.services.statement_image_handler import (
    StatementVisionError,
    TaishinStatementLine,
    extract_taishin_statement_lines,
    extract_huanan_statement_lines,
    extract_fubon_statement_lines,
    extract_sinopac_statement_lines,
    extract_taishin_statement_text,
    build_ocr_preview,
    append_statement_note,
    ensure_cc_statement_page,
    notion_create_cc_statement_lines,
    detect_statement_date_anomaly,
    _normalize_statement_date,
)
from app.services.reconcile_statement import reconcile_statement, format_reconcile_summary
from app.shared.credit_card_config import get_bank_config
from app.shared.category_resolver import resolve_category_input


_NEEDS_LLM_CATEGORIES = {None, "", "未分類", "N/A"}
_ASSISTANT_LAST_CREATED_KEY = "assistant_last_created:{user_id}"
_CC_AUTO_POST_KEY = "cc:auto:{statement_id}:{line_id}:{rule}"


def _load_classifications_yaml() -> dict:
    config_path = Path(__file__).resolve().parent / "config" / "classifications.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_deterministic_keyword_categories(entries: list[BookkeepingEntry], *, text: str) -> None:
    """Best-effort category fill for --no-llm mode.

    Uses keyword/regex rules from app/config/classifications.yaml under:
    - rules.food_beverages (or legacy rules.beverages_snacks)
    - rules.meal_three_layer.patterns

    Only fills entries whose category is missing.
    """

    data = _load_classifications_yaml()
    rules = (data.get("rules") or {}) if isinstance(data, dict) else {}

    # 1) Meal three-layer exact patterns (早餐/午餐/晚餐)
    meal = rules.get("meal_three_layer") or {}
    patterns = meal.get("patterns") or []
    for p in patterns:
        pat = p.get("pattern")
        cat = p.get("category")
        if not pat or not cat:
            continue
        try:
            if re.search(pat, text):
                for e in entries:
                    if e.分類 in _NEEDS_LLM_CATEGORIES:
                        e.分類 = cat
        except re.error:
            # ignore invalid regex patterns
            continue

    # 2) Food / beverages / fruit keywords
    food_rules = rules.get("food_beverages") or rules.get("beverages_snacks") or []
    for r in food_rules:
        pat = r.get("pattern")
        cat = r.get("category")
        if not pat or not cat:
            continue
        try:
            if re.search(pat, text):
                for e in entries:
                    if e.分類 in _NEEDS_LLM_CATEGORIES:
                        e.分類 = cat
        except re.error:
            continue


def _entry_to_dict(entry: BookkeepingEntry) -> dict[str, Any]:
    d = asdict(entry)
    # Remove fields that are not part of the stable contract
    d.pop("response_text", None)
    return d


def _print_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def _is_needs_llm_entry(entry: BookkeepingEntry) -> bool:
    # Cashflow categories are fixed by enricher; if still missing, treat as needs_llm.
    if entry.分類 in _NEEDS_LLM_CATEGORIES:
        # Income may be fixed to 收入/其他, but keep the rule generic.
        return True
    return False


def cmd_bk(args: argparse.Namespace) -> int:
    user_id = args.user_id
    text = args.text.strip()
    dry_run = bool(args.dry_run)

    result = process_with_parser(text, skip_gpt=bool(args.no_llm), user_id=user_id)

    if result.intent == "error":
        _print_json(
            {
                "status": "error",
                "error": {
                    "message": result.error_message,
                    "reason": result.error_reason,
                },
            }
        )
        return 1

    entries = list(result.entries or [])
    if not entries:
        _print_json({"status": "error", "error": {"message": "no entries", "reason": "empty"}})
        return 1

    # Deterministic category fill for --no-llm mode (keyword rules from YAML)
    if bool(args.no_llm):
        _apply_deterministic_keyword_categories(entries, text=text)

    # If any entry lacks a resolved category, ask OpenClaw to fill it.
    if any(_is_needs_llm_entry(e) for e in entries):
        _print_json(
            {
                "status": "needs_llm",
                "draft": {
                    "user_id": user_id,
                    "source_text": text,
                    "entries": [
                        {
                            "日期": e.日期,
                            "時間": e.時間,
                            "品項": e.品項,
                            "原幣別": e.原幣別,
                            "原幣金額": e.原幣金額,
                            "匯率": e.匯率,
                            "付款方式": e.付款方式,
                            "交易ID": e.交易ID,
                            "明細說明": e.明細說明,
                            "分類": None if e.分類 in _NEEDS_LLM_CATEGORIES else e.分類,
                            "交易類型": e.交易類型,
                            "專案": e.專案,
                            "必要性": e.必要性,
                            "代墊狀態": e.代墊狀態,
                            "收款支付對象": e.收款支付對象,
                            "附註": e.附註,
                        }
                        for e in entries
                    ],
                },
            }
        )
        return 0

    # Deterministic: write immediately (1B policy)
    if dry_run:
        transaction_ids = [e.交易ID for e in entries if e.交易ID]
        _print_json(
            {
                "status": "dry_run",
                "result": {
                    "count": len(entries),
                    "transaction_ids": transaction_ids,
                    "entries": [_entry_to_dict(e) for e in entries],
                },
            }
        )
        return 0

    ok = True
    if len(entries) == 1:
        ok = send_to_webhook(entries[0], user_id=user_id)
    else:
        success, failure = send_multiple_webhooks(entries, user_id=user_id)
        ok = failure == 0

    transaction_ids = [e.交易ID for e in entries if e.交易ID]
    if ok and user_id and transaction_ids:
        KVStore().set(
            _ASSISTANT_LAST_CREATED_KEY.format(user_id=user_id),
            {"transaction_ids": transaction_ids},
            ttl=1800,
        )

    _print_json(
        {
            "status": "created" if ok else "failed",
            "result": {
                "count": len(entries),
                "transaction_ids": transaction_ids,
                "entries": [
                    {
                        "品項": e.品項,
                        "金額": e.原幣金額,
                        "分類": e.分類,
                        "專案": e.專案,
                        "交易ID": e.交易ID,
                    }
                    for e in entries
                ],
            },
        }
    )
    return 0 if ok else 1


def _draft_to_entries(draft: dict[str, Any]) -> list[BookkeepingEntry]:
    raw_entries = draft.get("entries") or []
    out: list[BookkeepingEntry] = []
    for item in raw_entries:
        entry = BookkeepingEntry(intent="bookkeeping")
        for k, v in item.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        out.append(entry)
    return out


def cmd_apply(args: argparse.Namespace) -> int:
    user_id = args.user_id
    dry_run = bool(args.dry_run)

    try:
        draft = json.loads(args.draft_json)
    except Exception as e:
        _print_json({"status": "error", "error": {"message": f"invalid draft_json: {e}", "reason": "bad_json"}})
        return 1

    entries = _draft_to_entries(draft)
    if not entries:
        _print_json({"status": "error", "error": {"message": "empty draft entries", "reason": "empty"}})
        return 1

    # Validate category paths (do not create new categories).
    for e in entries:
        if not e.分類 or e.分類 in _NEEDS_LLM_CATEGORIES:
            _print_json({"status": "error", "error": {"message": "missing category", "reason": "missing_category"}})
            return 1
        try:
            e.分類 = resolve_category_input(e.分類, original_category=None)
        except Exception as ex:
            _print_json(
                {
                    "status": "error",
                    "error": {
                        "message": f"invalid category: {e.分類}",
                        "reason": "invalid_category",
                        "detail": str(ex),
                    },
                }
            )
            return 1

    if dry_run:
        transaction_ids = [e.交易ID for e in entries if e.交易ID]
        _print_json(
            {
                "status": "dry_run",
                "result": {
                    "count": len(entries),
                    "transaction_ids": transaction_ids,
                    "entries": [_entry_to_dict(e) for e in entries],
                },
            }
        )
        return 0

    ok = True
    if len(entries) == 1:
        ok = send_to_webhook(entries[0], user_id=user_id)
    else:
        success, failure = send_multiple_webhooks(entries, user_id=user_id)
        ok = failure == 0

    transaction_ids = [e.交易ID for e in entries if e.交易ID]
    if ok and user_id and transaction_ids:
        KVStore().set(
            _ASSISTANT_LAST_CREATED_KEY.format(user_id=user_id),
            {"transaction_ids": transaction_ids},
            ttl=1800,
        )

    _print_json(
        {
            "status": "created" if ok else "failed",
            "result": {
                "count": len(entries),
                "transaction_ids": transaction_ids,
                "entries": [
                    {
                        "品項": e.品項,
                        "金額": e.原幣金額,
                        "分類": e.分類,
                        "專案": e.專案,
                        "交易ID": e.交易ID,
                    }
                    for e in entries
                ],
            },
        }
    )
    return 0 if ok else 1


def cmd_undo(args: argparse.Namespace) -> int:
    user_id = args.user_id

    kv = KVStore()
    cached = kv.get(_ASSISTANT_LAST_CREATED_KEY.format(user_id=user_id))
    transaction_ids = []
    if isinstance(cached, dict):
        transaction_ids = cached.get("transaction_ids") or []

    if not transaction_ids:
        _print_json({"status": "error", "error": {"message": "no last created transaction", "reason": "empty"}})
        return 1

    notion = NotionService()
    archived: list[str] = []
    failed: list[str] = []
    for tid in transaction_ids:
        if notion.archive_by_transaction_id(str(tid), ignore_missing=True):
            archived.append(str(tid))
        else:
            failed.append(str(tid))

    # Clear last-created key best-effort to avoid repeated undo attempts.
    try:
        kv.set(_ASSISTANT_LAST_CREATED_KEY.format(user_id=user_id), {"transaction_ids": []}, ttl=60)
    except Exception:
        pass

    _print_json({"status": "ok" if not failed else "partial", "result": {"archived": archived, "failed": failed}})
    return 0 if not failed else 1


def _normalize_bank_name(value: str) -> str:
    raw = (value or "").strip()
    if raw in ("台新", "Taishin", "taishin"):
        return "台新"
    if raw in ("華南", "華南銀行", "huanan", "Huanan", "HUANAN"):
        return "華南"
    if raw in ("富邦", "台北富邦", "Fubon", "fubon"):
        return "富邦"
    if raw in ("永豐", "永豐銀行", "SinoPac", "sinopac", "SINOPAC"):
        return "永豐"
    return raw


def _bank_supported(bank: str) -> bool:
    return get_bank_config(bank) is not None


def _statement_lines_from_json_payload(raw: str) -> list[TaishinStatementLine]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("lines_json must be a JSON array")

    lines: list[TaishinStatementLine] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"line[{idx}] must be an object")

        desc = (item.get("description") or "").strip()
        if not desc:
            raise ValueError(f"line[{idx}] missing description")

        try:
            twd_amount = float(item.get("twd_amount"))
        except Exception as e:  # pragma: no cover - defensive parse error branch
            raise ValueError(f"line[{idx}] invalid twd_amount") from e

        lines.append(
            TaishinStatementLine(
                card_hint=item.get("card_hint"),
                trans_date=item.get("trans_date"),
                post_date=item.get("post_date"),
                description=desc,
                twd_amount=twd_amount,
                fx_date=item.get("fx_date"),
                country=item.get("country"),
                currency=item.get("currency"),
                foreign_amount=(float(item["foreign_amount"]) if item.get("foreign_amount") is not None else None),
                is_fee=bool(item.get("is_fee")),
                fee_reference_amount=(
                    float(item["fee_reference_amount"]) if item.get("fee_reference_amount") is not None else None
                ),
            )
        )

    if not lines:
        raise ValueError("lines_json is empty")

    return lines


def _normalize_statement_line_payment_methods(
    lines: list[TaishinStatementLine],
    *,
    allowed_payment_methods: list[str],
    card_aliases: dict[str, str] | None = None,
) -> list[TaishinStatementLine]:
    if not lines:
        return lines
    aliases = {
        str(k).strip(): str(v).strip()
        for k, v in (card_aliases or {}).items()
        if str(k).strip() and str(v).strip()
    }

    def _mapped_hint(raw_hint: str | None) -> str | None:
        if raw_hint is None:
            return None
        h = str(raw_hint).strip()
        if not h:
            return None
        return aliases.get(h, h)

    allowed = [m for m in (allowed_payment_methods or []) if isinstance(m, str) and m.strip()]
    if not allowed:
        return [
            TaishinStatementLine(
                card_hint=_mapped_hint(ln.card_hint),
                trans_date=ln.trans_date,
                post_date=ln.post_date,
                description=ln.description,
                twd_amount=ln.twd_amount,
                fx_date=ln.fx_date,
                country=ln.country,
                currency=ln.currency,
                foreign_amount=ln.foreign_amount,
                is_fee=ln.is_fee,
                fee_reference_amount=ln.fee_reference_amount,
            )
            for ln in lines
        ]

    # When reconcile lock has exactly one payment method, force all imported lines
    # to that method if model output is missing/noisy (e.g. last-4 digits like 8905).
    if len(allowed) == 1:
        target = allowed[0]
        return [
            TaishinStatementLine(
                card_hint=(mh if mh in allowed else target),
                trans_date=ln.trans_date,
                post_date=ln.post_date,
                description=ln.description,
                twd_amount=ln.twd_amount,
                fx_date=ln.fx_date,
                country=ln.country,
                currency=ln.currency,
                foreign_amount=ln.foreign_amount,
                is_fee=ln.is_fee,
                fee_reference_amount=ln.fee_reference_amount,
            )
            for ln in lines
            for mh in [_mapped_hint(ln.card_hint)]
        ]

    return [
        TaishinStatementLine(
            card_hint=(mh if mh in allowed else None),
            trans_date=ln.trans_date,
            post_date=ln.post_date,
            description=ln.description,
            twd_amount=ln.twd_amount,
            fx_date=ln.fx_date,
            country=ln.country,
            currency=ln.currency,
            foreign_amount=ln.foreign_amount,
            is_fee=ln.is_fee,
            fee_reference_amount=ln.fee_reference_amount,
        )
        for ln in lines
        for mh in [_mapped_hint(ln.card_hint)]
    ]


def _backfill_missing_statement_dates(lines: list[TaishinStatementLine]) -> list[TaishinStatementLine]:
    out: list[TaishinStatementLine] = []
    for ln in (lines or []):
        trans = (ln.trans_date or "").strip() or None
        post = (ln.post_date or "").strip() or None
        if trans and not post:
            post = trans
        if post and not trans:
            trans = post
        out.append(
            TaishinStatementLine(
                card_hint=ln.card_hint,
                trans_date=trans,
                post_date=post,
                description=ln.description,
                twd_amount=ln.twd_amount,
                fx_date=ln.fx_date,
                country=ln.country,
                currency=ln.currency,
                foreign_amount=ln.foreign_amount,
                is_fee=ln.is_fee,
                fee_reference_amount=ln.fee_reference_amount,
            )
        )
    return out


def _extract_amount_from_desc_yuan(desc: str) -> float | None:
    values = re.findall(r"([0-9][0-9,]*)\s*元", desc or "")
    if not values:
        return None
    try:
        return float(values[-1].replace(",", ""))
    except Exception:
        return None


def _execute_bk_text(
    *,
    user_id: str,
    text: str,
    tx_date: str | None = None,
) -> tuple[bool, list[str], str | None]:
    result = process_with_parser(text, skip_gpt=True, user_id=user_id)
    if result.intent == "error":
        return False, [], result.error_message

    entries = list(result.entries or [])
    if not entries:
        return False, [], "no_entries"
    if any(_is_needs_llm_entry(e) for e in entries):
        return False, [], "needs_llm"
    if tx_date:
        for e in entries:
            e.日期 = tx_date

    ok = True
    if len(entries) == 1:
        ok = send_to_webhook(entries[0], user_id=user_id)
    else:
        _success, failure = send_multiple_webhooks(entries, user_id=user_id)
        ok = failure == 0

    transaction_ids = [e.交易ID for e in entries if e.交易ID]
    return ok, transaction_ids, (None if ok else "webhook_failed")


def _apply_sinopac_autobookkeeping(
    *,
    user_id: str,
    statement_id: str,
    statement_month: str,
    lines: list[TaishinStatementLine],
    line_page_ids: list[str],
) -> dict[str, Any]:
    kv = KVStore()
    created = 0
    skipped = 0
    failed: list[dict[str, str]] = []

    for idx, ln in enumerate(lines):
        if idx >= len(line_page_ids):
            break
        line_id = line_page_ids[idx]
        desc = (ln.description or "").strip()
        if not desc:
            continue

        rule = None
        text = None
        if "大戶消費回饋入帳戶" in desc:
            amt = _extract_amount_from_desc_yuan(desc)
            if amt is None or amt <= 0:
                skipped += 1
                continue
            rule = "rebate_income"
            text = f"收入 {int(amt) if float(amt).is_integer() else amt} 回饋金 大戶信用卡"
        elif "永豐自扣已入帳" in desc:
            amt = abs(float(ln.twd_amount or 0))
            if amt <= 0:
                skipped += 1
                continue
            rule = "autodebit_card_payment"
            text = f"大戶網銀繳卡費到大戶信用卡 {int(amt) if float(amt).is_integer() else amt}"
        else:
            continue

        dedupe_key = _CC_AUTO_POST_KEY.format(statement_id=statement_id, line_id=line_id, rule=rule)
        if kv.get(dedupe_key):
            skipped += 1
            continue

        tx_date = _normalize_statement_date(statement_month, ln.trans_date) if ln.trans_date else None
        ok, tx_ids, err = _execute_bk_text(user_id=user_id, text=str(text), tx_date=tx_date)
        if not ok:
            failed.append({"line_id": line_id, "rule": str(rule), "error": str(err or "unknown")})
            continue

        kv.set(dedupe_key, {"line_id": line_id, "rule": rule, "transaction_ids": tx_ids}, ttl=86400 * 30)
        created += 1

    return {"created": created, "skipped": skipped, "failed": failed}


def cmd_cc_lock(args: argparse.Namespace) -> int:
    user_id = args.user_id
    bank = _normalize_bank_name(args.bank)
    period = args.period

    if not _bank_supported(bank):
        _print_json(
            {
                "status": "error",
                "error": {
                    "message": "unsupported bank",
                    "reason": "unsupported_bank",
                    "supported_banks": ["台新", "華南", "富邦", "永豐"],
                },
            }
        )
        return 1

    LockService(user_id).set_reconcile_lock(bank=bank, period=period)
    lock_val = LockService(user_id).get_reconcile_lock() or {}
    _print_json({"status": "ok", "result": lock_val})
    return 0


def cmd_cc_status(args: argparse.Namespace) -> int:
    user_id = args.user_id
    lock_val = LockService(user_id).get_reconcile_lock()
    _print_json({"status": "ok", "result": lock_val or {}})
    return 0


def cmd_cc_unlock(args: argparse.Namespace) -> int:
    user_id = args.user_id
    LockService(user_id).remove_reconcile_lock()
    _print_json({"status": "ok"})
    return 0


def cmd_cc_set_card_alias(args: argparse.Namespace) -> int:
    user_id = args.user_id
    bank = _normalize_bank_name(args.bank)
    last4 = (args.last4 or "").strip()
    payment_method = (args.payment_method or "").strip()
    if not bank or not last4 or not payment_method:
        _print_json(
            {
                "status": "error",
                "error": {"message": "bank, last4, payment_method are required", "reason": "invalid_input"},
            }
        )
        return 1

    try:
        lock_service = LockService(user_id)
        lock_service.set_card_alias(bank=bank, last4=last4, payment_method=payment_method)
        _print_json(
            {
                "status": "ok",
                "result": {"bank": bank, "last4": last4, "payment_method": payment_method, "aliases": lock_service.get_card_aliases(bank)},
            }
        )
        return 0
    except ValueError as e:
        _print_json({"status": "error", "error": {"message": str(e), "reason": "invalid_input"}})
        return 1
    except Exception as e:
        _print_json({"status": "error", "error": {"message": str(e), "reason": "unexpected"}})
        return 1


def cmd_cc_list_card_alias(args: argparse.Namespace) -> int:
    user_id = args.user_id
    bank = _normalize_bank_name(args.bank)
    aliases = LockService(user_id).get_card_aliases(bank)
    _print_json({"status": "ok", "result": {"bank": bank, "aliases": aliases}})
    return 0


def cmd_cc_del_card_alias(args: argparse.Namespace) -> int:
    user_id = args.user_id
    bank = _normalize_bank_name(args.bank)
    last4 = (args.last4 or "").strip()
    if not bank or not last4:
        _print_json({"status": "error", "error": {"message": "bank and last4 are required", "reason": "invalid_input"}})
        return 1
    lock_service = LockService(user_id)
    lock_service.remove_card_alias(bank=bank, last4=last4)
    _print_json({"status": "ok", "result": {"bank": bank, "last4": last4, "aliases": lock_service.get_card_aliases(bank)}})
    return 0


def cmd_cc_import(args: argparse.Namespace) -> int:
    user_id = args.user_id
    image_path = args.image_path
    message_id = args.message_id
    no_llm = bool(args.no_llm)
    lines_json = args.lines_json
    lines_json_path = args.lines_json_path

    lock_service = LockService(user_id)
    lock_val = lock_service.get_reconcile_lock() or {}
    bank = _normalize_bank_name(lock_val.get("bank") or "")
    period = lock_val.get("period")
    statement_id = lock_val.get("statement_id")
    methods = lock_val.get("payment_methods") or []

    if not period or not statement_id or not _bank_supported(bank):
        _print_json({"status": "error", "error": {"message": "reconcile lock not set", "reason": "missing_lock"}})
        return 1

    try:
        lines: list[TaishinStatementLine]
        image_data: bytes | None = None

        if lines_json or lines_json_path:
            if lines_json and lines_json_path:
                _print_json(
                    {
                        "status": "error",
                        "error": {"message": "provide only one of lines-json and lines-json-path", "reason": "invalid_input"},
                    }
                )
                return 1
            raw = lines_json
            if lines_json_path:
                raw = Path(str(lines_json_path)).read_text(encoding="utf-8")
            lines = _statement_lines_from_json_payload(str(raw or ""))
        elif image_path:
            if no_llm:
                _print_json(
                    {
                        "status": "error",
                        "error": {
                            "message": "no_llm mode requires lines-json or lines-json-path",
                            "reason": "missing_structured_lines",
                        },
                    }
                )
                return 1

            with open(image_path, "rb") as f:
                image_data = f.read()

            if bank == "台新":
                lines = extract_taishin_statement_lines(image_data, statement_month=period)
            elif bank == "華南":
                lines = extract_huanan_statement_lines(image_data, statement_month=period)
            elif bank == "富邦":
                lines = extract_fubon_statement_lines(image_data, statement_month=period)
            elif bank == "永豐":
                lines = extract_sinopac_statement_lines(image_data, statement_month=period)
            else:
                _print_json({"status": "error", "error": {"message": "unsupported bank", "reason": "unsupported_bank"}})
                return 1
        else:
            _print_json(
                {
                    "status": "error",
                    "error": {
                        "message": "missing input: provide image-path or structured lines",
                        "reason": "missing_input",
                    },
                }
            )
            return 1

        lines = _backfill_missing_statement_dates(lines)
        card_aliases = lock_service.get_card_aliases(bank)
        lines = _normalize_statement_line_payment_methods(
            lines,
            allowed_payment_methods=list(methods),
            card_aliases=card_aliases,
        )

        statement_page_id = ensure_cc_statement_page(
            statement_id=statement_id,
            period=period,
            bank=bank,
            source_note=(
                f"assistant_cli image_path={image_path}" + (f" message_id={message_id}" if message_id else "")
                if image_path
                else "assistant_cli lines_json import"
            ),
        )

        # OCR preview for audit (Taishin parser only)
        if bank == "台新" and image_data is not None:
            try:
                ocr_text = extract_taishin_statement_text(image_data, enable_compression=False)
                preview = build_ocr_preview(ocr_text)
                append_statement_note(statement_page_id=statement_page_id, note=f"[OCR preview]\n{preview}")
            except Exception:
                pass

        created_ids = notion_create_cc_statement_lines(
            statement_month=period,
            statement_id=statement_id,
            lines=lines,
            statement_page_id=statement_page_id,
        )

        warning = detect_statement_date_anomaly(period, lines)
        auto_bookkeeping = None
        if bank == "永豐":
            auto_bookkeeping = _apply_sinopac_autobookkeeping(
                user_id=user_id,
                statement_id=statement_id,
                statement_month=period,
                lines=lines,
                line_page_ids=created_ids,
            )

        # increment uploaded count (best-effort)
        try:
            lock_val["uploaded_images"] = int(lock_val.get("uploaded_images", 0)) + 1
            lock_service.kv.set(
                f"lock:reconcile:{user_id}",
                lock_val,
                ttl=86400 * 7,
            )
        except Exception:
            pass

        _print_json(
            {
                "status": "ok",
                "result": {
                    "bank": bank,
                    "period": period,
                    "statement_id": statement_id,
                    "statement_page_id": statement_page_id,
                    "created_count": len(created_ids),
                    "warning": warning,
                    "auto_bookkeeping": auto_bookkeeping,
                },
            }
        )
        return 0

    except StatementVisionError as e:
        _print_json({"status": "error", "error": {"message": str(e), "reason": "vision_error"}})
        return 1
    except Exception as e:
        _print_json({"status": "error", "error": {"message": str(e), "reason": "unexpected"}})
        return 1


def cmd_cc_run(args: argparse.Namespace) -> int:
    user_id = args.user_id

    lock_service = LockService(user_id)
    lock_val = lock_service.get_reconcile_lock() or {}
    bank = _normalize_bank_name(lock_val.get("bank") or "")
    period = lock_val.get("period")
    statement_id = lock_val.get("statement_id")

    if not period or not statement_id or not _bank_supported(bank):
        _print_json({"status": "error", "error": {"message": "reconcile lock not set", "reason": "missing_lock"}})
        return 1

    try:
        payment_methods = lock_val.get("payment_methods") or []
        summary = reconcile_statement(
            statement_id=statement_id,
            period=period,
            payment_methods=payment_methods,
            bank=bank,
        )
        text = format_reconcile_summary(summary)
        _print_json({"status": "ok", "result": summary.__dict__, "summary_text": text})
        return 0
    except Exception as e:
        _print_json({"status": "error", "error": {"message": str(e), "reason": "unexpected"}})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assistant_cli", description="OpenClaw local assistant CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    bk = sub.add_parser("bk", help="Parse and write bookkeeping entries (rules-first)")
    bk.add_argument("--user-id", required=True)
    bk.add_argument("--text", required=True)
    bk.add_argument("--no-llm", action="store_true", help="Never call OpenAI (deterministic-only)")
    bk.add_argument("--dry-run", action="store_true", help="Do not write to Notion/webhook")
    bk.set_defaults(func=cmd_bk)

    apply = sub.add_parser("apply", help="Apply OpenClaw-inferred fields and write to Notion")
    apply.add_argument("--user-id", required=True)
    apply.add_argument("--draft-json", required=True)
    apply.add_argument("--dry-run", action="store_true", help="Do not write to Notion/webhook")
    apply.set_defaults(func=cmd_apply)

    undo = sub.add_parser("undo", help="Archive the last created entries for this user")
    undo.add_argument("--user-id", required=True)
    undo.set_defaults(func=cmd_undo)

    cc = sub.add_parser("cc", help="Credit card statement import/reconcile helpers")
    cc_sub = cc.add_subparsers(dest="cc_command", required=True)

    cc_lock = cc_sub.add_parser("lock", help="Lock reconcile mode")
    cc_lock.add_argument("--user-id", required=True)
    cc_lock.add_argument("--bank", required=True)
    cc_lock.add_argument("--period", required=True)
    cc_lock.set_defaults(func=cmd_cc_lock)

    cc_status = cc_sub.add_parser("status", help="Show current reconcile lock")
    cc_status.add_argument("--user-id", required=True)
    cc_status.set_defaults(func=cmd_cc_status)

    cc_unlock = cc_sub.add_parser("unlock", help="Unlock reconcile mode")
    cc_unlock.add_argument("--user-id", required=True)
    cc_unlock.set_defaults(func=cmd_cc_unlock)

    cc_set_card_alias = cc_sub.add_parser("set-card-alias", help="Set per-bank card last4 -> payment method alias")
    cc_set_card_alias.add_argument("--user-id", required=True)
    cc_set_card_alias.add_argument("--bank", required=True)
    cc_set_card_alias.add_argument("--last4", required=True, help="Card last4 or card_hint token")
    cc_set_card_alias.add_argument("--payment-method", required=True)
    cc_set_card_alias.set_defaults(func=cmd_cc_set_card_alias)

    cc_list_card_alias = cc_sub.add_parser("list-card-alias", help="List per-bank card aliases")
    cc_list_card_alias.add_argument("--user-id", required=True)
    cc_list_card_alias.add_argument("--bank", required=True)
    cc_list_card_alias.set_defaults(func=cmd_cc_list_card_alias)

    cc_del_card_alias = cc_sub.add_parser("del-card-alias", help="Delete per-bank card alias by last4")
    cc_del_card_alias.add_argument("--user-id", required=True)
    cc_del_card_alias.add_argument("--bank", required=True)
    cc_del_card_alias.add_argument("--last4", required=True)
    cc_del_card_alias.set_defaults(func=cmd_cc_del_card_alias)

    cc_import = cc_sub.add_parser("import", help="Import statement image for current locked bank")
    cc_import.add_argument("--user-id", required=True)
    cc_import.add_argument("--image-path", required=False)
    cc_import.add_argument("--lines-json", required=False, help="Structured statement lines JSON array")
    cc_import.add_argument("--lines-json-path", required=False, help="Path to structured statement lines JSON file")
    cc_import.add_argument("--no-llm", action="store_true", help="Do not call OpenAI; requires structured lines input")
    cc_import.add_argument("--message-id", required=False)
    cc_import.set_defaults(func=cmd_cc_import)

    cc_run = cc_sub.add_parser("run", help="Run reconcile for current statement")
    cc_run.add_argument("--user-id", required=True)
    cc_run.set_defaults(func=cmd_cc_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
