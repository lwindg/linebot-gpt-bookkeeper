# -*- coding: utf-8 -*-
"""
Receipt processing helpers for GPT pipeline.
"""

import logging
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from app.gpt.types import BookkeepingEntry, MultiExpenseResult
from app.pipeline.transaction_id import generate_transaction_id
from app.shared.payment_resolver import normalize_payment_method
from app.services.exchange_rate import ExchangeRateService
from app.enricher.receipt_batch import enrich_receipt_items
from app.pipeline.image_flow import ImageItem

logger = logging.getLogger(__name__)


def process_receipt_data(receipt_items: List, receipt_date: Optional[str] = None) -> MultiExpenseResult:
    """
    將收據資料轉換為記帳項目（v1.5.0 圖片識別，v1.8.1 支援多日期）

    流程：
    1. 接收從 Vision API 提取的收據項目（List[ReceiptItem]，可能包含日期）
    2. 為每個項目補充預設值（日期優先使用項目自帶的日期）
    3. 為每個項目生成獨立交易ID（基於各自的日期）
    4. 回傳 MultiExpenseResult

    Args:
        receipt_items: 從圖片識別出的收據項目列表（ReceiptItem 物件，可能包含日期）
        receipt_date: 收據的整體日期（YYYY-MM-DD），作為 fallback

    Returns:
        MultiExpenseResult: 包含完整記帳資料的結果
    """
    try:
        if not receipt_items:
            return MultiExpenseResult(
                intent="error",
                error_message="未識別到任何收據項目"
            )

        # 台北時區
        taipei_tz = ZoneInfo("Asia/Taipei")
        now = datetime.now(taipei_tz)
        current_date = now.strftime("%Y-%m-%d")

        # 取得共用付款方式（第一個項目的付款方式）
        # 如果 Vision API 無法識別，預設為「現金」（最常見情況）
        payment_method_raw = receipt_items[0].付款方式 if receipt_items[0].付款方式 else "現金"
        payment_method = normalize_payment_method(payment_method_raw)
        payment_method_is_default = not receipt_items[0].付款方式  # 標記是否使用預設值

        # Batch enrichment (single GPT call)
        image_items = [
            ImageItem(
                item=receipt_item.品項,
                amount=float(receipt_item.原幣金額),
                currency=(receipt_item.原幣別 or "TWD").upper(),
            )
            for receipt_item in receipt_items
        ]
        enrichment_list = enrich_receipt_items(image_items, source_text="收據圖片")
        enrichment_map = {item.get("id"): item for item in enrichment_list}

        exchange_rate_service = ExchangeRateService()

        # v1.9.0: 生成批次時間戳（用於識別同一批次的項目）
        # 使用當前時間作為批次識別符
        batch_timestamp = now.strftime("%Y%m%d-%H%M%S")
        logger.info(f"批次時間戳：{batch_timestamp}")

        # 第一步：為每個項目生成基礎交易ID（基於實際日期）
        entries = []
        base_transaction_ids = []  # 儲存基礎交易ID（用於檢測重複）

        for idx, receipt_item in enumerate(receipt_items, start=1):
            # 日期選擇策略（混合模式，三層 fallback）
            # 優先級：項目日期 → 收據整體日期 → 當前日期
            if receipt_item.日期:
                item_date = receipt_item.日期
                logger.info(f"項目 {idx} 使用 Vision API 辨識的日期：{item_date}")
            elif receipt_date:
                item_date = receipt_date
                logger.info(f"項目 {idx} 使用收據整體日期（fallback）：{item_date}")
            else:
                item_date = current_date
                logger.info(f"項目 {idx} 使用當前日期（fallback）：{item_date}")

            # 生成基礎交易ID（使用實際日期）
            base_id = generate_transaction_id(
                item_date,
                None,  # 暫不支援時間提取
                receipt_item.品項,
                use_current_time=False  # 收據識別不使用當前時間
            )

            base_transaction_ids.append(base_id)

        # 第二步：處理重複的交易ID，為重複者加上序號
        transaction_id_counter = {}
        final_transaction_ids = []

        for base_id in base_transaction_ids:
            count = base_transaction_ids.count(base_id)
            if count > 1:
                # 有重複：加上序號
                if base_id not in transaction_id_counter:
                    transaction_id_counter[base_id] = 1
                else:
                    transaction_id_counter[base_id] += 1

                seq = transaction_id_counter[base_id]
                transaction_id = f"{base_id}-{seq:02d}"
            else:
                # 無重複：直接使用
                transaction_id = base_id

            final_transaction_ids.append(transaction_id)

        # 第三步：建立 BookkeepingEntry 物件
        for idx, receipt_item in enumerate(receipt_items, start=1):
            # 取得對應的日期和交易ID
            if receipt_item.日期:
                item_date = receipt_item.日期
            elif receipt_date:
                item_date = receipt_date
            else:
                item_date = current_date

            transaction_id = final_transaction_ids[idx - 1]

            品項 = receipt_item.品項
            enrichment = enrichment_map.get(f"t{idx}", {})
            分類 = enrichment.get("分類", "未分類")
            專案 = enrichment.get("專案", "日常")
            必要性 = enrichment.get("必要性", "必要日常支出")
            明細說明 = enrichment.get("明細說明", "") or f"收據識別 {idx}/{len(receipt_items)}"

            原幣別 = (receipt_item.原幣別 or "TWD").upper()
            if 原幣別 not in ExchangeRateService.SUPPORTED_CURRENCIES:
                return MultiExpenseResult(
                    intent="error",
                    error_message=f"不支援的幣別：{原幣別}",
                )

            匯率 = 1.0
            if 原幣別 != "TWD":
                rate = exchange_rate_service.get_rate(原幣別)
                if rate is None:
                    return MultiExpenseResult(
                        intent="error",
                        error_message=f"無法取得 {原幣別} 匯率，請稍後再試或改用新台幣記帳",
                    )
                匯率 = rate

            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=item_date,  # 使用項目自己的日期
                品項=品項,
                原幣別=原幣別,
                原幣金額=float(receipt_item.原幣金額),
                匯率=匯率,
                付款方式=payment_method,
                交易ID=transaction_id,  # 使用實際日期的交易ID
                明細說明=明細說明,
                分類=分類,
                交易類型="支出",
                專案=專案,
                必要性=必要性,
                代墊狀態="無",
                收款支付對象="",
                附註=""
            )

            entries.append(entry)

        result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=entries
        )

        # 如果付款方式是預設值，在 response_text 中加入提醒
        if payment_method_is_default:
            result.response_text = "⚠️ 未從收據識別到付款方式，已預設為「現金」"

        return result

    except Exception as e:
        logger.error(f"處理收據資料時發生錯誤: {e}")
        return MultiExpenseResult(
            intent="error",
            error_message="處理收據資料時發生錯誤，請重試"
        )
