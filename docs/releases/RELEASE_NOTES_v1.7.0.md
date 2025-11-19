# Release Notes - v1.7.0: Advance Payment & Need-to-Pay Tracking

**Release Date**: 2025-11-19
**Branch**: `002-advance-payment`
**Status**: Ready for Testing

---

## 🎯 Overview

v1.7.0 introduces **advance payment management** capabilities, enabling users to track:
- Money advanced to others (awaiting reimbursement)
- Money owed to others (need to repay)
- Non-collectible advances (gifts/family support)

This feature integrates seamlessly with the existing v1.5.0 multi-item expense tracking system.

---

## ✨ New Features

### 1. Advance Payment Status Recognition

The system now intelligently identifies three types of advance payment scenarios:

| Status | Keyword Pattern | Example |
|--------|----------------|---------|
| **代墊** (Advanced) | 「代」+對象, 「幫」+對象 | 代妹買Pizza, 幫同事墊車費 |
| **需支付** (Need to Pay) | 對象+「代訂」, 「幫我買」 | 弟代訂房間, 朋友幫我買票 |
| **不索取** (Non-collectible) | 「不用還」, 「不索取」, 「送給」 | 幫媽買藥不用還 |

### 2. Recipient/Payer Extraction

The system automatically extracts the name of the person involved:
- **Advanced**: Recipient who will repay you
- **Need to Pay**: Person you need to repay
- **Non-collectible**: Recipient of the gift/support

### 3. Enhanced Confirmation Messages

LINE confirmation messages now display advance payment information with emoji indicators:
- 💸 **代墊給**: Money advanced (awaiting reimbursement)
- 💰 **需支付給**: Money owed (need to repay)
- 🎁 **不索取**: Non-collectible advance (gift)

### 4. Payment Method Handling

- **Advanced items**: Use actual payment method (e.g., cash, card)
- **Need-to-Pay items**: Default to `"NA"` (not yet paid)
- **Non-collectible items**: Use actual payment method

---

## 🔧 Technical Changes

### Modified Files

1. **app/prompts.py**
   - Added `ADVANCE_PAYMENT_RULES` constant (~50 lines)
   - Integrated advance payment rules into `MULTI_EXPENSE_PROMPT`
   - Updated output format examples with advance payment fields

2. **app/gpt_processor.py**
   - Updated `process_multi_expense()` to read advance payment fields
   - Fields: `代墊狀態` and `收款支付對象`

3. **app/line_handler.py**
   - Enhanced `format_confirmation_message()` to display advance payment info
   - Enhanced `format_multi_confirmation_message()` for multi-item scenarios
   - Added conditional emoji display (💸/💰/🎁)

4. **app/webhook_sender.py**
   - Verified webhook payload includes advance payment fields (already present)

5. **tests/test_multi_expense.py**
   - Added 10 new test cases covering all advance payment scenarios
   - All tests passing (10/10)

### Data Model

No schema changes required. Existing fields are now actively used:
- `代墊狀態` (advance_payment_status): "無", "代墊", "需支付", "不索取"
- `收款支付對象` (recipient_or_payer): Person's name/relationship

---

## ✅ Test Coverage

### New Test Cases (10 total)

**Advance Payment (4 tests)**
- TC-V17-001: Basic advance payment (代妹購買Pizza)
- TC-V17-002: Advance for colleague (幫同事墊付計程車費)
- TC-V17-003: Advance for friend with card (代朋友買午餐刷狗卡)
- TC-V17-004: Coffee purchase for colleagues (代購咖啡給三位同事)

**Need to Pay (3 tests)**
- TC-V17-005: Basic need-to-pay (弟代訂房間)
- TC-V17-006: Friend helped purchase (朋友幫我買演唱會門票)
- TC-V17-007: Colleague advanced lunch (同事先墊午餐)

**Non-collectible (2 tests)**
- TC-V17-008: Gift to family (幫媽媽買藥不用還)
- TC-V17-009: Non-collectible parking fee (幫老婆付停車費不索取)

**Multi-item Integration (1 test)**
- TC-V17-010: Partial advance payment (早餐自己午餐代墊)

### Test Results
```
✅ 10/10 new feature tests passing
✅ Integration with existing multi-item tracking verified
✅ Local testing tool (test_local.py) validated
```

---

## 📝 Usage Examples

