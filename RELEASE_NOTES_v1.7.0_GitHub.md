# v1.7.0: Advance Payment & Need-to-Pay Tracking

> Track money lent to others, money owed to others, and non-collectible advances

**Release Date**: 2025-11-19
**Status**: ⚠️ Ready for Testing (Pre-release)

---

## ✨ What's New

### 💸 Advance Payment Tracking (代墊功能)

Track money you've advanced to others awaiting reimbursement.

**Keywords**: `代` + person, `幫` + person + `墊`

**Example**:
```
User: 代妹購買Pizza兌換券979元現金

Bot:
✅ 記帳成功！

📋 Pizza兌換券
💰 金額：979 元
💳 付款方式：現金
💸 代墊給：妹
🔖 交易ID：20251119-143052
```

### 💰 Need-to-Pay Tracking (需支付功能)

Track money you owe to others.

**Keywords**: person + `代訂`, person + `幫我買`, person + `先墊`

**Example**:
```
User: 弟代訂日本白馬房間10000元

Bot:
✅ 記帳成功！

📋 日本白馬房間
💰 金額：10000 元
💳 付款方式：NA
💰 需支付給：弟
🔖 交易ID：20251119-143053
```

### 🎁 Non-Collectible Advances (不索取功能)

Track advances you don't plan to collect (gifts, family support).

**Keywords**: `不用還`, `不索取`, `送給`

**Example**:
```
User: 幫媽媽買藥500元現金，不用還

Bot:
✅ 記帳成功！

📋 藥品
💰 金額：500 元
💳 付款方式：現金
🎁 不索取（代墊給：媽媽）
🔖 交易ID：20251119-143054
```

### 📅 Date Extraction (Restored)

Extract dates from messages for accurate transaction dating.

**Supported Formats**:
- MM/DD: `11/12 午餐120元現金` → Date: 2025-11-12
- Semantic: `昨天晚餐200元狗卡` → Date: Yesterday's date
- Supports: 今天, 昨天, 前天, 明天, 後天

**Example**:
```
User: 11/12 午餐120元現金

Bot:
📅 日期: 2025-11-12
🆔 交易ID: 20251112-120000
(Note: Time inferred from meal type - 午餐 → 12:00)
```

### 📝 Compound Item Names (Fixed)

Preserve complete item names with conjunctions.

**Conjunctions**: 和, 跟, 與, 加

**Example**:
```
User: 三明治和咖啡80元現金

Bot:
📋 三明治和咖啡  ✅ (not "三明治" or "早餐")
```

---

## 📋 Advance Payment Status Types

| Status | Chinese | Use Case | Payment Method |
|--------|---------|----------|----------------|
| **Advanced** | 代墊 | Money lent to others | Actual method used |
| **Need to Pay** | 需支付 | Money owed to others | `NA` (not paid yet) |
| **Non-collectible** | 不索取 | Gifts/family support | Actual method used |

---

## 🔧 Multi-Item Integration

Works seamlessly with multi-item expense tracking (v1.5.0):

```
User: 早餐80元，午餐150元幫同事代墊，現金

Bot:
✅ 記帳成功！已記錄 2 個項目：

📋 #1 早餐
💰 80 元

📋 #2 午餐
💰 150 元
💸 代墊給：同事

💳 付款方式：現金
```

---

## 🔄 Breaking Changes

None - fully backward compatible with v1.5.0.

---

## 📦 Installation

No new dependencies or environment variables required.

```bash
# Deploy as usual
git pull origin 002-advance-payment
vercel --prod
```

---

## 📊 Test Coverage

- **Test Cases**: 21 comprehensive tests
- **Categories**:
  - Advance payment: 4 tests
  - Need to pay: 3 tests
  - Non-collectible: 2 tests
  - Date extraction: 4 tests
  - Compound items: 4 tests
  - Backward compatibility: 3 tests
  - Multi-item integration: 1 test

**Run Tests**:
```bash
./run_v17_tests.sh --auto
```

---

## ⚠️ Known Limitations (v1.7.0 Scope)

The following features are **explicitly excluded** from v1.7.0:

1. **Status Updates**: Cannot update advance payment status
   - e.g., "已收款" (received), "已支付" (paid)

2. **Receipt Recognition**: Cannot identify advance payment from receipt images

3. **Reminders**: No automatic reminders for outstanding advances/debts

4. **Reporting**: No summary reports for advance payments

These features are planned for v1.8+.

---

## 🔮 Coming Next (v1.8+)

- Status transition tracking (代墊 → 已收款)
- Advance payment summary reports
- Outstanding balance tracking
- Reminder notifications
- Receipt image recognition for advance payments

---

## 📚 Resources

- Full Release Notes: [`RELEASE_NOTES_v1.7.0.md`](./RELEASE_NOTES_v1.7.0.md)
- Test Guide: [`tests/TEST_GUIDE_V17.md`](./tests/TEST_GUIDE_V17.md)
- Test Script: [`run_v17_tests.sh`](./run_v17_tests.sh)

---

## ⚠️ Pre-release Notice

This release is currently on the `002-advance-payment` branch and marked as **pre-release**.

**Testing Checklist**:
- [ ] Test advance payment recording
- [ ] Test need-to-pay recording
- [ ] Test non-collectible recording
- [ ] Test multi-item mixed scenarios
- [ ] Test date extraction (MM/DD and semantic)
- [ ] Test compound item names
- [ ] Verify webhook data in Make.com
- [ ] Verify LINE message formatting

**Before Production**:
- Merge `002-advance-payment` to `main`
- Complete testing checklist
- Update release status to stable

---

**Commit**: `90c227b`
**Branch**: `002-advance-payment`
**Contributors**: Claude AI, Spec Kit Framework
