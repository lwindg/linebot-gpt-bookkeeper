# -*- coding: utf-8 -*-
"""
End-to-End Integration Tests for Multi-Currency Feature

Tests the complete flow: message parsing -> exchange rate query -> webhook send
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.gpt_processor import process_multi_expense
from app.webhook_sender import send_to_webhook, send_multiple_webhooks


class TestSingleForeignCurrencyE2E:
    """Test single foreign currency expense end-to-end (T027)"""

    @patch('app.webhook_sender.requests.post')
    @patch('app.exchange_rate.requests.get')
    @patch('app.gpt_processor.OpenAI')
    def test_single_usd_expense_complete_flow(self, mock_openai, mock_exchange_get, mock_webhook_post):
        """Test: User sends 'WSJ 4.99美元 大戶' -> Full processing -> Webhook sent"""
        # Mock GPT response
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "大戶",
            "items": [{
                "品項": "WSJ",
                "原幣別": "USD",
                "原幣金額": 4.99,
                "明細說明": "Wall Street Journal subscription",
                "分類": "訂閱服務 > 新聞媒體",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock FinMind API response for exchange rate
        mock_exchange_response = Mock()
        mock_exchange_response.status_code = 200
        mock_exchange_response.json.return_value = {
            "data": [
                {"date": "2025-11-21", "cash_sell": "31.50"}
            ]
        }
        mock_exchange_get.return_value = mock_exchange_response

        # Mock webhook response
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook_post.return_value = mock_webhook_response

        # Process message
        result = process_multi_expense("WSJ 4.99美元 大戶")

        # Verify GPT parsing
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.品項 == "WSJ"
        assert entry.原幣別 == "USD"
        assert entry.原幣金額 == 4.99
        assert entry.匯率 == 31.50
        assert entry.付款方式 == "大戶"

        # Send to webhook
        success = send_to_webhook(entry)
        assert success is True

        # Verify webhook was called with correct data
        mock_webhook_post.assert_called_once()
        webhook_call_args = mock_webhook_post.call_args
        payload = webhook_call_args[1]['json']

        assert payload['品項'] == "WSJ"
        assert payload['原幣別'] == "USD"
        assert payload['原幣金額'] == 4.99
        assert payload['匯率'] == 31.50
        assert payload['付款方式'] == "大戶"

    @patch('app.webhook_sender.requests.post')
    @patch('app.gpt_processor.ExchangeRateService')
    @patch('app.gpt_processor.OpenAI')
    def test_eur_expense_with_fallback_to_csv(self, mock_openai, mock_exchange_service, mock_webhook_post):
        """Test: EUR expense with exchange rate service providing rate"""
        # Mock GPT response
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "信用卡",
            "items": [{
                "品項": "Hotel Booking",
                "原幣別": "EUR",
                "原幣金額": 150.0,
                "明細說明": "",
                "分類": "旅遊 > 住宿",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock exchange rate service (simulating CSV fallback)
        mock_rate_service = Mock()
        mock_rate_service.get_rate.return_value = 33.20  # Rate from CSV
        mock_exchange_service.return_value = mock_rate_service

        # Mock webhook response
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook_post.return_value = mock_webhook_response

        # Process message
        result = process_multi_expense("Hotel Booking 150EUR credit card")

        # Verify result
        assert result.intent == "multi_bookkeeping"
        entry = result.entries[0]
        assert entry.原幣別 == "EUR"
        assert entry.匯率 == 33.20

    @patch('app.webhook_sender.requests.post')
    @patch('app.gpt_processor.ExchangeRateService')
    @patch('app.gpt_processor.OpenAI')
    def test_backup_rate_when_all_apis_fail(self, mock_openai, mock_exchange_service, mock_webhook_post):
        """Test: Use backup rate when both FinMind and CSV fail"""
        # Mock GPT response
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "信用卡",
            "items": [{
                "品項": "Netflix",
                "原幣別": "USD",
                "原幣金額": 15.99,
                "明細說明": "",
                "分類": "訂閱服務 > 影音",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock exchange rate service with backup rate
        mock_rate_service = Mock()
        mock_rate_service.get_rate.return_value = 31.50  # Backup rate
        mock_exchange_service.return_value = mock_rate_service

        # Mock webhook response
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook_post.return_value = mock_webhook_response

        # Process message
        result = process_multi_expense("Netflix 15.99USD credit card")

        # Verify result uses backup rate
        assert result.intent == "multi_bookkeeping"
        entry = result.entries[0]
        assert entry.原幣別 == "USD"
        assert entry.匯率 == 31.50  # Backup rate for USD

    @patch('app.webhook_sender.requests.post')
    @patch('app.gpt_processor.OpenAI')
    def test_twd_expense_no_exchange_rate_query(self, mock_openai, mock_webhook_post):
        """Test: TWD expense doesn't query exchange rate"""
        # Mock GPT response
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "便當",
                "原幣別": "TWD",
                "原幣金額": 80,
                "明細說明": "",
                "分類": "飲食 > 午餐",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock webhook response
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook_post.return_value = mock_webhook_response

        # Process message
        result = process_multi_expense("便當 80 現金")

        # Verify result
        assert result.intent == "multi_bookkeeping"
        entry = result.entries[0]
        assert entry.原幣別 == "TWD"
        assert entry.匯率 == 1.0

        # Send to webhook
        success = send_to_webhook(entry)
        assert success is True


