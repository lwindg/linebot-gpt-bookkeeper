"""
JSON Schema definitions for Structured Output

使用 OpenAI Structured Output 確保 GPT 回應符合指定格式

v2.0 新增：
- AUTHORITATIVE_ENVELOPE_SCHEMA: Parser 輸出的權威 JSON 格式
- ENRICHMENT_RESPONSE_SCHEMA: AI Enrichment 回應格式
"""

# =============================================================================
# Parser-first Architecture Schemas (v2.0)
# =============================================================================

# Transaction type enum for Parser output
TRANSACTION_TYPES = [
    "expense",        # 一般支出
    "advance_paid",   # 代墊（我先付）
    "advance_due",    # 需支付（他人先付）
    "income",         # 收入
    "transfer",       # 轉帳
    "card_payment",   # 繳卡費
    "withdrawal",     # 提款
]

# Authoritative Envelope Schema - Parser output (T001)
# Parser 輸出的權威 JSON，AI 不得修改這些欄位
AUTHORITATIVE_ENVELOPE_SCHEMA = {
    "name": "authoritative_envelope",
    "version": "1.0",
    "description": "Parser 輸出的權威 JSON 格式，AI Enrichment 不得修改這些欄位",
    "schema": {
        "type": "object",
        "properties": {
            "version": {
                "type": "string",
                "description": "Schema version (e.g., '1.0')",
                "default": "1.0"
            },
            "source_text": {
                "type": "string",
                "description": "原始使用者輸入文字"
            },
            "parse_timestamp": {
                "type": "string",
                "description": "解析時間 (ISO 8601 format)"
            },
            "transactions": {
                "type": "array",
                "description": "解析出的交易列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "交易 ID (e.g., 't1', 't2')"
                        },
                        "type": {
                            "type": "string",
                            "enum": TRANSACTION_TYPES,
                            "description": "交易類型"
                        },
                        "raw_item": {
                            "type": "string",
                            "description": "原始品項文字（Parser 保留，AI 不可修改）"
                        },
                        "amount": {
                            "type": "number",
                            "minimum": 0,
                            "description": "金額（必須 > 0）"
                        },
                        "currency": {
                            "type": "string",
                            "enum": ["TWD", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CNY"],
                            "default": "TWD",
                            "description": "幣別 (ISO 4217)"
                        },
                        "payment_method": {
                            "type": "string",
                            "description": "付款方式（標準名稱或 'NA'）"
                        },
                        "counterparty": {
                            "type": "string",
                            "description": "收款/支付對象（代墊相關）",
                            "default": ""
                        },
                        "date": {
                            "type": ["string", "null"],
                            "description": "日期 (MM/DD 或語義化日期如 '今天')"
                        },
                        "accounts": {
                            "type": "object",
                            "description": "帳戶資訊（轉帳/繳卡費用）",
                            "properties": {
                                "from": {
                                    "type": ["string", "null"],
                                    "description": "轉出帳戶"
                                },
                                "to": {
                                    "type": ["string", "null"],
                                    "description": "轉入帳戶"
                                }
                            },
                            "default": {"from": None, "to": None}
                        },
                        "notes_raw": {
                            "type": "string",
                            "description": "原文中的額外描述（商家/地點等）",
                            "default": ""
                        }
                    },
                    "required": ["id", "type", "raw_item", "amount", "currency", "payment_method"],
                    "additionalProperties": False
                }
            },
            "constraints": {
                "type": "object",
                "description": "AI 約束條件",
                "properties": {
                    "classification_must_be_in_list": {
                        "type": "boolean",
                        "default": True
                    },
                    "do_not_modify_authoritative_fields": {
                        "type": "boolean",
                        "default": True
                    },
                    "unknown_payment_method_policy": {
                        "type": "string",
                        "enum": ["error", "fallback"],
                        "default": "error"
                    }
                }
            }
        },
        "required": ["version", "source_text", "transactions"]
    }
}

