# -*- coding: utf-8 -*-
"""
Unit tests for extract_advance module.
"""

import pytest
from app.parser.extract_advance import extract_advance_status


class TestExtractAdvanceStatus:
    """Tests for extract_advance_status function based on prompts.py rules."""

    # === 代墊 (I paid for someone) ===
    # Pattern: (幫|代) + 對象 + (買|付|墊|代墊)

    def test_advance_paid_help_buy(self):
        """幫同事買便當 -> 代墊, 同事"""
        status, who = extract_advance_status("幫同事買便當 100")
        assert status == "代墊"
        assert who == "同事"

    def test_advance_paid_help_pay(self):
        """幫媽付藥錢 -> 代墊, 媽"""
        status, who = extract_advance_status("幫媽付藥錢 200")
        assert status == "代墊"
        assert who == "媽"

    def test_advance_paid_dai_buy(self):
        """代妹買飲料 -> 代墊, 妹"""
        status, who = extract_advance_status("代妹買飲料 50")
        assert status == "代墊"
        assert who == "妹"

    def test_advance_paid_help_dianfu(self):
        """幫同事墊付 -> 代墊, 同事"""
        status, who = extract_advance_status("幫同事墊付午餐 80")
        assert status == "代墊"
        assert who == "同事"

    # === 需支付 (Someone paid for me) ===
    # Pattern: 對象 + (代訂|代付|幫買|先墊)

    def test_advance_due_dai_ding(self):
        """弟代訂披薩 -> 需支付, 弟"""
        status, who = extract_advance_status("弟代訂披薩 500")
        assert status == "需支付"
        assert who == "弟"

    def test_advance_due_dai_fu(self):
        """妹代付電影票 -> 需支付, 妹"""
        status, who = extract_advance_status("妹代付電影票 300")
        assert status == "需支付"
        assert who == "妹"

    def test_advance_due_help_buy(self):
        """朋友幫買咖啡 -> 需支付, 朋友"""
        status, who = extract_advance_status("朋友幫買咖啡 120")
        assert status == "需支付"
        assert who == "朋友"

    def test_advance_due_xian_dian(self):
        """同事先墊便當 -> 需支付, 同事"""
        status, who = extract_advance_status("同事先墊便當 80")
        assert status == "需支付"
        assert who == "同事"

    # === 不索取 (No claim / Gift) ===

    def test_no_claim_buyonghuan(self):
        """幫媽買藥不用還 -> 不索取"""
        status, who = extract_advance_status("幫媽買藥不用還 200現金")
        assert status == "不索取"

    def test_no_claim_songgei(self):
        """送給弟禮物 -> 不索取"""
        status, who = extract_advance_status("送給弟禮物 500 大戶")
        assert status == "不索取"

    def test_no_claim_qingke(self):
        """請客午餐 -> 不索取"""
        status, who = extract_advance_status("請客午餐 500")
        assert status == "不索取"

    def test_no_claim_qingke_lunch(self):
        """請同事午餐 -> 不索取"""
        status, who = extract_advance_status("請同事午餐 500 狗卡")
        assert status == "不索取"

    def test_no_claim_qingke_drink(self):
        """請喝飲料 -> 不索取"""
        status, who = extract_advance_status("請同事喝飲料 100")
        assert status == "不索取"

    # === 無 (No advance keywords) ===

    def test_no_advance_simple(self):
        """午餐120元現金 -> 無"""
        status, who = extract_advance_status("午餐120元現金")
        assert status == "無"
        assert who == ""

    def test_no_advance_with_name(self):
        """妹9-10月諮商費18900合庫 -> 無 (妹 is subject, not advance)"""
        status, who = extract_advance_status("妹9-10月諮商費18900合庫")
        assert status == "無"

    def test_no_advance_empty(self):
        """空字串 -> 無"""
        status, who = extract_advance_status("")
        assert status == "無"
        assert who == ""
