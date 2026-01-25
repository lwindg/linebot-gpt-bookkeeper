# -*- coding: utf-8 -*-
"""
Receipt processing helpers for GPT pipeline.
"""

import logging
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_MODEL
from app.gpt.types import BookkeepingEntry, MultiExpenseResult
from app.pipeline.transaction_id import generate_transaction_id
from app.category_resolver import resolve_category_autocorrect
from app.project_resolver import infer_project
from app.payment_resolver import normalize_payment_method

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

            # 分類處理：優先使用 Vision API 提供的分類，沒有則用 GPT 推斷
            品項 = receipt_item.品項
            if receipt_item.分類:
                # Vision API 已提供分類
                分類 = receipt_item.分類
                logger.info(f"使用 Vision API 分類：{品項} → {分類}")
            else:
                # Vision API 未提供分類，使用 GPT 推斷
                分類 = _infer_category(品項)
                logger.info(f"使用 GPT 推斷分類：{品項} → {分類}")

            # Normalize and enforce allow-list (auto-correct; fallback to 家庭支出)
            分類 = resolve_category_autocorrect(分類, fallback="家庭支出")
            專案 = infer_project(分類)

            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=item_date,  # 使用項目自己的日期
                品項=品項,
                原幣別="TWD",
                原幣金額=float(receipt_item.原幣金額),
                匯率=1.0,
                付款方式=payment_method,
                交易ID=transaction_id,  # 使用實際日期的交易ID
                明細說明=f"收據識別 {idx}/{len(receipt_items)}",
                分類=分類,
                交易類型="支出",
                專案=專案,
                必要性="必要日常支出",
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


def _infer_category(品項: str) -> str:
    """
    使用 GPT 進行智能分類推斷
    """
    from app.prompts import CLASSIFICATION_RULES

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        classification_prompt = f"""請根據品項名稱判斷最合適的分類。

{CLASSIFICATION_RULES}

**任務**：
- 品項：「{品項}」
- 請從上述分類列表中選擇**最合適**的分類
- 必須使用「大類／子類」或「大類／子類／細類」格式
- 只能使用已定義的分類，不可自創

**輸出格式**：
只回傳分類名稱，不要有其他文字。

範例：
- 輸入：咖啡 → 輸出：家庭／飲品
- 輸入：面紙 → 輸出：家庭／用品／雜項
- 輸入：早餐 → 輸出：家庭／餐飲／早餐
- 輸入：火車票 → 輸出：交通／接駁
"""

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "user", "content": classification_prompt}
            ],
            max_tokens=50,
            temperature=0.3
        )

        分類 = response.choices[0].message.content.strip()
        logger.info(f"GPT 分類推斷：{品項} → {分類}")

        return 分類

    except Exception as e:
        logger.error(f"GPT 分類推斷失敗：{e}")
        return _simple_category_fallback(品項)


def _simple_category_fallback(品項: str) -> str:
    """
    簡單的分類推斷（作為 GPT 分類失敗時的備選方案）
    """
    品項_lower = 品項.lower()

    # 餐飲類別
    if any(keyword in 品項_lower for keyword in ["早餐", "三明治", "蛋餅", "豆漿", "漢堡"]):
        return "家庭／餐飲／早餐"
    if any(keyword in 品項_lower for keyword in ["午餐", "便當", "麵", "飯"]):
        return "家庭／餐飲／午餐"
    if any(keyword in 品項_lower for keyword in ["晚餐", "火鍋"]):
        return "家庭／餐飲／晚餐"
    if any(keyword in 品項_lower for keyword in ["咖啡", "茶", "飲料", "果汁", "冰沙", "奶茶"]):
        return "家庭／飲品"
    if any(keyword in 品項_lower for keyword in ["點心", "蛋糕", "甜點", "餅乾", "糖果", "巧克力"]):
        return "家庭／點心"

    # 家庭用品
    if any(keyword in 品項_lower for keyword in ["面紙", "衛生紙", "紙巾", "棉條", "衛生棉"]):
        return "家庭／用品／雜項"

    # 交通類別
    if any(keyword in 品項_lower for keyword in ["計程車", "uber", "高鐵", "火車", "捷運", "公車"]):
        return "交通／接駁"
    if any(keyword in 品項_lower for keyword in ["加油", "汽油", "柴油"]):
        return "交通／加油"

    # 預設分類
    return "家庭支出"
