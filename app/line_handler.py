# -*- coding: utf-8 -*-
"""
LINE Message Handler Module

This module handles LINE message events and user interactions.
"""

import logging
from linebot.models import MessageEvent, TextSendMessage, FlexSendMessage
from linebot import LineBotApi
from linebot.v3.messaging import MessagingApiBlob

from app.pipeline.router import process_message
from app.services.webhook_sender import send_multiple_webhooks
from app.services.image_handler import (
    download_image,
    process_receipt_image,
    build_image_authoritative_envelope,
    ImageDownloadError,
    ImageTooLargeError,
    VisionAPIError,
)
from app.services.statement_image_handler import (
    extract_taishin_statement_lines,
    ensure_cc_statement_page,
    notion_create_cc_statement_lines,
    detect_statement_date_anomaly,
    StatementVisionError,
)
from app.pipeline.image_flow import process_image_envelope
from app.line.formatters import (
    format_confirmation_message,
    format_multi_confirmation_message,
    format_cashflow_confirmation_message,
    format_settlement_report,
    create_flex_menu,
)
from app.line.update import handle_update_last_entry
from app.line.project_list import handle_project_list_request, is_project_list_command
from app.services.lock_service import LockService
from app.services.notion_service import NotionService

logger = logging.getLogger(__name__)


def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    Handle text message main flow (v2.7 更新：支援 Flex Menu 與 專案結算)

    Flow:
    1. Receive user message
    2. Check for commands (menu, project list, locks, settlement, help)
    3. Process via GPT (using process_multi_expense) to determine intent
    4. If multi_bookkeeping -> send multiple webhooks + return confirmation
    5. If conversation -> return GPT response
    6. If error -> return error message

    Args:
        event: LINE MessageEvent
        line_bot_api: LINE Bot API client
    """
    user_message = event.message.text.strip()
    reply_token = event.reply_token
    user_id = event.source.user_id  # 取得使用者 ID（用於 KV 儲存）

    logger.info(f"Received message from user {user_id}: {user_message}")

    try:
        # Step 2a: Menu Command (v2.7)
        if user_message in ("功能", "選單"):
            lock_service = LockService(user_id)
            current_project = lock_service.get_project_lock()
            payment_lock = lock_service.get_payment_lock()
            currency_lock = lock_service.get_currency_lock()
            reconcile_lock = lock_service.get_reconcile_lock()

            parts = []
            if current_project:
                parts.append(f"🔒 專案：{current_project}")
            if payment_lock:
                parts.append(f"🔒 付款：{payment_lock}")
            if currency_lock:
                parts.append(f"🔒 幣別：{currency_lock}")
            if reconcile_lock:
                period = reconcile_lock.get("period")
                parts.append(f"💳 對帳：ON ({period})")

            lock_summary = "\n".join(parts) if parts else "目前沒有鎖定設定。"

            flex_contents = create_flex_menu(current_project, lock_summary=lock_summary)
            line_bot_api.reply_message(
                reply_token,
                FlexSendMessage(alt_text="功能選單", contents=flex_contents)
            )
            return

        # Step 2b: Project List Command
        if is_project_list_command(user_message):
            reply_text = handle_project_list_request()
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=reply_text)
            )
            return

        # Step 2c: Settlement Command (v2.7)
        if user_message == "結算" or user_message.startswith("結算 "):
            lock_service = LockService(user_id)
            raw_name = user_message[3:].strip() if user_message.startswith("結算 ") else None
            
            project_name = None
            if raw_name:
                resolved, error = lock_service.resolve_project_name(raw_name)
                if resolved:
                    project_name = resolved
                else:
                    line_bot_api.reply_message(reply_token, TextSendMessage(text=error))
                    return
            else:
                project_name = lock_service.get_project_lock()
                if not project_name:
                    line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text="ℹ️ 您目前沒有鎖定任何專案，請提供專案名稱或先進行鎖定。\n範例：結算 日本 / 鎖定專案 日本")
                    )
                    return
            
            # Perform settlement
            notion_service = NotionService()
            settlement_data = notion_service.get_project_settlement(project_name)
            reply_text = format_settlement_report(project_name, settlement_data)
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=reply_text)
            )
            return

        # Step 2d: Help Command (v2.7)
        if user_message == "記帳教學":
            reply_text = """📖 記帳教學

您可以直接輸入文字或上傳照片來記帳：

1️⃣ 一般支出 📝
• 單筆：午餐 150 現金
• 多筆：
  晚餐 200 悠遊卡
  買水 25 現金

2️⃣ 代墊與需支付 🤝
• 我幫人墊：幫 妹妹 墊午餐 150 現金
• 別人幫墊：妹妹 先墊纜車票 500

3️⃣ 現金流與收入 💸
• 轉帳：合庫轉帳到Richart 5000
• 提款：提款 2000 大戶
• 收入：收入 1000 獎金
• 繳卡費：合庫繳卡費 5000 (或 繳大戶卡費 5000)

4️⃣ 圖片記帳 📸
• 直接上傳發票或收據照片

5️⃣ 鎖定功能 (Session Locks) 🔒
• 鎖定：鎖定專案 日本玩雪 / 鎖定付款 日圓現金 / 鎖定幣別 日幣
• 解鎖：解鎖專案 / 解鎖全部
• 狀態：鎖定狀態

