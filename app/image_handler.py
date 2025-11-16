"""
圖片處理模組

此模組負責：
1. 從 LINE 下載圖片
2. 將圖片轉換為 base64 編碼
3. 使用 GPT-4 Vision API 分析收據內容
4. 回傳結構化收據資料
"""

import base64
import json
import logging
import io
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from PIL import Image
from openai import OpenAI
from linebot.v3.messaging import MessagingApiBlob

from app.config import OPENAI_API_KEY, GPT_VISION_MODEL
from app.prompts import RECEIPT_VISION_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ReceiptItem:
    """單筆收據項目"""
    品項: str
    原幣金額: float
    付款方式: Optional[str] = None
    分類: Optional[str] = None


class ImageDownloadError(Exception):
    """圖片下載失敗"""
    pass


class ImageTooLargeError(Exception):
    """圖片過大"""
    pass


class VisionAPIError(Exception):
    """Vision API 失敗"""
    pass


def download_image(message_id: str, messaging_api_blob: MessagingApiBlob) -> bytes:
    """
    從 LINE 下載圖片內容

    Args:
        message_id: LINE 訊息 ID
        messaging_api_blob: LINE Messaging API Blob 實例

    Returns:
        bytes: 圖片二進位內容

    Raises:
        ImageDownloadError: 下載失敗
        ImageTooLargeError: 圖片過大（>10MB）
    """
    try:
        logger.info(f"開始下載圖片，message_id={message_id}")

        # 使用 LINE SDK 下載圖片
        image_content = messaging_api_blob.get_message_content(message_id)

        # 讀取圖片內容
        image_data = b''
        max_size = 10 * 1024 * 1024  # 10MB

        for chunk in image_content.iter_content(chunk_size=8192):
            image_data += chunk
            if len(image_data) > max_size:
                raise ImageTooLargeError(f"圖片過大（>{max_size} bytes），請重新上傳")

        logger.info(f"圖片下載成功，大小={len(image_data)} bytes")
        return image_data

    except ImageTooLargeError:
        raise
    except Exception as e:
        logger.error(f"圖片下載失敗: {e}")
        raise ImageDownloadError(f"圖片下載失敗: {e}")


def compress_image(image_data: bytes, max_width: int = 1024, quality: int = 85) -> bytes:
    """
    壓縮圖片以減少 Vision API token 消耗

    策略：
    1. 調整圖片尺寸（保持比例，最大寬度 1024px）
    2. 降低 JPEG 品質（85% 仍保持良好可讀性）
    3. 轉換為 JPEG 格式（如果是 PNG）

    Args:
        image_data: 原始圖片二進位資料
        max_width: 最大寬度（預設 1024px）
        quality: JPEG 品質（1-100，預設 85）

    Returns:
        bytes: 壓縮後的圖片二進位資料

    Examples:
        >>> original_size = len(image_data)
        >>> compressed = compress_image(image_data)
        >>> compressed_size = len(compressed)
        >>> reduction = (1 - compressed_size / original_size) * 100
        >>> print(f"壓縮率：{reduction:.1f}%")
    """
    try:
        # 開啟圖片
        img = Image.open(io.BytesIO(image_data))

        # 記錄原始尺寸
        original_width, original_height = img.size
        logger.info(f"原始圖片尺寸：{original_width}x{original_height}")

        # 計算新尺寸（保持比例）
        if original_width > max_width:
            ratio = max_width / original_width
            new_width = max_width
            new_height = int(original_height * ratio)

            # 調整尺寸（使用高品質重採樣）
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"調整後尺寸：{new_width}x{new_height}")

        # 轉換為 RGB（如果是 RGBA 或其他模式）
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 壓縮並儲存到記憶體
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        compressed_data = output.getvalue()

        # 記錄壓縮結果
        original_size = len(image_data)
        compressed_size = len(compressed_data)
        reduction = (1 - compressed_size / original_size) * 100

        logger.info(f"原始大小：{original_size} bytes")
        logger.info(f"壓縮後大小：{compressed_size} bytes")
        logger.info(f"壓縮率：{reduction:.1f}%")

        return compressed_data

    except Exception as e:
        logger.warning(f"圖片壓縮失敗，使用原圖：{e}")
        return image_data


