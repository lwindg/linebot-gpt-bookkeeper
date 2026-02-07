# 進度紀錄

## 目前狀態
- 專案 options 取得、短期專案比對、專案清單指令已完成
- 健康/醫療分類預設（本人/家庭成員）已補上

## 已完成變更
- 新增 Notion 專案 options 取得（Make webhook + KV cache）、短期專案比對、專案清單指令、測試與本地測試工具更新（commit: d100eb5）
- 健康/醫療分類預設邏輯與家人關鍵字（含 妹/弟），並補齊測試（commit: 15c71a5）

## 已驗證
- `uv run pytest tests/unit/test_project_resolver.py tests/integration/test_edit_last_transaction.py`
- `uv run pytest tests/unit/test_project_list.py`
- `uv run pytest tests/unit/test_local_update.py`
- `uv run pytest tests/unit/test_category_resolver.py`
