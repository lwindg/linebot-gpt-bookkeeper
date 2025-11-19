# v1.5.0: Multi-Item Expense & Receipt Recognition

> Process multiple expenses in a single message + complete receipt recognition

**Release Date**: 2025-11-15

---

## ✨ What's New

### 🔢 Multi-Item Expense Processing

Record multiple transactions in one message with shared payment method.

**Example**:
```
User: 早餐80元，午餐150元，現金

Bot:
✅ 記帳成功！已記錄 2 個項目：

📋 #1 早餐
💰 80 元
📂 家庭／餐飲／早餐

📋 #2 午餐
💰 150 元
📂 家庭／餐飲／午餐

💳 付款方式：現金
🔖 交易ID：20251115-120000（共用）
```

**Supported Separators**:
- Comma: `早餐80元，午餐150元，現金`
- Semicolon: `咖啡50；蛋糕120；Line轉帳`
- Flexible word order: `用狗卡，咖啡50，三明治35`

### ✏️ Update Last Entry

Modify your most recent transaction without re-entering everything.

**Example**:
```
User: 上一筆改成Line轉帳

Bot:
✅ 已更新上一筆記帳！
💳 付款方式：Line 轉帳 (已更新)
```

**Supported Keywords**:
- `上一筆` / `剛才` / `剛剛`
- `修改` / `改成`

**What You Can Update**:
- Payment method
- Amount
- Category
- Item name

### 📸 Complete Receipt Recognition

Full integration of GPT-4 Vision API for receipt image processing (from v1.2.0).

---

## 🔧 Technical Highlights

### Unified Prompt Architecture

Refactored prompt system into modular components:
- `PAYMENT_METHODS` - Shared payment method mapping
- `CLASSIFICATION_RULES` - Consistent categorization
- `MULTI_EXPENSE_PROMPT` - Unified processing logic

**Benefits**:
- Single source of truth
- Easier maintenance
- Reduced token usage
- Consistent behavior

### Vercel KV Integration

Transaction storage for update functionality:
- 24-hour retention
- Atomic operations
- Redis-based (Vercel KV)

---

## 📝 Key Features

| Feature | Single Item | Multi-Item | Image |
|---------|-------------|------------|-------|
| Item Recognition | ✅ | ✅ | ✅ |
| Payment Method | ✅ | ✅ (shared) | ✅ |
| Transaction ID | ✅ | ✅ (shared) | ✅ |
| Update Entry | ✅ | ✅ | ✅ |
| Backward Compatible | ✅ | ✅ | ✅ |

---

## 🔄 Breaking Changes

None - fully backward compatible with v1.0, v1.2.0, and v1.3.0.

---

## 📦 Installation

### New Environment Variables

```bash
# Vercel KV (required for update-last-entry)
KV_REST_API_URL=https://...
KV_REST_API_TOKEN=...
KV_REST_API_READ_ONLY_TOKEN=...

# Existing variables (no changes)
OPENAI_API_KEY=sk-...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
MAKE_WEBHOOK_URL=...
```

### Deploy to Vercel

```bash
# Add KV database to your Vercel project
vercel env add KV_REST_API_URL
vercel env add KV_REST_API_TOKEN
vercel env add KV_REST_API_READ_ONLY_TOKEN

# Deploy
vercel --prod
```

---

## 📊 Test Coverage

- **Unit Tests**: 29 test cases (all passing)
- **Integration Tests**: 26 test cases
- **Test Scripts**: `run_v15_tests.sh` (included)

Run tests:
```bash
./run_v15_tests.sh --auto
```

---

## ⚠️ Known Limitations

1. **Single Payment Method**: Multi-item must share one payment method
   - ❌ `早餐80元現金，午餐150元刷卡` (different methods)
   - ✅ `早餐80元，午餐150元，現金` (shared method)

2. **Currency**: Only TWD supported (foreign currency in v2.0)

3. **Update Scope**: Last 24 hours only

---

## 🔮 Coming Next

- **v1.6.0**: Time extraction and meal-based timestamps
- **v1.7.0**: Advance payment tracking
- **v2.0.0**: Foreign currency support

---

## 📚 Resources

- Full Release Notes: [`RELEASE_NOTES_v1.5.0.md`](./RELEASE_NOTES_v1.5.0.md)
- Test Cases: [`tests/test_cases_v1.5.md`](./tests/test_cases_v1.5.md)
- Test Script: [`run_v15_tests.sh`](./run_v15_tests.sh)

---

**Commit**: `f6ee7ce`
**Contributors**: Claude AI, Spec Kit Framework
