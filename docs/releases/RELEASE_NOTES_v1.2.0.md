# Release Notes - v1.2.0

**版本**：v1.2.0
**發布日期**：2025-11-15
**基於**：v1.0 MVP
**開發分支**：claude/v1.5.0-multi-expense-vision-01QiASjyjw61GXEjH7P49vQQ
**最後提交**：e2b826e

---

## 🎯 版本摘要

v1.2.0 實現了**多項目支出處理功能**（原 v1.5.0 Phase 1），支援在單一訊息中記錄多筆消費，同時保持 v1 無狀態架構。

---

## ✨ 新增功能

### 🔢 多項目支出處理

支援在單一訊息中包含多筆記帳項目，並共用付款方式：

**範例輸入**：
```
早餐80元，午餐150元，現金
```

**處理結果**：
- ✅ 自動識別 2 個項目
- ✅ 共用付款方式「現金」
- ✅ 共用交易ID（YYYYMMDD-HHMMSS）
- ✅ 分別發送 2 個 webhook 到 Make.com

### 📝 支援的分隔符號

- 逗號 `，`：「早餐80元，午餐150元，現金」
- 分號 `；`：「咖啡50；三明治35；狗卡」
- 頓號 `、`：「咖啡50、三明治35、現金」

### 🔄 向後相容

單項目記帳完全相容 v1 格式：
- 輸入：「午餐120元現金」
- 輸出：v1 格式確認訊息

---

## 🔧 重大改進

### 1. **Prompt 統一與優化**

**變更**：
- 移除重複的 `SYSTEM_PROMPT`（v1 專用）
- 統一使用 `MULTI_EXPENSE_PROMPT`（同時支援單項和多項）
- 模組化設計：`PAYMENT_METHODS`、`CLASSIFICATION_RULES`、`NECESSITY_LEVELS`

**效果**：
- 減少 **115 行**（-26%）
- 減少 **5,856 bytes**（-31%）
- Token 使用量降低約 **30%**

### 2. **品項提取邏輯優化**

**改進**：
- ✅ 保留完整品牌名稱：「星巴克咖啡」不會被拆分
- ✅ 正確提取實際物品：「饅頭做早餐使用」→ 品項「饅頭」、明細「做早餐使用」
- ✅ 用途說明放明細：分類根據用途判斷（如「饅頭」+「做早餐使用」→ 分類「家庭／餐飲／早餐」）

**範例**：
```
輸入：今天買了星巴克咖啡，花了150元，用Line轉帳付款
輸出：
- 品項：星巴克咖啡 ✅
- 明細說明：（空）
- 分類：家庭／飲品
```

### 3. **必要欄位驗證**

**新增驗證**：
- ❌ 缺少品項 → 錯誤：「缺少品項名稱，請提供完整資訊」
- ❌ 缺少金額 → 錯誤：「第N個項目缺少金額，請提供完整資訊」
- ❌ 缺少付款方式 → 錯誤：「缺少付款方式，請提供完整資訊」
- ❌ 不同付款方式 → 錯誤：「偵測到不同付款方式，請分開記帳」

**範例**：
```
輸入：120元現金
輸出：❌ 錯誤：缺少品項名稱，請提供完整資訊
```

### 4. **分類規則完善**

**修復**：
- ✅ 移除未授權的子分類（咖啡、茶）
- ✅ 補全遺漏的分類（食材／釀造、用品／雜項、通訊子分類等）
- ✅ 強化早餐/午餐/晚餐三層結構要求
- ✅ 對齊 spec.md 的完整分類列表

**範例**：
```
輸入：早餐50元現金
輸出：
- 品項：早餐
- 分類：家庭／餐飲／早餐 ✅（三層結構）
```

### 5. **付款方式轉換**

**強化**：
- 明確要求嚴格按照對照表轉換
- 禁止使用用戶輸入的原始詞彙

**範例**：
```
輸入：午餐120元灰狗
輸出：
- 付款方式：FlyGo 信用卡 ✅（不是「灰狗」）
```

### 6. **明細說明支援**

**新增**：
- 支援商家/地點資訊提取
- 支援用途說明提取

**範例**：
```
輸入：在開飯早餐50元，在7-11買咖啡45元，現金
輸出：
項目 #1: 早餐（明細：開飯）
項目 #2: 咖啡（明細：7-11）
```

---

## 🧪 測試增強

### 單元測試

新增檔案：
- `tests/test_multi_expense.py` - 多項目支出測試（20+ 測試案例）
- `tests/test_webhook_batch.py` - Webhook 批次發送測試（15+ 測試案例）

### 整合測試腳本

新增檔案：
- `run_v1_tests.sh` - v1 單項目測試（40+ 測試案例）
- `run_v15_tests.sh` - v1.5.0 多項目測試（50+ 測試案例）

**功能**：
- ✅ 自動驗證模式（`--auto` 參數）
- ✅ 色彩化輸出（通過/失敗指示）
- ✅ 詳細差異報告
- ✅ 交易ID顯示（僅供參考）

