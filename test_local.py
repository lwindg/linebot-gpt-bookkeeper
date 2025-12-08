#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地測試工具 - 直接測試 GPT 解析功能（v1 & v1.5.0 & v003-multi-currency）

使用方式：
  python test_local.py                      # 互動模式（推薦，預設 v1.5.0）
  python test_local.py --v1                 # 互動模式（v1 單項目模式）
  python test_local.py '早餐80元，午餐150元，現金'  # 單次測試

KV 儲存操作：
  python test_local.py --kv                 # 查看 KV 中儲存的交易記錄
  python test_local.py --clear              # 清除 KV 中的交易記錄
  python test_local.py --user=U123456 --kv  # 指定用戶 ID 查看 KV

互動模式指令：
  - 直接輸入記帳訊息進行測試
  - 'v1' / 'v1.5' - 切換測試版本
  - 'json' - 切換 JSON 顯示
  - 'kv' - 查看 KV 中儲存的交易記錄
  - 'clear' - 清除 KV 中的交易記錄
  - 'exit' / 'quit' - 離開

版本差異：
  - v1: 單項目記帳（process_message）
  - v1.5.0: 多項目記帳（process_multi_expense）- 預設
  - v003-multi-currency: 多幣別記帳（已整合至 v1.5.0）

外幣消費測試案例（v003-multi-currency）：
  python test_local.py 'WSJ 4.99美元 大戶'
  python test_local.py 'Netflix 15.99USD 信用卡'
  python test_local.py '飯店住宿 290.97歐元 信用卡'
  python test_local.py '便當 80 現金' # TWD (default)
  python test_local.py '咖啡 10美金 現金' # 測試同義詞
