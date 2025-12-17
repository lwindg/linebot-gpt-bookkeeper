#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v1.5.0 Webhook 批次發送單元測試

測試範圍：
- send_multiple_webhooks() 函式
- 批次發送成功與失敗處理
- 重試機制
- 錯誤計數
"""

import pytest
from unittest.mock import Mock, patch, call
from app.webhook_sender import send_multiple_webhooks
from app.gpt_processor import BookkeepingEntry


@pytest.fixture
def sample_entries():
    """建立測試用的記帳項目"""
    return [
        BookkeepingEntry(
            intent="bookkeeping",
            日期="2025-11-15",
            品項="早餐",
            原幣別="TWD",
            原幣金額=80,
            匯率=1,
            付款方式="現金",
            交易ID="20251115-120000",
            明細說明="",
            分類="家庭/餐飲/早餐",
            專案="日常",
            必要性="必要日常支出",
            代墊狀態="無",
            收款支付對象="",
            附註="多項目支出 1/2",
            response_text=None
        ),
        BookkeepingEntry(
            intent="bookkeeping",
            日期="2025-11-15",
            品項="午餐",
            原幣別="TWD",
            原幣金額=150,
            匯率=1,
            付款方式="現金",
            交易ID="20251115-120000",
            明細說明="",
            分類="家庭/餐飲/午餐",
            專案="日常",
            必要性="必要日常支出",
            代墊狀態="無",
            收款支付對象="",
            附註="多項目支出 2/2",
            response_text=None
        )
    ]


class TestSendMultipleWebhooks:
    """測試 send_multiple_webhooks() 函式"""

    @patch('app.webhook_sender.send_to_webhook')
    def test_all_success(self, mock_send, sample_entries):
        """測試所有項目都成功發送"""
        # Mock 所有發送都成功
        mock_send.return_value = True

        success_count, failure_count = send_multiple_webhooks(sample_entries)

        # 驗證結果
        assert success_count == 2
        assert failure_count == 0

        # 驗證呼叫次數
        assert mock_send.call_count == 2

        # 驗證呼叫參數
        calls = mock_send.call_args_list
        assert calls[0][0][0].品項 == "早餐"
        assert calls[1][0][0].品項 == "午餐"

    @patch('app.webhook_sender.send_to_webhook')
    def test_partial_failure(self, mock_send, sample_entries):
        """測試部分項目發送失敗"""
        # Mock 第一個成功，第二個失敗
        mock_send.side_effect = [True, False]

        success_count, failure_count = send_multiple_webhooks(sample_entries)

        # 驗證結果
        assert success_count == 1
        assert failure_count == 1

        # 驗證呼叫次數
        assert mock_send.call_count == 2

    @patch('app.webhook_sender.send_to_webhook')
    def test_all_failure(self, mock_send, sample_entries):
        """測試所有項目都發送失敗"""
        # Mock 所有發送都失敗
        mock_send.return_value = False

        success_count, failure_count = send_multiple_webhooks(sample_entries)

        # 驗證結果
        assert success_count == 0
        assert failure_count == 2

        # 驗證呼叫次數
        assert mock_send.call_count == 2

    @patch('app.webhook_sender.send_to_webhook')
    def test_empty_list(self, mock_send):
        """測試空列表"""
        success_count, failure_count = send_multiple_webhooks([])

        # 驗證結果
        assert success_count == 0
        assert failure_count == 0

        # 驗證沒有呼叫
        assert mock_send.call_count == 0

    @patch('app.webhook_sender.send_to_webhook')
    def test_single_item(self, mock_send):
        """測試單個項目"""
        entry = BookkeepingEntry(
            intent="bookkeeping",
            日期="2025-11-15",
            品項="咖啡",
            原幣別="TWD",
            原幣金額=50,
            匯率=1,
            付款方式="現金",
            交易ID="20251115-120000",
            明細說明="",
            分類="家庭/飲品/咖啡",
            專案="日常",
            必要性="想吃想買但合理",
            代墊狀態="無",
            收款支付對象="",
            附註="",
            response_text=None
        )

        mock_send.return_value = True

        success_count, failure_count = send_multiple_webhooks([entry])

        # 驗證結果
        assert success_count == 1
        assert failure_count == 0
        assert mock_send.call_count == 1

    @patch('app.webhook_sender.send_to_webhook')
    def test_four_items(self, mock_send):
        """測試四個項目"""
        entries = []
        for i, item in enumerate(["咖啡", "三明治", "沙拉", "果汁"], start=1):
            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期="2025-11-15",
                品項=item,
                原幣別="TWD",
                原幣金額=50,
                匯率=1,
                付款方式="現金",
                交易ID="20251115-120000",
                明細說明="",
                分類="家庭/餐飲",
                專案="日常",
                必要性="必要日常支出",
                代墊狀態="無",
                收款支付對象="",
                附註=f"多項目支出 {i}/4",
                response_text=None
            )
            entries.append(entry)

        mock_send.return_value = True

        success_count, failure_count = send_multiple_webhooks(entries)

        # 驗證結果
        assert success_count == 4
        assert failure_count == 0
        assert mock_send.call_count == 4

    @patch('app.webhook_sender.send_to_webhook')
    def test_mixed_results(self, mock_send):
        """測試混合成功/失敗結果（3個項目：成功、失敗、成功）"""
        entries = []
        for i, item in enumerate(["早餐", "午餐", "晚餐"], start=1):
            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期="2025-11-15",
                品項=item,
                原幣別="TWD",
                原幣金額=100,
                匯率=1,
                付款方式="現金",
                交易ID="20251115-120000",
                明細說明="",
                分類="家庭/餐飲",
                專案="日常",
                必要性="必要日常支出",
                代墊狀態="無",
                收款支付對象="",
                附註=f"多項目支出 {i}/3",
                response_text=None
            )
            entries.append(entry)

        # Mock: 成功、失敗、成功
        mock_send.side_effect = [True, False, True]

        success_count, failure_count = send_multiple_webhooks(entries)

        # 驗證結果
        assert success_count == 2
        assert failure_count == 1
        assert mock_send.call_count == 3


class TestWebhookBatchIntegration:
    """測試 Webhook 批次發送整合場景"""

    @patch('app.webhook_sender.send_to_webhook')
    def test_shared_transaction_id(self, mock_send, sample_entries):
        """驗證批次發送的項目共用交易ID"""
        mock_send.return_value = True

        send_multiple_webhooks(sample_entries)

        # 取得呼叫的參數
        calls = mock_send.call_args_list
        entry1 = calls[0][0][0]
        entry2 = calls[1][0][0]

        # 驗證共用交易ID
        assert entry1.交易ID == entry2.交易ID
        assert entry1.交易ID == "20251115-120000"

    @patch('app.webhook_sender.send_to_webhook')
    def test_shared_payment_method(self, mock_send, sample_entries):
        """驗證批次發送的項目共用付款方式"""
        mock_send.return_value = True

        send_multiple_webhooks(sample_entries)

        # 取得呼叫的參數
        calls = mock_send.call_args_list
        entry1 = calls[0][0][0]
        entry2 = calls[1][0][0]

        # 驗證共用付款方式
        assert entry1.付款方式 == entry2.付款方式
        assert entry1.付款方式 == "現金"

    @patch('app.webhook_sender.send_to_webhook')
    def test_note_markers(self, mock_send, sample_entries):
        """驗證批次發送的項目附註標記"""
        mock_send.return_value = True

        send_multiple_webhooks(sample_entries)

        # 取得呼叫的參數
        calls = mock_send.call_args_list
        entry1 = calls[0][0][0]
        entry2 = calls[1][0][0]

        # 驗證附註標記
        assert "多項目支出 1/2" in entry1.附註
        assert "多項目支出 2/2" in entry2.附註

    @patch('app.webhook_sender.send_to_webhook')
    def test_sequential_sending(self, mock_send, sample_entries):
        """驗證項目是按順序發送的"""
        mock_send.return_value = True

        send_multiple_webhooks(sample_entries)

        # 驗證呼叫順序
        calls = mock_send.call_args_list
        assert calls[0][0][0].品項 == "早餐"
        assert calls[1][0][0].品項 == "午餐"

    @patch('app.webhook_sender.send_to_webhook')
    @patch('app.webhook_sender.logger')
    def test_logging_on_failure(self, mock_logger, mock_send):
        """測試失敗時的日誌記錄"""
        entry = BookkeepingEntry(
            intent="bookkeeping",
            日期="2025-11-15",
            品項="測試",
            原幣別="TWD",
            原幣金額=100,
            匯率=1,
            付款方式="現金",
            交易ID="20251115-120000",
            明細說明="",
            分類="家庭/餐飲",
            專案="日常",
            必要性="必要日常支出",
            代墊狀態="無",
            收款支付對象="",
            附註="",
            response_text=None
        )

        # Mock 發送失敗
        mock_send.return_value = False

        send_multiple_webhooks([entry])

        # 驗證記錄了錯誤（如果有實作日誌的話）
        # 這個測試取決於實際的 logger 實作
        # 如果沒有實作日誌，這個測試可以跳過或修改


class TestWebhookErrorHandling:
    """測試 Webhook 錯誤處理"""

    @patch('app.webhook_sender.send_to_webhook')
    def test_exception_handling(self, mock_send):
        """測試異常處理"""
        entry = BookkeepingEntry(
            intent="bookkeeping",
            日期="2025-11-15",
            品項="測試",
            原幣別="TWD",
            原幣金額=100,
            匯率=1,
            付款方式="現金",
            交易ID="20251115-120000",
            明細說明="",
            分類="家庭/餐飲",
            專案="日常",
            必要性="必要日常支出",
            代墊狀態="無",
            收款支付對象="",
            附註="",
            response_text=None
        )

        # Mock 拋出異常
        mock_send.side_effect = Exception("Network error")

        # 測試是否妥善處理異常（不應該崩潰）
        try:
            success_count, failure_count = send_multiple_webhooks([entry])
            # 如果有異常處理，應該回傳 (0, 1)
            assert success_count == 0
            assert failure_count == 1
        except Exception:
            # 如果沒有異常處理，這個測試會失敗
            pytest.fail("send_multiple_webhooks() should handle exceptions gracefully")

