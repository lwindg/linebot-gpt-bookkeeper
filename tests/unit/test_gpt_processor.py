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


class TestCategoryAutocorrect:
    """Test category normalization and allow-list autocorrect"""

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_category_normalize_fullwidth_separator(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "蘋果",
                "原幣別": "TWD",
                "原幣金額": 120,
                "明細說明": "",
                "分類": "家庭／水果",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("蘋果120元現金")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].分類 == "家庭/水果"

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_category_autocorrect_to_existing(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "香蕉",
                "原幣別": "TWD",
                "原幣金額": 50,
                "明細說明": "",
                "分類": "水果/香蕉",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("香蕉50元現金")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].分類 == "家庭/水果"

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_category_autocorrect_fallback(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "WSJ",
                "原幣別": "TWD",
                "原幣金額": 120,
                "明細說明": "",
                "分類": "Subscription",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("WSJ 120現金")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].分類 == "家庭支出"


class TestPaymentNormalization:
    """Test payment method normalization"""

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_payment_normalize_flygo_nickname(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "灰狗卡",
            "items": [{
                "品項": "午餐",
                "原幣別": "TWD",
                "原幣金額": 120,
                "明細說明": "",
                "分類": "家庭/餐飲/午餐",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("午餐120元灰狗")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].付款方式 == "FlyGo 信用卡"


class TestProjectInference:
    """Test project inference from category or explicit project field"""

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_infer_project_from_category(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "掛號費",
                "原幣別": "TWD",
                "原幣金額": 200,
                "明細說明": "",
                "分類": "健康/醫療/本人",
                "必要性": "必要日常支出",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("掛號費200元現金")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].專案 == "健康檢查"

    @patch('app.gpt_processor.OpenAI')
    @patch('app.gpt_processor.ExchangeRateService')
    def test_keep_explicit_project(self, mock_exchange_service, mock_openai):
        set_openai_mock_content(mock_openai, '''{
            "intent": "multi_bookkeeping",
            "payment_method": "現金",
            "items": [{
                "品項": "睡袋租借",
                "原幣別": "TWD",
                "原幣金額": 500,
                "明細說明": "",
                "分類": "行程/裝備/租借",
                "專案": "20250517-18 玉山南稜",
                "必要性": "想吃想買但合理",
                "代墊狀態": "無",
                "收款支付對象": ""
            }]
        }''')

        mock_exchange_service.return_value = Mock()

        result = process_multi_expense("睡袋租借500元現金（20250517-18 玉山南稜）")

        assert result.intent == "multi_bookkeeping"
        assert result.entries[0].專案 == "20250517-18 玉山南稜"

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
