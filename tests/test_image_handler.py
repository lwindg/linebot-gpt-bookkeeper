# -*- coding: utf-8 -*-
"""
圖片處理模組測試

測試 image_handler.py 的所有功能：
1. 圖片下載
2. Base64 編碼
3. Vision API 收據識別
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from app.image_handler import (
    download_image,
    encode_image_base64,
    process_receipt_image,
    ReceiptItem,
    ImageDownloadError,
    ImageTooLargeError,
    VisionAPIError
)


class TestDownloadImage:
    """測試圖片下載功能"""

    def test_download_image_success(self, mocker):
        """測試成功下載圖片"""
        # Mock LINE API
        mock_messaging_api_blob = MagicMock()
        mock_content = MagicMock()

        # 模擬分塊下載的圖片資料
        test_image_data = b'fake_image_data_12345'
        mock_content.iter_content.return_value = [test_image_data]
        mock_messaging_api_blob.get_message_content.return_value = mock_content

        # 執行下載
        result = download_image("test_message_id", mock_messaging_api_blob)

        # 驗證
        assert result == test_image_data
        mock_messaging_api_blob.get_message_content.assert_called_once_with("test_message_id")

    def test_download_image_too_large(self, mocker):
        """測試圖片過大的情況"""
        # Mock LINE API
        mock_messaging_api_blob = MagicMock()
        mock_content = MagicMock()

        # 模擬超大圖片（分塊大於 10MB）
        large_chunk = b'x' * (11 * 1024 * 1024)  # 11MB
        mock_content.iter_content.return_value = [large_chunk]
        mock_messaging_api_blob.get_message_content.return_value = mock_content

        # 執行並預期拋出異常
        with pytest.raises(ImageTooLargeError):
            download_image("test_message_id", mock_messaging_api_blob)

    def test_download_image_failure(self, mocker):
        """測試圖片下載失敗"""
        # Mock LINE API
        mock_messaging_api_blob = MagicMock()
        mock_messaging_api_blob.get_message_content.side_effect = Exception("Network error")

        # 執行並預期拋出異常
        with pytest.raises(ImageDownloadError):
            download_image("test_message_id", mock_messaging_api_blob)


class TestEncodeImageBase64:
    """測試 Base64 編碼功能"""

    def test_encode_image_base64(self):
        """測試 Base64 編碼"""
        test_data = b'test_image_data'
        result = encode_image_base64(test_data)

        # 驗證結果是字串且為 Base64 編碼
        assert isinstance(result, str)
        assert len(result) > 0

        # 驗證可以解碼回原始資料
        import base64
        decoded = base64.b64decode(result)
        assert decoded == test_data


class TestProcessReceiptImage:
    """測試收據圖片識別功能"""

    def test_process_receipt_success_single_item(self, mocker):
        """測試成功識別收據（單筆項目）"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應
        vision_response = {
            "status": "success",
            "currency": "TWD",
            "date": "2025-11-15",
            "items": [
                {"品項": "咖啡", "金額": 50}
            ],
            "total": 50,
            "payment_method": "現金"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code is None
        assert error_message is None
        assert len(receipt_items) == 1
        assert receipt_items[0].品項 == "咖啡"
        assert receipt_items[0].原幣金額 == 50
        assert receipt_items[0].付款方式 == "現金"

    def test_process_receipt_success_multi_items(self, mocker):
        """測試成功識別收據（多筆項目）"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應（多筆項目）
        vision_response = {
            "status": "success",
            "currency": "TWD",
            "date": "2025-11-15",
            "items": [
                {"品項": "咖啡", "金額": 50},
                {"品項": "三明治", "金額": 80}
            ],
            "total": 130,
            "payment_method": "現金"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code is None
        assert error_message is None
        assert len(receipt_items) == 2
        assert receipt_items[0].品項 == "咖啡"
        assert receipt_items[1].品項 == "三明治"
        # 兩個項目共用付款方式
        assert receipt_items[0].付款方式 == "現金"
        assert receipt_items[1].付款方式 == "現金"

    def test_process_receipt_not_receipt(self, mocker):
        """測試非收據圖片（風景照）"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應（非收據）
        vision_response = {
            "status": "not_receipt",
            "message": "這不是收據圖片"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code == "not_receipt"
        assert error_message == "這不是收據圖片"
        assert len(receipt_items) == 0

    def test_process_receipt_unsupported_currency(self, mocker):
        """測試非台幣收據（日幣）"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應（非台幣）
        vision_response = {
            "status": "unsupported_currency",
            "message": "收據幣別為 JPY，v1.5.0 僅支援台幣"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code == "unsupported_currency"
        assert "JPY" in error_message
        assert len(receipt_items) == 0

    def test_process_receipt_unclear(self, mocker):
        """測試模糊收據圖片"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應（圖片模糊）
        vision_response = {
            "status": "unclear",
            "message": "圖片模糊，無法辨識品項和金額"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code == "unclear"
        assert "模糊" in error_message
        assert len(receipt_items) == 0

    def test_process_receipt_incomplete(self, mocker):
        """測試資訊不完整的收據"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬 GPT Vision API 回應（資訊不完整）
        vision_response = {
            "status": "incomplete",
            "message": "無法辨識品項或金額"
        }
        mock_message.content = json.dumps(vision_response)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code == "incomplete"
        assert len(receipt_items) == 0

    def test_process_receipt_api_error(self, mocker):
        """測試 Vision API 失敗"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        # 執行測試並預期拋出異常
        test_image = b'fake_image_data'
        with pytest.raises(VisionAPIError):
            process_receipt_image(test_image, mock_client)

    def test_process_receipt_json_parse_error(self, mocker):
        """測試 JSON 解析失敗"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()

        # 模擬無效的 JSON 回應
        mock_message.content = "invalid json"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # 執行測試
        test_image = b'fake_image_data'
        receipt_items, error_code, error_message = process_receipt_image(test_image, mock_client)

        # 驗證結果
        assert error_code == "api_error"
        assert "無法解析" in error_message
        assert len(receipt_items) == 0


class TestReceiptItem:
    """測試 ReceiptItem 資料類別"""

    def test_receipt_item_creation(self):
        """測試建立 ReceiptItem"""
        item = ReceiptItem(
            品項="咖啡",
            原幣金額=50.0,
            付款方式="現金",
            分類="家庭／飲品"
        )

        assert item.品項 == "咖啡"
        assert item.原幣金額 == 50.0
        assert item.付款方式 == "現金"
        assert item.分類 == "家庭／飲品"

    def test_receipt_item_optional_fields(self):
        """測試 ReceiptItem 的可選欄位"""
        item = ReceiptItem(品項="咖啡", 原幣金額=50.0)

        assert item.品項 == "咖啡"
        assert item.原幣金額 == 50.0
        assert item.付款方式 is None
        assert item.分類 is None
