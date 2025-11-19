# Tasks: v1.7 代墊與需支付功能

**功能分支**: `002-advance-payment`
**建立日期**: 2025-11-18
**狀態**: Ready for Implementation

## 概述

本文件將 v1.7 代墊功能拆解為可執行任務，按使用者故事組織以確保獨立交付和測試。

**技術堆疊**:
- Python 3.11+
- LINE Bot SDK 3.8.0
- OpenAI SDK ≥1.12.0
- Flask ≥3.0.0
- pytest ≥7.4.0

**專案結構**: Single project (Serverless 單體架構)

## 實作策略

### MVP 範圍
**最小可行產品 (MVP)**: 使用者故事 1 + 使用者故事 2（P1 功能）
- 代墊支出記錄（US1）
- 需支付款項記錄（US2）
- 排除：不索取代墊（US3，P2 可延後）

### 漸進式交付
1. **Phase 1-2**: 基礎設施和共用功能
2. **Phase 3**: US1（代墊）— 第一個可交付增量
3. **Phase 4**: US2（需支付）— 第二個可交付增量
4. **Phase 5**: US3（不索取）— 可選增量
5. **Phase 6**: 收尾和品質保證

## 任務清單

### Phase 1: 專案設置（Setup）

**目標**: 準備開發環境和基礎設施

- [ ] T001 確認分支 002-advance-payment 已建立並切換
- [ ] T002 確認現有依賴已安裝（requirements.txt 無變更）
- [ ] T003 確認本地 Python 3.11+ 環境可用
- [ ] T004 確認 GPT-4o API key 已配置（.env 檔案）

**完成標準**:
- 分支已切換
- `pytest --version` 可執行
- `python test_local.py` 可執行（現有功能測試）

---

### Phase 2: 基礎設施（Foundational）

**目標**: 建立所有使用者故事的共用基礎

#### GPT Prompt 基礎建設

- [ ] T005 [P] 在 app/prompts.py 新增 ADVANCE_PAYMENT_RULES 常數（表格格式，包含關鍵字對照表）
- [ ] T006 在 app/prompts.py 整合 ADVANCE_PAYMENT_RULES 到 MULTI_EXPENSE_PROMPT（使用 f-string）
- [ ] T007 [P] 在 app/prompts.py 更新輸出格式範例（新增代墊狀態和收款支付對象欄位）

#### 資料處理基礎建設

- [ ] T008 在 app/gpt_processor.py 確認 BookkeepingEntry 包含代墊欄位（代墊狀態、收款支付對象）
- [ ] T009 在 app/gpt_processor.py 更新 process_multi_expense 讀取代墊欄位（使用 .get() 提供預設值）

#### 訊息格式基礎建設

- [ ] T010 [P] 在 app/line_handler.py 修改 format_confirmation_message 新增代墊資訊顯示邏輯（條件顯示 + 圖示）
- [ ] T011 [P] 在 app/line_handler.py 修改 format_multi_confirmation_message 新增代墊資訊顯示邏輯

#### Webhook 基礎建設

- [ ] T012 在 app/webhook_sender.py 確認 send_to_webhook 的 payload 包含代墊欄位

**完成標準**:
- ADVANCE_PAYMENT_RULES 常數已定義（~300 tokens）
- GPT prompt 包含代墊識別規則
- 資料處理器可讀取代墊欄位
- 確認訊息格式可顯示代墊資訊
- Webhook payload 包含代墊欄位

**阻塞風險**: 此階段必須完成才能進入任何使用者故事實作

---

### Phase 3: 使用者故事 1 — 記錄代墊支出（P1）

**故事目標**: 使用者能透過 LINE 訊息記錄代墊支出，系統識別「代墊」狀態並提取收款對象

