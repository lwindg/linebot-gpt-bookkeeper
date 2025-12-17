# Test GPT Processor for multi-currency feature

from unittest.mock import Mock, patch

from app.gpt_processor import process_multi_expense
from tests.test_utils import set_openai_mock_content


class TestForeignCurrencyParsing:
    """Test foreign currency parsing (v003-multi-currency)"""

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_parse_usd_expense(self, mock_exchange_service, mock_openai):
        """Test parsing USD expense: WSJ 4.99 USD"""
        # Mock GPT response
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "Credit Card",
            "items": [{
                "品項": "WSJ",
                "原幣別": "USD",
                "原幣金額": 4.99,
                "明細說明": "",
                "分類": "Subscription",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        # Mock exchange rate service
        mock_rate_service = Mock()
        mock_rate_service.get_rate.return_value = 31.50
        mock_exchange_service.return_value = mock_rate_service

        # Process message
        result = process_multi_expense("WSJ 4.99USD")

        # Assertions
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.品項 == "WSJ"
        assert entry.原幣別 == "USD"
        assert entry.原幣金額 == 4.99
        assert entry.匯率 == 31.50

        # Verify exchange rate service was called
        mock_rate_service.get_rate.assert_called_once_with("USD")

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_parse_eur_expense(self, mock_exchange_service, mock_openai):
        """Test parsing EUR expense"""
        # Mock GPT response
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "Credit Card",
            "items": [{
                "品項": "Hotel",
                "原幣別": "EUR",
                "原幣金額": 290.97,
                "明細說明": "",
                "分類": "Travel",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        # Mock exchange rate service
        mock_rate_service = Mock()
        mock_rate_service.get_rate.return_value = 33.20
        mock_exchange_service.return_value = mock_rate_service

        # Process message
        result = process_multi_expense("Hotel 290.97EUR")

        # Assertions
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.原幣別 == "EUR"
        assert entry.原幣金額 == 290.97
        assert entry.匯率 == 33.20

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_twd_expense_no_rate_query(self, mock_exchange_service, mock_openai):
        """Test TWD expense doesn't query exchange rate"""
        # Mock GPT response
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "Cash",
            "items": [{
                "品項": "Lunch",
                "原幣別": "TWD",
                "原幣金額": 80,
                "明細說明": "",
                "分類": "Food",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        # Mock exchange rate service
        mock_rate_service = Mock()
        mock_exchange_service.return_value = mock_rate_service

        # Process message
        result = process_multi_expense("Lunch 80 Cash")

        # Assertions
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.原幣別 == "TWD"
        assert entry.匯率 == 1.0

        # Verify exchange rate service was NOT called
        mock_rate_service.get_rate.assert_not_called()
