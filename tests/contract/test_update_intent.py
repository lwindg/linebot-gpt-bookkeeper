#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Update intent contract tests.

Ensures update intent outputs match expected structure and normalization rules.
"""

import json
from pathlib import Path
from unittest.mock import patch

from app.gpt_processor import process_multi_expense
from tests.test_utils import set_openai_mock_content


class TestUpdateIntentContract:
    def test_contract_schema_loads(self):
        schema_path = Path("specs/007-update-intent/contracts/update-intent.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        assert schema.get("title") == "Update Intent Response"
        assert schema.get("type") == "object"
        assert isinstance(schema.get("oneOf"), list)

    @patch("app.gpt_processor.OpenAI")
    def test_update_payment_method_normalized(self, mock_openai):
        set_openai_mock_content(mock_openai, '''
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "付款方式": "狗卡"
  }
}
''')

        result = process_multi_expense("修改付款方式為狗卡")

        assert result.intent == "update_last_entry"
        assert result.fields_to_update == {"付款方式": "台新狗卡"}

    @patch("app.gpt_processor.OpenAI")
    def test_update_multiple_fields_error(self, mock_openai):
        set_openai_mock_content(mock_openai, '''
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "付款方式": "台新狗卡",
    "分類": "交通/接駁"
  }
}
''')

        result = process_multi_expense("改付款方式與分類")

        assert result.intent == "error"
        assert result.error_message == "一次只允許更新一個欄位，請分開修改。"

    @patch("app.gpt_processor.OpenAI")
    def test_update_negative_amount_error(self, mock_openai):
        set_openai_mock_content(mock_openai, '''
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "原幣金額": -100
  }
}
''')

        result = process_multi_expense("更新金額 -100")

        assert result.intent == "error"
        assert result.error_message == "金額不可為負數"
