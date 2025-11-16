#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地圖片識別測試腳本

用途：在本地測試 GPT-4 Vision API 收據識別功能，不需要透過 LINE

使用方式：
    python test_local_vision.py <圖片路徑>

範例：
    python test_local_vision.py receipt.jpg
    python test_local_vision.py ~/Downloads/receipt.png
"""

import sys
import os
from pathlib import Path

# 將專案根目錄加入 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.image_handler import process_receipt_image, ReceiptItem, compress_image
from app.gpt_processor import process_receipt_data
from openai import OpenAI
from app.config import OPENAI_API_KEY


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


def format_receipt_items(receipt_items: list[ReceiptItem]) -> str:
    """格式化收據項目"""
    if not receipt_items:
        return "無項目"

    lines = []
    for idx, item in enumerate(receipt_items, 1):
        lines.append(f"  {idx}. {item.品項} - {item.原幣金額} 元")
        if item.付款方式:
            lines.append(f"     付款方式: {item.付款方式}")
    return "\n".join(lines)


def main():
    """主函式"""
    # 檢查參數
    if len(sys.argv) < 2:
        print("❌ 使用方式: python test_local_vision.py <圖片路徑> [--no-compress]")
        print("\n範例:")
        print("  python test_local_vision.py receipt.jpg")
        print("  python test_local_vision.py ~/Downloads/receipt.png")
        print("  python test_local_vision.py receipt.jpg --no-compress  # 測試不壓縮")
        sys.exit(1)

    image_path = sys.argv[1]

    # 檢查是否停用壓縮
    enable_compression = "--no-compress" not in sys.argv

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
        from app.image_handler import encode_image_base64
        from app.prompts import RECEIPT_VISION_PROMPT
        from app.config import GPT_VISION_MODEL

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

        # 現在使用正常流程處理
        receipt_items, error_code, error_message = process_receipt_image(
            image_data,
            client,
            enable_compression=enable_compression
        )

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
                print("  - 目前僅支援台幣（TWD）收據")
                print("  - 請使用文字描述並手動換算台幣金額")
            elif error_code == "unclear":
                print("  - 請重新拍攝更清晰的圖片")
                print("  - 確保收據上的文字清楚可見")
            elif error_code == "incomplete":
                print("  - 請確認收據上有品項和金額資訊")

        else:
            # 識別成功
            print(f"✅ 識別成功！共 {len(receipt_items)} 個項目")
            print("\n📋 識別到的項目:")
            print(format_receipt_items(receipt_items))

            # 轉換為記帳資料
            print("\n🔄 轉換為記帳資料...")
            result = process_receipt_data(receipt_items)

            if result.intent == "multi_bookkeeping":
                print("✅ 轉換成功！\n")

                # 顯示記帳資料
                for idx, entry in enumerate(result.entries, 1):
                    print(f"記帳項目 #{idx}:")
                    print(f"  品項: {entry.品項}")
                    print(f"  金額: {entry.原幣金額} TWD")
                    print(f"  付款方式: {entry.付款方式}")
                    print(f"  分類: {entry.分類}")
                    print(f"  日期: {entry.日期}")
                    print(f"  交易ID: {entry.交易ID}")
                    if idx < len(result.entries):
                        print()
            else:
                print(f"❌ 轉換失敗: {result.error_message}")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 處理過程發生錯誤: {e}")
        import traceback
        print("\n詳細錯誤:")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
