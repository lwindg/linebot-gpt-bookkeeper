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
import sys
from dataclasses import asdict
from typing import Any

from app.gpt.types import BookkeepingEntry
from app.processor import process_with_parser
from app.services.webhook_sender import send_multiple_webhooks, send_to_webhook
from app.services.kv_store import KVStore
from app.services.notion_service import NotionService
from app.shared.category_resolver import resolve_category_input


_NEEDS_LLM_CATEGORIES = {None, "", "未分類", "N/A"}
_ASSISTANT_LAST_CREATED_KEY = "assistant_last_created:{user_id}"


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
