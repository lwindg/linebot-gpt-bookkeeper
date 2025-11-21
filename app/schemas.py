"""
JSON Schema definitions for Structured Output

使用 OpenAI Structured Output 確保 GPT 回應符合指定格式
"""

# Multi-item bookkeeping response schema
# Note: Using strict=False to allow optional fields based on intent type
MULTI_BOOKKEEPING_SCHEMA = {
    "name": "multi_bookkeeping_response",
    "strict": False,
    "schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["multi_bookkeeping", "update_last_entry", "conversation", "error"],
                "description": "User intent type"
            },
            "payment_method": {
                "type": "string",
                "description": "Payment method (for multi_bookkeeping)"
            },
            "date": {
                "type": "string",
                "description": "Extracted date in MM/DD format or semantic date"
            },
            "items": {
                "type": "array",
                "description": "List of expense items (for multi_bookkeeping)",
                "items": {
                    "type": "object",
                    "properties": {
                        "品項": {
                            "type": "string",
                            "description": "Item name"
                        },
                        "原幣別": {
                            "type": "string",
                            "enum": ["TWD", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CNY"],
                            "description": "Currency code (ISO 4217), default TWD"
                        },
                        "原幣金額": {
                            "type": "number",
                            "description": "Amount in original currency"
                        },
                        "明細說明": {
                            "type": "string",
                            "description": "Additional details"
                        },
                        "分類": {
                            "type": "string",
                            "description": "Category path"
                        },
                        "必要性": {
                            "type": "string",
                            "enum": ["必要日常支出", "想吃想買但合理", "療癒性支出", "衝動購物（提醒）"],
                            "description": "Necessity level"
                        },
                        "代墊狀態": {
                            "type": "string",
                            "enum": ["無", "代墊", "需支付", "不索取"],
                            "description": "Advance payment status"
                        },
                        "收款支付對象": {
                            "type": "string",
                            "description": "Person to receive or pay"
                        }
                    },
                    "required": ["品項", "原幣別", "原幣金額", "明細說明", "分類", "必要性", "代墊狀態", "收款支付對象"],
                    "additionalProperties": False
                }
            },
            "update_field": {
                "type": "string",
                "description": "Field name to update (for update_last_entry)"
            },
            "update_value": {
                "type": "string",
                "description": "New value for the field (for update_last_entry)"
            },
            "response": {
                "type": "string",
                "description": "Response text (for conversation)"
            },
            "message": {
                "type": "string",
                "description": "Error message (for error)"
            }
        },
        "required": ["intent"]
    }
}
