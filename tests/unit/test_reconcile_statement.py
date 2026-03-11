# -*- coding: utf-8 -*-

import app.services.reconcile_statement as reconcile_mod


def test_reconcile_statement_ambiguous_marks_proposed_and_counts(monkeypatch) -> None:
    rows = [
        {
            "id": "stmt-1",
            "properties": {
                "付款方式": {"select": {"name": "富邦 Costco"}},
                "消費日": {"date": {"start": "2026-02-10"}},
                "新臺幣金額": {"number": 100},
                "幣別": {"select": {"name": "TWD"}},
                "消費明細": {"rich_text": [{"plain_text": "一般消費"}]},
                "是否手續費": {"checkbox": False},
                "對帳狀態": {"select": {"name": "unmatched"}},
            },
        }
    ]

    ledgers = [
        {
            "id": "ledger-1",
            "properties": {
                "原幣別": {"select": {"name": "TWD"}},
                "原幣金額": {"number": 100},
            },
        },
        {
            "id": "ledger-2",
            "properties": {
                "原幣別": {"select": {"name": "TWD"}},
                "原幣金額": {"number": 100},
            },
        },
    ]

    ensured_banks: list[str] = []

    def fake_ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
        ensured_banks.append(bank)
        return "statement-page-1"

    def fake_fetch_statement_lines(statement_id: str):
        return rows

    def fake_fetch_ledger_candidates(*, payment_method: str, day):
        return ledgers

    def fake_notion_patch_page(page_id: str, properties):
        for row in rows:
            if row["id"] != page_id:
                continue
            if "對帳狀態" in properties:
                row["properties"]["對帳狀態"] = properties["對帳狀態"]
            if "所屬帳單" in properties:
                row["properties"]["所屬帳單"] = properties["所屬帳單"]
            if "對應帳目" in properties:
                row["properties"]["對應帳目"] = properties["對應帳目"]

    monkeypatch.setattr(reconcile_mod, "NOTION_TOKEN", "test-token")
    monkeypatch.setattr(reconcile_mod, "_ensure_statement_page", fake_ensure_statement_page)
    monkeypatch.setattr(reconcile_mod, "_fetch_statement_lines", fake_fetch_statement_lines)
    monkeypatch.setattr(reconcile_mod, "_fetch_ledger_candidates", fake_fetch_ledger_candidates)
    monkeypatch.setattr(reconcile_mod, "_notion_patch_page", fake_notion_patch_page)
    monkeypatch.setattr(reconcile_mod, "_allocate_foreign_fee_lines", lambda **kwargs: 0)
    monkeypatch.setattr(reconcile_mod, "_backfill_unmatched_statement_lines", lambda **kwargs: 0)

    summary = reconcile_mod.reconcile_statement(
        statement_id="fubon-2026-02-20260309-220000",
        period="2026-02",
        payment_methods=["富邦 Costco"],
        bank="富邦",
    )

    assert ensured_banks == ["富邦"]
    assert rows[0]["properties"]["對帳狀態"]["select"]["name"] == "proposed"
    assert summary.statement_lines_total == 1
    assert summary.matched == 0
    assert summary.ambiguous == 1
    assert summary.unmatched == 0


def test_reconcile_statement_preserves_ignored_status(monkeypatch) -> None:
    rows = [
        {
            "id": "stmt-ignored",
            "properties": {
                "付款方式": {"select": {"name": "富邦 Costco"}},
                "消費日": {"date": {"start": "2026-02-10"}},
                "新臺幣金額": {"number": -194},
                "幣別": {"select": {"name": "TWD"}},
                "消費明細": {"rich_text": [{"plain_text": "繳款"}]},
                "是否手續費": {"checkbox": False},
                "對帳狀態": {"select": {"name": "ignored"}},
            },
        }
    ]

    def fake_ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
        return "statement-page-1"

    def fake_fetch_statement_lines(statement_id: str):
        return rows

    def fake_fetch_ledger_candidates(*, payment_method: str, day):  # noqa: ARG001
        return []

    def fake_notion_patch_page(page_id: str, properties):
        for row in rows:
            if row["id"] != page_id:
                continue
            if "對帳狀態" in properties:
                row["properties"]["對帳狀態"] = properties["對帳狀態"]
            if "所屬帳單" in properties:
                row["properties"]["所屬帳單"] = properties["所屬帳單"]

    monkeypatch.setattr(reconcile_mod, "NOTION_TOKEN", "test-token")
    monkeypatch.setattr(reconcile_mod, "_ensure_statement_page", fake_ensure_statement_page)
    monkeypatch.setattr(reconcile_mod, "_fetch_statement_lines", fake_fetch_statement_lines)
    monkeypatch.setattr(reconcile_mod, "_fetch_ledger_candidates", fake_fetch_ledger_candidates)
    monkeypatch.setattr(reconcile_mod, "_notion_patch_page", fake_notion_patch_page)
    monkeypatch.setattr(reconcile_mod, "_allocate_foreign_fee_lines", lambda **kwargs: 0)
    monkeypatch.setattr(reconcile_mod, "_backfill_unmatched_statement_lines", lambda **kwargs: 0)

    summary = reconcile_mod.reconcile_statement(
        statement_id="fubon-2026-02-20260310-220000",
        period="2026-02",
        payment_methods=["富邦 Costco"],
        bank="富邦",
    )

    assert rows[0]["properties"]["對帳狀態"]["select"]["name"] == "ignored"
    assert summary.statement_lines_total == 1
    assert summary.matched == 0
    assert summary.ambiguous == 0
    assert summary.unmatched == 0


