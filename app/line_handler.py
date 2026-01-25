# -*- coding: utf-8 -*-
"""
LINE Message Handler Module

This module handles LINE message events and user interactions.
"""

import logging
import re
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi
from linebot.v3.messaging import MessagingApiBlob

from app.gpt_processor import process_multi_expense, process_receipt_data
from app.gpt_types import MultiExpenseResult, BookkeepingEntry
from app.webhook_sender import send_multiple_webhooks, send_update_webhook_batch
from app.image_handler import download_image, process_receipt_image, ImageDownloadError, ImageTooLargeError, VisionAPIError
from app.kv_store import KVStore, delete_last_transaction
from app.config import LAST_TRANSACTION_TTL
from app.category_resolver import resolve_category_input
from app.payment_resolver import normalize_payment_method

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


def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """
    Format bookkeeping confirmation message (v1 單項目格式)

    Formats the bookkeeping entry data into a user-friendly confirmation message
    with all important details.

    Args:
        entry: BookkeepingEntry object

    Returns:
        str: Formatted confirmation message
    """
    # Calculate TWD amount
    twd_amount = entry.原幣金額 * entry.匯率

    message = f"""✅ 記帳成功！

📋 {entry.品項}"""

    # Display currency info (v003-multi-currency)
    if entry.原幣別 != "TWD":
        message += f"""
💵 新台幣：{twd_amount:.2f} 元 (原幣 {entry.原幣金額:.2f} {entry.原幣別} / 匯率 {entry.匯率:.4f})"""
    else:
        message += f"\n💵 新台幣：{twd_amount:.0f} 元"

    message += f"""
💳 付款方式：{entry.付款方式}
📂 分類：{entry.分類}
⭐ 必要性：{entry.必要性}"""

    # Add advance payment information if present
    if entry.代墊狀態 == "代墊":
        message += f"\n💸 代墊給：{entry.收款支付對象}"
    elif entry.代墊狀態 == "需支付":
        message += f"\n💰 需支付給：{entry.收款支付對象}"
    elif entry.代墊狀態 == "不索取":
        message += f"\n🎁 不索取（代墊給：{entry.收款支付對象}）"

    message += f"""
📅 日期：{entry.日期}
🔖 交易ID：{entry.交易ID}"""

    # Add optional detail note if present
    if entry.明細說明:
        message += f"\n📝 明細說明：{entry.明細說明}"

    return message


def format_multi_confirmation_message(result: MultiExpenseResult, success_count: int, failure_count: int) -> str:
    """
    Format multi-item bookkeeping confirmation message (v1.5.0 新增)

    Formats multiple bookkeeping entries into a user-friendly confirmation message
    with all items listed.

    Args:
        result: MultiExpenseResult object containing all entries
        success_count: Number of successfully sent webhooks
        failure_count: Number of failed webhooks

    Returns:
        str: Formatted confirmation message
    """
    entries = result.entries
    total_items = len(entries)

    if result.intent == "cashflow_intents":
        return format_cashflow_confirmation_message(entries, success_count, failure_count)

    # 單項目：使用 v1 格式（向後相容）
    if total_items == 1:
        return format_confirmation_message(entries[0])

    # 多項目：使用 v1.5.0 新格式
    if success_count == total_items:
        message = f"✅ 記帳成功！已記錄 {total_items} 個項目：\n"
    elif failure_count == total_items:
        message = f"❌ 記帳失敗！{total_items} 個項目均未能記錄。\n"
    else:
        message = f"⚠️ 部分記帳成功！已記錄 {success_count}/{total_items} 個項目：\n"

    # 列出所有項目
    for idx, entry in enumerate(entries, start=1):
        twd_amount = entry.原幣金額 * entry.匯率

        message += f"\n📋 #{idx} {entry.品項}"

        # Display currency info (v003-multi-currency)
        if entry.原幣別 != "TWD":
            # Foreign currency: show original amount, rate, and TWD amount
            message += f"\n💰 {entry.原幣金額:.2f} {entry.原幣別} (匯率: {entry.匯率:.4f})"
            message += f"\n💵 {twd_amount:.2f} 元 TWD"
        else:
            # TWD: show amount only
            message += f"\n💰 {twd_amount:.0f} 元"

        if entry.交易類型:
            message += f"\n🧾 {entry.交易類型}"

        message += f"\n📂 {entry.分類}"
        message += f"\n⭐ {entry.必要性}"

        if entry.明細說明:
            message += f"\n📝 {entry.明細說明}"

        # Add advance payment information if present
        if entry.代墊狀態 == "代墊":
            message += f"\n💸 代墊給：{entry.收款支付對象}"
        elif entry.代墊狀態 == "需支付":
            message += f"\n💰 需支付給：{entry.收款支付對象}"
        elif entry.代墊狀態 == "不索取":
            message += f"\n🎁 不索取（代墊給：{entry.收款支付對象}）"

        # 項目之間加空行（除了最後一個）
        if idx < total_items:
            message += "\n"

    # 顯示共用資訊
    if entries:
        message += f"\n\n💳 付款方式：{entries[0].付款方式}"
        message += f"\n🔖 交易ID：{entries[0].交易ID}"
        message += f"\n📅 日期：{entries[0].日期}"

    return message


