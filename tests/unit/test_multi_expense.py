#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v1.5.0 多項目支出單元測試

測試範圍：
- process_multi_expense() 函式
- 單項目記帳（向後相容）
- 多項目記帳（核心功能）
- 錯誤處理（不同付款方式、缺少資訊等）
"""

from unittest.mock import patch
from app.gpt_processor import process_multi_expense
from tests.test_utils import set_openai_mock_content


class TestMultiExpenseSingleItem:
    """測試單項目記帳（向後相容 v1）"""

    @patch('app.gpt_processor.OpenAI')
    def test_single_item_standard_format(self, mock_openai):
        """TC-V15-001: v1 格式兼容 - 標準記帳"""
        # Mock GPT 回應
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "午餐",
      "原幣金額": 120,
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        # 執行測試
        result = process_multi_expense("午餐120元現金")

        # 驗證結果
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "午餐"
        assert result.entries[0].原幣金額 == 120
        assert result.entries[0].付款方式 == "現金"
        assert "餐飲" in result.entries[0].分類

    @patch('app.gpt_processor.OpenAI')
    def test_single_item_with_nickname(self, mock_openai):
        """TC-V15-002: v1 格式兼容 - 含暱稱"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "台新狗卡",
  "items": [
    {
      "品項": "點心",
      "原幣別": "TWD",
      "原幣金額": 200,
      "分類": "家庭/點心",
      "必要性": "想吃想買但合理",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("點心200元狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "點心"
        assert result.entries[0].原幣金額 == 200
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_single_item_natural_language(self, mock_openai):
        """TC-V15-003: v1 格式兼容 - 自然語句"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "Line Pay",
  "items": [
    {
      "品項": "咖啡",
      "原幣別": "TWD",
      "原幣金額": 50,
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("買了咖啡50元，Line Pay")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "咖啡"
        assert result.entries[0].付款方式 == "Line Pay"


class TestMultiExpenseMultipleItems:
    """測試多項目記帳（核心功能）"""

    @patch('app.gpt_processor.OpenAI')
    def test_two_items_comma_separated(self, mock_openai):
        """TC-V15-010: 雙項目 - 逗號分隔"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣別": "TWD",
      "原幣金額": 80,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "午餐",
      "原幣別": "TWD",
      "原幣金額": 150,
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("早餐80元，午餐150元，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # 驗證兩個項目
        assert result.entries[0].品項 == "早餐"
        assert result.entries[0].原幣金額 == 80
        assert result.entries[1].品項 == "午餐"
        assert result.entries[1].原幣金額 == 150

        # 驗證共用付款方式
        assert result.entries[0].付款方式 == result.entries[1].付款方式 == "現金"

        # 驗證獨立交易ID（v1.9.0：每個項目有獨立ID）
        assert result.entries[0].交易ID != result.entries[1].交易ID
        assert result.entries[0].交易ID is not None
        assert result.entries[1].交易ID is not None
        # 驗證交易ID格式（應該有序號後綴）
        assert result.entries[0].交易ID.endswith('-01')
        assert result.entries[1].交易ID.endswith('-02')

    @patch('app.gpt_processor.OpenAI')
    def test_payment_method_at_beginning(self, mock_openai):
        """TC-V15-011: 雙項目 - 付款方式在前"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "台新狗卡",
  "items": [
    {
      "品項": "咖啡",
      "原幣別": "TWD",
      "原幣金額": 50,
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "三明治",
      "原幣別": "TWD",
      "原幣金額": 35,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("用狗卡，咖啡50，三明治35")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2
        assert result.entries[0].付款方式 == result.entries[1].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_three_items_breakfast_lunch_dinner(self, mock_openai):
        """TC-V15-012: 三項目 - 早午晚餐"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 50,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "午餐",
      "原幣金額": 120,
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "晚餐",
      "原幣金額": 200,
      "分類": "家庭/餐飲/晚餐",
      "必要性": "必要日常支出",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("早餐50元，午餐120元，晚餐200元，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 3

        # 驗證所有項目共用付款方式
        assert all(e.付款方式 == "現金" for e in result.entries)

        # 驗證獨立交易ID（v1.9.0：每個項目有獨立ID）
        transaction_ids = [e.交易ID for e in result.entries]
        assert len(set(transaction_ids)) == 3  # 每個項目ID不同
        assert all(tid.endswith(f'-{str(i+1).zfill(2)}') for i, tid in enumerate(transaction_ids))

    @patch('app.gpt_processor.OpenAI')
    def test_four_items_or_more(self, mock_openai):
        """TC-V15-052: 四項目以上"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {"品項": "咖啡", "原幣別": "TWD", "原幣金額": 50, "分類": "家庭/飲品/咖啡", "必要性": "想吃想買但合理", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "三明治", "原幣別": "TWD", "原幣金額": 35, "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "沙拉", "原幣別": "TWD", "原幣金額": 80, "分類": "家庭/餐飲", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "果汁", "原幣別": "TWD", "原幣金額": 40, "分類": "家庭/飲品", "必要性": "想吃想買但合理", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""}
  ]
}
''')

        result = process_multi_expense("咖啡50、三明治35、沙拉80、果汁40、現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 4
        assert all(e.付款方式 == "現金" for e in result.entries)

        # 驗證獨立交易ID（v1.9.0：每個項目有獨立ID）
        transaction_ids = [e.交易ID for e in result.entries]
        assert len(set(transaction_ids)) == 4  # 每個項目ID不同


class TestMultiExpenseSharedValidation:
    """測試共用付款方式驗證"""

    @patch('app.gpt_processor.OpenAI')
    def test_shared_transaction_id(self, mock_openai):
        """TC-V15-020: 共用交易ID驗證"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {"品項": "早餐", "原幣別": "TWD", "原幣金額": 80, "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "午餐", "原幣別": "TWD", "原幣金額": 150, "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""}
  ]
}
''')

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # v1.9.0: 驗證每個項目有獨立的交易ID（批次ID + 序號）
        assert result.entries[0].交易ID != result.entries[1].交易ID
        assert result.entries[0].交易ID.endswith("-01")
        assert result.entries[1].交易ID.endswith("-02")

        # 驗證批次ID相同（去掉序號部分）
        batch_id_1 = result.entries[0].交易ID.rsplit('-', 1)[0]
        batch_id_2 = result.entries[1].交易ID.rsplit('-', 1)[0]
        assert batch_id_1 == batch_id_2

        # 驗證交易ID格式 YYYYMMDD-HHMMSS-NN
        transaction_id = result.entries[0].交易ID
        parts = transaction_id.split("-")
        assert len(parts) == 3  # 日期-時間-序號
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 2  # NN (序號)

    @patch('app.gpt_processor.OpenAI')
    def test_shared_date(self, mock_openai):
        """TC-V15-021: 共用日期驗證"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {"品項": "早餐", "原幣別": "TWD", "原幣金額": 80, "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "午餐", "原幣別": "TWD", "原幣金額": 150, "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""}
  ]
}
''')

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # 驗證兩個項目的日期相同
        assert result.entries[0].日期 == result.entries[1].日期

        # 驗證日期格式 YYYY-MM-DD
        date = result.entries[0].日期
        assert len(date.split("-")) == 3

    @patch('app.gpt_processor.OpenAI')
    def test_shared_note_markers(self, mock_openai):
        """TC-V15-023: 附註標記驗證"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {"品項": "早餐", "原幣別": "TWD", "原幣金額": 80, "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""},
    {"品項": "午餐", "原幣別": "TWD", "原幣金額": 150, "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出", "明細說明": "", "代墊狀態": "無", "收款支付對象": ""}
  ]
}
''')

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # v1.9.0: 驗證附註標記（包含批次ID）
        assert "多項目支出 1/2" in result.entries[0].附註
        assert "多項目支出 2/2" in result.entries[1].附註
        assert "批次ID:" in result.entries[0].附註
        assert "批次ID:" in result.entries[1].附註


class TestCashflowTransactionIds:
    """現金流交易ID測試"""

    def test_cashflow_withdrawal_transaction_ids(self):
        """提款雙筆：交易ID應使用批次ID-序號"""
        result = process_multi_expense("合庫提款 5000")

        assert result.intent == "cashflow_intents"
        assert len(result.entries) == 2
        assert result.entries[0].交易ID.endswith("-01")
        assert result.entries[1].交易ID.endswith("-02")

        batch_id_1 = result.entries[0].交易ID.rsplit("-", 1)[0]
        batch_id_2 = result.entries[1].交易ID.rsplit("-", 1)[0]
        assert batch_id_1 == batch_id_2

    def test_cashflow_transfer_account_transaction_ids(self):
        """帳戶間轉帳：交易ID應使用批次ID-序號"""
        result = process_multi_expense("合庫轉帳到富邦 2000")

        assert result.intent == "cashflow_intents"
        assert len(result.entries) == 2
        assert result.entries[0].交易ID.endswith("-01")
        assert result.entries[1].交易ID.endswith("-02")

        batch_id_1 = result.entries[0].交易ID.rsplit("-", 1)[0]
        batch_id_2 = result.entries[1].交易ID.rsplit("-", 1)[0]
        assert batch_id_1 == batch_id_2

@patch('app.config.USE_PARSER_FIRST', False)
class TestMultiExpenseErrorHandling:
    """測試錯誤處理與邊界案例"""

    @patch('app.gpt_processor.OpenAI')
    def test_different_payment_methods_error(self, mock_openai):
        """TC-V15-030: ❌ 不同付款方式（錯誤）"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "error",
  "message": "偵測到不同付款方式，請分開記帳"
}
''')

        result = process_multi_expense("早餐80元現金，午餐150元刷卡")

        assert result.intent == "error"
        assert "不同付款方式" in result.error_message or "分開記帳" in result.error_message

    @patch('app.gpt_processor.OpenAI')
    def test_missing_amount_error(self, mock_openai):
        """TC-V15-031: ❌ 第二項缺少金額（錯誤）"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "error",
  "message": "第2個項目缺少金額，請提供完整資訊"
}
''')

        result = process_multi_expense("早餐80元，午餐，現金")

        assert result.intent == "error"
        assert "缺少金額" in result.error_message or "完整資訊" in result.error_message

    @patch('app.gpt_processor.OpenAI')
    def test_compound_item_with_and(self, mock_openai):
        """TC-V15-032: ✅ 「和」連接詞視為單項目"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("三明治和咖啡80元現金")

        # 應該是單項目，不是錯誤
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].原幣金額 == 80

    @patch('app.gpt_processor.OpenAI')
    def test_missing_payment_method_error(self, mock_openai):
        """TC-V15-033: ❌ 缺少付款方式"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "error",
  "message": "缺少付款方式，請提供完整資訊"
}
''')

        result = process_multi_expense("早餐80元，午餐150元")

        assert result.intent == "error"
        assert "缺少付款方式" in result.error_message or "付款方式" in result.error_message


class TestMultiExpenseConversation:
    """測試對話意圖識別"""

    @patch('app.gpt_processor.OpenAI')
    def test_greeting(self, mock_openai):
        """TC-V15-040: 打招呼"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "conversation",
  "response": "您好！有什麼可以協助您的嗎？"
}
''')

        result = process_multi_expense("你好")

        assert result.intent == "conversation"
        assert result.response_text is not None
        assert len(result.entries) == 0

    @patch('app.gpt_processor.OpenAI')
    def test_function_inquiry(self, mock_openai):
        """TC-V15-041: 詢問功能"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "conversation",
  "response": "我可以幫您記錄日常開支，只要告訴我品項、金額和付款方式即可！"
}
''')

        result = process_multi_expense("可以幫我做什麼？")

        assert result.intent == "conversation"
        assert result.response_text is not None

    @patch('app.gpt_processor.OpenAI')
    def test_thanks(self, mock_openai):
        """TC-V15-042: 感謝"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "conversation",
  "response": "不客氣！有需要隨時找我幫忙記帳喔！"
}
''')

        result = process_multi_expense("謝謝")

        assert result.intent == "conversation"
        assert result.response_text is not None


class TestMultiExpenseComplexScenarios:
    """測試複雜場景"""

    @patch('app.gpt_processor.OpenAI')
    def test_items_with_detail_description(self, mock_openai):
        """TC-V15-050: 含明細說明的多項目"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 50,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "明細說明": "開飯",
      "原幣別": "TWD",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "咖啡",
      "原幣金額": 45,
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理",
      "明細說明": "7-11",
      "原幣別": "TWD",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("在開飯早餐50元，在7-11買咖啡45元，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # 驗證明細說明
        assert result.entries[0].明細說明 == "開飯"
        assert "7-11" in result.entries[1].明細說明 or result.entries[1].明細說明 == "7-11"

    @patch('app.gpt_processor.OpenAI')
    def test_items_with_different_categories(self, mock_openai):
        """TC-V15-051: 含不同分類的多項目"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "台新狗卡",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    },
    {
      "品項": "蛋糕",
      "原幣金額": 120,
      "分類": "家庭/點心",
      "必要性": "想吃想買但合理",
      "原幣別": "TWD",
      "明細說明": "",
      "代墊狀態": "無",
      "收款支付對象": ""
    }
  ]
}
''')

        result = process_multi_expense("咖啡50元，蛋糕120元，狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # 驗證不同分類
        assert "飲品" in result.entries[0].分類 or "咖啡" in result.entries[0].分類
        assert "點心" in result.entries[1].分類


class _MovedTestAdvancePayment:
    """測試代墊功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_basic(self, mock_openai):
        """TC-V17-001: 基本代墊 - 代妹購買Pizza兌換券"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "Pizza兌換券",
      "原幣金額": 979,
      "分類": "家庭支出",
      "必要性": "想吃想買但合理",
      "代墊狀態": "代墊",
      "收款支付對象": "妹",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("代妹購買Pizza兌換券979元現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "Pizza兌換券"
        assert result.entries[0].原幣金額 == 979
        assert result.entries[0].付款方式 == "現金"
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "妹"

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_colleague(self, mock_openai):
        """TC-V17-002: 幫同事墊付計程車費"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "計程車費",
      "原幣金額": 300,
      "分類": "交通/接駁",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "同事",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("幫同事墊付計程車費300元現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_lunch_with_card(self, mock_openai):
        """TC-V17-003: 代朋友買午餐刷狗卡"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "台新狗卡",
  "items": [
    {
      "品項": "午餐",
      "原幣金額": 150,
      "分類": "個人/餐飲",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "朋友",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("代朋友買了午餐150元刷狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_coffee_line_transfer(self, mock_openai):
        """TC-V17-004: 代購咖啡給三位同事 Line Pay"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "Line Pay",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "明細說明": "給三位同事",
      "分類": "家庭/飲品",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "同事",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("代購咖啡50元給三位同事，Line Pay")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "Line Pay"


class _MovedTestNeedToPay:
    """測試需支付功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_need_to_pay_basic(self, mock_openai):
        """TC-V17-005: 基本需支付 - 弟代訂房間"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "NA",
  "items": [
    {
      "品項": "日本白馬房間",
      "原幣金額": 10000,
      "分類": "行程/住宿",
      "必要性": "必要日常支出",
      "代墊狀態": "需支付",
      "收款支付對象": "弟",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("弟代訂日本白馬房間10000元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "日本白馬房間"
        assert result.entries[0].原幣金額 == 10000
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "弟"
        assert result.entries[0].付款方式 == "NA"

    @patch('app.gpt_processor.OpenAI')
    def test_need_to_pay_friend_ticket(self, mock_openai):
        """TC-V17-006: 朋友幫我買演唱會門票"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "NA",
  "items": [
    {
      "品項": "演唱會門票",
      "原幣金額": 3000,
      "分類": "個人/娛樂",
      "必要性": "想吃想買但合理",
      "代墊狀態": "需支付",
      "收款支付對象": "朋友",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("朋友幫我買了演唱會門票3000元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "NA"

    @patch('app.gpt_processor.OpenAI')
    def test_need_to_pay_colleague_lunch(self, mock_openai):
        """TC-V17-007: 同事先墊午餐費"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "NA",
  "items": [
    {
      "品項": "午餐",
      "原幣金額": 120,
      "分類": "個人/餐飲",
      "必要性": "必要日常支出",
      "代墊狀態": "需支付",
      "收款支付對象": "同事",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("同事先墊了午餐120元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "同事"


class _MovedTestNoCollection:
    """測試不索取功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_no_collection_basic(self, mock_openai):
        """TC-V17-008: 基本不索取 - 幫媽媽買藥不用還"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "藥品",
      "原幣金額": 500,
      "分類": "健康/醫療/家庭成員",
      "必要性": "必要日常支出",
      "代墊狀態": "不索取",
      "收款支付對象": "媽媽",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("幫媽媽買藥500元現金，不用還")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "媽媽"
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_no_collection_parking(self, mock_openai):
        """TC-V17-009: 幫老婆付停車費不索取"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "停車費",
      "原幣金額": 100,
      "分類": "交通/停車",
      "必要性": "必要日常支出",
      "代墊狀態": "不索取",
      "收款支付對象": "老婆",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("幫老婆付停車費100元，不索取")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "老婆"


class _MovedTestMultiItemWithAdvance:
    """測試多項目含代墊（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_partial_advance_payment(self, mock_openai):
        """TC-V17-010: 部分項目代墊 - 早餐自己午餐代墊"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "原幣別": "TWD",
      "明細說明": ""
    },
    {
      "品項": "午餐",
      "原幣金額": 150,
      "分類": "個人/餐飲",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "同事",
      "原幣別": "TWD",
      "明細說明": ""
    }
  ]
}
''')

        result = process_multi_expense("早餐80元，午餐150元幫同事代墊，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2
        assert result.entries[0].代墊狀態 == "無"
        assert result.entries[0].收款支付對象 == ""
        assert result.entries[1].代墊狀態 == "代墊"
        assert result.entries[1].收款支付對象 == "同事"


class TestCompactFormatRecognition:
    """測試連寫格式識別（修復無空格格式問題）"""

    @patch('app.gpt_processor.OpenAI')
    def test_item_dollar_amount_payment_compact(self, mock_openai):
        """TC-COMPACT-001: 品項+$+金額+付款方式（無空格）"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "魚",
      "原幣金額": 395,
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": "",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("魚$395現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "魚"
        assert result.entries[0].原幣金額 == 395
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_item_amount_payment_fully_compact(self, mock_openai):
        """TC-COMPACT-002: 品項+金額+付款方式（完全連寫）"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "豬肉",
      "原幣金額": 1430,
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": "",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("豬肉1430現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "豬肉"
        assert result.entries[0].原幣金額 == 1430
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_item_space_amount_payment_compact(self, mock_openai):
        """TC-COMPACT-003: 品項+空格+金額付款連寫"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "菇",
      "原幣金額": 240,
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": "",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("菇 240現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "菇"
        assert result.entries[0].原幣金額 == 240
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_long_item_dollar_amount_payment_compact(self, mock_openai):
        """TC-COMPACT-004: 長品項+$+金額+付款方式"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "蔬果菇類",
      "原幣金額": 240,
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": "",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("蔬果菇類$240現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "蔬果菇類"
        assert result.entries[0].原幣金額 == 240
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_compact_format_with_nickname(self, mock_openai):
        """TC-COMPACT-005: 連寫格式+付款方式暱稱"""
        set_openai_mock_content(mock_openai, '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "台新狗卡",
  "items": [
    {
      "品項": "食材",
      "原幣金額": 500,
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": "",
      "原幣別": "TWD"
    }
  ]
}
''')

        result = process_multi_expense("食材$500狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "食材"
        assert result.entries[0].原幣金額 == 500
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_all_six_failing_formats(self, mock_openai):
        """TC-COMPACT-006: 驗證原始 6 種失敗格式"""
        test_cases = [
            ("魚$395現金", "魚", 395, "現金"),
            ("豬肉1430現金", "豬肉", 1430, "現金"),
            ("雞肉$770現金", "雞肉", 770, "現金"),
            ("菇 240現金", "菇", 240, "現金"),
            ("蔬果菇類$240現金", "蔬果菇類", 240, "現金"),
            ("菇類240現金", "菇類", 240, "現金"),
        ]

        for user_input, expected_item, expected_amount, expected_payment in test_cases:
            set_openai_mock_content(mock_openai, f'''
{{
  "intent": "multi_bookkeeping",
  "payment_method": "{expected_payment}",
  "items": [
    {{
      "品項": "{expected_item}",
      "原幣金額": {expected_amount},
      "分類": "家庭/食材",
      "必要性": "必要日常支出",
      "代墊狀態": "無",
      "收款支付對象": "",
      "明細說明": ""
    }}
  ]
}}
''')

            result = process_multi_expense(user_input)

            assert result.intent == "multi_bookkeeping", f"Failed for: {user_input}"
            assert len(result.entries) == 1, f"Failed for: {user_input}"
            assert result.entries[0].品項 == expected_item, f"Failed for: {user_input}"
            assert result.entries[0].原幣金額 == expected_amount, f"Failed for: {user_input}"
            assert result.entries[0].付款方式 == expected_payment, f"Failed for: {user_input}"
