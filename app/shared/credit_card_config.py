# -*- coding: utf-8 -*-
"""Credit card reconciliation configuration loader.

MVP: Load deterministic mappings from YAML.
Future: Optionally overlay dynamic options from Notion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, List, Dict

import yaml


@dataclass(frozen=True)
class CreditCardBankConfig:
    bank_key: str
    payment_methods_default: List[str]
    statement_section_map: List[Dict[str, Any]]


def _config_path() -> Path:
    # app/shared/credit_card_config.py -> app/config/credit_cards.yaml
    return Path(__file__).resolve().parents[1] / "config" / "credit_cards.yaml"


def load_credit_card_config() -> dict:
    path = _config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("credit_cards.yaml must be a mapping")
    return data


def get_bank_config(bank_key: str) -> Optional[CreditCardBankConfig]:
    bank_key_norm = (bank_key or "").strip().lower()
    data = load_credit_card_config()
    banks = data.get("banks") or {}

    if bank_key_norm in ("台新", "taishin"):
        bank_key_norm = "taishin"

    b = banks.get(bank_key_norm)
    if not b:
        return None

    reconcile = b.get("reconcile") or {}
    payment_methods_default = reconcile.get("payment_methods_default") or []
    statement_section_map = b.get("statement_section_map") or []

    return CreditCardBankConfig(
        bank_key=bank_key_norm,
        payment_methods_default=list(payment_methods_default),
        statement_section_map=list(statement_section_map),
    )
