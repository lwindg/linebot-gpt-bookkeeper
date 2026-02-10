# -*- coding: utf-8 -*-
"""
Lock Service Module

Handles per-user session locks for Project and Payment Method.
"""

import logging
import re
from typing import Optional, Tuple, List
from app.services.kv_store import KVStore
from app.shared.payment_resolver import normalize_payment_method
from app.shared.project_resolver import (
    get_long_term_project,
    match_short_term_project,
    extract_project_date_range,
)
from app.services.project_options import get_project_options
from app.parser.extract_amount import _CURRENCY_MAP

logger = logging.getLogger(__name__)

LOCK_PROJECT_KEY = "lock:project:{user_id}"
LOCK_PAYMENT_KEY = "lock:payment:{user_id}"
LOCK_CURRENCY_KEY = "lock:currency:{user_id}"

# Command Patterns
_RE_LOCK_PROJECT = re.compile(r"鎖定專案\s*(?:名稱)?\s*(?P<name>.+)?")
_RE_UNLOCK_PROJECT = re.compile(r"解鎖專案\s*(?:名稱)?")
_RE_LOCK_PAYMENT = re.compile(r"鎖定付款\s*(?:方式)?\s*(?P<name>.+)?")
_RE_UNLOCK_PAYMENT = re.compile(r"解鎖付款\s*(?:方式)?")
_RE_LOCK_CURRENCY = re.compile(r"鎖定幣別\s*(?:名稱)?\s*(?P<name>.+)?")
_RE_UNLOCK_CURRENCY = re.compile(r"解鎖幣別\s*(?:名稱)?")
_RE_UNLOCK_ALL = re.compile(r"(?:解鎖全部|全部解鎖)")
_RE_LOCK_STATUS = re.compile(r"鎖定狀態")