### Example 1: Advance Payment
```
User: 代妹購買Pizza兌換券979元現金
Bot Response:
✅ 記帳成功！

📋 Pizza兌換券
💰 金額：979 元 TWD
💳 付款方式：現金
📂 分類：家庭支出
⭐ 必要性：想吃想買但合理
💸 代墊給：妹
🔖 交易ID：20251119-143052
📅 日期：2025-11-19
```

### Example 2: Need to Pay
```
User: 弟代訂日本白馬房間10000元
Bot Response:
✅ 記帳成功！

📋 日本白馬房間
💰 金額：10000 元 TWD
💳 付款方式：NA
📂 分類：行程/住宿
⭐ 必要性：必要日常支出
💰 需支付給：弟
🔖 交易ID：20251119-143053
📅 日期：2025-11-19
```

### Example 3: Non-collectible
```
User: 幫媽媽買藥500元現金，不用還
Bot Response:
✅ 記帳成功！

📋 藥品
💰 金額：500 元 TWD
💳 付款方式：現金
📂 分類：健康/醫療/家庭成員
⭐ 必要性：必要日常支出
🎁 不索取（代墊給：媽媽）
🔖 交易ID：20251119-143054
📅 日期：2025-11-19
```

### Example 4: Multi-item with Partial Advance
```
User: 早餐80元，午餐150元幫同事代墊，現金
Bot Response:
✅ 記帳成功！已記錄 2 個項目：

📋 #1 早餐
💰 80 元
📂 家庭/餐飲/早餐
⭐ 必要性：必要日常支出

📋 #2 午餐
💰 150 元
📂 個人/餐飲
⭐ 必要性：必要日常支出
💸 代墊給：同事

💳 付款方式：現金
🔖 交易ID：20251119-143055
📅 日期：2025-11-19
```

---

## 🚀 Deployment Notes

### Prerequisites
- Python 3.11+
- All existing dependencies (no new packages required)
- GPT-4o API access
- LINE Bot SDK 3.8.0

### Migration
- No database migration required
- Existing data remains compatible
- New fields use default values for legacy entries

### Environment Variables
No new environment variables required.

---

## 📋 Testing Checklist

### Pre-deployment Testing
- [x] Unit tests passing (10/10)
- [x] Local testing tool verification
- [ ] Vercel deployment test
- [ ] Real LINE bot testing (3+ scenarios)
- [ ] Make.com webhook verification

### Post-deployment Verification
- [ ] Test advance payment recording
- [ ] Test need-to-pay recording
- [ ] Test non-collectible recording
- [ ] Test multi-item mixed scenarios
- [ ] Verify webhook data in Make.com
- [ ] Verify LINE message formatting

---

## ⚠️ Known Limitations (v1.7.0 Scope)

The following features are **explicitly excluded** from v1.7.0:

1. **Status Updates**: Cannot update advance payment status (e.g., "已收款", "已支付")
2. **Receipt Recognition**: Cannot identify advance payment from receipt images
3. **Reminders**: No automatic reminders for outstanding advances/debts
4. **Reporting**: No summary reports for advance payments

These features are planned for future releases (v1.8+).

---

## 🔮 Future Enhancements (v1.8 Planning)

- Status transition tracking (代墊 → 已收款, 需支付 → 已支付)
- Advance payment summary reports
- Outstanding balance tracking
- Reminder notifications
- Receipt image recognition for advance payments

---

## 🐛 Bug Fixes

None (new feature release).

---

## 📚 Documentation Updates

- Updated `CLAUDE.md` with development guidelines
- Created specification documents in `specs/002-advance-payment/`
  - `spec.md`: Feature specification
  - `plan.md`: Implementation plan
  - `data-model.md`: Data model design
  - `quickstart.md`: Quick start guide
  - `tasks.md`: Task breakdown
  - `contracts/advance-payment-webhook.json`: Webhook schema

---

## 👥 Contributors

- Claude AI (Implementation)
- Spec Kit (Planning framework)

---

## 📞 Support

For issues or questions:
- GitHub Issues: [linebot-gpt-bookkeeper/issues](https://github.com/yourusername/linebot-gpt-bookkeeper/issues)
- Documentation: See `specs/002-advance-payment/quickstart.md`

---

**Version**: 1.7.0
**Build Date**: 2025-11-19
**Build Branch**: 002-advance-payment