"""

import sys
import json
from app.gpt_processor import process_message, process_multi_expense, MultiExpenseResult, BookkeepingEntry
from app.kv_store import get_last_transaction, KVStore
from app.config import KV_ENABLED

# Default test user ID for local testing
DEFAULT_TEST_USER_ID = "test_local_user"


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

def print_result(entry, show_json=False):
    """美化輸出測試結果（v1 單項目格式）"""
    print("\n" + "=" * 60)

    if entry.intent == "conversation":
        print(f"📝 意圖: 對話")
        print(f"💬 回應: {entry.response_text}")
    else:
        print(f"📝 意圖: 記帳")
        print(f"📅 日期: {entry.日期}")
        print(f"🛍️ 品項: {entry.品項}")

        # Display currency info (v003-multi-currency)
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
    """美化輸出測試結果（v1.5.0 多項目格式）"""

    # 單項目：使用 v1 格式（向後相容）
    if result.intent == "multi_bookkeeping" and len(result.entries) == 1:
        print("\n" + "=" * 60)
        print("📝 v1.5.0 單項目模式（向後相容 v1 格式）")
        print("=" * 60)
        print_result(result.entries[0], show_json)
        return

    # 多項目或其他 intent：使用 v1.5.0 格式
    print("\n" + "=" * 60)

    if result.intent == "conversation":
        print(f"📝 意圖: 對話")
        print(f"💬 回應: {result.response_text}")

    elif result.intent == "error":
        print(f"📝 意圖: 錯誤")
        print(f"💬 錯誤訊息: {result.error_message}")

    elif result.intent == "update_last_entry":
        print(f"📝 意圖: 修改上一筆")
        print(f"📋 要更新的欄位:")
        if result.fields_to_update:
            for field, value in result.fields_to_update.items():
                print(f"  • {field}: {value}")
        else:
            print(f"  (無)")

    elif result.intent == "multi_bookkeeping":
        entries = result.entries
        total_items = len(entries)

        print(f"📝 意圖: 記帳")
        print(f"📊 項目數量: {total_items}")

        if total_items > 0:
            # 顯示共用資訊
            print(f"💳 共用付款方式: {entries[0].付款方式}")
            print(f"🆔 交易ID: {entries[0].交易ID}（共用）")
            print(f"📅 日期: {entries[0].日期}")
            print()

            # 列出所有項目
            for idx, entry in enumerate(entries, start=1):
                print(f"--- 項目 #{idx} ---")
                print(f"  🛍️ 品項: {entry.品項}")

                # Display currency info (v003-multi-currency)
                if entry.原幣別 != "TWD":
                    twd_amount = entry.原幣金額 * entry.匯率
                    print(f"  💰 原幣金額: {entry.原幣金額} {entry.原幣別}")
                    print(f"  💱 匯率: {entry.匯率}")
                    print(f"  💵 新台幣: {twd_amount:.2f} TWD")
                else:
                    print(f"  💰 金額: {entry.原幣金額} TWD")

                print(f"  🏷️ 分類: {entry.分類}")
                print(f"  📊 必要性: {entry.必要性}")
                if entry.明細說明:
                    print(f"  📝 明細: {entry.明細說明}")
                if entry.代墊狀態 != "無":
                    print(f"  💸 代墊: {entry.代墊狀態}")
                    if entry.收款支付對象:
                        print(f"  👤 對象: {entry.收款支付對象}")
                if idx < total_items:
                    print()

    if show_json:
        print("\n📄 完整 JSON:")
        if result.intent == "multi_bookkeeping":
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
                    }
                    for e in result.entries
                ]
            }
        elif result.intent == "conversation":
            data = {"intent": "conversation", "response": result.response_text}
        elif result.intent == "update_last_entry":
            data = {"intent": "update_last_entry", "fields_to_update": result.fields_to_update}
        else:  # error
            data = {"intent": "error", "message": result.error_message}

        print(json.dumps(data, ensure_ascii=False, indent=2))

    print("=" * 60)


def interactive_mode(use_v1=False, test_user_id=DEFAULT_TEST_USER_ID):
    """互動模式 - 持續接收輸入並測試"""
    print("=" * 60)
    print("🤖 LINE Bot GPT Bookkeeper - 本地測試工具")
    print("=" * 60)
    print("\n指令:")
    print("  - 直接輸入記帳訊息進行測試")
    print("  - 'v1' - 切換到 v1 模式（單項目）")
    print("  - 'v1.5' - 切換到 v1.5.0 模式（多項目）")
    print("  - 'json' - 切換 JSON 顯示模式")
    print("  - 'kv' - 查看 KV 中儲存的交易記錄")
    print("  - 'clear' - 清除 KV 中的交易記錄")
    print("  - 'exit' / 'quit' - 離開")
    print("  - Ctrl+C - 離開\n")

    show_json = False
    version = "v1" if use_v1 else "v1.5.0"

    print(f"🔖 當前版本: {version}")
    print(f"👤 測試用戶: {test_user_id}")
    if KV_ENABLED:
        print(f"📦 KV 狀態: 已啟用")
    else:
        print(f"📦 KV 狀態: 未啟用 (設定 KV_ENABLED=true 啟用)")
    print()

    while True:
        try:
            user_input = input("💬 輸入訊息: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 再見！")
                break

            if user_input.lower() == 'json':
                show_json = not show_json
                status = "開啟" if show_json else "關閉"
                print(f"✅ JSON 顯示模式已{status}")
                continue

            if user_input.lower() == 'v1':
                version = "v1"
                print(f"✅ 已切換到 v1 模式（單項目記帳）")
                continue

            if user_input.lower() in ['v1.5', 'v15']:
                version = "v1.5.0"
                print(f"✅ 已切換到 v1.5.0 模式（多項目記帳）")
                continue

            if user_input.lower() == 'kv':
                print_kv_status(test_user_id)
                continue

            if user_input.lower() == 'clear':
                clear_kv(test_user_id)
                continue

            # 測試處理訊息
            try:
                if version == "v1":
                    result = process_message(user_input)
                    print_result(result, show_json)
                else:  # v1.5.0
                    result = process_multi_expense(user_input)
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


def single_test(message, use_v1=False):
    """單次測試模式"""
    version = "v1" if use_v1 else "v1.5.0"
    print(f"\n🧪 測試訊息: {message}")
    print(f"🔖 版本: {version}\n")

    try:
        if use_v1:
            result = process_message(message)
            print_result(result, show_json=True)
        else:
            result = process_multi_expense(message)
            print_multi_result(result, show_json=True)
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    use_v1 = False
    test_user_id = DEFAULT_TEST_USER_ID
    show_kv = False
    do_clear = False

    # 解析參數
    args = sys.argv[1:]

    # 檢查是否有 --v1 參數
    if '--v1' in args:
        use_v1 = True
        args.remove('--v1')

    # 檢查是否有 --kv 參數（顯示 KV 內容）
    if '--kv' in args:
        show_kv = True
        args.remove('--kv')

    # 檢查是否有 --clear 參數（清除 KV）
    if '--clear' in args:
        do_clear = True
        args.remove('--clear')

    # 檢查是否有 --user 參數（指定測試用戶 ID）
    for i, arg in enumerate(args):
        if arg.startswith('--user='):
            test_user_id = arg.split('=', 1)[1]
            args.remove(arg)
            break
        elif arg == '--user' and i + 1 < len(args):
            test_user_id = args[i + 1]
            args.remove('--user')
            args.remove(test_user_id)
            break

    # 執行 KV 操作
    if do_clear:
        clear_kv(test_user_id)
        if not show_kv and len(args) == 0:
            sys.exit(0)

    if show_kv:
        print_kv_status(test_user_id)
        if len(args) == 0:
            sys.exit(0)

    if len(args) > 0:
        # 單次測試模式
        message = " ".join(args)
        single_test(message, use_v1)
    else:
        # 互動模式
        interactive_mode(use_v1, test_user_id)