def test_reconcile_statement_negative_transfer_marks_ignored(monkeypatch) -> None:
    rows = [
        {
            "id": "stmt-transfer",
            "properties": {
                "付款方式": {"select": {"name": "富邦 Costco"}},
                "消費日": {"date": {"start": "2026-02-18"}},
                "新臺幣金額": {"number": -1200},
                "幣別": {"select": {"name": "TWD"}},
                "消費明細": {"rich_text": [{"plain_text": "轉帳扣款"}]},
                "是否手續費": {"checkbox": False},
                "對帳狀態": {"select": {"name": "unmatched"}},
            },
        }
    ]

    def fake_ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
        return "statement-page-1"

    def fake_fetch_statement_lines(statement_id: str):  # noqa: ARG001
        return rows

    def fake_fetch_ledger_candidates(*, payment_method: str, day):  # noqa: ARG001
        return []

    def fake_notion_patch_page(page_id: str, properties):
        for row in rows:
            if row["id"] != page_id:
                continue
            if "對帳狀態" in properties:
                row["properties"]["對帳狀態"] = properties["對帳狀態"]
            if "所屬帳單" in properties:
                row["properties"]["所屬帳單"] = properties["所屬帳單"]

    monkeypatch.setattr(reconcile_mod, "NOTION_TOKEN", "test-token")
    monkeypatch.setattr(reconcile_mod, "_ensure_statement_page", fake_ensure_statement_page)
    monkeypatch.setattr(reconcile_mod, "_fetch_statement_lines", fake_fetch_statement_lines)
    monkeypatch.setattr(reconcile_mod, "_fetch_ledger_candidates", fake_fetch_ledger_candidates)
    monkeypatch.setattr(reconcile_mod, "_notion_patch_page", fake_notion_patch_page)
    monkeypatch.setattr(reconcile_mod, "_allocate_foreign_fee_lines", lambda **kwargs: 0)
    monkeypatch.setattr(reconcile_mod, "_backfill_unmatched_statement_lines", lambda **kwargs: 0)

    summary = reconcile_mod.reconcile_statement(
        statement_id="fubon-2026-02-20260310-230000",
        period="2026-02",
        payment_methods=["富邦 Costco"],
        bank="富邦",
    )

    assert rows[0]["properties"]["對帳狀態"]["select"]["name"] == "ignored"
    assert summary.statement_lines_total == 1
    assert summary.matched == 0
    assert summary.ambiguous == 0
    assert summary.unmatched == 0


def test_reconcile_statement_keeps_prelinked_relations_as_matched(monkeypatch) -> None:
    rows = [
        {
            "id": "stmt-prelinked",
            "properties": {
                "付款方式": {"select": {"name": "大戶信用卡"}},
                "消費日": {"date": {"start": "2026-02-02"}},
                "新臺幣金額": {"number": 0},
                "幣別": {"select": {"name": "TWD"}},
                "消費明細": {"rich_text": [{"plain_text": "大戶消費回饋入帳戶"}]},
                "是否手續費": {"checkbox": False},
                "對應帳目": {"relation": [{"id": "ledger-1"}]},
                "對帳狀態": {"select": {"name": "unmatched"}},
            },
        }
    ]
    ledger_pages = {
        "ledger-1": {
            "properties": {
                "對應帳單明細": {"relation": []},
                "對應帳單": {"relation": []},
            }
        }
    }

    def fake_ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
        return "statement-page-1"

    def fake_fetch_statement_lines(statement_id: str):  # noqa: ARG001
        return rows

    def fake_fetch_ledger_candidates(*, payment_method: str, day):  # noqa: ARG001
        return []

    def fake_notion_get_page(page_id: str):
        return ledger_pages[page_id]

    def fake_notion_patch_page(page_id: str, properties):
        if page_id == "stmt-prelinked":
            row = rows[0]
            if "對帳狀態" in properties:
                row["properties"]["對帳狀態"] = properties["對帳狀態"]
            if "所屬帳單" in properties:
                row["properties"]["所屬帳單"] = properties["所屬帳單"]
            if "對應帳目" in properties:
                row["properties"]["對應帳目"] = properties["對應帳目"]
            return
        if page_id == "ledger-1":
            page = ledger_pages["ledger-1"]["properties"]
            if "對應帳單明細" in properties:
                page["對應帳單明細"] = properties["對應帳單明細"]
            if "對應帳單" in properties:
                page["對應帳單"] = properties["對應帳單"]

    monkeypatch.setattr(reconcile_mod, "NOTION_TOKEN", "test-token")
    monkeypatch.setattr(reconcile_mod, "_ensure_statement_page", fake_ensure_statement_page)
    monkeypatch.setattr(reconcile_mod, "_fetch_statement_lines", fake_fetch_statement_lines)
    monkeypatch.setattr(reconcile_mod, "_fetch_ledger_candidates", fake_fetch_ledger_candidates)
    monkeypatch.setattr(reconcile_mod, "_notion_get_page", fake_notion_get_page)
    monkeypatch.setattr(reconcile_mod, "_notion_patch_page", fake_notion_patch_page)
    monkeypatch.setattr(reconcile_mod, "_allocate_foreign_fee_lines", lambda **kwargs: 0)
    monkeypatch.setattr(reconcile_mod, "_backfill_unmatched_statement_lines", lambda **kwargs: 0)

    summary = reconcile_mod.reconcile_statement(
        statement_id="sinopac-2026-02-20260311-103852",
        period="2026-02",
        payment_methods=["大戶信用卡"],
        bank="永豐",
    )

    assert rows[0]["properties"]["對帳狀態"]["select"]["name"] == "matched"
    stmt_rel = ledger_pages["ledger-1"]["properties"]["對應帳單"]["relation"]
    line_rel = ledger_pages["ledger-1"]["properties"]["對應帳單明細"]["relation"]
    assert {"id": "statement-page-1"} in stmt_rel
    assert {"id": "stmt-prelinked"} in line_rel
    assert summary.matched == 1
    assert summary.unmatched == 0


