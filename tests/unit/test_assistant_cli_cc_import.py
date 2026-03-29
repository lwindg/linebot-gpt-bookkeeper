# -*- coding: utf-8 -*-

from argparse import Namespace
from pathlib import Path

import app.assistant_cli as assistant_cli
from app.gpt.types import BookkeepingEntry, MultiExpenseResult


class _FakeKV:
    def __init__(self, owner):
        self._owner = owner

    def set(self, _key, value, ttl=None):  # noqa: ARG002
        self._owner.__class__.store[self._owner.user_id] = value


class _FakeLockService:
    store: dict[str, dict] = {}
    alias_store: dict[tuple[str, str], dict[str, str]] = {}

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.kv = _FakeKV(self)

    def get_reconcile_lock(self):
        return self.__class__.store.get(self.user_id)

    def get_card_aliases(self, bank: str):
        return dict(self.__class__.alias_store.get((self.user_id, bank), {}))

    def set_card_alias(self, *, bank: str, last4: str, payment_method: str):
        key = (self.user_id, bank)
        current = dict(self.__class__.alias_store.get(key, {}))
        for k, v in current.items():
            if k != last4 and v == payment_method:
                raise ValueError(f"payment_method already mapped to another card last4: {k}")
        current[last4] = payment_method
        self.__class__.alias_store[key] = current

    def remove_card_alias(self, *, bank: str, last4: str):
        key = (self.user_id, bank)
        current = dict(self.__class__.alias_store.get(key, {}))
        current.pop(last4, None)
        self.__class__.alias_store[key] = current


def test_cc_import_no_llm_requires_structured_lines(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "富邦",
        "period": "2026-02",
        "statement_id": "fubon-2026-02-mock",
        "payment_methods": ["富邦 Costco"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())

    image_path = tmp_path / "x.jpg"
    image_path.write_bytes(b"dummy")

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=str(image_path),
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=None,
        )
    )

    assert rc == 1
    assert outputs[-1]["status"] == "error"
    assert outputs[-1]["error"]["reason"] == "missing_structured_lines"


def test_cc_import_no_llm_with_lines_json_path(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "富邦",
        "period": "2026-02",
        "statement_id": "fubon-2026-02-mock",
        "payment_methods": ["富邦 Costco"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())
    monkeypatch.setattr(assistant_cli, "extract_taishin_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected taishin extractor call")))
    monkeypatch.setattr(assistant_cli, "extract_huanan_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected huanan extractor call")))
    monkeypatch.setattr(assistant_cli, "extract_fubon_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected fubon extractor call")))
    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", lambda **_kwargs: "statement-page-1")
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["lines"] = kwargs.get("lines") or []
        return ["line-1"]

    monkeypatch.setattr(assistant_cli, "notion_create_cc_statement_lines", _fake_create)
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"8905","trans_date":"115/02/10","post_date":"115/02/11",'
            '"description":"好市多EC","twd_amount":579,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["created_count"] == 1
    assert captured["lines"][0].card_hint == "富邦 Costco"


def test_cc_import_applies_card_alias_before_payment_method_normalize(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test-alias"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "富邦",
        "period": "2026-02",
        "statement_id": "fubon-2026-02-mock",
        "payment_methods": ["富邦 Costco", "富邦 J卡"],
        "uploaded_images": 0,
    }
    _FakeLockService.alias_store[(user_id, "富邦")] = {"8006": "富邦 Costco"}
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())
    monkeypatch.setattr(assistant_cli, "extract_taishin_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected taishin extractor call")))
    monkeypatch.setattr(assistant_cli, "extract_huanan_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected huanan extractor call")))
    monkeypatch.setattr(assistant_cli, "extract_fubon_statement_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected fubon extractor call")))
    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", lambda **_kwargs: "statement-page-1")
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["lines"] = kwargs.get("lines") or []
        return ["line-1"]

    monkeypatch.setattr(assistant_cli, "notion_create_cc_statement_lines", _fake_create)
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"8006","trans_date":"115/02/10","post_date":"115/02/11",'
            '"description":"測試交易","twd_amount":579,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert captured["lines"][0].card_hint == "富邦 Costco"


