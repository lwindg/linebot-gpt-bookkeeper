# -*- coding: utf-8 -*-
"""
Batch enrichment for receipt image items.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, TYPE_CHECKING

from openai import OpenAI

from app.enricher.validator import validate_category
if TYPE_CHECKING:
    from app.pipeline.image_flow import ImageItem
from app.schemas import ENRICHMENT_RESPONSE_SCHEMA
from app.shared.category_resolver import allowed_categories, get_classification_rules_description

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")


def _build_receipt_enrichment_prompt(items: list[dict], source_text: str) -> str:
    categories = allowed_categories()
    category_list = "\n".join(f"- {c}" for c in sorted(categories))

    item_lines = []
    for item in items:
        item_lines.append(
            f"- id={item['id']}, item=\"{item['item']}\", amount={item['amount']} {item['currency']}"
        )

    rules_desc = get_classification_rules_description()

    prompt = f"""你是一個記帳助手。請根據以下收據項目資訊，補充分類、專案、必要性和明細說明。

## 原始來源
{source_text or "收據圖片"}

## 收據項目（權威資料，不可修改）
{chr(10).join(item_lines)}

## 你需要為每筆項目補充的欄位
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


def _items_to_payload(items: list[ImageItem]) -> list[dict]:
    payload: list[dict] = []
    for idx, item in enumerate(items, start=1):
        payload.append({
            "id": f"t{idx}",
            "item": item.item,
            "amount": item.amount,
            "currency": item.currency,
        })
    return payload


def call_gpt_receipt_enrichment(
    items: list[ImageItem],
    *,
    source_text: str = "",
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    key = api_key or OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY is not set")

    model_name = model or GPT_MODEL
    client = OpenAI(api_key=key)

    payload = _items_to_payload(items)
    prompt = _build_receipt_enrichment_prompt(payload, source_text)

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
    logger.debug(f"GPT receipt enrichment response: {result}")
    return result


def enrich_receipt_items(
    items: list[ImageItem],
    *,
    source_text: str = "",
    skip_gpt: bool = False,
    mock_enrichment: Optional[list[dict]] = None,
) -> list[dict]:
    if mock_enrichment is not None:
        enrichment_list = mock_enrichment
    elif skip_gpt:
        enrichment_list = [
            {
                "id": f"t{idx}",
                "分類": "未分類",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
            for idx, _item in enumerate(items, start=1)
        ]
    else:
        response = call_gpt_receipt_enrichment(items, source_text=source_text)
        enrichment_list = response.get("enrichment", [])

    normalized = []
    for item in enrichment_list:
        normalized.append({
            "id": item.get("id", ""),
            "分類": validate_category(item.get("分類", "未分類")),
            "專案": item.get("專案", "日常"),
            "必要性": item.get("必要性", "必要日常支出"),
            "明細說明": item.get("明細說明", ""),
        })
    return normalized