**獨立測試標準**:
- ✅ 發送「代妹購買Pizza兌換券979元現金」→ 回覆顯示代墊狀態「代墊」、收款對象「妹」
- ✅ GPT 正確識別關鍵字「代」+對象
- ✅ Webhook 包含代墊狀態和收款對象
- ✅ 確認訊息顯示 💸 圖示和收款對象

#### Prompt 增強

- [ ] T013 [US1] 在 ADVANCE_PAYMENT_RULES 定義「代墊」關鍵字（「代」+對象、「幫」+對象、「代購」等）
- [ ] T014 [US1] 在 ADVANCE_PAYMENT_RULES 定義提取收款對象規則（正規表達式模式）
- [ ] T015 [US1] 在 ADVANCE_PAYMENT_RULES 新增代墊項目付款方式規則（保留實際付款方式）

#### 整合測試（US1）

- [ ] T016 [US1] 在 tests/test_gpt_processor.py 新增測試案例：基本代墊（「代妹購買Pizza兌換券979元現金」）
- [ ] T017 [P] [US1] 在 tests/test_gpt_processor.py 新增測試案例：幫同事墊付（「幫同事墊付計程車費300元現金」）
- [ ] T018 [P] [US1] 在 tests/test_gpt_processor.py 新增測試案例：代朋友買午餐（「代朋友買了午餐150元刷狗卡」）
- [ ] T019 [P] [US1] 在 tests/test_gpt_processor.py 新增測試案例：代購咖啡（「代購咖啡50元給三位同事，Line轉帳」）
- [ ] T020 [US1] 在 tests/test_webhook_sender.py 驗證代墊項目 webhook payload 包含正確欄位

#### 錯誤處理（US1）

- [ ] T021 [US1] 在 tests/test_gpt_processor.py 新增測試案例：缺少收款對象（「幫忙買了東西200元」）→ 回傳 error intent
- [ ] T022 [US1] 驗證錯誤訊息：「請提供收款對象資訊（例如：幫誰代墊？）」

#### 端到端測試（US1）

- [ ] T023 [US1] 使用 test_local.py 測試完整流程（輸入 → GPT → 確認訊息）
- [ ] T024 [US1] 驗證確認訊息顯示 💸 代墊給：{對象}

**完成標準（US1）**:
- ✅ 5 個代墊測試案例通過（基於 spec.md 驗收場景）
- ✅ 錯誤處理測試通過（缺少對象時正確提示）
- ✅ 確認訊息格式正確（顯示代墊資訊）
- ✅ Webhook payload 正確（包含代墊狀態和收款對象）

**並行執行機會**:
- T016-T019 可並行執行（獨立測試案例）
- T017、T018、T019 可並行執行（不同測試檔案）

---

### Phase 4: 使用者故事 2 — 記錄需支付款項（P1）

**故事目標**: 使用者能透過 LINE 訊息記錄需支付款項，系統識別「需支付」狀態並提取支付對象

**獨立測試標準**:
- ✅ 發送「弟代訂日本白馬房間10000元」→ 回覆顯示代墊狀態「需支付」、支付對象「弟」、付款方式「NA」
- ✅ GPT 正確識別關鍵字「對象+代訂」
- ✅ Webhook 包含代墊狀態和支付對象
- ✅ 確認訊息顯示 💰 圖示和支付對象

#### Prompt 增強

- [ ] T025 [US2] 在 ADVANCE_PAYMENT_RULES 定義「需支付」關鍵字（對象+「代訂」、「幫我買」等）
- [ ] T026 [US2] 在 ADVANCE_PAYMENT_RULES 定義提取支付對象規則（對象在句首）
- [ ] T027 [US2] 在 ADVANCE_PAYMENT_RULES 新增需支付項目付款方式規則（預設「NA」）

#### 整合測試（US2）