def test_cc_set_list_del_card_alias(monkeypatch) -> None:
    user_id = "u-test-cmd"
    _FakeLockService.alias_store.clear()
    outputs: list[dict] = []
    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))

    rc_set = assistant_cli.cmd_cc_set_card_alias(
        Namespace(user_id=user_id, bank="富邦", last4="8006", payment_method="富邦 Costco")
    )
    assert rc_set == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["aliases"]["8006"] == "富邦 Costco"

    rc_list = assistant_cli.cmd_cc_list_card_alias(Namespace(user_id=user_id, bank="富邦"))
    assert rc_list == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["aliases"]["8006"] == "富邦 Costco"

    rc_del = assistant_cli.cmd_cc_del_card_alias(Namespace(user_id=user_id, bank="富邦", last4="8006"))
    assert rc_del == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["aliases"] == {}


def test_cc_set_card_alias_enforces_payment_method_uniqueness(monkeypatch) -> None:
    user_id = "u-test-unique"
    _FakeLockService.alias_store.clear()
    outputs: list[dict] = []
    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))

    rc1 = assistant_cli.cmd_cc_set_card_alias(
        Namespace(user_id=user_id, bank="富邦", last4="8006", payment_method="富邦 Costco")
    )
    assert rc1 == 0

    rc2 = assistant_cli.cmd_cc_set_card_alias(
        Namespace(user_id=user_id, bank="富邦", last4="1234", payment_method="富邦 Costco")
    )
    assert rc2 == 1
    assert outputs[-1]["status"] == "error"
    assert outputs[-1]["error"]["reason"] == "invalid_input"


