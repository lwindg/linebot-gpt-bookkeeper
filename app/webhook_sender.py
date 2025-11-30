# -*- coding: utf-8 -*-
"""
Webhook Sender Module

This module sends bookkeeping data to Make.com webhook.
"""

import requests
import logging
import time
from typing import List, Tuple, Optional
from app.config import WEBHOOK_URL, WEBHOOK_TIMEOUT
from app.gpt_processor import BookkeepingEntry
from app.kv_store import save_last_transaction

logger = logging.getLogger(__name__)


def send_to_webhook(entry: BookkeepingEntry, user_id: Optional[str] = None) -> bool:
    """
    Send bookkeeping data to Make.com webhook

    Converts BookkeepingEntry to JSON format expected by Make.com
    and sends via POST request to webhook URL.

    Args:
        entry: BookkeepingEntry object
        user_id: LINE user ID (optional, for saving to KV)

    Returns:
        bool: True if success, False if failed

    Error handling:
        - Network errors: returns False
        - HTTP 4xx/5xx: returns False
        - Timeout (default 10s): returns False
    """
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured, skipping webhook send")
        return True

    # Prepare payload for Make.com (using Chinese field names as per spec)
    payload = {
        "operation": "CREATE",  # v1.5.0: 用於 Make.com Router 區分操作類型
        "日期": entry.日期,
        "品項": entry.品項,
        "原幣別": entry.原幣別,
        "原幣金額": entry.原幣金額,
        "匯率": entry.匯率,
        "付款方式": entry.付款方式,
        "交易ID": entry.交易ID,
        "明細說明": entry.明細說明,
        "分類": entry.分類,
        "專案": entry.專案,
        "必要性": entry.必要性,
        "代墊狀態": entry.代墊狀態,
        "收款支付對象": entry.收款支付對象,
        "附註": entry.附註,
    }
    
    try:
        logger.info(f"Sending webhook for transaction {entry.交易ID}")
        
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=WEBHOOK_TIMEOUT
        )
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Webhook sent successfully: {entry.交易ID}")

            # 儲存最後一筆交易到 KV（用於「修改上一筆」功能）
            if user_id:
                transaction_data = {
                    "交易ID": entry.交易ID,
                    "品項": entry.品項,
                    "原幣金額": entry.原幣金額,
                    "付款方式": entry.付款方式,
                    "分類": entry.分類,
                    "日期": entry.日期,
                }
                save_last_transaction(user_id, transaction_data)

            return True
        else:
            logger.error(f"Webhook failed with status {response.status_code}: {response.text}")
            return False
    
    except requests.Timeout:
        logger.error(f"Webhook request timeout for transaction {entry.交易ID}")
        return False
    
    except requests.RequestException as e:
        logger.error(f"Webhook request failed for transaction {entry.交易ID}: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error sending webhook: {e}")
        return False


def send_multiple_webhooks(entries: List[BookkeepingEntry], user_id: Optional[str] = None, delay_seconds: float = 0.5) -> Tuple[int, int]:
    """
    為多個項目發送 webhook（v1.5.0 新功能）

    依序為每個 entry 呼叫 send_to_webhook()，記錄成功/失敗數量。
    即使部分失敗，仍繼續處理剩餘項目。

    **v1.8.1 改進**：加入延遲機制以避免後端並發寫入衝突（HTTP 409 Conflict）

    Args:
        entries: BookkeepingEntry 列表（共用交易ID）
        user_id: LINE user ID (optional, for saving to KV)
        delay_seconds: 每筆 webhook 之間的延遲秒數（預設 0.5 秒）

    Returns:
        Tuple[int, int]: (成功數量, 失敗數量)

    Examples:
        >>> entries = [entry1, entry2, entry3]
        >>> success, failure = send_multiple_webhooks(entries)
        >>> success
        3
        >>> failure
        0

    Note:
        延遲機制可避免 Google Sheets 等後端系統的並發寫入衝突。
        例如：4 筆記錄耗時約 2 秒（含 0.5s 延遲），但能確保全部成功寫入。
    """
    success_count = 0
    failure_count = 0

    logger.info(f"Sending {len(entries)} webhooks for multi-item transaction (delay={delay_seconds}s)")

    # 記錄交易項目數量和所有交易ID（用於 UPDATE webhook 批次更新）
    item_count = len(entries)
    transaction_ids = [entry.交易ID for entry in entries]

    # 提取批次識別符（v1.9.0：從附註中提取或使用第一個交易ID）
    # 優先從附註中提取批次時間戳（收據識別或文字記帳）
    if item_count > 1 and entries[0].附註:
        # 嘗試從附註中提取批次時間戳
        # 格式：「多項目支出 1/2 (批次ID: 20251125-143027)」或「收據圖片識別 1/4 (批次: 20251125-143027)」
        import re
        match = re.search(r'批次[ID]*[:：]\s*(\d{8}-\d{6})', entries[0].附註)
        if match:
            batch_id = match.group(1)
        else:
            # 無法從附註提取，使用第一個交易ID（去掉序號）
            batch_id = entries[0].交易ID.rsplit('-', 1)[0] if '-' in entries[0].交易ID.rsplit('-', 2)[-1] and len(entries[0].交易ID.rsplit('-', 2)[-1]) == 2 else entries[0].交易ID
    else:
        # 單項目：批次ID就是交易ID
        batch_id = entries[0].交易ID

    for idx, entry in enumerate(entries, start=1):
        logger.info(f"Sending webhook {idx}/{len(entries)}: {entry.品項} - {entry.原幣金額} TWD (交易ID: {entry.交易ID})")

        # 只儲存最後一筆到 KV（代表最近的記帳項目，用於「修改上一筆」功能）
        # v1.9.0: 儲存批次ID和所有交易ID列表，支援批次更新
        if idx == len(entries) and user_id:
            # 儲存交易資訊，包含批次ID和所有交易ID列表
            transaction_data = {
                "batch_id": batch_id,
                "transaction_ids": transaction_ids,
                "品項": entry.品項,
                "原幣金額": entry.原幣金額,
                "付款方式": entry.付款方式,
                "分類": entry.分類,
                "日期": entry.日期,
                "item_count": item_count,
            }
            save_last_transaction(user_id, transaction_data)
            logger.info(f"Saved multi-item transaction to KV: batch_id={batch_id}, transaction_ids={transaction_ids}")

        if send_to_webhook(entry, user_id=None):  # 不在 send_to_webhook 中儲存，已經在上面儲存
            success_count += 1
            logger.info(f"Webhook {idx}/{len(entries)} sent successfully")
        else:
            failure_count += 1
            logger.error(f"Webhook {idx}/{len(entries)} failed")

        # 在非最後一筆時加入延遲，避免後端並發寫入衝突
        if idx < len(entries):
            logger.debug(f"Waiting {delay_seconds}s before next webhook...")
            time.sleep(delay_seconds)

    logger.info(f"Multi-webhook batch complete: {success_count} success, {failure_count} failure")

    return (success_count, failure_count)


