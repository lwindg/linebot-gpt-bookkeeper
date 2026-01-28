# -*- coding: utf-8 -*-
"""
Unit tests for receipt batch enrichment.
"""

from app.enricher.receipt_batch import enrich_receipt_items
from app.pipeline.image_flow import ImageItem


def test_enrich_receipt_items_with_mock():
    items = [
        ImageItem(item="咖啡", amount=50, currency="TWD"),
        ImageItem(item="三明治", amount=80, currency="TWD"),
    ]
    mock_enrichment = [
        {
            "id": "t1",
            "分類": "家庭/飲品",
            "專案": "日常",
            "必要性": "必要日常支出",
            "明細說明": "",
        },
        {
            "id": "t2",
            "分類": "家庭/餐飲/午餐",
            "專案": "日常",
            "必要性": "必要日常支出",
            "明細說明": "",
        },
    ]

    result = enrich_receipt_items(items, mock_enrichment=mock_enrichment)

    assert len(result) == 2
    assert result[0]["id"] == "t1"
    assert result[1]["id"] == "t2"
    assert result[0]["分類"] == "家庭/飲品"
    assert result[1]["分類"] == "家庭/餐飲/午餐"


def test_enrich_receipt_items_skip_gpt_defaults():
    items = [ImageItem(item="咖啡", amount=50, currency="TWD")]

    result = enrich_receipt_items(items, skip_gpt=True)

    assert result[0]["分類"] == "未分類"
    assert result[0]["專案"] == "日常"
    assert result[0]["必要性"] == "必要日常支出"