- [ ] T028 [US2] 在 tests/test_gpt_processor.py 新增測試案例：基本需支付（「弟代訂日本白馬房間10000元」）
- [ ] T029 [P] [US2] 在 tests/test_gpt_processor.py 新增測試案例：朋友幫我買（「朋友幫我買了演唱會門票3000元」）
- [ ] T030 [P] [US2] 在 tests/test_gpt_processor.py 新增測試案例：同事先墊（「同事先墊了午餐120元」）
- [ ] T031 [P] [US2] 在 tests/test_gpt_processor.py 新增測試案例：媽媽幫忙付（「媽媽幫忙付了學費50000元」）
- [ ] T032 [P] [US2] 在 tests/test_gpt_processor.py 新增測試案例：室友代付（「室友代付了水電費1500元」）
- [ ] T033 [US2] 在 tests/test_webhook_sender.py 驗證需支付項目 webhook payload 付款方式為「NA」

#### 付款方式預設測試（US2）

- [ ] T034 [US2] 驗證需支付項目未說明付款方式時預設為「NA」

#### 端到端測試（US2）

- [ ] T035 [US2] 使用 test_local.py 測試完整流程（輸入 → GPT → 確認訊息）
- [ ] T036 [US2] 驗證確認訊息顯示 💰 需支付給：{對象}

**完成標準（US2）**:
- ✅ 5 個需支付測試案例通過（基於 spec.md 驗收場景）
- ✅ 付款方式預設「NA」測試通過
- ✅ 確認訊息格式正確（顯示需支付資訊）
- ✅ Webhook payload 正確（包含代墊狀態和支付對象）

**並行執行機會**:
- T028-T032 可並行執行（獨立測試案例）
- T029、T030、T031、T032 可並行執行（不同測試檔案）

---

### Phase 5: 使用者故事 3 — 處理不索取的代墊款項（P2）

**故事目標**: 使用者能透過 LINE 訊息記錄不索取代墊款項，系統識別「不索取」狀態

**獨立測試標準**:
- ✅ 發送「幫媽媽買藥500元現金，不用還」→ 回覆顯示代墊狀態「不索取」、收款對象「媽媽」
- ✅ GPT 正確識別關鍵字「不用還」、「不索取」
- ✅ 確認訊息顯示 🎁 圖示

#### Prompt 增強

- [ ] T037 [US3] 在 ADVANCE_PAYMENT_RULES 定義「不索取」關鍵字（「不用還」、「不索取」、「送給」）
- [ ] T038 [US3] 在 ADVANCE_PAYMENT_RULES 定義優先順序規則（不索取優先級最高）

#### 整合測試（US3）

- [ ] T039 [US3] 在 tests/test_gpt_processor.py 新增測試案例：基本不索取（「幫媽媽買藥500元現金，不用還」）
- [ ] T040 [P] [US3] 在 tests/test_gpt_processor.py 新增測試案例：不索取停車費（「幫老婆付停車費100元，不索取」）
- [ ] T041 [P] [US3] 在 tests/test_gpt_processor.py 新增測試案例：送給女兒（「代女兒繳補習費5000元Line轉帳，送給她的」）

#### 端到端測試（US3）

- [ ] T042 [US3] 使用 test_local.py 測試完整流程（輸入 → GPT → 確認訊息）
- [ ] T043 [US3] 驗證確認訊息顯示 🎁 不索取（代墊給：{對象}）

**完成標準（US3）**:
- ✅ 3 個不索取測試案例通過（基於 spec.md 驗收場景）
- ✅ 確認訊息格式正確（顯示不索取資訊）
- ✅ Webhook payload 正確（包含代墊狀態「不索取」）

**並行執行機會**:
- T039-T041 可並行執行（獨立測試案例）
- T040、T041 可並行執行（不同測試檔案）

---

### Phase 6: 多項目整合與邊緣案例

**目標**: 確保代墊功能與現有多項目記帳功能整合，處理邊緣案例

#### 多項目混合測試

