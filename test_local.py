#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地測試工具 - 直接測試 GPT 解析功能

使用方式：
  python test_local.py                      # 互動模式
  python test_local.py '早餐80元，午餐150元，現金'  # 單次測試（僅 GPT 解析）
  python test_local.py --raw '11/12 午餐120元現金'  # 單次測試（僅輸出 JSON，給測試 runner 用）
  python test_local.py --full '午餐 100 現金'      # 完整流程測試（GPT + Webhook + KV）

完整流程模式（--full）：
  python test_local.py --full               # 互動模式，啟用完整流程（預設 dry-run）
  python test_local.py --full '午餐 100'    # 單次測試，顯示 webhook payload + 儲存 KV
  python test_local.py --full --live '午餐 100'  # 實際發送 webhook（謹慎使用）

  完整流程包含：
  - GPT 解析訊息
  - 記帳時：顯示 webhook payload + 儲存到 KV（--live 時才實際發送）
  - 修改時：讀取 KV + 顯示 UPDATE webhook payload + 刪除 KV（--live 時才實際發送）

KV 儲存操作：
  python test_local.py --kv                 # 查看 KV 中儲存的交易記錄
  python test_local.py --clear              # 清除 KV 中的交易記錄
  python test_local.py --user=U123456 --kv  # 指定用戶 ID 查看 KV

互動模式指令：
  - 直接輸入記帳訊息進行測試
  - 'full' - 切換完整流程模式（含 webhook payload 顯示 + KV）
  - 'live' - 切換 live 模式（實際發送 webhook，謹慎使用）
  - 'json' - 切換 JSON 顯示
  - 'kv' - 查看 KV 中儲存的交易記錄
  - 'clear' - 清除 KV 中的交易記錄
  - 'exit' / 'quit' - 離開

外幣消費測試案例（多幣別）：
  python test_local.py 'WSJ 4.99美元 大戶'
  python test_local.py 'Netflix 15.99USD 信用卡'
  python test_local.py '飯店住宿 290.97歐元 信用卡'
  python test_local.py '便當 80 現金' # TWD (default)
  python test_local.py '咖啡 10美金 現金' # 測試同義詞