def send_update_webhook_batch(user_id: str, transaction_ids: List[str], fields_to_update: dict, delay_seconds: float = 0.1) -> Tuple[int, int]:
    """
    批次發送多筆 UPDATE webhook（v1.9.0 新增）

    用於「修改上一筆」功能，當一次記帳包含多個項目時，
    逐一發送 UPDATE webhook 更新每個項目。

    Args:
        user_id: LINE 使用者 ID
        transaction_ids: 要更新的交易 ID 列表
        fields_to_update: 要更新的欄位（dict）
        delay_seconds: 每筆 webhook 之間的延遲秒數（預設 0.1 秒）

    Returns:
        Tuple[int, int]: (成功數量, 失敗數量)

    Examples:
        >>> # 批次更新 3 筆記錄
        >>> send_update_webhook_batch("U1234", ["20251125-143027-01", "20251125-143027-02", "20251125-143027-03"], {"付款方式": "Line 轉帳"})
        (3, 0)
    """
    success_count = 0
    failure_count = 0
    total = len(transaction_ids)

    logger.info(f"Sending {total} UPDATE webhooks for batch update")

    for idx, txn_id in enumerate(transaction_ids, start=1):
        logger.info(f"Sending UPDATE webhook {idx}/{total}: {txn_id}")

        if send_update_webhook(user_id, txn_id, fields_to_update, item_count=1):
            success_count += 1
            logger.info(f"UPDATE webhook {idx}/{total} sent successfully")
        else:
            failure_count += 1
            logger.error(f"UPDATE webhook {idx}/{total} failed")

        # 在非最後一筆時加入延遲，避免後端並發寫入衝突
        if idx < total:
            logger.debug(f"Waiting {delay_seconds}s before next UPDATE webhook...")
            time.sleep(delay_seconds)

    logger.info(f"Batch UPDATE complete: {success_count} success, {failure_count} failure")

    return (success_count, failure_count)


def send_update_webhook(user_id: str, transaction_id: str, fields_to_update: dict, item_count: int = 1) -> bool:
    """
    發送 UPDATE webhook 到 Make.com（v1.5.0 新功能）

    用於「修改上一筆」功能，發送 UPDATE 操作到 Make.com Router。
    支援多項目交易批次更新（相同交易ID的所有項目）。

    Args:
        user_id: LINE 使用者 ID
        transaction_id: 要更新的交易 ID
        fields_to_update: 要更新的欄位（dict）
        item_count: 項目數量（預設為 1，多項目交易時傳入實際數量）

    Returns:
        bool: 成功回傳 True，失敗回傳 False

    Examples:
        >>> # 單筆更新
        >>> send_update_webhook("U1234567890abcdef", "20251115-143052", {"付款方式": "Line 轉帳"}, 1)
        True

        >>> # 多項目批次更新（5 個項目共享同一交易ID）
        >>> send_update_webhook("U1234567890abcdef", "20251116-143027", {"付款方式": "Line 轉帳"}, 5)
        True
    """
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured, skipping update webhook")
        return True

    # Prepare UPDATE payload
    payload = {
        "operation": "UPDATE",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "fields_to_update": fields_to_update,
        "item_count": item_count  # 告訴 Make.com 需要更新幾筆記錄
    }

    try:
        logger.info(f"Sending UPDATE webhook for transaction {transaction_id} ({item_count} item(s))")
        logger.info(f"Fields to update: {fields_to_update}")

        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=WEBHOOK_TIMEOUT
        )

        if response.status_code in [200, 201, 202]:
            logger.info(f"UPDATE webhook sent successfully: {transaction_id}")
            return True
        else:
            logger.error(f"UPDATE webhook failed with status {response.status_code}: {response.text}")
            return False

    except requests.Timeout:
        logger.error(f"UPDATE webhook request timeout for transaction {transaction_id}")
        return False

    except requests.RequestException as e:
        logger.error(f"UPDATE webhook request failed for transaction {transaction_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error sending UPDATE webhook: {e}")
        return False
