# -*- coding: utf-8 -*-
"""
Integration test for assistant_cli Fubon reconcile flow.
"""

from argparse import Namespace
from types import SimpleNamespace

import app.assistant_cli as assistant_cli
from app.services.reconcile_statement import ReconcileSummary
from app.services.statement_image_handler import TaishinStatementLine


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

    def set_reconcile_lock(self, *, bank: str, period: str, payment_methods=None):  # noqa: ARG002
        self.__class__.store[self.user_id] = {
            "bank": bank,
            "period": period,
            "payment_methods": ["富邦 Costco"],
            "statement_id": f"fubon-{period}-mock",
            "uploaded_images": 0,
        }

    def get_reconcile_lock(self):
        return self.__class__.store.get(self.user_id)

    def remove_reconcile_lock(self):
        self.__class__.store.pop(self.user_id, None)


def test_assistant_cli_fubon_reconcile_flow(monkeypatch, tmp_path) -> None:
    outputs: list[dict] = []
    ensure_calls: list[dict] = []
    run_calls: list[dict] = []

    image_path = tmp_path / "fubon.jpg"
    image_path.write_bytes(b"fake-image-bytes")

    monkeypatch.setattr(assistant_cli, "LockService", _FakeLockService)
    monkeypatch.setattr(assistant_cli, "_print_json", lambda payload: outputs.append(payload))
    monkeypatch.setattr(
        assistant_cli,
        "get_bank_config",
        lambda _bank: SimpleNamespace(bank_key="fubon", payment_methods_default=["富邦 Costco"]),
    )
    monkeypatch.setattr(
        assistant_cli,
        "extract_fubon_statement_lines",
        lambda *_args, **_kwargs: [
            TaishinStatementLine(
                card_hint="富邦 Costco",
                trans_date="115/02/10",
                post_date="115/02/11",
                description="好市多EC",
                twd_amount=579.0,
                fx_date=None,
                country=None,
                currency="TWD",
                foreign_amount=None,
                is_fee=False,
                fee_reference_amount=None,
            )
        ],
    )

    def _fake_ensure_cc_statement_page(**kwargs):
        ensure_calls.append(kwargs)
        return "statement-page-1"

    monkeypatch.setattr(assistant_cli, "ensure_cc_statement_page", _fake_ensure_cc_statement_page)
    monkeypatch.setattr(assistant_cli, "notion_create_cc_statement_lines", lambda **_kwargs: ["line-1"])
    monkeypatch.setattr(assistant_cli, "detect_statement_date_anomaly", lambda *_args, **_kwargs: None)

    def _fake_reconcile_statement(**kwargs):
        run_calls.append(kwargs)
        return ReconcileSummary(
            statement_id=kwargs["statement_id"],
            period=kwargs["period"],
            statement_lines_total=1,
            matched=1,
            ambiguous=0,
            unmatched=0,
            statement_page_id="statement-page-1",
        )

    monkeypatch.setattr(assistant_cli, "reconcile_statement", _fake_reconcile_statement)

    assert assistant_cli.cmd_cc_lock(Namespace(user_id="u1", bank="富邦", period="2026-02")) == 0
    assert assistant_cli.cmd_cc_import(
        Namespace(
            user_id="u1",
            image_path=str(image_path),
            message_id="m1",
            no_llm=False,
            lines_json=None,
            lines_json_path=None,
        )
    ) == 0
    assert assistant_cli.cmd_cc_run(Namespace(user_id="u1")) == 0

    assert outputs[0]["status"] == "ok"
    assert outputs[0]["result"]["bank"] == "富邦"
    assert outputs[1]["status"] == "ok"
    assert outputs[1]["result"]["bank"] == "富邦"
    assert outputs[1]["result"]["created_count"] == 1
    assert outputs[2]["status"] == "ok"
    assert "對帳完成" in outputs[2]["summary_text"]

    assert ensure_calls and ensure_calls[0]["bank"] == "富邦"
    assert run_calls and run_calls[0]["bank"] == "富邦"
    assert run_calls[0]["payment_methods"] == ["富邦 Costco"]
