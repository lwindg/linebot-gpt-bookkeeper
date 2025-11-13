#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地測試工具 - 直接測試 GPT 解析功能

使用方式：
  python test_local.py                      # 互動模式（推薦）
  python test_local.py '午餐$120現金'       # 單次測試（使用單引號）
  python test_local.py "午餐\\$120現金"     # 單次測試（使用雙引號需跳脫 $）

注意：
  - 單次測試模式中，如果訊息包含 $ 符號，請使用單引號 '...'
  - 或使用雙引號但需跳脫：\\$
  - 推薦使用互動模式以避免 shell 特殊字元問題
"""

import sys
import json
from app.gpt_processor import process_message

def print_result(entry, show_json=False):
    """美化輸出測試結果"""
    print("\n" + "=" * 60)

    if entry.intent == "conversation":
        print(f"📝 意圖: 對話")
        print(f"💬 回應: {entry.response_text}")
    else:
        print(f"📝 意圖: 記帳")
        print(f"📅 日期: {entry.日期}")
        if entry.時間:
            print(f"🕐 時間: {entry.時間}")
        print(f"🛍️  品項: {entry.品項}")
        print(f"💰 金額: {entry.原幣別} {entry.原幣金額}")
        print(f"💳 付款: {entry.付款方式}")
        print(f"🏷️  分類: {entry.分類}")
        print(f"📊 必要性: {entry.必要性}")
        print(f"🆔 交易ID: {entry.交易ID}")
        if entry.明細說明:
            print(f"📝 明細: {entry.明細說明}")
        if entry.專案 != "日常":
            print(f"📂 專案: {entry.專案}")
        if entry.代墊狀態 != "無":
            print(f"💸 代墊: {entry.代墊狀態}")

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


def interactive_mode():
    """互動模式 - 持續接收輸入並測試"""
    print("=" * 60)
    print("🤖 LINE Bot GPT Bookkeeper - 本地測試工具")
    print("=" * 60)
    print("\n指令:")
    print("  - 直接輸入記帳訊息進行測試")
    print("  - 輸入 'json' 切換 JSON 顯示模式")
    print("  - 輸入 'exit' 或 'quit' 離開")
    print("  - 按 Ctrl+C 離開\n")

    show_json = False

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

            # 測試處理訊息
            try:
                result = process_message(user_input)
                print_result(result, show_json)
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


def single_test(message):
    """單次測試模式"""
    print(f"\n🧪 測試訊息: {message}")
    try:
        result = process_message(message)
        print_result(result, show_json=True)
    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 單次測試模式
        message = " ".join(sys.argv[1:])
        single_test(message)
    else:
        # 互動模式
        interactive_mode()
