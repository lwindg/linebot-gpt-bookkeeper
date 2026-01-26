# -*- coding: utf-8 -*-
"""
Update handling for LINE bookkeeping.
"""

import logging
import re

from app.shared.category_resolver import resolve_category_input
from app.services.kv_store import KVStore, delete_last_transaction
from app.shared.payment_resolver import normalize_payment_method
from app.services.webhook_sender import send_update_webhook_batch

logger = logging.getLogger(__name__)

_UPDATE_CATEGORY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:把)?分類(?:改成|改為|改到|變成|設為)\s*(?P<value>.+)$"),
    re.compile(r"分類\s*[:：]\s*(?P<value>.+)$"),
)


def _extract_category_from_update_message(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None

    for pattern in _UPDATE_CATEGORY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = (match.group("value") or "").strip()
        value = value.strip(" \t\r\n\"'`")
        return value or None

    return None


def handle_update_last_entry(user_id: str, fields_to_update: dict, *, raw_message: str | None = None) -> str:
    """
    Update last transaction with optimistic locking (v1.10.0 新增)
    """
    # Step 1: Validate fields_to_update is not empty
    if not fields_to_update:
        logger.warning(f"Empty fields_to_update for user {user_id}")
        return (
            "❌ 無法修改：未指定要更新的欄位\n\n"
            "請指定要修改的欄位，例如：\n"
            "• 品項\n"
            "• 分類\n"
            "• 專案\n"
            "• 付款方式\n"
            "• 金額"
        )

    # Step 2: Read original transaction from KV
    key = f"last_transaction:{user_id}"
    kv_store = KVStore()

    original_tx = kv_store.get(key)

    # Step 3: Return error if transaction not found
    if not original_tx:
        logger.warning(f"No last transaction found for user {user_id}")
        return "❌ 找不到最近的記帳記錄\n\n可能原因：\n1. 超過 10 分鐘（記錄已過期）\n2. 尚未進行過記帳\n\n請直接輸入完整記帳資訊。"

    # Step 4: Record target transaction ID (optimistic lock)
    target_id = original_tx.get("交易ID") or original_tx.get("batch_id")
    if not target_id:
        logger.error(f"Transaction ID not found in KV for user {user_id}")
        return "❌ 交易記錄格式錯誤\n\n請重新記帳。"

    logger.info(f"Updating transaction {target_id} for user {user_id}")
    logger.info(f"Original transaction: {original_tx}")
    logger.info(f"Fields to update: {fields_to_update}")

    # Category validation/normalization: do not create new categories.
    raw_category = _extract_category_from_update_message(raw_message or "") if raw_message else None
    category_value = raw_category if raw_category is not None else fields_to_update.get("分類")
    if category_value not in (None, ""):
        try:
            resolved = resolve_category_input(
                str(category_value),
                original_category=original_tx.get("分類"),
            )
            fields_to_update = {**fields_to_update, "分類": resolved}
        except ValueError as e:
            logger.warning(f"Invalid category update for user {user_id}: {fields_to_update.get('分類')} ({e})")
            return (
                "❌ 分類無效：請從既有分類中選擇，且不要新建分類\n\n"
                f"你輸入的是：{fields_to_update.get('分類')}\n"
                "範例：\n"
                "• 把分類改成 家庭/水果\n"
                "• 把分類改成 交通/接駁\n"
            )

    payment_value = fields_to_update.get("付款方式")
    if payment_value not in (None, ""):
        normalized = normalize_payment_method(str(payment_value))
        fields_to_update = {**fields_to_update, "付款方式": normalized}

    # Step 5: Update target fields in transaction dict (skip empty/None values)
    updated_tx = original_tx.copy()
    for field_name, new_value in fields_to_update.items():
        if new_value is not None and new_value != "":
            updated_tx[field_name] = new_value
            logger.info(f"Updated field {field_name}: {original_tx.get(field_name)} -> {new_value}")

    # Step 6: Re-read KV and verify transaction ID matches (concurrency check)
    current_tx = kv_store.get(key)

    if not current_tx:
        logger.warning(f"Transaction expired during update for user {user_id}")
        return "❌ 交易記錄已過期（超過 10 分鐘）\n\n請重新記帳。"

    current_id = current_tx.get("交易ID") or current_tx.get("batch_id")
    if current_id != target_id:
        logger.warning(f"Transaction ID mismatch for user {user_id}: expected {target_id}, got {current_id}")
        return "❌ 交易已變更，請重新操作\n\n系統偵測到並發修改，請重新輸入修改指令。"

    # Step 7: Get transaction IDs for webhook batch update
    transaction_ids = original_tx.get("transaction_ids", [])
    item_count = original_tx.get("item_count", 1)

    # Backward compatibility: if no transaction_ids, use single 交易ID
    if not transaction_ids and "交易ID" in original_tx:
        transaction_ids = [original_tx["交易ID"]]

    if not transaction_ids:
        logger.error(f"No transaction IDs found for user {user_id}")
        return "❌ 交易記錄格式錯誤\n\n請重新記帳。"

    # Step 8: Send UPDATE webhooks to Make (batch update all items)
    logger.info(f"Sending UPDATE webhooks for {len(transaction_ids)} transaction(s)")
    success_count, failure_count = send_update_webhook_batch(user_id, transaction_ids, fields_to_update)

    if success_count == 0:
        logger.error(f"All UPDATE webhooks failed for user {user_id}")
        return "❌ 更新失敗\n\n請稍後再試，或直接輸入完整記帳資訊。"

    # Step 9: Delete KV record to prevent duplicate modifications
    delete_last_transaction(user_id)
    logger.info(f"Deleted last transaction from KV for user {user_id}")

    # Step 10: Format success message
    logger.info(f"Transaction {target_id} updated successfully for user {user_id}")

    if item_count > 1:
        if failure_count == 0:
            message = f"✅ 已更新上一筆記帳（共 {item_count} 個項目）\n\n"
        else:
            message = f"⚠️ 部分更新成功（{success_count}/{item_count} 個項目）\n\n"
    else:
        message = "✅ 修改成功！\n\n"

    message += f"🔖 批次ID：{target_id}\n"
    message += f"📝 原品項：{original_tx.get('品項', '未知')}"
    if item_count > 1:
        message += f" 等 {item_count} 項\n"
    else:
        message += "\n"

    message += "已更新："
    for field_name, new_value in fields_to_update.items():
        old_value = original_tx.get(field_name, "未設定")
        message += f"\n• {field_name}：{old_value} → {new_value}"

    if item_count > 1 and failure_count == 0:
        message += f"\n\n💡 已同時更新所有 {success_count} 筆記錄"

    return message
