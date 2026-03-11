# -*- coding: utf-8 -*-

from app.cashflow_rules import infer_transfer_accounts


def test_infer_transfer_accounts_supports_dawho_netbank_to_card() -> None:
    source, target = infer_transfer_accounts("大戶網銀繳卡費到大戶信用卡 23003")
    assert source == "大戶網銀"
    assert target == "大戶信用卡"
