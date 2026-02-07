# -*- coding: utf-8 -*-
"""
Webhook Sender Module

This module sends bookkeeping data to Make.com webhook.
"""

import logging
import re
import requests
import time
from typing import List, Tuple, Optional
from app.config import WEBHOOK_URL, WEBHOOK_TIMEOUT, USE_NOTION_API, NOTION_TOKEN
from app.gpt.types import BookkeepingEntry
from app.services.kv_store import save_last_transaction, delete_last_transaction
from app.services.notion_service import NotionService

logger = logging.getLogger(__name__)

_BATCH_ID_SUFFIX = re.compile(r"-\d{2}$")


def _extract_batch_id(transaction_id: str) -> Optional[str]:
    if _BATCH_ID_SUFFIX.search(transaction_id):
        return transaction_id.rsplit("-", 1)[0]
    return None


def build_create_payload(entry: BookkeepingEntry) -> dict:
    """
    Build webhook payload for CREATE operation.

    Args:
        entry: BookkeepingEntry object

    Returns:
        dict: Payload dictionary ready for JSON serialization
    """
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
        "交易類型": entry.交易類型,
        "附註": entry.附註,
    }
    batch_id = _extract_batch_id(entry.交易ID)
    if batch_id:
        payload["批次ID"] = batch_id
    return payload


def build_update_payload(user_id: str, transaction_id: str, fields_to_update: dict, item_count: int = 1) -> dict:
    """
    Build webhook payload for UPDATE operation.

    Args:
        user_id: LINE user ID
        transaction_id: Transaction ID to update
        fields_to_update: Fields to update (dict)
        item_count: Number of items in batch (default 1)

    Returns:
        dict: Payload dictionary ready for JSON serialization
    """
    return {
        "operation": "UPDATE",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "fields_to_update": fields_to_update,
        "item_count": item_count  # 告訴 Make.com 需要更新幾筆記錄
    }


def send_to_webhook(entry: BookkeepingEntry, user_id: Optional[str] = None) -> bool:
    """
    Send bookkeeping data to Make.com webhook or Notion API.

    Args:
        entry: BookkeepingEntry object
        user_id: LINE user ID (optional, for saving to KV)

    Returns:
        bool: True if success, False if failed
    """
    # 1. Notion API Integration (v2.0)
    if USE_NOTION_API and NOTION_TOKEN:
        logger.info(f"Using Notion API for transaction {entry.交易ID}")
        notion = NotionService()
        success = notion.create_page(entry)
        
        if success:
            # v1.10.1: Clear previous last transaction before saving new one (single entry)
            if user_id:
                delete_last_transaction(user_id)
                
                # 儲存最後一筆交易到 KV（用於「修改上一筆」功能）
                transaction_data = {
                    "交易ID": entry.交易ID,
                    "品項": entry.品項,
                    "原幣金額": entry.原幣金額,
                    "原幣別": entry.原幣別,
                    "匯率": entry.匯率,
                    "付款方式": entry.付款方式,
                    "分類": entry.分類,
                    "日期": entry.日期,
                }
                save_last_transaction(user_id, transaction_data)
            return True
        else:
            logger.error(f"Notion API failed for transaction {entry.交易ID}")
            return False

    # 2. Legacy Webhook Integration
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("Neither Notion nor Webhook URL is configured, skipping")
        return True

    # Prepare payload for Make.com (using Chinese field names as per spec)
    payload = build_create_payload(entry)
    
    # v1.10.1: Clear previous last transaction before saving new one (single entry)
    if user_id:
        delete_last_transaction(user_id)
        logger.info(f"Cleared previous last transaction for user {user_id} before new single bookkeeping")
    
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
                    "原幣別": entry.原幣別,
                    "匯率": entry.匯率,
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

    # v1.10.1: Delete any existing 'last transaction' before saving new ones
    if user_id:
        delete_last_transaction(user_id)
        logger.info(f"Cleared previous last transaction for user {user_id} before new bookkeeping")

    # Handle empty entries list
    if not entries:
        logger.warning("No entries to send webhooks for")
        return (0, 0)

    # 記錄交易項目數量和所有交易ID（用於 UPDATE webhook 批次更新）
    item_count = len(entries)
    transaction_ids = [entry.交易ID for entry in entries]

    # 批次ID一律由交易ID推斷（不再依賴附註）
    batch_id = _extract_batch_id(entries[0].交易ID) or entries[0].交易ID

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
                "原幣別": entry.原幣別,
                "匯率": entry.匯率,
                "付款方式": entry.付款方式,
                "分類": entry.分類,
                "日期": entry.日期,
                "item_count": item_count,
            }
            save_last_transaction(user_id, transaction_data)
            logger.info(f"Saved multi-item transaction to KV: batch_id={batch_id}, transaction_ids={transaction_ids}")

        try:
            if send_to_webhook(entry, user_id=None):  # 不在 send_to_webhook 中儲存，已經在上面儲存
                success_count += 1
                logger.info(f"Webhook {idx}/{len(entries)} sent successfully")
            else:
                failure_count += 1
                logger.error(f"Webhook {idx}/{len(entries)} failed")
        except Exception as e:
            # Handle unexpected exceptions gracefully (e.g., network errors, serialization errors)
            failure_count += 1
            logger.error(f"Exception while sending webhook {idx}/{len(entries)}: {e}")

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
        >>> send_update_webhook_batch("U1234", ["20251125-143027-01", "20251125-143027-02", "20251125-143027-03"], {"付款方式": "Line Pay"})
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
    發送 UPDATE 操作到 Notion API 或 Make.com Webhook。
    """
    # 1. Notion API Integration
    if USE_NOTION_API and NOTION_TOKEN:
        logger.info(f"Using Notion API for UPDATE transaction {transaction_id}")
        notion = NotionService()
        return notion.update_page(transaction_id, fields_to_update)

    # 2. Legacy Webhook Integration
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("Neither Notion nor Webhook URL is configured for update")
        return True

    # Prepare UPDATE payload
    payload = build_update_payload(user_id, transaction_id, fields_to_update, item_count)

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