- [ ] T044 在 tests/test_multi_expense.py 新增測試案例：部分代墊（「早餐80元，午餐150元幫同事代墊，現金」）
- [ ] T045 [P] 驗證多項目確認訊息正確顯示代墊資訊（僅午餐項目顯示代墊）
- [ ] T046 驗證多項目 webhook 發送兩筆（早餐代墊狀態「無」，午餐代墊狀態「代墊」）

#### 邊緣案例測試

- [ ] T047 [P] 測試「已支付」狀態拒絕（「已還給朋友500元」）→ 回傳 error：「v1.7 僅支援記錄新的代墊和需支付項目」
- [ ] T048 [P] 測試「已收款」狀態拒絕（「已收到同事還款300元」）→ 回傳 error
- [ ] T049 測試混合代墊狀態拒絕（「幫A代墊100元，B幫我墊付200元」）→ 回傳 error：「偵測到不同代墊狀態，請分開記帳」

#### 修改上一筆功能整合

- [ ] T050 測試 update_last_entry 支援修改代墊狀態（「上一筆改成代墊給朋友」）
- [ ] T051 [P] 測試 update_last_entry 支援修改收款對象（「上一筆收款對象改成同事」）

**完成標準**:
- ✅ 多項目混合代墊測試通過
- ✅ 邊緣案例錯誤處理正確
- ✅ update_last_entry 整合測試通過

**並行執行機會**:
- T045、T047、T048、T051 可並行執行（獨立測試案例）

---

### Phase 7: 品質保證與收尾

**目標**: 確保代碼品質和功能完整性

#### 完整性測試

- [ ] T052 執行完整測試套件 `pytest tests/ -v`，確保所有測試通過
- [ ] T053 驗證測試覆蓋率達到 90% 準確率目標（15+ 測試案例）
- [ ] T054 使用 test_local.py 執行冒煙測試（代墊、需支付、不索取各 1 個案例）

#### 本地測試工具更新

- [ ] T055 [P] 在 test_local.py 更新顯示邏輯支援代墊資訊（已在 line 46-47 預留）
- [ ] T056 驗證 test_local.py 正確顯示代墊狀態和收款對象

#### 文件更新

- [ ] T057 [P] 更新 README.md 說明 v1.7 代墊功能（如需要）
- [ ] T058 [P] 建立 RELEASE_NOTES_v1.7.0.md（參考 RELEASE_NOTES_v1.3.0.md 格式）

#### 端到端驗證（真實 LINE）

- [ ] T059 部署到 Vercel 測試環境
- [ ] T060 使用真實 LINE bot 測試代墊功能（至少 3 個案例）
- [ ] T061 驗證 Make.com webhook 接收代墊資料正確

**完成標準**:
- ✅ 所有 pytest 測試通過
- ✅ 本地測試工具正確顯示代墊資訊
- ✅ 真實 LINE bot 測試通過
- ✅ Make.com 接收資料正確

**並行執行機會**:
- T055、T057、T058 可並行執行（獨立文件）

---

## 依賴關係圖

### 故事完成順序

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (Integration) → Phase 7 (QA)
                                              ↓                ↓                ↓
                                          可獨立交付        可獨立交付        可獨立交付