# AI Enrichment Response Schema (T002)
# AI 只需回傳這些補充欄位，不可修改 Parser 的權威欄位
ENRICHMENT_RESPONSE_SCHEMA = {
    "name": "enrichment_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "enrichment": {
                "type": "array",
                "description": "每筆交易的補充資訊",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "對應 transactions 的 id"
                        },
                        "分類": {
                            "type": "string",
                            "description": "分類路徑 (e.g., '家庭/餐飲/午餐')"
                        },
                        "專案": {
                            "type": "string",
                            "description": "專案名稱 (預設: '日常')"
                        },
                        "必要性": {
                            "type": "string",
                            "enum": ["必要日常支出", "想吃想買但合理", "療癒性支出", "衝動購物（提醒）"],
                            "description": "必要性等級"
                        },
                        "明細說明": {
                            "type": "string",
                            "description": "額外說明（商家/地點/用途）"
                        }
                    },
                    "required": ["id", "分類", "專案", "必要性", "明細說明"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["enrichment"],
        "additionalProperties": False
    }
}

# =============================================================================
# Legacy Schemas (v1.x - 保留向後相容)
# =============================================================================


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
                "enum": ["multi_bookkeeping", "cashflow_intents", "update_last_entry", "conversation", "error"],
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
                            "description": "Currency code (ISO 4217). MUST identify currency keywords: 美元/美金→USD, 歐元→EUR, 日圓/日幣→JPY, etc. Default TWD only when NO currency keyword present."
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
                        "專案": {
                            "type": "string",
                            "description": "Project name (default: 日常; may be inferred from category)"
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
                    "required": ["品項", "原幣別", "原幣金額", "明細說明", "分類", "專案", "必要性", "代墊狀態", "收款支付對象"],
                    "additionalProperties": False
                }
            },
            "cashflow_items": {
                "type": "array",
                "description": "List of cashflow items (for cashflow_intents)",
                "items": {
                    "type": "object",
                    "properties": {
                        "現金流意圖": {
                            "type": "string",
                            "enum": ["withdrawal", "transfer", "income", "card_payment"],
                            "description": "Cashflow intent type"
                        },
                        "品項": {
                            "type": "string",
                            "description": "Item name"
                        },
                        "原幣別": {
                            "type": "string",
                            "enum": ["TWD", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CNY"],
                            "description": "Currency code (ISO 4217)"
                        },
                        "原幣金額": {
                            "type": "number",
                            "description": "Amount in original currency"
                        },
                        "付款方式": {
                            "type": "string",
                            "description": "Payment method or account"
                        },
                        "分類": {
                            "type": "string",
                            "description": "Category path"
                        },
                        "日期": {
                            "type": "string",
                            "description": "Extracted date in MM/DD or semantic date"
                        }
                    },
                    "required": ["現金流意圖", "品項", "原幣別", "原幣金額", "付款方式", "分類"],
                    "additionalProperties": False
                }
            },
            "fields_to_update": {
                "type": "object",
                "description": "Fields to update (for update_last_entry)",
                "properties": {
                    "品項": {
                        "type": "string",
                        "description": "New item name"
                    },
                    "分類": {
                        "type": "string",
                        "description": "New category"
                    },
                    "專案": {
                        "type": "string",
                        "description": "New project"
                    },
                    "付款方式": {
                        "type": "string",
                        "description": "New payment method (must be canonical)"
                    },
                    "明細說明": {
                        "type": "string",
                        "description": "New detail note"
                    },
                    "必要性": {
                        "type": "string",
                        "enum": ["必要日常支出", "想吃想買但合理", "療癒性支出", "衝動購物（提醒）"],
                        "description": "New necessity level"
                    },
                    "原幣金額": {
                        "type": "number",
                        "minimum": 0,
                        "description": "New amount (must be >= 0)"
                    }
                },
                "additionalProperties": False
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