**文件**：
- `AUTO_TEST_GUIDE.md` - 自動測試使用指南
- `tests/README.md` - 測試文件更新

---

## 📁 檔案變更

### 新增檔案

```
tests/
├── test_multi_expense.py          # 多項目單元測試
└── test_webhook_batch.py          # Webhook 批次測試

scripts/
├── run_v1_tests.sh                # v1 測試腳本
├── run_v15_tests.sh               # v1.5.0 測試腳本
└── AUTO_TEST_GUIDE.md             # 測試指南
```

### 修改檔案

```
app/
├── prompts.py                     # 重構：統一 v1/v1.5.0 prompt
├── gpt_processor.py               # 新增：process_multi_expense()
├── line_handler.py                # 更新：支援多項目處理
└── webhook_sender.py              # 新增：send_multiple_webhooks()

tests/
└── README.md                      # 更新：測試文件
```

---

## 🐛 Bug 修復

### 提交記錄

以下是本版本的主要 bug 修復：

1. **e2b826e** - fix(prompt): extract actual item name, not meal type
   - 修復：「饅頭做早餐使用」正確提取品項「饅頭」

2. **6f50c0c** - fix(prompt): require item name - reject incomplete bookkeeping entries
   - 修復：「120元現金」不再猜測品項，正確回傳錯誤

3. **1d64589** - fix(prompt): preserve complete item names like "星巴克咖啡"
   - 修復：保留完整品牌名稱，不拆分

4. **f380b0a** - chore(prompt): remove redundant payment method examples
   - 精簡：移除冗餘範例

5. **4849e90** - fix(prompt): enforce strict payment method conversion
   - 修復：「灰狗」正確轉換為「FlyGo 信用卡」

6. **15b87cb** - fix(test): use consistent emoji for error intent display
   - 修復：錯誤意圖顯示格式統一

7. **8a450f2** - fix(test): align intent and payment display with test expectations
   - 修復：測試顯示格式對齊

8. **a62af18** - refactor(prompts): unify v1 and v1.5.0 to single modular prompt
   - 重構：統一 v1 和 v1.5.0 prompt

9. **9114e0c** - fix(prompt): restore complete classification list from spec
   - 修復：補全分類列表

10. **6b46a1c** - fix(prompt): remove unauthorized coffee and tea sub-categories
    - 修復：移除未授權的分類

11. **2c9c6e2** - fix(prompt): add detail description field to output examples
    - 修復：添加明細說明欄位支援

12. **f6925ca** - fix(prompt): enforce three-layer classification for meals
    - 修復：強制早餐/午餐/晚餐三層結構

13. **dd1c40b** - fix(prompt): explicitly specify intent values to prevent GPT confusion
    - 修復：明確指定 intent 值，防止 GPT 混淆

14. **2458407** - fix(test): correct coffee classification and add transaction ID display
    - 修復：咖啡分類和交易ID顯示

---

## 📊 測試覆蓋

### 單元測試

| 測試模組 | 測試案例數 | 狀態 |
|---------|----------|------|
| test_multi_expense.py | 20+ | ✅ 通過 |
| test_webhook_batch.py | 15+ | ✅ 通過 |

### 整合測試

| 測試腳本 | 測試案例數 | 狀態 |
|---------|----------|------|
| run_v1_tests.sh | 42 | ✅ 通過 |
| run_v15_tests.sh | 50+ | ✅ 通過 |

---

## 🔄 升級指南

### 從 v1.0 升級

v1.2.0 **完全向後相容** v1.0：

1. **單項目記帳**：無需修改，繼續使用原有格式
2. **新功能**：可選使用多項目格式
3. **部署**：直接部署即可，無需資料遷移

### 測試建議

升級後建議執行以下測試：

```bash
# 1. 單項目測試（v1 相容性）
./run_v1_tests.sh --auto

# 2. 多項目測試（新功能）
./run_v15_tests.sh --auto

# 3. 手動測試
python test_local.py '早餐80元，午餐150元，現金'
```

---

## 📚 文件更新

- ✅ `tests/README.md` - 測試文件
- ✅ `AUTO_TEST_GUIDE.md` - 自動測試指南
- ✅ `RELEASE_NOTES_v1.2.0.md` - 本版本發布說明

---

## 🚀 下一步

### Phase 2: 圖片識別功能（計劃中）

下個版本將實作：
- 📸 支援 LINE 圖片訊息
- 🔍 使用 GPT-4o Vision API 識別收據
- 📊 從收據提取品項、金額、付款方式

---

## 🙏 致謝

感謝使用者的詳細測試和反饋，協助我們完善了品項提取、分類規則和驗證邏輯。

---

## 📞 支援

如遇問題，請參考：
- 測試指南：`AUTO_TEST_GUIDE.md`
- 測試文件：`tests/README.md`
- 規格文件：`specs/001-linebot-gpt-bookkeeper/spec.md`

---

**完整變更集**：[查看所有提交](https://github.com/lwindg/linebot-gpt-bookkeeper/compare/...claude/v1.5.0-multi-expense-vision-01QiASjyjw61GXEjH7P49vQQ)