def _summary_batch_id(entries: list[BookkeepingEntry]) -> str:
    for entry in entries:
        if entry.交易ID.endswith("-01") or entry.交易ID.endswith("-02"):
            return entry.交易ID.rsplit("-", 1)[0]
    return entries[0].交易ID


def format_cashflow_confirmation_message(entries: list[BookkeepingEntry], success_count: int, failure_count: int) -> str:
    total_items = len(entries)
    if total_items == 0:
        return "❌ 現金流記帳失敗！未能記錄項目。"

    if success_count == total_items:
        message = "✅ 現金流記帳完成\n"
    elif failure_count == total_items:
        message = "❌ 現金流記帳失敗！\n"
    else:
        message = f"⚠️ 部分記帳成功（{success_count}/{total_items}）\n"

    batch_id = _summary_batch_id(entries)

    grouped: dict[str, BookkeepingEntry] = {}
    for entry in entries:
        grouped[entry.交易類型] = entry

    if "提款" in grouped:
        withdrawal = grouped["提款"]
        amount = withdrawal.原幣金額 * withdrawal.匯率
        summary = f"🏧 提款：{withdrawal.付款方式} → 現金 {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    if "轉帳" in grouped:
        transfer = grouped["轉帳"]
        amount = transfer.原幣金額 * transfer.匯率
        target_name = ""
        if "收入" in grouped:
            target_name = grouped["收入"].付款方式
        elif "支出" in grouped:
            target_name = grouped["支出"].付款方式

        if target_name:
            summary = f"🔁 轉帳：{transfer.付款方式} → {target_name} {amount:.0f}"
        else:
            summary = f"🔁 轉帳：{transfer.付款方式} {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    if "收入" in grouped and len(grouped) == 1:
        income = grouped["收入"]
        amount = income.原幣金額 * income.匯率
        summary = f"💰 收入：{income.付款方式} {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    message += f"\n- 記錄 {total_items} 筆現金流項目"
    return message