class LockService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.kv = KVStore()

    def get_project_lock(self) -> Optional[str]:
        return self.kv.get(LOCK_PROJECT_KEY.format(user_id=self.user_id))

    def set_project_lock(self, project_name: str):
        self.kv.set(LOCK_PROJECT_KEY.format(user_id=self.user_id), project_name, ttl=86400 * 7) # 7 days

    def remove_project_lock(self):
        if self.kv.client:
            self.kv.client.delete(LOCK_PROJECT_KEY.format(user_id=self.user_id))

    def get_payment_lock(self) -> Optional[str]:
        return self.kv.get(LOCK_PAYMENT_KEY.format(user_id=self.user_id))

    def set_payment_lock(self, payment_name: str):
        normalized = normalize_payment_method(payment_name)
        self.kv.set(LOCK_PAYMENT_KEY.format(user_id=self.user_id), normalized, ttl=86400 * 7)

    def remove_payment_lock(self):
        if self.kv.client:
            self.kv.client.delete(LOCK_PAYMENT_KEY.format(user_id=self.user_id))

    def get_currency_lock(self) -> Optional[str]:
        return self.kv.get(LOCK_CURRENCY_KEY.format(user_id=self.user_id))

    def set_currency_lock(self, currency_name: str):
        normalized = _CURRENCY_MAP.get(currency_name.upper(), _CURRENCY_MAP.get(currency_name, currency_name.upper()))
        self.kv.set(LOCK_CURRENCY_KEY.format(user_id=self.user_id), normalized, ttl=86400 * 7)

    def remove_currency_lock(self):
        if self.kv.client:
            self.kv.client.delete(LOCK_CURRENCY_KEY.format(user_id=self.user_id))

    def remove_all_locks(self):
        if self.kv.client:
            self.kv.client.delete(LOCK_PROJECT_KEY.format(user_id=self.user_id))
            self.kv.client.delete(LOCK_PAYMENT_KEY.format(user_id=self.user_id))
            self.kv.client.delete(LOCK_CURRENCY_KEY.format(user_id=self.user_id))

    def resolve_project_name(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve a project name using fuzzy matching.
        Returns (resolved_name, error_message).
        """
        name = name.strip()
        if not name:
            return None, "❌ 請提供專案名稱。"

        # 1. Check long term projects
        long_term_project = get_long_term_project(name)
        if long_term_project:
            return long_term_project, None

        # 2. Check for date range prefix
        has_date_prefix = extract_project_date_range(name) is not None

        # 3. Fuzzy matching with options
        options, error = get_project_options(self.kv)
        if options:
            # Exact match check
            name_lower = name.lower()
            for opt in options:
                if opt.lower().strip() == name_lower:
                    return opt, None

            resolved, candidates = match_short_term_project(name, options)
            if resolved:
                return resolved, None
            elif has_date_prefix:
                return name, None
            else:
                return None, self.format_project_candidates_message(candidates)
        else:
            if has_date_prefix:
                return name, None
            else:
                logger.warning("Failed to fetch project options: %s", error or "unknown_error")
                return None, "❌ 無法取得專案清單，請稍後再試或提供完整名稱（含日期）。"

    def handle_command(self, text: str) -> Optional[str]:
        """
        Check if text is a lock command. 
        Returns reply text if it's a command, else None.
        """
        # Unlock Project
        if _RE_UNLOCK_PROJECT.search(text):
            self.remove_project_lock()
            return "🔓 已解除專案鎖定。後續記帳將恢復自動推斷。"

        # Lock Project
        m = _RE_LOCK_PROJECT.search(text)
        if m:
            name = (m.group("name") or "").strip()
            resolved, error = self.resolve_project_name(name)
            if resolved:
                self.set_project_lock(resolved)
                return f"🔒 專案已鎖定為：{resolved}\n後續記帳將自動帶入此專案。"
            return error

        # Unlock Payment
        if _RE_UNLOCK_PAYMENT.search(text):
            self.remove_payment_lock()
            return "🔓 已解除付款方式鎖定。"

        # Lock Payment
        m = _RE_LOCK_PAYMENT.search(text)
        if m:
            name = (m.group("name") or "").strip()
            if not name:
                return "❌ 請提供要鎖定的付款方式。\n範例：鎖定付款 日圓現金"
            self.set_payment_lock(name)
            lock_val = self.get_payment_lock()
            return f"🔒 付款方式已鎖定為：{lock_val}\n後續記帳將自動帶入此方式。"

        # Unlock Currency
        if _RE_UNLOCK_CURRENCY.search(text):
            self.remove_currency_lock()
            return "🔓 已解除幣別鎖定。"

        # Unlock All
        if _RE_UNLOCK_ALL.search(text):
            self.remove_all_locks()
            return "🔓 已解除所有鎖定設定（專案、付款方式、幣別）。"

        # Lock Currency
        m = _RE_LOCK_CURRENCY.search(text)
        if m:
            name = (m.group("name") or "").strip()
            if not name:
                return "❌ 請提供要鎖定的幣別。\n範例：鎖定幣別 日幣"
            self.set_currency_lock(name)
            lock_val = self.get_currency_lock()
            return f"🔒 幣別已鎖定為：{lock_val}\n後續記帳將自動帶入此幣別。"

        # Status
        if _RE_LOCK_STATUS.search(text):
            p = self.get_project_lock()
            pay = self.get_payment_lock()
            curr = self.get_currency_lock()
            if not p and not pay and not curr:
                return "ℹ️ 目前沒有任何鎖定中的設定。"
            res = "📌 目前鎖定設定："
            if p: res += f"\n• 專案：{p}"
            if pay: res += f"\n• 付款方式：{pay}"
            if curr: res += f"\n• 幣別：{curr}"
            return res

        return None

    def format_project_candidates_message(self, candidates: List[str]) -> str:
        if not candidates:
            return "❌ 找不到唯一專案\n請輸入完整名稱（含日期）。"
        lines = [
            "❌ 找不到唯一專案",
            "請輸入完整名稱（含日期），或從以下候選擇一個：",
        ]
        for idx, candidate in enumerate(candidates, start=1):
            lines.append(f"{idx}) {candidate}")
        return "\n".join(lines)