6️⃣ 其他指令 🛠️
• 「選單」：開啟功能選單
• 「專案清單」：查看近期專案
• 「結算 {專案名稱}」：產出結算報告

💡 提示：使用「鎖定」功能可省去重複輸入專案或付款方式的時間！

🔗 專案位址：https://github.com/lwindg/linebot-gpt-bookkeeper
🏷 目前版本：v3.0.0"""
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=reply_text)
            )
            return

        # Step 2e: Lock Commands (v2.2.0)
        lock_service = LockService(user_id)
        lock_reply = lock_service.handle_command(user_message)
        if lock_reply:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=lock_reply)
            )
            return

        # Process message via Router (v2.2.0: pass user_id for locks)
        result = process_message(user_message, user_id=user_id)

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

        # 2. Routing: reconcile lock => statement import; else receipt flow
        lock_service = LockService(user_id)
        reconcile_lock = lock_service.get_reconcile_lock()

        if reconcile_lock:
            # Statement import mode
            period = reconcile_lock.get("period")
            statement_id = reconcile_lock.get("statement_id")
            bank = reconcile_lock.get("bank")

            if bank not in ("台新", "Taishin", "taishin"):
                reply_text = "❌ 目前僅支援台新帳單對帳。"
            else:
                try:
                    logger.info("開始分析台新帳單圖片")
                    lines = extract_taishin_statement_lines(image_data, statement_month=period)
                    statement_page_id = ensure_cc_statement_page(
                        statement_id=statement_id,
                        period=period,
                        bank="台新",
                        source_note=f"LINE image message_id={message_id}",
                    )

                    created_ids = notion_create_cc_statement_lines(
                        statement_month=period,
                        statement_id=statement_id,
                        lines=lines,
                        statement_page_id=statement_page_id,
                    )

                    if not created_ids:
                        raise StatementVisionError("no_statement_lines")

                    warning = detect_statement_date_anomaly(period, lines)

                    # increment uploaded count (best-effort)
                    try:
                        reconcile_lock["uploaded_images"] = int(reconcile_lock.get("uploaded_images", 0)) + 1
                        lock_service.kv.set(
                            f"lock:reconcile:{user_id}",
                            reconcile_lock,
                            ttl=86400 * 7,
                        )
                    except Exception:
                        pass

                    reply_text = (
                        "✅ 已匯入台新帳單明細"
                        f"\n• 期別：{period}"
                        f"\n• 帳單ID：{statement_id}"
                        f"\n• 新增明細：{len(created_ids)} 筆"
                    )
                    if warning:
                        reply_text += f"\n\n{warning}"
                    reply_text += "\n\n接著可輸入：執行對帳"
                except StatementVisionError as e:
                    reply_text = f"❌ 無法辨識台新帳單\n\n{str(e)}\n\n💡 請確認圖片是帳單明細截圖（非 Notion/聊天截圖），或重拍清晰一點。"
                except Exception as e:
                    logger.error(f"台新帳單匯入失敗: {e}")
                    reply_text = "❌ 匯入台新帳單時發生錯誤，請稍後再試。"

        else:
            # Receipt flow (existing)
            logger.info("開始分析收據圖片")
            receipt_items, error_code, error_message = process_receipt_image(image_data)

            # 檢查處理結果
            if error_code:
                # 識別失敗：根據錯誤碼回覆不同訊息
                if error_code == "not_receipt":
                    reply_text = f"❌ 無法辨識收據資訊\n\n{error_message}\n\n💡 請提供文字描述進行記帳，格式如：\n「午餐花了150元，用現金」"
                elif error_code == "unclear":
                    reply_text = f"❌ 收據圖片不清晰\n\n{error_message}\n\n💡 請提供文字描述，格式如：\n「品項、金額、付款方式」\n範例：「午餐花了150元，用現金」"
                elif error_code == "incomplete":
                    reply_text = f"❌ 收據資訊不完整\n\n{error_message}\n\n💡 請提供文字描述補充完整資訊，格式如：\n「品項、金額、付款方式」"
                else:
                    reply_text = f"❌ 無法處理收據圖片\n\n{error_message}\n\n💡 請改用文字描述進行記帳"

                logger.warning(f"收據識別失敗: {error_code} - {error_message}")

            else:
                # 識別成功：走 Parser-first image pipeline
                logger.info(f"收據識別成功，共 {len(receipt_items)} 個項目")

                image_envelope = build_image_authoritative_envelope(receipt_items)
                result = process_image_envelope(image_envelope, user_id=user_id)

                if result.intent in ("multi_bookkeeping", "cashflow_intents"):
                    entries = result.entries
                    total_items = len(entries)
                    logger.info(f"轉換為 {total_items} 筆記帳項目")

                    success_count, failure_count = send_multiple_webhooks(entries, user_id)
                    reply_text = format_multi_confirmation_message(result, success_count, failure_count)

                elif result.intent == "error":
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
        reply_text = f"❌ 無法處理圖片\n\n系統暫時無法分析收據。\n錯誤細節：{str(e)}\n\n請使用文字描述進行記帳"
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
