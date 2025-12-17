# AGENTS 開發指南

本文件定義本專案中所有代理（Agents）的開發規範和工作流程，內容以 CLAUDE.md 為基礎並刪除了僅限 Claude 的部分。這些指令在發生衝突時優先於使用者提示。

---

## 溝通與語言

- 規格、計畫、任務與溝通：使用正體中文
- 程式碼註解、識別符、Git 訊息、技術文件、配置：使用英文

---

## 專案重點與原則

- 主要技術：Python 3.11+（uv 管理）、SQLite（主要）、PostgreSQL（次要）、Spec Kit
- 取向：正確性與一致性優先，小且明確的變更，遵循既有模式
- 工具限制：除非明確要求，不引入 pip/poetry/venv 等替代工具

---

## 工具與環境

### Python 套件管理

- 僅使用 uv：
  - 安裝：`uv add <package>`
  - 移除：`uv remove <package>`
  - 同步：`uv sync`
  - 執行：`uv run <script>.py`、`uv run pytest`、`uv run ruff`

### Shell 工具偏好

- 搜尋檔案：`fd`（無法使用時可改用同類工具）
- 搜尋文字：`rg`
- 程式碼結構：`ast-grep`
- 互動選擇：`fzf`
- JSON：`jq`
- YAML/XML：`yq`

---

## Git 工作流程

- 分支：`<action>/<description>`（例：`feat/integrate-line`）
- 提交：`<action>(module): <message>`（例：`fix(linebot): handle empty messages`）
- actions：`feat` `fix` `refactor` `docs` `test` `style` `chore`

---

## 進度與提交（必做）

- 每次完成一段可交付變更後必須：
  - 以符合規範的 commit message 提交「本次實際修改的檔案」
  - 同步更新對應的進度檔（例如：`specs/004-prompt-refactor/progress.md`），在「已完成變更」內補上摘要與 commit hash

## 指令：「讀取進度」

- 當使用者下「讀取進度」且未指定路徑時：
  - 預設讀取：`specs/004-prompt-refactor/progress.md`
- 若使用者指定檔案/路徑，則以使用者指定為準。

---

## Spec Kit 流程

**暫時狀態**：Spec Kit 工具目前無法使用，開發期間可暫時跳過 `/speckit.*` 指令與 `specify check`；待工具恢復後再回到以下流程。

1. Specify：撰寫使用者故事與驗收標準（/speckit.specify）
2. Plan：技術規劃（/speckit.plan）
3. Clarify：釐清需求（/speckit.clarify）
4. Tasks：拆解任務（/speckit.tasks）
5. Implement：執行開發（/speckit.implement）
6. Analyze：驗證一致性與品質（/speckit.analyze）

### 快速參考

- `/speckit.constitution`：憲章
- `/speckit.specify`：功能規格
- `/speckit.plan`：實作規劃
- `/speckit.tasks`：任務清單
- `/speckit.implement`：開發執行
- `/speckit.analyze`：一致性與品質檢查

**恢復後規範**：工具恢復可用時，**必須**在功能視為就緒、提交或合併之前執行 `specify check`。