def test_cc_import_backfills_missing_post_date_from_trans_date(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test-datefill"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "永豐",
        "period": "2026-02",
        "statement_id": "sinopac-2026-02-mock",
        "payment_methods": ["大戶信用卡"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())
    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", lambda **_kwargs: "statement-page-1")
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["lines"] = kwargs.get("lines") or []
        return ["line-1"]

    monkeypatch.setattr(assistant_cli, "notion_create_cc_statement_lines", _fake_create)
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"8006","trans_date":"02/01","post_date":null,'
            '"description":"測試交易","twd_amount":100,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert captured["lines"][0].trans_date == "02/01"
    assert captured["lines"][0].post_date == "02/01"


def test_cc_import_drops_lines_without_dates(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test-drop-no-date"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "聯邦",
        "period": "2026-03",
        "statement_id": "union-2026-03-mock",
        "payment_methods": ["聯邦綠卡"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())
    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", lambda **_kwargs: "statement-page-1")
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)
    captured: dict = {}

    def _fake_create(**kwargs):
        captured["lines"] = kwargs.get("lines") or []
        return ["line-1"]

    monkeypatch.setattr(assistant_cli, "notion_create_cc_statement_lines", _fake_create)

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"聯邦綠卡","trans_date":null,"post_date":null,'
            '"description":"無日期雜訊","twd_amount":111,"currency":"TWD","is_fee":false},'
            '{"card_hint":"聯邦綠卡","trans_date":"03/06","post_date":"03/06",'
            '"description":"有效明細","twd_amount":199,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["created_count"] == 1
    assert outputs[-1]["result"]["dropped_no_date_count"] == 1
    assert len(captured["lines"]) == 1
    assert captured["lines"][0].description == "有效明細"


def test_cc_import_errors_when_all_lines_missing_dates(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test-all-no-date"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "聯邦",
        "period": "2026-03",
        "statement_id": "union-2026-03-mock",
        "payment_methods": ["聯邦綠卡"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"聯邦綠卡","trans_date":null,"post_date":null,'
            '"description":"無日期1","twd_amount":111,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 1
    assert outputs[-1]["status"] == "error"
    assert outputs[-1]["error"]["reason"] == "missing_statement_date"


def test_cc_import_sinopac_includes_auto_bookkeeping_result(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test-sinopac-auto"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "永豐",
        "period": "2026-02",
        "statement_id": "sinopac-2026-02-mock",
        "payment_methods": ["大戶信用卡"],
        "uploaded_images": 0,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(assistant_cli, "get_bank_config", lambda _bank: object())
    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", lambda **_kwargs: "statement-page-1")
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        assistant_cli,
        "_apply_sinopac_autobookkeeping",
        lambda **_kwargs: {"created": 2, "skipped": 0, "failed": []},
    )

    monkeypatch.setattr(
        assistant_cli,
        "notion_create_cc_statement_lines",
        lambda **_kwargs: ["line-1", "line-2"],
    )

    lines_json_path = tmp_path / "lines.json"
    lines_json_path.write_text(
        (
            '[{"card_hint":"8006","trans_date":"02/02","post_date":"02/02",'
            '"description":"大戶消費回饋入帳戶＿國內 217 元","twd_amount":0,"currency":"TWD","is_fee":false},'
            '{"card_hint":"8006","trans_date":"02/05","post_date":"02/05",'
            '"description":"永豐自扣已入帳，謝謝！","twd_amount":-23003,"currency":"TWD","is_fee":false}]'
        ),
        encoding="utf-8",
    )

    rc = assistant_cli.cmd_cc_import(
        Namespace(
            user_id=user_id,
            image_path=None,
            message_id=None,
            no_llm=True,
            lines_json=None,
            lines_json_path=str(lines_json_path),
        )
    )

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["auto_bookkeeping"]["created"] == 2


def test_sinopac_autobookkeeping_uses_statement_trans_date(monkeypatch) -> None:
    class _KV:
        def get(self, _key):
            return None

        def set(self, _key, _value, ttl=None):  # noqa: ARG002
            return None

    sent_dates: list[str] = []
    sent_txids: list[str] = []
    seen_texts: list[str] = []

    monkeypatch.setattr(assistant_cli, "KVStore", lambda: _KV())
    monkeypatch.setattr(
        assistant_cli,
        "process_with_parser",
        lambda _text, **_kwargs: (
            seen_texts.append(str(_text))
            or MultiExpenseResult(
                intent="create",
                entries=[
                    BookkeepingEntry(
                        intent="記帳",
                        日期="2099-01-01",
                        品項="回饋金",
                        原幣別="TWD",
                        原幣金額=217.0,
                        付款方式="大戶網銀",
                        交易ID="tx-auto-1",
                        分類="其他",
                        交易類型="收入",
                    )
                ],
            )
        ),
    )
    monkeypatch.setattr(
        assistant_cli,
        "send_to_webhook",
        lambda entry, **_kwargs: sent_dates.append(str(entry.日期)) or sent_txids.append(str(entry.交易ID)) or True,
    )

    result = assistant_cli._apply_sinopac_autobookkeeping(
        user_id="u-test-date",
        statement_id="sinopac-2026-02-mock",
        statement_month="2026-02",
        lines=[
            assistant_cli.TaishinStatementLine(
                card_hint="8006",
                trans_date="02/02",
                post_date="02/02",
                description="大戶消費回饋入帳戶—國內217元",
                twd_amount=0.0,
                fx_date=None,
                country=None,
                currency="TWD",
                foreign_amount=None,
                is_fee=False,
                fee_reference_amount=None,
            )
        ],
        line_page_ids=["line-1"],
    )

    assert result["created"] == 1
    assert sent_dates == ["2026-02-02"]
    assert len(sent_txids) == 1
    assert sent_txids[0].startswith("20260202-")
    assert seen_texts == ["收入 217 回饋金 大戶網銀"]


def test_cc_reapply_auto_reuses_existing_statement_lines(monkeypatch) -> None:
    user_id = "u-test-reapply"
    _FakeLockService.alias_store.clear()
    _FakeLockService.store[user_id] = {
        "bank": "永豐",
        "period": "2026-02",
        "statement_id": "sinopac-2026-02-mock",
        "payment_methods": ["大戶信用卡"],
        "uploaded_images": 1,
    }
    outputs: list[dict] = []

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(
        assistant_cli,
        "_fetch_statement_lines_for_autobookkeeping",
        lambda _sid: (
            [
                assistant_cli.TaishinStatementLine(
                    card_hint="大戶信用卡",
                    trans_date="2026-02-02",
                    post_date="2026-02-02",
                    description="大戶消費回饋入帳戶—國內217元",
                    twd_amount=0.0,
                    fx_date=None,
                    country=None,
                    currency="TWD",
                    foreign_amount=None,
                    is_fee=False,
                    fee_reference_amount=None,
                )
            ],
            ["line-1"],
        ),
    )
    monkeypatch.setattr(
        assistant_cli,
        "_apply_sinopac_autobookkeeping",
        lambda **_kwargs: {"created": 1, "skipped": 0, "failed": []},
    )

    rc = assistant_cli.cmd_cc_reapply_auto(Namespace(user_id=user_id, force=False))

    assert rc == 0
    assert outputs[-1]["status"] == "ok"
    assert outputs[-1]["result"]["line_count"] == 1
    assert outputs[-1]["result"]["auto_bookkeeping"]["created"] == 1
