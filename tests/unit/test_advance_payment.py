#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v1.7 Advance payment / payment status unit tests

Scope:
- process_multi_expense() with advance payment status
- need-to-pay / no-collection flows
- multi-item mixed status
"""

from unittest.mock import patch

from app.gpt_processor import process_multi_expense
from tests.test_utils import set_openai_mock_content


class TestAdvancePayment:
    """測試代墊功能（v1.7 新增）"""

    @patch("app.gpt_processor.OpenAI")
    def test_advance_payment_basic(self, mock_openai):
        """TC-V17-001: 基本代墊 - 代妹購買Pizza兌換券"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("代妹購買Pizza兌換券979元現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "Pizza兌換券"
        assert result.entries[0].原幣金額 == 979
        assert result.entries[0].付款方式 == "現金"
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "妹"

    @patch("app.gpt_processor.OpenAI")
    def test_advance_payment_colleague(self, mock_openai):
        """TC-V17-002: 幫同事墊付計程車費"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("幫同事墊付計程車費300元現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "現金"

    @patch("app.gpt_processor.OpenAI")
    def test_advance_payment_lunch_with_card(self, mock_openai):
        """TC-V17-003: 代朋友買午餐刷狗卡"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("代朋友買了午餐150元刷狗卡")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "台新狗卡"

    @patch("app.gpt_processor.OpenAI")
    def test_advance_payment_coffee_line_transfer(self, mock_openai):
        """TC-V17-004: 代購咖啡給三位同事 Line轉帳"""
        set_openai_mock_content(
            mock_openai,
            """
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
      "收款支付對象": "同事",
      "原幣別": "TWD"
    }
  ]
}
""",
        )

        result = process_multi_expense("代購咖啡50元給三位同事，Line轉帳")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "代墊"
        assert result.entries[0].收款支付對象 == "同事"
        assert result.entries[0].付款方式 == "Line 轉帳"


class TestNeedToPay:
    """測試需支付功能（v1.7 新增）"""

    @patch("app.gpt_processor.OpenAI")
    def test_need_to_pay_basic(self, mock_openai):
        """TC-V17-005: 基本需支付 - 弟代訂房間"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("弟代訂日本白馬房間10000元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].品項 == "日本白馬房間"
        assert result.entries[0].原幣金額 == 10000
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "弟"
        assert result.entries[0].付款方式 == "NA"

    @patch("app.gpt_processor.OpenAI")
    def test_need_to_pay_friend_ticket(self, mock_openai):
        """TC-V17-006: 朋友幫我買演唱會門票"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("朋友幫我買了演唱會門票3000元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "朋友"
        assert result.entries[0].付款方式 == "NA"

    @patch("app.gpt_processor.OpenAI")
    def test_need_to_pay_colleague_lunch(self, mock_openai):
        """TC-V17-007: 同事先墊午餐費"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("同事先墊了午餐120元")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "需支付"
        assert result.entries[0].收款支付對象 == "同事"


class TestNoCollection:
    """測試不索取功能（v1.7 新增）"""

    @patch("app.gpt_processor.OpenAI")
    def test_no_collection_basic(self, mock_openai):
        """TC-V17-008: 基本不索取 - 幫媽媽買藥不用還"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("幫媽媽買藥500元現金，不用還")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "媽媽"
        assert result.entries[0].付款方式 == "現金"

    @patch("app.gpt_processor.OpenAI")
    def test_no_collection_parking(self, mock_openai):
        """TC-V17-009: 幫老婆付停車費不索取"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("幫老婆付停車費100元，不索取")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 1
        assert result.entries[0].代墊狀態 == "不索取"
        assert result.entries[0].收款支付對象 == "老婆"
        assert result.entries[0].付款方式 == "現金"


class TestMultiItemWithAdvance:
    """測試多項目含代墊（v1.7 新增）"""

    @patch("app.gpt_processor.OpenAI")
    def test_partial_advance_payment(self, mock_openai):
        """TC-V17-010: 部分項目代墊 - 早餐自己午餐代墊"""
        set_openai_mock_content(
            mock_openai,
            """
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
""",
        )

        result = process_multi_expense("早餐80元，午餐150元幫同事代墊，現金")

        assert result.intent == "multi_bookkeeping"
        assert len(result.entries) == 2
        assert result.entries[0].代墊狀態 == "無"
        assert result.entries[0].收款支付對象 == ""
        assert result.entries[1].代墊狀態 == "代墊"
        assert result.entries[1].收款支付對象 == "同事"
