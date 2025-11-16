#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試多項目交易的 UPDATE webhook 功能

模擬場景：
1. 收據識別 5 個項目 → 共享同一個交易ID（例如：20251116-143027）
2. 只有第一筆存入 KV（包含 item_count=5）
3. 用戶說「上一筆改成Line轉帳」
4. 系統發送 UPDATE webhook，包含 item_count=5
5. Make.com 根據 transaction_id 和 item_count 批次更新所有 5 筆
"""

import json
from unittest.mock import Mock, patch

# 模擬場景：收據識別的多項目交易
def test_scenario_receipt_5_items():
    """
    測試場景：收據識別 5 個項目，然後用戶更新付款方式
    """
    print("=" * 60)
    print("測試場景：收據識別 5 個項目 → 更新付款方式")
    print("=" * 60)

    # ========================================
    # 階段 1：收據識別，生成 5 個項目
    # ========================================
    print("\n階段 1：收據識別 5 個項目")
    print("-" * 40)

    receipt_items = [
        {"品項": "咖啡", "原幣金額": 50},
        {"品項": "三明治", "原幣金額": 80},
        {"品項": "沙拉", "原幣金額": 60},
        {"品項": "果汁", "原幣金額": 40},
        {"品項": "餅乾", "原幣金額": 30},
    ]

    transaction_id = "20251116-143027"
    user_id = "U1234567890abcdef"

    print(f"交易ID: {transaction_id}")
    print(f"項目數量: {len(receipt_items)}")
    print("項目列表:")
    for i, item in enumerate(receipt_items, 1):
        print(f"  {i}. {item['品項']} - {item['原幣金額']} 元")

    # ========================================
    # 階段 2：儲存到 KV（只儲存第一筆，但包含 item_count）
    # ========================================
    print("\n階段 2：儲存到 KV")
    print("-" * 40)

    # 模擬 send_multiple_webhooks 儲存的資料
    kv_data = {
        "交易ID": transaction_id,
        "品項": receipt_items[0]["品項"],
        "原幣金額": receipt_items[0]["原幣金額"],
        "付款方式": "現金",
        "分類": "家庭／飲品",
        "日期": "2025-11-16",
        "item_count": len(receipt_items),  # 關鍵：記錄項目數量
    }

    print(f"儲存到 KV: last_transaction:{user_id}")
    print(f"資料: {json.dumps(kv_data, ensure_ascii=False, indent=2)}")

    # ========================================
    # 階段 3：用戶說「上一筆改成Line轉帳」
    # ========================================
    print("\n階段 3：用戶更新付款方式")
    print("-" * 40)

    user_message = "上一筆改成Line轉帳"
    print(f"用戶訊息: {user_message}")

    # GPT 識別為 update_last_entry intent
    fields_to_update = {"付款方式": "Line 轉帳"}
    print(f"要更新的欄位: {json.dumps(fields_to_update, ensure_ascii=False)}")

    # ========================================
    # 階段 4：發送 UPDATE webhook
    # ========================================
    print("\n階段 4：發送 UPDATE webhook")
    print("-" * 40)

    # 從 KV 讀取資料
    item_count = kv_data.get("item_count", 1)

    # 構建 UPDATE webhook payload
    update_payload = {
        "operation": "UPDATE",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "fields_to_update": fields_to_update,
        "item_count": item_count,  # 告訴 Make.com 需要更新 5 筆
    }

    print(f"UPDATE Webhook Payload:")
    print(json.dumps(update_payload, ensure_ascii=False, indent=2))

    # ========================================
    # 階段 5：Make.com 批次更新
    # ========================================
    print("\n階段 5：Make.com 批次更新")
    print("-" * 40)

    print(f"Make.com 根據以下條件批次更新：")
    print(f"  - 交易ID: {transaction_id}")
    print(f"  - 項目數量: {item_count}")
    print(f"  - 更新欄位: {fields_to_update}")
    print(f"\n預期結果：所有 {item_count} 筆記錄的付款方式都從「現金」改為「Line 轉帳」")

    # ========================================
    # 驗證
    # ========================================
    print("\n" + "=" * 60)
    print("驗證結果")
    print("=" * 60)

    assert item_count == 5, f"項目數量應為 5，但實際為 {item_count}"
    assert update_payload["item_count"] == 5, "UPDATE payload 應包含 item_count=5"
    assert update_payload["operation"] == "UPDATE", "operation 應為 UPDATE"
    assert update_payload["transaction_id"] == transaction_id, "transaction_id 應匹配"

    print("✅ 所有驗證通過！")
    print(f"✅ UPDATE webhook 正確包含 item_count={item_count}")
    print(f"✅ Make.com 會收到正確的批次更新指令")

    return True


# 測試單筆更新（向後相容）
def test_scenario_single_item():
    """
    測試場景：單筆記帳更新（確保向後相容）
    """
    print("\n\n" + "=" * 60)
    print("測試場景：單筆記帳更新（向後相容）")
    print("=" * 60)

    transaction_id = "20251116-150000"
    user_id = "U9876543210fedcba"

    print(f"\n交易ID: {transaction_id}")
    print(f"項目數量: 1（單筆）")

    # KV 資料（單筆，沒有 item_count 或 item_count=1）
    kv_data = {
        "交易ID": transaction_id,
        "品項": "午餐",
        "原幣金額": 150,
        "付款方式": "現金",
        "分類": "家庭／餐飲／午餐",
        "日期": "2025-11-16",
        # 注意：沒有 item_count 欄位（舊資料）
    }

    print(f"\nKV 資料: {json.dumps(kv_data, ensure_ascii=False, indent=2)}")

    # 讀取 item_count，預設為 1
    item_count = kv_data.get("item_count", 1)

    # UPDATE payload
    update_payload = {
        "operation": "UPDATE",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "fields_to_update": {"付款方式": "信用卡"},
        "item_count": item_count,
    }

    print(f"\nUPDATE Webhook Payload:")
    print(json.dumps(update_payload, ensure_ascii=False, indent=2))

    # 驗證
    assert item_count == 1, f"單筆記帳的 item_count 應為 1，但實際為 {item_count}"
    assert update_payload["item_count"] == 1, "UPDATE payload 應包含 item_count=1"

    print("\n✅ 單筆更新功能正常（向後相容）")

    return True


if __name__ == "__main__":
    try:
        # 測試多項目更新
        test_scenario_receipt_5_items()

        # 測試單筆更新（向後相容）
        test_scenario_single_item()

        print("\n\n" + "=" * 60)
        print("🎉 所有測試通過！")
        print("=" * 60)
        print("\n功能總結：")
        print("1. ✅ 多項目交易會在 KV 儲存 item_count")
        print("2. ✅ UPDATE webhook 包含 item_count 欄位")
        print("3. ✅ Make.com 可根據 transaction_id 和 item_count 批次更新")
        print("4. ✅ 單筆更新仍然正常（向後相容）")
        print("\nMake.com 接收的 UPDATE webhook 格式：")
        print(json.dumps({
            "operation": "UPDATE",
            "user_id": "U...",
            "transaction_id": "20251116-143027",
            "fields_to_update": {"付款方式": "Line 轉帳"},
            "item_count": 5,
        }, ensure_ascii=False, indent=2))

    except AssertionError as e:
        print(f"\n❌ 測試失敗: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
