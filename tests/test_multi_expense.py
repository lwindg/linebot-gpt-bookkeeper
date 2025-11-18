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

import pytest
from unittest.mock import Mock, patch
from app.gpt_processor import process_multi_expense, MultiExpenseResult, BookkeepingEntry


class TestMultiExpenseSingleItem:
    """測試單項目記帳（向後相容 v1）"""

    @patch('app.gpt_processor.OpenAI')
    def test_single_item_standard_format(self, mock_openai):
        """TC-V15-001: v1 格式兼容 - 標準記帳"""
        # Mock GPT 回應
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "午餐",
      "原幣金額": 120,
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

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
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "點心",
      "原幣金額": 200,
      "付款方式": "台新狗卡",
      "分類": "家庭/點心",
      "必要性": "想吃想買但合理"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("點心200元狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "點心"
        assert result.entries[0].原幣金額 == 200
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_single_item_natural_language(self, mock_openai):
        """TC-V15-003: v1 格式兼容 - 自然語句"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "付款方式": "Line 轉帳",
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("買了咖啡50元，Line轉帳")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "咖啡"
        assert result.entries[0].付款方式 == "Line 轉帳"


class TestMultiExpenseMultipleItems:
    """測試多項目記帳（核心功能）"""

    @patch('app.gpt_processor.OpenAI')
    def test_two_items_comma_separated(self, mock_openai):
        """TC-V15-010: 雙項目 - 逗號分隔"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "付款方式": "現金",
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出"
    },
    {
      "品項": "午餐",
      "原幣金額": 150,
      "付款方式": "現金",
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

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

        # 驗證共用交易ID
        assert result.entries[0].交易ID == result.entries[1].交易ID
        assert result.entries[0].交易ID is not None

    @patch('app.gpt_processor.OpenAI')
    def test_payment_method_at_beginning(self, mock_openai):
        """TC-V15-011: 雙項目 - 付款方式在前"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "付款方式": "台新狗卡",
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理"
    },
    {
      "品項": "三明治",
      "原幣金額": 35,
      "付款方式": "台新狗卡",
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("用狗卡，咖啡50，三明治35")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2
        assert result.entries[0].付款方式 == result.entries[1].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_three_items_breakfast_lunch_dinner(self, mock_openai):
        """TC-V15-012: 三項目 - 早午晚餐"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 50,
      "付款方式": "現金",
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出"
    },
    {
      "品項": "午餐",
      "原幣金額": 120,
      "付款方式": "現金",
      "分類": "家庭/餐飲/午餐",
      "必要性": "必要日常支出"
    },
    {
      "品項": "晚餐",
      "原幣金額": 200,
      "付款方式": "現金",
      "分類": "家庭/餐飲/晚餐",
      "必要性": "必要日常支出"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐50元，午餐120元，晚餐200元，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 3

        # 驗證所有項目共用付款方式
        assert all(e.付款方式 == "現金" for e in result.entries)

        # 驗證所有項目共用交易ID
        transaction_ids = [e.交易ID for e in result.entries]
        assert len(set(transaction_ids)) == 1  # 所有ID相同

    @patch('app.gpt_processor.OpenAI')
    def test_four_items_or_more(self, mock_openai):
        """TC-V15-052: 四項目以上"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {"品項": "咖啡", "原幣金額": 50, "付款方式": "現金", "分類": "家庭/飲品/咖啡", "必要性": "想吃想買但合理"},
    {"品項": "三明治", "原幣金額": 35, "付款方式": "現金", "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出"},
    {"品項": "沙拉", "原幣金額": 80, "付款方式": "現金", "分類": "家庭/餐飲", "必要性": "必要日常支出"},
    {"品項": "果汁", "原幣金額": 40, "付款方式": "現金", "分類": "家庭/飲品", "必要性": "想吃想買但合理"}
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("咖啡50、三明治35、沙拉80、果汁40、現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 4
        assert all(e.付款方式 == "現金" for e in result.entries)

        # 驗證所有項目共用交易ID
        transaction_ids = [e.交易ID for e in result.entries]
        assert len(set(transaction_ids)) == 1


class TestMultiExpenseSharedValidation:
    """測試共用付款方式驗證"""

    @patch('app.gpt_processor.OpenAI')
    def test_shared_transaction_id(self, mock_openai):
        """TC-V15-020: 共用交易ID驗證"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {"品項": "早餐", "原幣金額": 80, "付款方式": "現金", "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出"},
    {"品項": "午餐", "原幣金額": 150, "付款方式": "現金", "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出"}
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # 驗證交易ID格式 YYYYMMDD-HHMMSS
        assert result.entries[0].交易ID == result.entries[1].交易ID
        assert "-" in result.entries[0].交易ID

        # 驗證交易ID格式
        transaction_id = result.entries[0].交易ID
        date_part, time_part = transaction_id.split("-")
        assert len(date_part) == 8  # YYYYMMDD
        assert len(time_part) == 6  # HHMMSS

    @patch('app.gpt_processor.OpenAI')
    def test_shared_date(self, mock_openai):
        """TC-V15-021: 共用日期驗證"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {"品項": "早餐", "原幣金額": 80, "付款方式": "現金", "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出"},
    {"品項": "午餐", "原幣金額": 150, "付款方式": "現金", "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出"}
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # 驗證兩個項目的日期相同
        assert result.entries[0].日期 == result.entries[1].日期

        # 驗證日期格式 YYYY-MM-DD
        date = result.entries[0].日期
        assert len(date.split("-")) == 3

    @patch('app.gpt_processor.OpenAI')
    def test_shared_note_markers(self, mock_openai):
        """TC-V15-023: 附註標記驗證"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {"品項": "早餐", "原幣金額": 80, "付款方式": "現金", "分類": "家庭/餐飲/早餐", "必要性": "必要日常支出"},
    {"品項": "午餐", "原幣金額": 150, "付款方式": "現金", "分類": "家庭/餐飲/午餐", "必要性": "必要日常支出"}
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐150元，現金")

        # 驗證附註標記
        assert "多項目支出 1/2" in result.entries[0].附註
        assert "多項目支出 2/2" in result.entries[1].附註


class TestMultiExpenseErrorHandling:
    """測試錯誤處理與邊界案例"""

    @patch('app.gpt_processor.OpenAI')
    def test_different_payment_methods_error(self, mock_openai):
        """TC-V15-030: ❌ 不同付款方式（錯誤）"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "error",
  "message": "偵測到不同付款方式，請分開記帳"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元現金，午餐150元刷卡")

        assert result.intent == "error"
        assert "不同付款方式" in result.error_message or "分開記帳" in result.error_message

    @patch('app.gpt_processor.OpenAI')
    def test_missing_amount_error(self, mock_openai):
        """TC-V15-031: ❌ 第二項缺少金額（錯誤）"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "error",
  "message": "第2個項目缺少金額，請提供完整資訊"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐，現金")

        assert result.intent == "error"
        assert "缺少金額" in result.error_message or "完整資訊" in result.error_message

    @patch('app.gpt_processor.OpenAI')
    def test_compound_item_with_and(self, mock_openai):
        """TC-V15-032: ✅ 「和」連接詞視為單項目"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "付款方式": "現金",
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("三明治和咖啡80元現金")

        # 應該是單項目，不是錯誤
        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].原幣金額 == 80

    @patch('app.gpt_processor.OpenAI')
    def test_missing_payment_method_error(self, mock_openai):
        """TC-V15-033: ❌ 缺少付款方式"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "error",
  "message": "缺少付款方式，請提供完整資訊"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐150元")

        assert result.intent == "error"
        assert "缺少付款方式" in result.error_message or "付款方式" in result.error_message


class TestMultiExpenseConversation:
    """測試對話意圖識別"""

    @patch('app.gpt_processor.OpenAI')
    def test_greeting(self, mock_openai):
        """TC-V15-040: 打招呼"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "conversation",
  "response": "您好！有什麼可以協助您的嗎？"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("你好")

        assert result.intent == "conversation"
        assert result.response_text is not None
        assert len(result.entries) == 0

    @patch('app.gpt_processor.OpenAI')
    def test_function_inquiry(self, mock_openai):
        """TC-V15-041: 詢問功能"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "conversation",
  "response": "我可以幫您記錄日常開支，只要告訴我品項、金額和付款方式即可！"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("可以幫我做什麼？")

        assert result.intent == "conversation"
        assert result.response_text is not None

    @patch('app.gpt_processor.OpenAI')
    def test_thanks(self, mock_openai):
        """TC-V15-042: 感謝"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "conversation",
  "response": "不客氣！有需要隨時找我幫忙記帳喔！"
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("謝謝")

        assert result.intent == "conversation"
        assert result.response_text is not None


class TestMultiExpenseComplexScenarios:
    """測試複雜場景"""

    @patch('app.gpt_processor.OpenAI')
    def test_items_with_detail_description(self, mock_openai):
        """TC-V15-050: 含明細說明的多項目"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 50,
      "付款方式": "現金",
      "分類": "家庭/餐飲/早餐",
      "必要性": "必要日常支出",
      "明細說明": "開飯"
    },
    {
      "品項": "咖啡",
      "原幣金額": 45,
      "付款方式": "現金",
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理",
      "明細說明": "7-11"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("在開飯早餐50元，在7-11買咖啡45元，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # 驗證明細說明
        assert result.entries[0].明細說明 == "開飯"
        assert "7-11" in result.entries[1].明細說明 or result.entries[1].明細說明 == "7-11"

    @patch('app.gpt_processor.OpenAI')
    def test_items_with_different_categories(self, mock_openai):
        """TC-V15-051: 含不同分類的多項目"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "付款方式": "台新狗卡",
      "分類": "家庭/飲品/咖啡",
      "必要性": "想吃想買但合理"
    },
    {
      "品項": "蛋糕",
      "原幣金額": 120,
      "付款方式": "台新狗卡",
      "分類": "家庭/點心",
      "必要性": "想吃想買但合理"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("咖啡50元，蛋糕120元，狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2

        # 驗證不同分類
        assert "飲品" in result.entries[0].分類 or "咖啡" in result.entries[0].分類
        assert "點心" in result.entries[1].分類


class TestAdvancePayment:
    """測試代墊功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_basic(self, mock_openai):
        """TC-V17-001: 基本代墊 - 代妹購買Pizza兌換券"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "妹"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

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
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "同事"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("幫同事墊付計程車費300元現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_lunch_with_card(self, mock_openai):
        """TC-V17-003: 代朋友買午餐刷狗卡"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "朋友"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("代朋友買了午餐150元刷狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch('app.gpt_processor.OpenAI')
    def test_advance_payment_coffee_line_transfer(self, mock_openai):
        """TC-V17-004: 代購咖啡給三位同事 Line轉帳"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
{
  "intent": "multi_bookkeeping",
  "payment_method": "Line 轉帳",
  "items": [
    {
      "品項": "咖啡",
      "原幣金額": 50,
      "明細說明": "給三位同事",
      "分類": "家庭/飲品",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "同事"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("代購咖啡50元給三位同事，Line轉帳")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "Line 轉帳"


class TestNeedToPay:
    """測試需支付功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_need_to_pay_basic(self, mock_openai):
        """TC-V17-005: 基本需支付 - 弟代訂房間"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "弟"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

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
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "朋友"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("朋友幫我買了演唱會門票3000元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "NA"

    @patch('app.gpt_processor.OpenAI')
    def test_need_to_pay_colleague_lunch(self, mock_openai):
        """TC-V17-007: 同事先墊午餐費"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "同事"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("同事先墊了午餐120元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "同事"


class TestNoCollection:
    """測試不索取功能（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_no_collection_basic(self, mock_openai):
        """TC-V17-008: 基本不索取 - 幫媽媽買藥不用還"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "媽媽"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("幫媽媽買藥500元現金，不用還")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "媽媽"
        assert result.entries[0].付款方式 == "現金"

    @patch('app.gpt_processor.OpenAI')
    def test_no_collection_parking(self, mock_openai):
        """TC-V17-009: 幫老婆付停車費不索取"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": "老婆"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("幫老婆付停車費100元，不索取")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "老婆"


class TestMultiItemWithAdvance:
    """測試多項目含代墊（v1.7 新增）"""

    @patch('app.gpt_processor.OpenAI')
    def test_partial_advance_payment(self, mock_openai):
        """TC-V17-010: 部分項目代墊 - 早餐自己午餐代墊"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
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
      "收款支付對象": ""
    },
    {
      "品項": "午餐",
      "原幣金額": 150,
      "分類": "個人/餐飲",
      "必要性": "必要日常支出",
      "代墊狀態": "代墊",
      "收款支付對象": "同事"
    }
  ]
}
'''
        mock_client.chat.completions.create.return_value = mock_response

        result = process_multi_expense("早餐80元，午餐150元幫同事代墊，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2
        assert result.entries[0].代墊狀態 == "無"
        assert result.entries[0].收款支付對象 == ""
        assert result.entries[1].代墊狀態 == "代墊"
        assert result.entries[1].收款支付對象 == "同事"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