class TestMultiItemMixedCurrency:
    """Test multiple items with mixed currencies"""

    @patch('app.webhook_sender.requests.post')
    @patch('app.exchange_rate.requests.get')
    @patch('app.gpt_processor.OpenAI')
    def test_mixed_twd_and_foreign_currency(self, mock_openai, mock_exchange_get, mock_webhook_post):
        """Test: Multiple items with TWD and foreign currency"""
        # Mock GPT response
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "信用卡",
            "items": [
                {
                    "品項": "便當",
                    "原幣別": "TWD",
                    "原幣金額": 80,
                    "明細說明": "",
                    "分類": "飲食 > 午餐",
                    "必要性": "必要日常支出",
                    "代墊狀態": "無",
                    "收款支付對象": ""
                },
                {
                    "品項": "Netflix",
                    "原幣別": "USD",
                    "原幣金額": 15.99,
                    "明細說明": "",
                    "分類": "訂閱服務",
                    "必要性": "想吃想買但合理",
                    "代墊狀態": "無",
                    "收款支付對象": ""
                }
            ]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock FinMind API response for USD
        mock_exchange_response = Mock()
        mock_exchange_response.status_code = 200
        mock_exchange_response.json.return_value = {
            "data": [
                {"date": "2025-11-21", "cash_sell": "31.50"}
            ]
        }
        mock_exchange_get.return_value = mock_exchange_response

        # Mock webhook response
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook_post.return_value = mock_webhook_response

        # Process message
        result = process_multi_expense("便當 80 Netflix 15.99USD 信用卡")

        # Verify result
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # First entry (TWD)
        entry1 = result.entries[0]
        assert entry1.原幣別 == "TWD"
        assert entry1.匯率 == 1.0

        # Second entry (USD)
        entry2 = result.entries[1]
        assert entry2.原幣別 == "USD"
        assert entry2.匯率 == 31.50

        # Send all to webhook
        success_count, failure_count = send_multiple_webhooks(result.entries)
        assert success_count == 2
        assert failure_count == 0


class TestErrorHandling:
    """Test error handling scenarios"""

    @patch('app.gpt_processor.ExchangeRateService')
    @patch('app.gpt_processor.OpenAI')
    def test_unsupported_currency_returns_error(self, mock_openai, mock_exchange_service):
        """Test: Unsupported currency returns error"""
        # Mock GPT response with unsupported currency
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = '''{
            "intent": "multi_bookkeeping",
            "payment_method": "信用卡",
            "items": [{
                "品項": "Item",
                "原幣別": "GBP",
                "原幣金額": 100,
                "明細說明": "",
                "分類": "其他",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }'''
        mock_client.chat.completions.create.return_value = mock_completion

        # Mock exchange rate service returns None (no rate available)
        mock_rate_service = Mock()
        mock_rate_service.get_rate.return_value = None
        mock_exchange_service.return_value = mock_rate_service

        # Process message
        result = process_multi_expense("Item 100GBP credit card")

        # Verify error returned
        assert result.intent == "error"
        assert "無法取得 GBP 匯率" in result.error_message
