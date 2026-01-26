# -*- coding: utf-8 -*-
"""
GPT Client for Enrichment (T017)

封裝 GPT API 呼叫，使用 ENRICHMENT_RESPONSE_SCHEMA。
"""

import json
import logging
import os
from typing import Any

from openai import OpenAI

from app.schemas import ENRICHMENT_RESPONSE_SCHEMA
from app.gpt.prompts import CLASSIFICATION_RULES, CURRENCY_DETECTION
from app.shared.category_resolver import allowed_categories, get_classification_rules_description

logger = logging.getLogger(__name__)

# 從環境變數或 config 取得設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")


def _build_enrichment_prompt(transactions: list[dict], source_text: str) -> str:
    """
    建構 Enrichment 用的 GPT prompt。
    
    Args:
        transactions: Parser 輸出的交易列表
        source_text: 原始使用者訊息
    
    Returns:
        完整的 prompt 字串
    """
    # 取得分類清單
    categories = allowed_categories()
    category_list = "\n".join(f"- {c}" for c in sorted(categories))
    
    # 建構交易描述
    tx_descriptions = []
    for tx in transactions:
        tx_desc = (
            f"- id={tx['id']}, type={tx['type']}, "
            f"raw_item=\"{tx['raw_item']}\", amount={tx['amount']} {tx['currency']}, "
            f"payment={tx['payment_method']}"
        )
        if tx.get("counterparty"):
            tx_desc += f", counterparty={tx['counterparty']}"
        tx_descriptions.append(tx_desc)
    
    # 取得分類規則描述
    rules_desc = get_classification_rules_description()
    
    prompt = f"""你是一個記帳助手。請根據以下交易資訊，補充分類、專案、必要性和明細說明。

## 原始訊息
{source_text}

## Parser 已解析的交易（權威資料，不可修改）
{chr(10).join(tx_descriptions)}

## 你需要為每筆交易補充的欄位
1. **分類**：從允許的分類清單中選擇最適合的，禁止自建分類；若無完全符合，請選擇最相似的清單項目，並嚴格遵守下方分類規則。
2. **專案**：預設為「日常」，特殊情況可推導（如健康類別 → 健康檢查）
3. **必要性**：從以下選項選擇 - 必要日常支出 / 想吃想買但合理 / 療癒性支出 / 衝動購物（提醒）
4. **明細說明**：額外的商家、地點或用途說明
"""
    if rules_desc:
        prompt += f"""
## 分類規則（必須嚴格遵守）
{rules_desc}
"""
    prompt += f"""

## 允許的分類清單
{category_list}

請以 JSON 格式回覆，格式如下：
{{
  "version": "1.0",
  "enrichment": [
    {{
      "id": "t1",
      "分類": "家庭/餐飲/午餐",
      "專案": "日常",
      "必要性": "必要日常支出",
      "明細說明": ""
    }}
  ]
}}
"""
    return prompt


def call_gpt_enrichment(
    transactions: list[dict],
    source_text: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    呼叫 GPT API 進行 Enrichment。
    
    Args:
        transactions: Parser 輸出的交易列表（dict 格式）
        source_text: 原始使用者訊息
        api_key: OpenAI API Key（可選，預設從環境變數讀取）
        model: GPT 模型名稱（可選，預設 gpt-4o-mini）
    
    Returns:
        GPT 回應的 enrichment 結果（dict）
    
    Raises:
        ValueError: API Key 未設定
        Exception: GPT API 呼叫失敗
    """
    key = api_key or OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY is not set")
    
    model_name = model or GPT_MODEL
    client = OpenAI(api_key=key)
    
    prompt = _build_enrichment_prompt(transactions, source_text)
    
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一個專業的記帳分類助手。"},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": ENRICHMENT_RESPONSE_SCHEMA,
            },
        )
        
        response_text = completion.choices[0].message.content
        result = json.loads(response_text)
        
        logger.debug(f"GPT enrichment response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"GPT enrichment failed: {e}")
        raise
