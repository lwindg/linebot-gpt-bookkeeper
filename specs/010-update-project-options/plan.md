# 010 更新專案：短期專案比對與清單查詢 — 計畫

## 實作策略

- 維持 update intent 流程不變，只在「更新專案」時插入 resolver。
- 專案比對採規則化流程（無 AI），透過 Make.com 取得 Notion select options。
- 使用 KV 快取 options，降低 Make/Notion 負載。

## 實作步驟

1. **新增設定與常數**
   - 新增 `PROJECT_OPTIONS_WEBHOOK_URL`（Make webhook）
   - 新增 `PROJECT_OPTIONS_TTL`（專案清單快取 TTL）
   - 新增長期專案清單常數（code config）

2. **新增專案清單服務**
   - `app/services/project_options.py`
   - 呼叫 Make webhook，解析 `{"options": [...]}` 或純陣列回應
   - KV 快取成功結果（TTL 可設定）
   - 回傳失敗狀態與錯誤碼

3. **新增專案解析與比對工具**
   - `app/shared/project_resolver.py` 擴充：
     - `normalize_project_name()`
     - `extract_project_date_range()`（支援 4 種日期前綴格式）
     - `is_long_term_project()`
     - `match_short_term_project()`（相似度 + 唯一判斷）
     - 候選排序：相似度由高到低；同分時日期越近優先
     - `filter_recent_project_options()`（專案清單篩選）

4. **更新更新流程**
   - `app/line/update.py`：
     - 當欄位為「專案」時：
       - 長期命中 → 直接更新
       - 含日期 → 若無唯一候選 → 直接使用輸入
       - 不含日期 → Make 取清單 → 比對 → 唯一則更新，否則回候選 3 筆
      - 候選不足 3 筆時只列出實際數量；無候選時不列清單

5. **新增專案清單指令**
   - `app/line/project_list.py`：
     - 指令判斷：`專案清單`
     - Make 取清單 → 近期篩選 → 回覆列表
   - `app/line_handler.py`：指令優先於 GPT 路徑

6. **補測試**
   - 新增單元測試：日期解析、相似度、唯一判定
   - 新增單元測試：專案清單指令與回覆
   - 新增整合測試：更新專案的成功/失敗路徑

## 影響範圍

- 新增檔案：`app/services/project_options.py`
- 新增檔案：`app/line/project_list.py`
- 更新檔案：
  - `app/shared/project_resolver.py`
  - `app/line/update.py`
  - `app/line_handler.py`
  - `app/config.py`
- 測試新增：`tests/unit/test_project_resolver.py`（擴充）或新增對應測試檔

## 設定變數

- `PROJECT_OPTIONS_WEBHOOK_URL`
- `PROJECT_OPTIONS_TTL`（預設 21600 或 86400 秒）

## 驗證方式

- 手動：在 LINE 輸入「專案修改為日本玩雪」檢查回覆
- 自動：執行 `uv run pytest` 中相關測試

## 風險與緩解

- Make 失敗 → 允許含日期輸入直接更新；不含日期則回錯誤
- 候選不唯一 → 回候選 3 筆並要求完整名稱
- 日期解析失敗 → 視為無日期（走一般比對或回錯誤）
