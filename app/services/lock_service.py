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

logger = logging.getLogger(__name__)

LOCK_PROJECT_KEY = "lock:project:{user_id}"
LOCK_PAYMENT_KEY = "lock:payment:{user_id}"

# Command Patterns
_RE_LOCK_PROJECT = re.compile(r"鎖定專案\s*(?P<name>.+)?")
_RE_UNLOCK_PROJECT = re.compile(r"解鎖專案")
_RE_LOCK_PAYMENT = re.compile(r"鎖定付款\s*(?P<name>.+)?")
_RE_UNLOCK_PAYMENT = re.compile(r"解鎖付款")
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
            if not name:
                return "❌ 請提供要鎖定的專案名稱。\n範例：鎖定專案 日本玩雪"
            
            # Fuzzy matching logic (v1.10.0 inspired)
            long_term_project = get_long_term_project(name)
            if long_term_project:
                self.set_project_lock(long_term_project)
                return f"🔒 專案已鎖定為：{long_term_project}\n後續記帳將自動帶入此專案。"
            
            has_date_prefix = extract_project_date_range(name) is not None
            options, error = get_project_options(self.kv)
            if options:
                resolved, candidates = match_short_term_project(name, options)
                if resolved:
                    self.set_project_lock(resolved)
                    return f"🔒 專案已鎖定為：{resolved}\n後續記帳將自動帶入此專案。"
                elif has_date_prefix:
                    self.set_project_lock(name)
                    return f"🔒 專案已鎖定為：{name}\n後續記帳將自動帶入此專案。"
                else:
                    return self._format_project_candidates_message(candidates)
            else:
                if has_date_prefix:
                    self.set_project_lock(name)
                    return f"🔒 專案已鎖定為：{name}\n後續記帳將自動帶入此專案。"
                else:
                    logger.warning(
                        "Failed to fetch project options: %s", error or "unknown_error"
                    )
                    return "❌ 無法取得專案清單，請稍後再試或提供完整名稱（含日期）。"

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

        # Status
        if _RE_LOCK_STATUS.search(text):
            p = self.get_project_lock()
            pay = self.get_payment_lock()
            if not p and not pay:
                return "ℹ️ 目前沒有任何鎖定中的設定。"
            res = "📌 目前鎖定設定："
            if p: res += f"\n• 專案：{p}"
            if pay: res += f"\n• 付款方式：{pay}"
            return res

        return None

    def _format_project_candidates_message(self, candidates: List[str]) -> str:
        if not candidates:
            return "❌ 找不到唯一專案\n請輸入完整名稱（含日期）。"
        lines = [
            "❌ 找不到唯一專案",
            "請輸入完整名稱（含日期），或從以下候選擇一個：",
        ]
        for idx, candidate in enumerate(candidates, start=1):
            lines.append(f"{idx}) {candidate}")
        return "\n".join(lines)