"""

import sys
import logging
import json
import argparse
from unittest.mock import patch
from app.gpt_processor import process_multi_expense, MultiExpenseResult, BookkeepingEntry
from app.kv_store import get_last_transaction, KVStore
from app.config import KV_ENABLED
from app.webhook_sender import send_multiple_webhooks, build_create_payload, build_update_payload
from app.line_handler import handle_update_last_entry, format_multi_confirmation_message

# Default test user ID for local testing
DEFAULT_TEST_USER_ID = "test_local_user"


def entry_to_dict(entry: BookkeepingEntry) -> dict:
    return {
        "日期": entry.日期,
        "品項": entry.品項,
        "原幣別": entry.原幣別,
        "原幣金額": entry.原幣金額,
        "匯率": entry.匯率,
        "付款方式": entry.付款方式,
        "交易ID": entry.交易ID,
        "明細說明": entry.明細說明,
        "分類": entry.分類,
        "交易類型": entry.交易類型,
        "專案": entry.專案,
        "必要性": entry.必要性,
        "代墊狀態": entry.代墊狀態,
        "收款支付對象": entry.收款支付對象,
        "附註": entry.附註,
    }


def normalize_error_message(result: MultiExpenseResult) -> str:
    message = getattr(result, "error_message", None)
    return message or "未知錯誤"


def normalize_error_reason(result: MultiExpenseResult) -> str | None:
    return getattr(result, "error_reason", None)


def result_to_raw_json(result) -> dict:
    """
    Convert processing result to a stable, machine-readable JSON.

    Notes:
    - Always returns an object with at least `intent`.
    - For bookkeeping intents, returns `entries` (list) for uniform consumption by test runners.
    """
    intent = getattr(result, "intent", "")
    if intent in ("multi_bookkeeping", "cashflow_intents"):
        intent_display = "現金流" if intent == "cashflow_intents" else "記帳"
        return {"intent": intent, "intent_display": intent_display, "entries": [entry_to_dict(e) for e in result.entries]}
    if intent == "update_last_entry":
        return {"intent": intent, "intent_display": "修改上一筆", "fields_to_update": getattr(result, "fields_to_update", {})}
    if intent == "conversation":
        return {"intent": intent, "intent_display": "對話", "response_text": getattr(result, "response_text", "")}
    if intent == "error":
        return {
            "intent": intent,
            "intent_display": "錯誤",
            "error_message": normalize_error_message(result),
            "reason": normalize_error_reason(result),
        }
    return {"intent": intent, "intent_display": intent}


def single_test_raw(message: str, *, debug: bool = False) -> int:
    """
    Raw single-test mode: print JSON only (no extra text).

    This is designed for automated test runners (e.g., run_tests.sh).
    """
    try:
        result = process_multi_expense(message, debug=debug)
        data = result_to_raw_json(result)
        print(json.dumps(data, ensure_ascii=False))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test_local.py",
        description="Local test tool for LINE Bot GPT Bookkeeper.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("message", nargs="*", help="Message to test (single-run mode).")
    parser.add_argument("--full", action="store_true", help="Simulate full flow (GPT + webhook payload + KV).")
    parser.add_argument("--live", action="store_true", help="Enable LIVE webhook sending (only with --full).")
    parser.add_argument("--raw", action="store_true", help="Print JSON only for single-run mode (no extra text).")
    parser.add_argument("--user", default=DEFAULT_TEST_USER_ID, help="Test user id used for KV/full flow.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logs for prompt routing and GPT output.")
    parser.add_argument("--parser", action="store_true", help="Use parser-first pipeline (process_with_parser).")
    parser.add_argument("--kv", action="store_true", help="Show last transaction stored in KV and exit.")
    parser.add_argument("--clear", action="store_true", help="Clear KV record for the user and exit.")
    return parser


def simulate_full_flow(
    message: str,
    user_id: str = DEFAULT_TEST_USER_ID,
    show_json: bool = True,
    live_mode: bool = False,
    debug: bool = False,
    use_parser: bool = False,
):
    """
    模擬完整的 LINE handler 流程

    包含：
    - GPT 解析
    - 記帳時：顯示 webhook payload + 儲存 KV（live_mode=True 時才發送）
    - 修改時：讀取 KV + 顯示 UPDATE webhook payload + 刪除 KV（live_mode=True 時才發送）

    Args:
        message: 使用者輸入的訊息
        user_id: 測試用戶 ID
        show_json: 是否顯示 JSON
        live_mode: 是否實際發送 webhook（預設 False，只顯示 payload）
    """
    print("\n" + "=" * 60)
    mode_indicator = "🔴 LIVE" if live_mode else "🟢 DRY-RUN"
    print(f"🔄 完整流程模擬 [{mode_indicator}] (user_id: {user_id})")
    print(f"💬 訊息: {message}")
    print("=" * 60)

    # Step 1: GPT 解析
    print("\n📝 Step 1: GPT 解析...")
    if use_parser:
        from app.processor import process_with_parser

        result = process_with_parser(message)
    else:
        result = process_multi_expense(message, debug=debug)
    print(f"   意圖: {result.intent}")

    # Step 2: 根據意圖執行對應操作
    if result.intent in ("multi_bookkeeping", "cashflow_intents"):
        print(f"\n📝 Step 2: 發送 webhook 並儲存 KV...")
        print(f"   項目數量: {len(result.entries)}")

        for i, entry in enumerate(result.entries, 1):
            print(f"   [{i}] {entry.品項} - {entry.原幣金額} {entry.原幣別}")

        # 顯示完整的 webhook payload（使用與實際發送相同的函數）
        print(f"\n📤 Webhook Payloads (CREATE):")
        for i, entry in enumerate(result.entries, 1):
            payload = build_create_payload(entry)
            print(f"\n--- Webhook #{i} ---")
            print(json.dumps(payload, ensure_ascii=False, indent=2))

        if live_mode:
            # 實際發送 webhook（這會同時儲存到 KV）
            success_count, failure_count = send_multiple_webhooks(result.entries, user_id)
            print(f"\n✅ Webhook 結果: {success_count} 成功, {failure_count} 失敗")
        else:
            # Dry-run 模式：只儲存到 KV，不發送 webhook
            print(f"\n⏭️  DRY-RUN: 跳過 webhook 發送（使用 --live 實際發送）")
            # 模擬儲存到 KV（與 send_multiple_webhooks 相同的邏輯）
            if result.entries:
                from app.kv_store import save_last_transaction
                entries = result.entries
                item_count = len(entries)
                transaction_ids = [entry.交易ID for entry in entries]
                batch_id = entries[0].交易ID
                transaction_data = {
                    "batch_id": batch_id,
                    "transaction_ids": transaction_ids,
                    "品項": entries[-1].品項,
                    "原幣金額": entries[-1].原幣金額,
                    "付款方式": entries[-1].付款方式,
                    "分類": entries[-1].分類,
                    "日期": entries[-1].日期,
                    "item_count": item_count,
                }
                save_last_transaction(user_id, transaction_data)
            success_count = len(result.entries)
            failure_count = 0

        if success_count > 0:
            print(f"📦 已儲存到 KV (user_id: {user_id})")

            # 顯示儲存的內容
            tx = get_last_transaction(user_id)
            if tx:
                print(f"   交易ID: {tx.get('交易ID') or tx.get('batch_id')}")
                print(f"   品項: {tx.get('品項')}")

        reply = format_multi_confirmation_message(result, success_count, failure_count)
        print(f"\n💬 回覆訊息:\n{reply}")

    elif result.intent == "update_last_entry":
        print(f"\n📝 Step 2: 執行修改上一筆...")
        print(f"   要更新的欄位: {result.fields_to_update}")

        # 先讀取 KV 顯示將發送的 UPDATE payload
        tx = get_last_transaction(user_id)
        if tx:
            transaction_ids = tx.get("transaction_ids", [tx.get("交易ID")])
            print(f"\n📤 Webhook Payloads (UPDATE):")
            for i, txn_id in enumerate(transaction_ids, 1):
                payload = build_update_payload(user_id, txn_id, result.fields_to_update, item_count=1)
                print(f"\n--- Webhook #{i} (txn_id: {txn_id}) ---")
                print(json.dumps(payload, ensure_ascii=False, indent=2))

            if live_mode:
                # 呼叫實際的修改函式（會發送 webhook）
                reply = handle_update_last_entry(user_id, result.fields_to_update, raw_message=message)
            else:
                # Dry-run 模式：仍執行完整的驗證/處理流程，但 mock 掉 webhook 與 KV 刪除
                print(f"\n⏭️  DRY-RUN: 模擬執行修改上一筆（不發送 UPDATE webhook、不刪除 KV）")
                success_tuple = (len([t for t in transaction_ids if t]), 0)
                with patch('app.line_handler.send_update_webhook_batch', return_value=success_tuple), patch(
                    'app.line_handler.delete_last_transaction', return_value=True
                ):
                    reply = handle_update_last_entry(user_id, result.fields_to_update, raw_message=message)
                if reply.startswith("✅ "):
                    reply = reply.replace("✅ ", "✅ [DRY-RUN] ", 1)
        else:
            print(f"\n⚠️ KV 中無交易記錄，無法顯示 UPDATE payload")
            reply = "❌ 找不到上一筆交易記錄"

        print(f"\n💬 回覆訊息:\n{reply}")

    elif result.intent == "conversation":
        print(f"\n💬 對話回應: {result.response_text}")

    elif result.intent == "error":
        print(f"\n❌ 錯誤: {normalize_error_message(result)}")

    if show_json:
        print("\n📄 GPT 解析結果:")
        if result.intent == "multi_bookkeeping":
            data = {
                "intent": result.intent,
                "entries_count": len(result.entries),
                "entries": [
                    {"品項": e.品項, "原幣金額": e.原幣金額, "付款方式": e.付款方式, "交易ID": e.交易ID}
                    for e in result.entries
                ]
            }
        elif result.intent == "update_last_entry":
            data = {"intent": result.intent, "fields_to_update": result.fields_to_update}
        elif result.intent == "conversation":
            data = {"intent": result.intent, "response": result.response_text}
        else:
            data = {
                "intent": result.intent,
                "error": normalize_error_message(result),
                "reason": normalize_error_reason(result),
            }

        print(json.dumps(data, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    return result


def print_kv_status(user_id: str = DEFAULT_TEST_USER_ID):
    """顯示 KV 中儲存的最後一筆交易"""
    print("\n" + "=" * 60)
    print(f"📦 KV 儲存狀態 (user_id: {user_id})")
    print("=" * 60)

    if not KV_ENABLED:
        print("⚠️  KV 未啟用 (KV_ENABLED=false)")
        print("   請設定環境變數：")
        print("   export KV_ENABLED=true")
        print("   export REDIS_URL=redis://localhost:6379")
        print("=" * 60)
        return None

    try:
        transaction = get_last_transaction(user_id)

        if not transaction:
            print("📭 無儲存的交易記錄")
            print("   (記錄會在 10 分鐘後自動過期)")
        else:
            print("📬 找到儲存的交易記錄：")
            print()

            # 顯示主要欄位
            if "batch_id" in transaction:
                print(f"  🔖 批次ID：{transaction.get('batch_id')}")
            if "交易ID" in transaction:
                print(f"  🆔 交易ID：{transaction.get('交易ID')}")
            if "transaction_ids" in transaction:
                print(f"  📋 交易ID列表：{transaction.get('transaction_ids')}")

            print(f"  🛍️ 品項：{transaction.get('品項', '未知')}")
            print(f"  💰 金額：{transaction.get('原幣金額', 0)}")
            print(f"  💳 付款方式：{transaction.get('付款方式', '未知')}")
            print(f"  🏷️ 分類：{transaction.get('分類', '未知')}")
            print(f"  📅 日期：{transaction.get('日期', '未知')}")

            if transaction.get('item_count', 1) > 1:
                print(f"  📊 項目數量：{transaction.get('item_count')}")

            print()
            print("📄 完整 JSON:")
            print(json.dumps(transaction, ensure_ascii=False, indent=2))

        print("=" * 60)
        return transaction

    except Exception as e:
        print(f"❌ 讀取 KV 失敗：{e}")
        print("=" * 60)
        return None


def clear_kv(user_id: str = DEFAULT_TEST_USER_ID):
    """清除 KV 中的交易記錄"""
    if not KV_ENABLED:
        print("⚠️  KV 未啟用")
        return False

    try:
        kv_store = KVStore()
        key = f"last_transaction:{user_id}"
        if kv_store.client:
            kv_store.client.delete(key)
            print(f"✅ 已清除 KV 記錄 (user_id: {user_id})")
            return True
        else:
            print("❌ KV 連線失敗")
            return False
    except Exception as e:
        print(f"❌ 清除 KV 失敗：{e}")
        return False

def print_result(entry, show_json=False, intent_label="記帳"):
    """美化輸出測試結果（v1 單項目格式）"""
    print("\n" + "=" * 60)

    if entry.intent == "conversation":
        print(f"📝 意圖: 對話")
        print(f"💬 回應: {entry.response_text}")
    else:
        print(f"📝 意圖: {intent_label}")
        print(f"📅 日期: {entry.日期}")
        print(f"🛍️ 品項: {entry.品項}")

        # Display currency info (multi-currency)
        if entry.原幣別 != "TWD":
            twd_amount = entry.原幣金額 * entry.匯率
            print(f"💰 原幣金額: {entry.原幣金額} {entry.原幣別}")
            print(f"💱 匯率: {entry.匯率}")
            print(f"💵 新台幣: {twd_amount:.2f} TWD")
        else:
            print(f"💰 金額: {entry.原幣金額} {entry.原幣別}")

        print(f"💳 付款: {entry.付款方式}")
        print(f"🏷️ 分類: {entry.分類}")
        print(f"📊 必要性: {entry.必要性}")
        print(f"🆔 交易ID: {entry.交易ID}")
        if entry.明細說明:
            print(f"📝 明細: {entry.明細說明}")
        if entry.專案 != "日常":
            print(f"📂 專案: {entry.專案}")
        if entry.代墊狀態 != "無":
            print(f"💸 代墊: {entry.代墊狀態}")
            if entry.收款支付對象:
                print(f"👤 對象: {entry.收款支付對象}")

    if show_json:
        print("\n📄 完整 JSON:")
        if entry.intent == "bookkeeping":
            data = {
                "日期": entry.日期,
                "品項": entry.品項,
                "原幣別": entry.原幣別,
                "原幣金額": entry.原幣金額,
                "匯率": entry.匯率,
                "付款方式": entry.付款方式,
                "交易ID": entry.交易ID,
                "明細說明": entry.明細說明,
                "分類": entry.分類,
                "專案": entry.專案,
                "必要性": entry.必要性,
                "代墊狀態": entry.代墊狀態,
                "收款支付對象": entry.收款支付對象,
                "附註": entry.附註,
            }
        else:
            data = {"response": entry.response_text}
        print(json.dumps(data, ensure_ascii=False, indent=2))

    print("=" * 60)


def print_multi_result(result: MultiExpenseResult, show_json=False):
    """Pretty print result (multi-entry format)."""

    # Single item: show a compact format.
    if result.intent in ("multi_bookkeeping", "cashflow_intents") and len(result.entries) == 1:
        print("\n" + "=" * 60)
        print("📝 單項目模式")
        print("=" * 60)
        intent_label = "現金流" if result.intent == "cashflow_intents" else "記帳"
        print_result(result.entries[0], show_json, intent_label=intent_label)
        reply_preview = format_multi_confirmation_message(result, 1, 0)
        print(f"\n📩 LINE 回應預覽:\n{reply_preview}")
        return

    # Multi items or other intents: show multi-entry format.
    print("\n" + "=" * 60)

    if result.intent == "conversation":
        print(f"📝 意圖: 對話")
        print(f"💬 回應: {result.response_text}")

    elif result.intent == "error":
        print(f"📝 意圖: 錯誤")
        print(f"💬 錯誤訊息: {normalize_error_message(result)}")

    elif result.intent == "update_last_entry":
        print(f"📝 意圖: 修改上一筆")
        print(f"📋 要更新的欄位:")
        if result.fields_to_update:
            for field, value in result.fields_to_update.items():
                print(f"  • {field}: {value}")
        else:
            print(f"  (無)")

    elif result.intent in ("multi_bookkeeping", "cashflow_intents"):
        entries = result.entries
        total_items = len(entries)

        print(f"📝 意圖: {'現金流' if result.intent == 'cashflow_intents' else '記帳'}")
        print(f"📊 項目數量: {total_items}")

        if total_items > 0:
            if result.intent == "multi_bookkeeping":
                # 顯示共用資訊
                print(f"💳 共用付款方式: {entries[0].付款方式}")
                print(f"🆔 交易ID: {entries[0].交易ID}（共用）")
                print(f"📅 日期: {entries[0].日期}")
                print()
            else:
                print(f"📅 日期: {entries[0].日期}")
                print()

            # 列出所有項目
            for idx, entry in enumerate(entries, start=1):
                print(f"--- 項目 #{idx} ---")
                print(f"  🛍️ 品項: {entry.品項}")

                # Display currency info (multi-currency)
                if entry.原幣別 != "TWD":
                    twd_amount = entry.原幣金額 * entry.匯率
                    print(f"  💰 原幣金額: {entry.原幣金額} {entry.原幣別}")
                    print(f"  💱 匯率: {entry.匯率}")
                    print(f"  💵 新台幣: {twd_amount:.2f} TWD")
                else:
                    print(f"  💰 金額: {entry.原幣金額} TWD")

                if result.intent == "cashflow_intents":
                    print(f"  💳 付款方式: {entry.付款方式}")
                print(f"  🏷️ 分類: {entry.分類}")
                if entry.交易類型:
                    print(f"  🧾 交易類型: {entry.交易類型}")
                print(f"  📊 必要性: {entry.必要性}")
                if entry.明細說明:
                    print(f"  📝 明細: {entry.明細說明}")
                if entry.代墊狀態 != "無":
                    print(f"  💸 代墊: {entry.代墊狀態}")
                    if entry.收款支付對象:
                        print(f"  👤 對象: {entry.收款支付對象}")
                if idx < total_items:
                    print()

        if total_items > 0:
            reply_preview = format_multi_confirmation_message(result, total_items, 0)
            print(f"\n📩 LINE 回應預覽:\n{reply_preview}")

    if show_json:
        print("\n📄 完整 JSON:")
        if result.intent in ("multi_bookkeeping", "cashflow_intents"):
            data = {
                "intent": result.intent,
                "entries": [
                    {
                        "日期": e.日期,
                        "品項": e.品項,
                        "原幣別": e.原幣別,
                        "原幣金額": e.原幣金額,
                        "匯率": e.匯率,
                        "付款方式": e.付款方式,
                        "交易ID": e.交易ID,
                        "明細說明": e.明細說明,
                        "分類": e.分類,
                        "專案": e.專案,
                        "必要性": e.必要性,
                        "代墊狀態": e.代墊狀態,
                        "收款支付對象": e.收款支付對象,
                        "附註": e.附註,
                        "交易類型": e.交易類型,
                    }
                    for e in result.entries
                ]
            }
        elif result.intent == "conversation":
            data = {"intent": "conversation", "response": result.response_text}
        elif result.intent == "update_last_entry":
            data = {"intent": "update_last_entry", "fields_to_update": result.fields_to_update}
        else:  # error
            data = {
                "intent": "error",
                "message": normalize_error_message(result),
                "reason": normalize_error_reason(result),
            }

        print(json.dumps(data, ensure_ascii=False, indent=2))

    print("=" * 60)


def interactive_mode(test_user_id=DEFAULT_TEST_USER_ID, full_mode=False, live_mode=False):
    """互動模式 - 持續接收輸入並測試"""
    print("=" * 60)
    print("🤖 LINE Bot GPT Bookkeeper - 本地測試工具")
    print("=" * 60)
    print("\n指令:")
    print("  - 直接輸入記帳訊息進行測試")
    print("  - 'full' - 切換完整流程模式（含 webhook payload 顯示 + KV）")
    print("  - 'live' - 切換 live 模式（實際發送 webhook，謹慎使用）")
    print("  - 'json' - 切換 JSON 顯示模式")
    print("  - 'kv' - 查看 KV 中儲存的交易記錄")
    print("  - 'clear' - 清除 KV 中的交易記錄")
    print("  - 'exit' / 'quit' - 離開\n")

    show_json = False
    print(f"👤 測試用戶: {test_user_id}")
    if full_mode:
        mode_str = "🔴 完整流程 LIVE（實際發送 webhook）" if live_mode else "🟢 完整流程 DRY-RUN（不發送 webhook）"
        print(f"🔄 模式: {mode_str}")
    else:
        print(f"🔄 模式: 僅 GPT 解析")
    if KV_ENABLED:
        print(f"📦 KV 狀態: 已啟用")
    else:
        print(f"📦 KV 狀態: 未啟用 (設定 KV_ENABLED=true 啟用)")
    print()

    while True:
        try:
            if full_mode:
                prompt = "🔴 " if live_mode else "🟢 "
            else:
                prompt = "💬 "
            user_input = input(f"{prompt}輸入訊息: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 再見！")
                break

            if user_input.lower() == 'full':
                full_mode = not full_mode
                if full_mode:
                    mode_str = "LIVE（實際發送 webhook）" if live_mode else "DRY-RUN（不發送 webhook）"
                    print(f"✅ 已切換到完整流程模式 [{mode_str}]")
                else:
                    print("✅ 已切換到僅 GPT 解析模式")
                continue

            if user_input.lower() == 'live':
                live_mode = not live_mode
                if live_mode:
                    print("⚠️  已啟用 LIVE 模式（將實際發送 webhook，請謹慎使用）")
                else:
                    print("✅ 已切換到 DRY-RUN 模式（不發送 webhook）")
                continue

            if user_input.lower() == 'json':
                show_json = not show_json
                status = "開啟" if show_json else "關閉"
                print(f"✅ JSON 顯示模式已{status}")
                continue

            if user_input.lower() == 'kv':
                print_kv_status(test_user_id)
                continue

            if user_input.lower() == 'clear':
                clear_kv(test_user_id)
                continue

            # 測試處理訊息
            try:
                if full_mode:
                    # 完整流程模式
                    simulate_full_flow(
                        user_input,
                        test_user_id,
                        show_json,
                        live_mode,
                        debug=args.debug,
                        use_parser=args.parser,
                    )
                else:
                    if args.parser:
                        from app.processor import process_with_parser

                        result = process_with_parser(user_input)
                    else:
                        result = process_multi_expense(user_input, debug=args.debug)
                    print_multi_result(result, show_json)
            except Exception as e:
                print(f"\n❌ 錯誤: {str(e)}\n")
                import traceback
                traceback.print_exc()

        except KeyboardInterrupt:
            print("\n\n👋 再見！")
            break
        except EOFError:
            print("\n\n👋 再見！")
            break


def single_test(
    message,
    full_mode=False,
    test_user_id=DEFAULT_TEST_USER_ID,
    live_mode=False,
    debug: bool = False,
    use_parser: bool = False,
):
    """單次測試模式"""
    if full_mode:
        print(f"\n🧪 測試訊息: {message}")
        mode_str = "🔴 LIVE（實際發送 webhook）" if live_mode else "🟢 DRY-RUN（不發送 webhook）"
        print(f"🔄 模式: 完整流程 [{mode_str}]")
        print(f"👤 用戶: {test_user_id}\n")
        try:
            simulate_full_flow(
                message,
                test_user_id,
                show_json=True,
                live_mode=live_mode,
                debug=debug,
                use_parser=use_parser,
            )
        except Exception as e:
            print(f"\n❌ 錯誤: {str(e)}\n")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        return

    print(f"\n🧪 測試訊息: {message}")
    print("")

    try:
        if use_parser:
            from app.processor import process_with_parser

            result = process_with_parser(message)
        else:
            result = process_multi_expense(message, debug=debug)
        print_multi_result(result, show_json=True)
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.INFO)
    if args.raw:
        logging.disable(logging.CRITICAL)

    full_mode = args.full
    live_mode = args.live  # Default is DRY-RUN (no webhook sending)
    test_user_id = args.user

    if args.clear:
        clear_kv(test_user_id)
        if not args.kv and not args.message:
            raise SystemExit(0)

    if args.kv:
        print_kv_status(test_user_id)
        if not args.message:
            raise SystemExit(0)

    if args.message:
        message = " ".join(args.message)
        if args.raw:
            if full_mode:
                print("--raw cannot be used with --full.", file=sys.stderr)
                raise SystemExit(2)
            raise SystemExit(single_test_raw(message, debug=args.debug))
        single_test(message, full_mode, test_user_id, live_mode, debug=args.debug, use_parser=args.parser)
    else:
        if args.raw:
            print("--raw requires a message argument.", file=sys.stderr)
            raise SystemExit(2)
        interactive_mode(test_user_id, full_mode, live_mode)
