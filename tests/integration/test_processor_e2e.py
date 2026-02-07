from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
import pytest
from app.processor import process_with_parser
from app.gpt_processor import MultiExpenseResult

# Set Taipei timezone for testing
TAIPEI_TZ = ZoneInfo("Asia/Taipei")

@pytest.fixture
def taipei_now():
    """Returns a fixed datetime in Taipei timezone for testing."""
    return datetime(2025, 12, 14, 15, 30, 0, tzinfo=TAIPEI_TZ)

@pytest.fixture
def mock_parser_context(mocker, taipei_now):
    """Mocks datetime.now() to return fixed time."""
    mock_datetime = mocker.patch("app.processor.datetime")
    mock_datetime.now.return_value = taipei_now
    return mock_datetime

class TestEndToEndIntegration:
    """End-to-end tests for Parser-first flow (T021)."""

    def test_e2e_simple_expense_skip_gpt(self, mock_parser_context):
        """Test simple expense with skip_gpt=True (Authoritative only)."""
        # 使用顯式日期以驗證日期提取
        result = process_with_parser("12/14 午餐120元現金", skip_gpt=True)
        
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        entry = result.entries[0]
        
        # Check authoritative fields
        assert entry.原幣金額 == 120.0
        assert entry.付款方式 == "現金"
        assert entry.日期 == "12/14"  # Explicit date should be extracted
        assert "午餐" in entry.品項
        
        # Check enriched fields (skip_gpt uses defaults)
        assert entry.分類 == "未分類"  # No GPT -> default
        assert entry.專案 == "日常"
        assert entry.必要性 == "必要日常支出"

    def test_e2e_multi_item_shared_payment(self, mock_parser_context):
        """Test multi-item message with shared payment method."""
        result = process_with_parser("早餐80\n午餐150 現金", skip_gpt=True)
        
        assert len(result.entries) == 2
        
        # First item: 早餐80 (inherits shared payment)
        entry1 = result.entries[0]
        assert entry1.原幣金額 == 80.0
        assert "早餐" in entry1.品項
        assert entry1.付款方式 == "現金"  # Should inherit shared payment
        
        # Second item: 午餐150 (explicit payment, same as shared)
        entry2 = result.entries[1]
        assert entry2.原幣金額 == 150.0
        assert "午餐" in entry2.品項
        assert entry2.付款方式 == "現金"

    def test_e2e_foreign_currency_exchange_rate(self, mock_parser_context, mocker):
        """Test foreign currency rate lookup in parser-first flow."""
        mocker.patch(
            "app.enricher.enricher.ExchangeRateService.get_rate",
            return_value=0.21,
        )

        result = process_with_parser("拉麵 日幣 1500 現金", skip_gpt=True)

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.原幣別 == "JPY"
        assert entry.原幣金額 == 1500.0
        assert entry.匯率 == 0.21

    def test_e2e_cashflow_transfer(self, mock_parser_context):
        """Test cashflow intent handling (Withdrawal)."""
        # "從richart提款5000" -> withdrawal intent, source=Richart
        result = process_with_parser("從richart提款5000", skip_gpt=True)
        
        assert result.intent == "cashflow_intents"
        assert len(result.entries) == 1
        entry = result.entries[0]
        
        assert entry.原幣金額 == 5000.0
        assert entry.付款方式 == "台新 Richart"
        assert entry.交易類型 == "提款"
        assert "提款" in entry.品項

    def test_e2e_error_handling(self, mock_parser_context):
        """Test error handling for invalid input (no amount)."""
        result = process_with_parser("你好", skip_gpt=True)
        
        # Parser throws error for missing amount -> mapped to error intent in process_with_parser
        assert result.intent == "error"
        assert result.error_reason == "ParserErrorCode.MISSING_AMOUNT"

    def test_e2e_with_gpt_enrichment(self, mock_parser_context, mocker):
        """Test full flow with mocked GPT enrichment."""
        # Mock GPT response to verify flow integration
        mock_enrich_response = {
            "enrichment": [
                {
                    "id": "t1",  # Assuming parser assigns t1
                    "分類": "家庭/餐飲/午餐",
                    "專案": "日常",
                    "必要性": "必要日常支出",
                    "明細說明": "麥當勞"
                }
            ]
        }
        
        # Patch call_gpt_enrichment in enricher module (where it is imported)
        mocker.patch("app.enricher.enricher.call_gpt_enrichment", return_value=mock_enrich_response)
        
        # Also need to ensure OPENAI_API_KEY check doesn't fail before calling GPT
        # But wait, the check is INSIDE call_gpt_enrichment, which is mocked.
        # Why did it fail? Maybe gpt_processor checks it? No.
        # Maybe enricher tests reload module?
        # The previous error "OPENAI_API_KEY is not set" comes from gpt_client.py line 112
        # which means the REAL function was called.
        # So patching where it's correctly imported should fix it.
        
        # Force set parser ID to match mock (since parser IDs are auto-generated)
        # Alternatively, we can rely on enricher matching logic if ID doesn't matter for single items
        # But enricher uses ID to match. Let's mock parser's uuid generation or just check result content.
        # Actually enricher uses ID from parser output.
        # Let's just mock the enrich() function to avoid ID mismatch issues in this test level
        # OR better: mock call_gpt_enrichment and ensure id matches what parser produces? 
        # Parser IDs are t1, t2... sequential. So it should match "t1" for single item.
        
        result = process_with_parser("麥當勞午餐189元狗卡")
        
        assert len(result.entries) == 1
        entry = result.entries[0]
        
        # Authoritative
        assert entry.原幣金額 == 189.0
        assert entry.付款方式 == "台新狗卡"
        
        # Enriched (from mock)
        assert entry.分類 == "家庭/餐飲/午餐"
        assert entry.專案 == "日常"
        assert entry.明細說明 == "麥當勞"
