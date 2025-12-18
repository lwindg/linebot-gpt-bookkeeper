# Expected v2 (Typed) for Functional Suites

## Background

Current suites use a flattened `expected` object with many optional string fields.
This makes it easy to accidentally fill incompatible combinations (e.g. `intent=錯誤` but missing `error_contains`).

This document proposes an `expected` v2 format that is typed by `intent` while keeping the same 3 intents:

- `記帳`
- `對話`
- `錯誤`

## Observed usage (v1)

Based on existing JSONL suites:

- `expense`: `記帳` uses `item/amount/payment/category`; `對話` uses no bookkeeping fields.
- `multi_expense`: `記帳` uses `payment/item_count`; `錯誤` uses `error_contains`.
- `advance_payment`: `記帳` uses `item/amount/payment/advance_status/recipient` (and occasionally `item_count/date`).
- `date`: `記帳` uses `item/amount/payment/category/date` (and occasionally `item_count`).

## v2 shape

### Common

```json
{
  "id": "TC-...",
  "group": "...",
  "name": "...",
  "message": "...",
  "expected": {
    "intent": "記帳|對話|錯誤",
    "...": "typed payload (see below)"
  }
}
```

### `intent=記帳`

```json
{
  "expected": {
    "intent": "記帳",
    "bookkeeping": {
      "item": "string (optional)",
      "amount": "string (optional)",
      "payment": "string (optional)",
      "category": "string (optional)",
      "project": "string (optional)",
      "item_count": "string (optional)",
      "advance_status": "string (optional)",
      "recipient": "string (optional)",
      "date": "string (optional: YYYY-MM-DD or {YEAR}-MM-DD)"
    }
  }
}
```

Rules:

- `bookkeeping` must be an object.
- Only fields present in `bookkeeping` are compared.
- `date` must be either `YYYY-MM-DD` or `{YEAR}-MM-DD`.

### `intent=錯誤`

```json
{
  "expected": {
    "intent": "錯誤",
    "error": {
      "contains": "non-empty string"
    }
  }
}
```

Rules:

- `error.contains` is required and must be non-empty.
- No `bookkeeping` payload is allowed.

### `intent=對話`

```json
{
  "expected": {
    "intent": "對話",
    "conversation": {}
  }
}
```

Rules:

- `conversation` is optional and currently not asserted (reserved for future checks).
- No `bookkeeping` or `error` payload is allowed.

## Compatibility plan

- Runner requires v2 (typed `expected`) and rejects v1 (flattened) formats.
- Suites are fully migrated to v2; keep this document as the single source of truth for authoring new cases.