```

### 任務依賴

**阻塞依賴**（必須按順序）:
- Phase 1 → Phase 2（基礎設施依賴專案設置）
- Phase 2 → Phase 3/4/5（使用者故事依賴基礎設施）
- Phase 3/4/5 → Phase 6（整合測試依賴故事完成）
- Phase 6 → Phase 7（品質保證依賴所有功能完成）

**並行機會**（可同時執行）:
- Phase 3、Phase 4、Phase 5 可並行開發（使用者故事獨立）
- 同一 Phase 內標記 [P] 的任務可並行執行

### MVP 交付路徑

**最快交付路徑**（僅 P1 功能）:
```
T001-T004 (Setup) → T005-T012 (Foundational) → T013-T024 (US1) → T025-T036 (US2) → T052-T061 (QA)
```

**預估時間**: 2.5-3 小時（基於 quickstart.md）

---

## 並行執行範例

### 範例 1：Phase 2 基礎設施並行

**可並行任務**:
- 開發者 A（或 LLM Session 1）: T005, T007（Prompt 相關）
- 開發者 B（或 LLM Session 2）: T010, T011（訊息格式）

### 範例 2：Phase 3 US1 測試並行

**可並行任務**:
- 開發者 A: T016, T017（測試案例 1, 2）
- 開發者 B: T018, T019（測試案例 3, 4）

### 範例 3：跨故事並行（US1 + US2 同時開發）

**可並行任務**:
- 團隊 A: T013-T024（完整 US1）
- 團隊 B: T025-T036（完整 US2）

**前提**: Phase 2 已完成

---

## 實作檢查清單

### MVP 完成標準（US1 + US2）

- [ ] ✅ GPT prompt 包含代墊和需支付識別規則
- [ ] ✅ 代墊項目測試案例通過（5 個）
- [ ] ✅ 需支付項目測試案例通過（5 個）
- [ ] ✅ 確認訊息顯示代墊資訊（💸 和 💰 圖示）
- [ ] ✅ Webhook payload 包含代墊欄位
- [ ] ✅ 錯誤處理測試通過（缺少對象、混合狀態）
- [ ] ✅ 真實 LINE bot 測試通過

### 完整功能標準（US1 + US2 + US3）

- [ ] ✅ MVP 標準 + 不索取項目測試案例通過（3 個）
- [ ] ✅ 多項目混合代墊測試通過
- [ ] ✅ 邊緣案例測試通過
- [ ] ✅ update_last_entry 整合測試通過
- [ ] ✅ 所有 pytest 測試通過（25+ 案例）

---

## 任務統計

**總任務數**: 61 個任務

**各階段任務分佈**:
- Phase 1 (Setup): 4 個任務
- Phase 2 (Foundational): 8 個任務
- Phase 3 (US1): 12 個任務
- Phase 4 (US2): 12 個任務
- Phase 5 (US3): 7 個任務
- Phase 6 (Integration): 8 個任務
- Phase 7 (QA): 10 個任務

**並行機會**: 23 個任務標記為 [P]（可並行執行）

**使用者故事任務分佈**:
- US1: 12 個任務
- US2: 12 個任務
- US3: 7 個任務
- 整合與 QA: 18 個任務（共用）

---

## 建議 MVP 範圍

**推薦**: Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2) + Phase 7 (QA subset)

**理由**:
- US1 和 US2 均為 P1 優先級，構成核心雙向金流管理
- US3（不索取）為 P2，可在 MVP 驗證後再引入
- MVP 包含 36 個任務（T001-T036 + T052-T061），預估 2.5-3 小時

**延後到 v1.7.1**:
- Phase 5 (US3) — 不索取代墊（7 個任務）
- Phase 6 部分邊緣案例（可選）

---

## 格式驗證

✅ **所有任務符合檢查清單格式**:
- ✅ 每個任務以 `- [ ]` 開頭（Markdown checkbox）
- ✅ 每個任務包含 Task ID（T001-T061，依執行順序）
- ✅ 並行任務標記 [P]（23 個任務）
- ✅ 使用者故事任務標記 [US1]/[US2]/[US3]（31 個任務）
- ✅ Setup、Foundational、Integration、QA 階段無故事標籤
- ✅ 描述包含具體檔案路徑（如需要）

---

## 下一步

1. **審查任務清單**: 確認任務完整性和優先級
2. **執行 MVP 任務**: T001-T036 + T052-T061（約 36 個任務）
3. **驗證獨立測試**: 每個使用者故事完成後執行獨立測試
4. **漸進式部署**: US1 驗證通過 → US2 → US3 → 完整發布

執行 `/speckit.implement` 開始自動化實作，或手動按任務順序開發。
