# -*- coding: utf-8 -*-

from app.parser.extract_cashflow import extract_exchange_transfer_details


def test_extract_exchange_transfer_details_for_crypto_exchange() -> None:
    src_amt, src_cur, tgt_amt, tgt_cur = extract_exchange_transfer_details(
        "MAX 4294.712 換比特幣 0.002",
        target_account="比特幣",
    )

    assert src_amt == 4294.712
    assert src_cur == "TWD"
    assert tgt_amt == 0.002
    assert tgt_cur == "BTC"