def handle_update_last_entry(user_id: str, fields_to_update: dict, *, raw_message: str | None = None) -> str:
    """
    Update last transaction with optimistic locking (v1.10.0 新增)

    Implements optimistic locking strategy:
    1. Read original transaction from KV
    2. Record target transaction ID
    3. Update target fields
    4. Re-read KV and verify transaction ID matches (concurrency check)
    5. Write updated transaction back to KV

    Args:
        user_id: LINE user ID
        fields_to_update: Fields to update (dict with keys: 品項, 分類, 專案, 付款方式, 明細說明, 必要性, 原幣金額)

    Returns:
        str: Success or error message for LINE user

    Examples:
        >>> handle_update_last_entry("U123456", {"品項": "工作午餐"})
        "✅ 修改成功！\n已更新：品項: 工作午餐"

        >>> handle_update_last_entry("U123456", {"原幣金額": 350.0})
        "✅ 修改成功！\n已更新：原幣金額: 350.0"
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


def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    Handle text message main flow (v1.5.0 更新：支援多項目支出)

    Flow:
    1. Receive user message
    2. Process via GPT (using process_multi_expense) to determine intent
    3. If multi_bookkeeping -> send multiple webhooks + return confirmation
    4. If conversation -> return GPT response
    5. If error -> return error message

    Args:
        event: LINE MessageEvent
        line_bot_api: LINE Bot API client
    """
    user_message = event.message.text
    reply_token = event.reply_token
    user_id = event.source.user_id  # 取得使用者 ID（用於 KV 儲存）

    logger.info(f"Received message from user {user_id}: {user_message}")

    try:
        # Process message via GPT (v1.5.0: using process_multi_expense)
        result = process_multi_expense(user_message)

        if result.intent in ("multi_bookkeeping", "cashflow_intents"):
            # Multi-item or single-item bookkeeping
            entries = result.entries
            total_items = len(entries)

            logger.info(f"Processing {total_items} bookkeeping item(s)")

            # Send webhooks for all entries (傳入 user_id 以儲存到 KV)
            success_count, failure_count = send_multiple_webhooks(entries, user_id)

            # Generate confirmation message
            reply_text = format_multi_confirmation_message(result, success_count, failure_count)

        elif result.intent == "update_last_entry":
            # 修改上一筆記帳（v1.10.0：使用 optimistic locking）
            logger.info(f"Update last entry request from user {user_id}")
            reply_text = handle_update_last_entry(user_id, result.fields_to_update, raw_message=user_message)

        elif result.intent == "conversation":
            # Conversation: return GPT response
            reply_text = result.response_text if result.response_text else "您好！有什麼可以協助您的嗎？"
            logger.info(f"Conversation response: {reply_text}")

        elif result.intent == "error":
            # Error: return error message from GPT
            reply_text = result.error_message if result.error_message else "無法處理您的訊息，請檢查輸入格式。"
            logger.info(f"Error response: {reply_text}")

        else:
            reply_text = "無法理解您的訊息。"

        # Reply to LINE user
        logger.info(f"Sending reply to LINE: {reply_text[:100]}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

        logger.info(f"Reply sent successfully")

    except Exception as e:
        # Unexpected error
        import traceback
        logger.error(f"Error handling message: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="系統處理訊息時發生錯誤，請重試。")
        )


def handle_image_message(event: MessageEvent, messaging_api_blob: MessagingApiBlob, line_bot_api: LineBotApi) -> None:
    """
    處理圖片訊息的主流程（v1.5.0 新增）

    流程：
    1. 取得圖片訊息 ID
    2. 下載圖片內容
    3. 使用 Vision API 分析收據
    4. 若識別成功：
       - 轉換為 BookkeepingEntry 列表
       - 為每一筆發送 webhook
       - 回覆確認訊息（列出所有項目）
    5. 若識別失敗：
       - 回覆錯誤訊息並建議使用文字描述

    Args:
        event: LINE MessageEvent（圖片訊息）
        messaging_api_blob: LINE Messaging API Blob 實例（用於下載圖片）
        line_bot_api: LINE Bot API client（用於回覆訊息）

    錯誤處理：
        - 下載失敗 → 「圖片下載失敗，請稍後再試」
        - Vision API 失敗 → 「無法處理圖片，請改用文字描述」
        - 非台幣收據 → 「v1.5.0 僅支援台幣，請提供文字描述並換算台幣金額」
        - 非收據圖片 → 「無法辨識收據資訊，請提供文字描述」
        - 圖片模糊 → 「收據圖片不清晰，請提供文字描述：品項、金額、付款方式」
    """
    message_id = event.message.id
    reply_token = event.reply_token
    user_id = event.source.user_id  # 取得使用者 ID（用於 KV 儲存）

    logger.info(f"Received image message from user {user_id}, message_id={message_id}")

    try:
        # 1. 下載圖片
        logger.info("開始下載圖片")
        image_data = download_image(message_id, messaging_api_blob)
        logger.info(f"圖片下載成功，大小={len(image_data)} bytes")

        # 2. 使用 Vision API 分析收據
        logger.info("開始分析收據圖片")
        receipt_items, error_code, error_message = process_receipt_image(image_data)

        # 3. 檢查處理結果
        if error_code:
            # 識別失敗：根據錯誤碼回覆不同訊息
            if error_code == "not_receipt":
                reply_text = f"❌ 無法辨識收據資訊\n\n{error_message}\n\n💡 請提供文字描述進行記帳，格式如：\n「午餐花了150元，用現金」"
            elif error_code == "unsupported_currency":
                reply_text = f"❌ 不支援的幣別\n\n{error_message}\n\n💡 請提供文字描述並手動換算台幣金額，格式如：\n「午餐花了150元，用現金」"
            elif error_code == "unclear":
                reply_text = f"❌ 收據圖片不清晰\n\n{error_message}\n\n💡 請提供文字描述，格式如：\n「品項、金額、付款方式」\n範例：「午餐花了150元，用現金」"
            elif error_code == "incomplete":
                reply_text = f"❌ 收據資訊不完整\n\n{error_message}\n\n💡 請提供文字描述補充完整資訊，格式如：\n「品項、金額、付款方式」"
            else:
                reply_text = f"❌ 無法處理收據圖片\n\n{error_message}\n\n💡 請改用文字描述進行記帳"

            logger.warning(f"收據識別失敗: {error_code} - {error_message}")

        else:
            # 識別成功：處理收據資料
            logger.info(f"收據識別成功，共 {len(receipt_items)} 個項目")

            # 4. 轉換為 BookkeepingEntry 列表
            # process_receipt_data 會自動處理每個項目的日期（v1.8.1）
            result = process_receipt_data(receipt_items, receipt_date=None)

            if result.intent == "multi_bookkeeping":
                # 成功轉換為記帳項目
                entries = result.entries
                total_items = len(entries)

                logger.info(f"轉換為 {total_items} 筆記帳項目")

                # 5. 發送 webhook（傳入 user_id 以儲存到 KV，支援「修改上一筆」功能）
                success_count, failure_count = send_multiple_webhooks(entries, user_id)

                # 6. 回覆確認訊息（使用統一的多項目格式）
                reply_text = format_multi_confirmation_message(result, success_count, failure_count)

                # 如果付款方式是預設值，顯示警告訊息
                if result.response_text:
                    reply_text += f"\n\n{result.response_text}"
                    reply_text += "\n💡 如不正確，請用文字補充記帳\n範例：「剛買的咖啡用Line Pay，50元」"

            elif result.intent == "error":
                # 處理收據資料時發生錯誤
                reply_text = f"❌ 處理收據資料時發生錯誤\n\n{result.error_message}"
                logger.error(f"處理收據資料失敗: {result.error_message}")

            else:
                reply_text = "無法處理收據資料，請重試"

        # 回覆 LINE 使用者
        logger.info(f"回覆 LINE 訊息: {reply_text[:100]}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

        logger.info("圖片訊息處理完成")

    except ImageTooLargeError as e:
        logger.error(f"圖片過大: {e}")
        reply_text = "❌ 圖片過大（超過 10MB）\n\n請重新上傳較小的圖片，或使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except ImageDownloadError as e:
        logger.error(f"圖片下載失敗: {e}")
        reply_text = "❌ 圖片下載失敗\n\n請稍後再試，或使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except VisionAPIError as e:
        logger.error(f"Vision API 失敗: {e}")
        reply_text = "❌ 無法處理圖片\n\n系統暫時無法分析收據，請使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except Exception as e:
        # 未預期的錯誤
        import traceback
        logger.error(f"處理圖片訊息時發生錯誤: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="系統處理圖片時發生錯誤，請重試或使用文字描述進行記帳。")
        )
