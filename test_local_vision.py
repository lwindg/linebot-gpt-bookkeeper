#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地圖片識別測試腳本

用途：在本地測試 GPT-4 Vision API 收據識別功能，不需要透過 LINE

使用方式：
    python test_local_vision.py <圖片路徑>
    python test_local_vision.py --fixture <json> [--raw] [--skip-gpt]

範例：
    python test_local_vision.py receipt.jpg
    python test_local_vision.py ~/Downloads/receipt.png
    python test_local_vision.py --fixture tests/functional/fixtures/image_receipt_tc001.json --raw --skip-gpt
"""

import sys
import os
from pathlib import Path

# 將專案根目錄加入 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.image_handler import (
    process_receipt_image,
    ReceiptItem,
    compress_image,
    build_image_authoritative_envelope,
)
from app.gpt_processor import process_receipt_data, process_multi_expense
from app.pipeline.image_flow import process_image_envelope
from openai import OpenAI
from app.config import OPENAI_API_KEY
from app.services.kv_store import save_last_transaction, KV_ENABLED
from app.line_handler import handle_update_last_entry


def save_compressed_image(compressed_data: bytes, original_path: str) -> str:
    """儲存壓縮後的圖片供人眼確認"""
    # 產生輸出檔名
    path_obj = Path(original_path)
    output_path = path_obj.parent / f"{path_obj.stem}_compressed.jpg"

    # 儲存檔案
    with open(output_path, 'wb') as f:
        f.write(compressed_data)

    return str(output_path)


def load_image_from_file(image_path: str) -> bytes:
    """從檔案載入圖片"""
    with open(image_path, 'rb') as f:
        return f.read()


def main():
    """主函式"""
    # 檢查參數
    if len(sys.argv) < 2:
        print("❌ 使用方式: python test_local_vision.py <圖片路徑> [--no-compress] [--user-id <id>] [--update <訊息>] [--raw] [--skip-gpt]")
        print("   或: python test_local_vision.py --fixture <json> [--raw] [--skip-gpt]")
        print("\n範例:")
        print("  python test_local_vision.py receipt.jpg")
        print("  python test_local_vision.py ~/Downloads/receipt.png")
        print("  python test_local_vision.py receipt.jpg --no-compress  # 測試不壓縮")
        print("  python test_local_vision.py receipt.jpg --user-id U123 --update \"上一筆付款方式改為富邦\"")
        print("  python test_local_vision.py --fixture tests/functional/fixtures/image_receipt_tc001.json --raw --skip-gpt")
        sys.exit(1)

    image_path = None
    enable_compression = True
    user_id = None
    update_message = None
    fixture_path = None
    raw_mode = False
    skip_gpt = False

    args = sys.argv[1:]
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--no-compress":
            enable_compression = False
        elif arg == "--raw":
            raw_mode = True
        elif arg == "--skip-gpt":
            skip_gpt = True
        elif arg == "--fixture":
            if idx + 1 >= len(args):
                print("❌ 缺少參數值: --fixture")
                sys.exit(1)
            fixture_path = args[idx + 1]
            idx += 1
        elif arg in ("--user-id", "--update"):
            if idx + 1 >= len(args):
                print(f"❌ 缺少參數值: {arg}")
                sys.exit(1)
            value = args[idx + 1]
            if arg == "--user-id":
                user_id = value
            else:
                update_message = value
            idx += 1
        elif arg.startswith("--user-id="):
            user_id = arg.split("=", 1)[1]
        elif arg.startswith("--update="):
            update_message = arg.split("=", 1)[1]
        elif image_path is None:
            image_path = arg
        else:
            print(f"⚠️  忽略未知參數: {arg}")
        idx += 1

    raw_stdout = None
    if raw_mode:
        raw_stdout = sys.stdout
        sys.stdout = sys.stderr

    if not image_path and not fixture_path:
        print("❌ 請提供圖片路徑或 fixture")
        sys.exit(1)

    image_data = None
    if image_path:
        # 檢查檔案是否存在
        if not os.path.exists(image_path):
            print(f"❌ 圖片檔案不存在: {image_path}")
            sys.exit(1)

        print(f"📸 讀取圖片: {image_path}")

        # 載入圖片
        try:
            image_data = load_image_from_file(image_path)
            image_size_mb = len(image_data) / (1024 * 1024)
            print(f"✅ 圖片載入成功 ({image_size_mb:.2f} MB)")
        except Exception as e:
            print(f"❌ 圖片載入失敗: {e}")
            sys.exit(1)

        # 檢查圖片大小
        if len(image_data) > 10 * 1024 * 1024:
            print("⚠️  圖片過大（超過 10MB），可能導致處理失敗")

        # 壓縮圖片並儲存供人眼確認（僅在啟用壓縮時）
        if enable_compression:
            print("\n🗜️  壓縮圖片...")
            compressed_data = compress_image(image_data)
            compressed_size_mb = len(compressed_data) / (1024 * 1024)
            compression_ratio = (1 - len(compressed_data) / len(image_data)) * 100

            print(f"   原始大小: {image_size_mb:.2f} MB")
            print(f"   壓縮後大小: {compressed_size_mb:.2f} MB")
            print(f"   壓縮率: {compression_ratio:.1f}%")

            # 儲存壓縮後的圖片
            compressed_path = save_compressed_image(compressed_data, image_path)
            print(f"✅ 壓縮後圖片已儲存: {compressed_path}")
            print(f"   請用圖片查看器打開確認品質是否足以辨識")
        else:
            print("\n⚠️  壓縮已停用，將使用原圖測試")

        # 初始化 OpenAI client
        print("\n🤖 初始化 OpenAI client...")
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 處理圖片
        if enable_compression:
            print("🔍 開始分析收據...\n")
            print("   ℹ️  注意：process_receipt_image 會壓縮圖片")
            print("   ℹ️  你可以對比儲存的 _compressed.jpg 與實際發送給 API 的壓縮版本\n")
        else:
            print("🔍 開始分析收據（使用原圖，不壓縮）...\n")

    try:
        # 為了診斷，我們需要看到原始的 Vision API 回應
        from app.services.image_handler import encode_image_base64, ReceiptItem
        from app.gpt.prompts import RECEIPT_VISION_PROMPT
        from app.config import GPT_VISION_MODEL

        if fixture_path:
            if not os.path.exists(fixture_path):
                print(f"❌ Fixture 檔案不存在: {fixture_path}")
                sys.exit(1)
            print(f"🧪 使用 fixture: {fixture_path}")
            with open(fixture_path, "r", encoding="utf-8") as f:
                response_text = f.read()
        else:
            # 準備圖片（compress_image 已在頂部 import）
            if enable_compression:
                compressed_image = compress_image(image_data)
            else:
                compressed_image = image_data

            base64_image = encode_image_base64(compressed_image)

            # 直接呼叫 Vision API 並顯示原始回應
            print("🔍 呼叫 Vision API...")
            response = client.chat.completions.create(
                model=GPT_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": RECEIPT_VISION_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,  # 提高 token 上限以支援更複雜的收據
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content

        # 顯示原始 API 回應
        print("\n" + "=" * 60)
        print("📋 Vision API 原始回應:")
        print("=" * 60)
        print(response_text)
        print("=" * 60 + "\n")

        # 解析回應（避免重複調用 Vision API）
        import json
        result = json.loads(response_text)
        status = result.get("status")

        if status == "success":
            # 成功識別收據
            items_data = result.get("items", [])
            payment_method = result.get("payment_method")

            # 轉換為 ReceiptItem 列表
            fallback_date = result.get("date")  # 最外層日期作為 fallback
            fallback_time = result.get("time")  # 最外層時間作為 fallback
            receipt_items = []
            for item in items_data:
                # 提取項目日期/時間，若無則使用 fallback
                item_date = item.get("日期") or fallback_date
                item_time = item.get("時間") or fallback_time
                item_currency = item.get("幣別") or result.get("currency", "TWD")

                receipt_items.append(ReceiptItem(
                    品項=item["品項"],
                    原幣金額=float(item["金額"]),
                    原幣別=item_currency,
                    付款方式=payment_method,
                    日期=item_date,  # Vision API 提供的日期（可選）
                    時間=item_time,  # Vision API 提供的時間（可選）
                    原文=item.get("原文")
                ))

            error_code = None
            error_message = None

        elif status in ["not_receipt", "unsupported_currency", "unclear", "incomplete"]:
            # 錯誤情況
            receipt_items = []
            error_code = status
            error_message = result.get("message", "無法處理收據")

        else:
            # 未知狀態
            receipt_items = []
            error_code = "api_error"
            error_message = f"無法處理收據（狀態：{status}）"

        # 顯示結果
        print("=" * 60)

        if error_code:
            # 識別失敗
            print(f"❌ 識別失敗")
            print(f"錯誤代碼: {error_code}")
            print(f"錯誤訊息: {error_message}")

            # 提供建議
            print("\n💡 建議:")
            if error_code == "not_receipt":
                print("  - 請確認圖片是否為收據或發票")
            elif error_code == "unsupported_currency":
                print("  - 不支援的幣別")
            elif error_code == "unclear":
                print("  - 請重新拍攝更清晰的圖片")
                print("  - 確保收據上的文字清楚可見")
            elif error_code == "incomplete":
                print("  - 請確認收據上有品項和金額資訊")

        else:
            # 識別成功
            print(f"✅ 識別成功！共 {len(receipt_items)} 個項目\n")

            # 轉換為記帳資料
            if skip_gpt:
                image_envelope = build_image_authoritative_envelope(receipt_items)
                result = process_image_envelope(image_envelope, skip_gpt=True)
            else:
                result = process_receipt_data(receipt_items)

            if result.intent == "multi_bookkeeping":
                entries = result.entries
                total_items = len(entries)

                # 使用統一的多項目格式顯示
                print(f"✅ 記帳成功！已記錄 {total_items} 個項目：\n")

                # 檢查是否所有項目的日期相同
                all_dates = [entry.日期 for entry in entries]
                dates_differ = len(set(all_dates)) > 1

                # 列出所有項目
                for idx, entry in enumerate(entries, start=1):
                    twd_amount = entry.原幣金額 * entry.匯率

                    print(f"📋 #{idx} {entry.品項}")
                    print(f"💰 {twd_amount:.0f} 元")
                    print(f"📂 {entry.分類}")

                    # 只有當日期不同時才顯示每個項目的日期
                    if dates_differ:
                        print(f"📅 日期：{entry.日期}")

                    print(f"🔖 交易ID：{entry.交易ID}")
                    print(f"⭐ {entry.必要性}")

                    if entry.明細說明:
                        print(f"📝 {entry.明細說明}")

                    # 項目之間加空行（除了最後一個）
                    if idx < total_items:
                        print()

                # 顯示共用資訊
                print(f"\n💳 付款方式：{entries[0].付款方式}")

                # 如果所有項目日期相同，在這裡統一顯示
                if not dates_differ:
                    print(f"📅 日期：{entries[0].日期}")

                # 如果有警告訊息（例如付款方式預設為現金）
                if result.response_text:
                    print(f"\n{result.response_text}")

                # ========================================
                # KV 儲存（用於「修改上一筆」功能）
                # ========================================
                print("\n" + "=" * 60)
                print("🗄️  KV 儲存（用於「修改上一筆」功能）")
                print("=" * 60)

                # 提取批次ID和交易ID列表
                transaction_ids = [entry.交易ID for entry in entries]

                # v1.9.0: 從附註中提取批次時間戳
                import re
                if total_items > 1 and entries[0].附註:
                    match = re.search(r'批次[ID]*[:：]\s*(\d{8}-\d{6})', entries[0].附註)
                    if match:
                        batch_id = match.group(1)
                    else:
                        batch_id = entries[0].交易ID.rsplit('-', 1)[0] if '-' in entries[0].交易ID else entries[0].交易ID
                else:
                    batch_id = entries[0].交易ID

                kv_data = {
                    "batch_id": batch_id,
                    "transaction_ids": transaction_ids,
                    "品項": entries[-1].品項,  # 最後一筆的品項
                    "原幣金額": entries[-1].原幣金額,
                    "付款方式": entries[-1].付款方式,
                    "分類": entries[-1].分類,
                    "日期": entries[-1].日期,
                    "item_count": total_items,
                }

                if user_id:
                    print("\n儲存的資料結構：")
                    print(json.dumps(kv_data, indent=2, ensure_ascii=False))
                    if KV_ENABLED:
                        saved = save_last_transaction(user_id, kv_data)
                        print(f"\nKV Key: last_transaction:{user_id}")
                        print("TTL: 600 秒（10 分鐘）")
                        if saved:
                            print("✅ KV 寫入成功")
                        else:
                            print("❌ KV 寫入失敗，請確認 REDIS_URL")
                    else:
                        print("\n⚠️  KV 未啟用（REDIS_URL 未設定），略過寫入")
                else:
                    print("\n⚠️  未提供 user_id，略過 KV 寫入")

                if update_message:
                    if not user_id:
                        print("\n❌ 未提供 user_id，無法執行修改測試")
                    elif not KV_ENABLED:
                        print("\n❌ KV 未啟用，無法執行修改測試（請設定 REDIS_URL）")
                    else:
                        print("\n" + "=" * 60)
                        print("🔄 測試「修改上一筆」功能")
                        print("=" * 60)
                        print(f"\n使用者訊息：{update_message}\n")
                        update_result = process_multi_expense(update_message)
                        if update_result.intent != "update_last_entry":
                            if update_result.intent == "error":
                                print(f"❌ 修改解析失敗：{update_result.error_message}")
                            else:
                                print(f"❌ 解析結果非修改意圖：{update_result.intent}")
                            return
                        reply = handle_update_last_entry(
                            user_id,
                            update_result.fields_to_update,
                            raw_message=update_message,
                        )
                        print(reply)
            else:
                print(f"❌ 轉換失敗: {result.error_message}")

        if raw_mode:
            sys.stdout = raw_stdout
            if error_code:
                raw_output = {
                    "intent": "error",
                    "intent_display": "錯誤",
                    "error_message": error_message,
                    "reason": error_code,
                }
            else:
                if result.intent == "multi_bookkeeping":
                    raw_output = {
                        "intent": "multi_bookkeeping",
                        "intent_display": "記帳",
                        "entries": [
                            {
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
                            for entry in result.entries
                        ],
                    }
                else:
                    raw_output = {
                        "intent": "error",
                        "intent_display": "錯誤",
                        "error_message": getattr(result, "error_message", "未知錯誤"),
                        "reason": getattr(result, "error_reason", None),
                    }

            print(json.dumps(raw_output, ensure_ascii=False))
            return

        print("=" * 60)

    except Exception as e:
        print(f"❌ 處理過程發生錯誤: {e}")
        import traceback
        print("\n詳細錯誤:")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