def encode_image_base64(image_data: bytes) -> str:
    """
    將圖片轉換為 base64 編碼

    Args:
        image_data: 圖片二進位資料

    Returns:
        str: base64 編碼字串（用於 GPT Vision API）
    """
    return base64.b64encode(image_data).decode('utf-8')


def process_receipt_image(
    image_data: bytes,
    openai_client: Optional[OpenAI] = None,
    enable_compression: bool = True
) -> tuple[List[ReceiptItem], Optional[str], Optional[str]]:
    """
    使用 GPT-4 Vision API 分析收據圖片

    Args:
        image_data: 圖片二進位資料
        openai_client: OpenAI client 實例（可選，用於測試）
        enable_compression: 是否啟用圖片壓縮（預設 True，用於測試可設為 False）

    Returns:
        tuple: (收據項目列表, 錯誤狀態碼, 錯誤訊息)

        正常情況：([ReceiptItem, ...], None, None)
        錯誤情況：([], "error_code", "錯誤訊息")

        錯誤狀態碼：
        - "not_receipt": 非收據圖片
        - "unsupported_currency": 非台幣收據
        - "unclear": 圖片模糊/無法辨識
        - "incomplete": 缺少關鍵資訊
        - "api_error": API 呼叫失敗

    流程：
        1. 將圖片編碼為 base64
        2. 呼叫 GPT-4o Vision API
        3. 解析回應（JSON 格式）
        4. 驗證資料完整性
        5. 回傳 ReceiptItem 列表

    錯誤處理：
        - 圖片模糊/無法識別 → 回傳空列表 + 錯誤訊息
        - 非收據圖片 → 回傳空列表 + 提示訊息
        - API 失敗 → 拋出 VisionAPIError
    """
    try:
        # 初始化 OpenAI client
        if openai_client is None:
            openai_client = OpenAI(api_key=OPENAI_API_KEY)

        # 壓縮圖片以減少 token 消耗（可選）
        if enable_compression:
            compressed_image = compress_image(image_data)
            logger.info("圖片壓縮已啟用")
        else:
            compressed_image = image_data
            logger.info("圖片壓縮已停用（使用原圖）")

        # 編碼圖片為 base64
        base64_image = encode_image_base64(compressed_image)

        logger.info("開始呼叫 GPT-4 Vision API 分析收據")

        # 呼叫 GPT-4 Vision API
        response = openai_client.chat.completions.create(
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

        # 解析回應
        response_text = response.choices[0].message.content
        logger.info(f"GPT Vision 回應: {response_text}")

        result = json.loads(response_text)

        # 檢查狀態
        status = result.get("status")

        if status == "success":
            # 成功識別收據
            items_data = result.get("items", [])
            payment_method = result.get("payment_method")

            # 轉換為 ReceiptItem 列表
            receipt_items = []
            for item in items_data:
                receipt_items.append(ReceiptItem(
                    品項=item["品項"],
                    原幣金額=float(item["金額"]),
                    付款方式=payment_method,
                    分類=item.get("分類")  # Vision API 提供的分類（可選）
                ))

            logger.info(f"成功識別 {len(receipt_items)} 個收據項目")
            return receipt_items, None, None

        elif status == "not_receipt":
            # 非收據圖片
            message = result.get("message", "這不是收據圖片")
            logger.warning(f"非收據圖片: {message}")
            return [], "not_receipt", message

        elif status == "unsupported_currency":
            # 非台幣收據
            message = result.get("message", "v1.5.0 僅支援台幣")
            logger.warning(f"非台幣收據: {message}")
            return [], "unsupported_currency", message

        elif status == "unclear":
            # 圖片模糊
            message = result.get("message", "圖片模糊，無法辨識")
            logger.warning(f"圖片模糊: {message}")
            return [], "unclear", message

        elif status == "incomplete":
            # 資訊不完整
            message = result.get("message", "缺少關鍵資訊")
            logger.warning(f"收據資訊不完整: {message}")
            return [], "incomplete", message

        else:
            # 未知狀態
            logger.error(f"未知的回應狀態: {status}")
            return [], "api_error", f"無法處理收據（狀態：{status}）"

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {e}, response_text={response_text}")
        return [], "api_error", "無法解析 Vision API 回應"

    except Exception as e:
        logger.error(f"Vision API 呼叫失敗: {e}")
        raise VisionAPIError(f"Vision API 失敗: {e}")