def test_reconcile_statement_fee_fallback_matches_by_tag_when_currency_missing(monkeypatch) -> None:
    rows = [
        {
            "id": "stmt-apple-main",
            "properties": {
                "付款方式": {"select": {"name": "大戶信用卡"}},
                "消費日": {"date": {"start": "2026-02-06"}},
                "新臺幣金額": {"number": 300},
                "幣別": {"select": None},
                "消費明細": {"rich_text": [{"plain_text": "APPLE.COM/BILL ITUNES.COM IE"}]},
                "是否手續費": {"checkbox": False},
                "對應帳目": {"relation": [{"id": "ledger-apple-1"}]},
                "對帳狀態": {"select": {"name": "matched"}},
            },
        },
        {
            "id": "stmt-apple-fee",
            "properties": {
                "付款方式": {"select": {"name": "大戶信用卡"}},
                "消費日": {"date": {"start": "2026-02-06"}},
                "新臺幣金額": {"number": 5},
                "幣別": {"select": None},
                "消費明細": {"rich_text": [{"plain_text": "APPLE.COM/BILL 國外交易服務費"}]},
                "是否手續費": {"checkbox": True},
                "對應帳目": {"relation": []},
                "對帳狀態": {"select": {"name": "unmatched"}},
            },
        },
    ]

    ledger_pages = {
        "ledger-apple-1": {
            "properties": {
                "原幣金額": {"number": 300},
                "手續費": {"number": 0},
                "對應帳單明細": {"relation": [{"id": "stmt-apple-main"}]},
                "對應帳單": {"relation": []},
            }
        }
    }

    def fake_ensure_statement_page(*, statement_id: str, period: str, bank: str = "台新") -> str:
        return "statement-page-1"

    def fake_fetch_statement_lines(statement_id: str):  # noqa: ARG001
        return rows

    def fake_fetch_ledger_candidates(*, payment_method: str, day):  # noqa: ARG001
        return []

    def fake_notion_get_page(page_id: str):
        if page_id in ledger_pages:
            return ledger_pages[page_id]
        for r in rows:
            if r["id"] == page_id:
                return r
        return {"properties": {}}

    def fake_notion_patch_page(page_id: str, properties):
        if page_id in ledger_pages:
            page = ledger_pages[page_id]["properties"]
            for k, v in properties.items():
                page[k] = v
            return
        for r in rows:
            if r["id"] == page_id:
                for k, v in properties.items():
                    r["properties"][k] = v
                return

    monkeypatch.setattr(reconcile_mod, "NOTION_TOKEN", "test-token")
    monkeypatch.setattr(reconcile_mod, "_ensure_statement_page", fake_ensure_statement_page)
    monkeypatch.setattr(reconcile_mod, "_fetch_statement_lines", fake_fetch_statement_lines)
    monkeypatch.setattr(reconcile_mod, "_fetch_ledger_candidates", fake_fetch_ledger_candidates)
    monkeypatch.setattr(reconcile_mod, "_notion_get_page", fake_notion_get_page)
    monkeypatch.setattr(reconcile_mod, "_notion_patch_page", fake_notion_patch_page)
    monkeypatch.setattr(reconcile_mod, "_backfill_unmatched_statement_lines", lambda **kwargs: 0)

    summary = reconcile_mod.reconcile_statement(
        statement_id="sinopac-2026-02-20260311-103852",
        period="2026-02",
        payment_methods=["大戶信用卡"],
        bank="永豐",
    )

    fee_status = rows[1]["properties"]["對帳狀態"]["select"]["name"]
    assert fee_status == "matched"
    assert ledger_pages["ledger-apple-1"]["properties"]["手續費"]["number"] == 5
    assert summary.unmatched == 0
