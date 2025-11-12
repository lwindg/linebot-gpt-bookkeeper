#!/usr/bin/env python3
"""
簡單測試腳本 - 測試 GPT 處理器

這個腳本可以獨立測試 GPT 意圖識別功能，不需要 LINE Bot。
"""

import sys
import os

# 將專案根目錄加入 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gpt_processor import process_message


def test_bookkeeping_messages():
    """測試記帳訊息"""
    print("=" * 60)
    print("測試 1: 記帳訊息（完整資訊）")
    print("=" * 60)

    test_cases = [
        "午餐 120 現金",
        "200 點心 狗卡",
        "早餐 50 Line轉帳",
        "晚餐 300 聯邦綠卡"
    ]

    for msg in test_cases:
        print(f"\n輸入: {msg}")
        try:
            result = process_message(msg)
            print(f"意圖: {result.intent}")

            if result.intent == "bookkeeping":
                print(f"品項: {result.品項}")
                print(f"金額: {result.原幣金額}")
                print(f"付款方式: {result.付款方式}")
                print(f"分類: {result.分類}")
                print(f"必要性: {result.必要性}")
                print(f"交易ID: {result.交易ID}")
                print(f"✅ 成功")
            else:
                print(f"⚠️ 意圖錯誤: 應該是 bookkeeping")

        except Exception as e:
            print(f"❌ 錯誤: {e}")


def test_conversation_messages():
    """測試一般對話訊息"""
    print("\n" + "=" * 60)
    print("測試 2: 一般對話訊息")
    print("=" * 60)

    test_cases = [
        "你好",
        "怎麼記帳？",
        "今天天氣如何？"
    ]

    for msg in test_cases:
        print(f"\n輸入: {msg}")
        try:
            result = process_message(msg)
            print(f"意圖: {result.intent}")

            if result.intent == "conversation":
                print(f"回應: {result.response_text}")
                print(f"✅ 成功")
            else:
                print(f"⚠️ 意圖錯誤: 應該是 conversation")

        except Exception as e:
            print(f"❌ 錯誤: {e}")


def test_incomplete_messages():
    """測試不完整訊息"""
    print("\n" + "=" * 60)
    print("測試 3: 不完整訊息（缺少必要資訊）")
    print("=" * 60)

    test_cases = [
        "午餐 120",  # 缺付款方式
        "現金 50",   # 缺品項
        "午餐 現金"  # 缺金額
    ]

    for msg in test_cases:
        print(f"\n輸入: {msg}")
        try:
            result = process_message(msg)
            print(f"意圖: {result.intent}")

            if result.intent == "conversation":
                print(f"回應: {result.response_text}")
                print(f"✅ 正確處理（應提示缺少資訊）")
            else:
                print(f"⚠️ 應該回傳 conversation 提示缺少資訊")

        except Exception as e:
            print(f"❌ 錯誤: {e}")


def main():
    """主測試函式"""
    print("\n🧪 開始 GPT 處理器測試\n")
    print("請確保已設定 .env 檔案，包含 OPENAI_API_KEY\n")

    try:
        # 測試 1: 記帳訊息
        test_bookkeeping_messages()

        # 測試 2: 一般對話
        test_conversation_messages()

        # 測試 3: 不完整訊息
        test_incomplete_messages()

        print("\n" + "=" * 60)
        print("✅ 所有測試完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 測試過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
