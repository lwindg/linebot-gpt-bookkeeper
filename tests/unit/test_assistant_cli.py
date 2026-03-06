# -*- coding: utf-8 -*-

from app.assistant_cli import _apply_deterministic_keyword_categories, _normalize_bank_name, _bank_supported
from app.gpt.types import BookkeepingEntry


def _entry_with_category(category=None) -> BookkeepingEntry:
    return BookkeepingEntry(
        intent="bookkeeping",
        日期="2026-02-27",
        時間=None,
        品項="測試",
        原幣別="TWD",
        原幣金額=100.0,
        匯率=1.0,
        付款方式="現金",
        交易ID="T1",
        明細說明="",
        分類=category,
        交易類型="支出",
        專案="日常",
        必要性="必要日常支出",
        代墊狀態="無",
        收款支付對象="",
        附註="",
    )


def test_apply_deterministic_keyword_categories_meal(monkeypatch) -> None:
    def fake_rules():
        return {
            "rules": {
                "meal_three_layer": {
                    "patterns": [
                        {"pattern": "早餐", "category": "家庭/餐飲/早餐"},
                    ]
                }
            }
        }

    monkeypatch.setattr(
        "app.assistant_cli._load_classifications_yaml",
        fake_rules,
    )

    entries = [_entry_with_category(None), _entry_with_category("家庭/點心")]
    _apply_deterministic_keyword_categories(entries, text="早餐80")

    assert entries[0].分類 == "家庭/餐飲/早餐"
    assert entries[1].分類 == "家庭/點心"


def test_apply_deterministic_keyword_categories_food_rules(monkeypatch) -> None:
    def fake_rules():
        return {
            "rules": {
                "food_beverages": [
                    {"pattern": "咖啡", "category": "家庭/飲品"},
                ]
            }
        }

    monkeypatch.setattr(
        "app.assistant_cli._load_classifications_yaml",
        fake_rules,
    )

    entries = [_entry_with_category(None)]
    _apply_deterministic_keyword_categories(entries, text="咖啡50")

    assert entries[0].分類 == "家庭/飲品"


def test_normalize_bank_name_supports_huanan() -> None:
    assert _normalize_bank_name("台新") == "台新"
    assert _normalize_bank_name("taishin") == "台新"
    assert _normalize_bank_name("華南") == "華南"
    assert _normalize_bank_name("華南銀行") == "華南"
    assert _normalize_bank_name("huanan") == "華南"


def test_bank_supported_uses_credit_card_config(monkeypatch) -> None:
    monkeypatch.setattr("app.assistant_cli.get_bank_config", lambda bank: object() if bank in ("台新", "華南") else None)

    assert _bank_supported("台新") is True
    assert _bank_supported("華南") is True
    assert _bank_supported("unknown") is False
