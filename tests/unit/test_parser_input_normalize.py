# -*- coding: utf-8 -*-

from app.parser.normalize_input import normalize_parser_input
from app.processor import process_with_parser


def test_normalize_inserts_space_after_dollar() -> None:
    assert normalize_parser_input("花菜$150") == "花菜 $150"


def test_normalize_splits_amount_and_cash() -> None:
    assert normalize_parser_input("菇類$250現金") == "菇類 $250 現金"


def test_parser_first_accepts_glued_amount_and_payment() -> None:
    res = process_with_parser("花菜$150\n菇類$250現金", skip_gpt=True, user_id="U")
    assert res.intent == "multi_bookkeeping"
    assert len(res.entries) == 2
    assert res.entries[0].品項 == "花菜"
    assert res.entries[0].原幣金額 == 150.0
    assert res.entries[0].付款方式 == "現金"
    assert res.entries[1].品項 == "菇類"
    assert res.entries[1].原幣金額 == 250.0
    assert res.entries[1].付款方式 == "現金"
