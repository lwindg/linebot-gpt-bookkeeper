# -*- coding: utf-8 -*-

from argparse import Namespace
from pathlib import Path

import app.assistant_cli as assistant_cli


class _FakeKV:
    def __init__(self, owner):
        self._owner = owner

    def set(self, _key, value, ttl=None):  # noqa: ARG002
        self._owner.__class__.store[self._owner.user_id] = value


class _FakeLockService:
    store: dict[str, dict] = {}

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.kv = _FakeKV(self)

    def get_reconcile_lock(self):
        return self.__class__.store.get(self.user_id)


def test_cc_import_no_llm_requires_structured_lines(monkeypatch, tmp_path: Path) -> None:
    user_id = "u-test"
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
