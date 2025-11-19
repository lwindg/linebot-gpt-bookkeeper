# Claude 開發指南

本文件定義 Claude AI 助手在本專案的開發規範和工作流程。

這些指令在發生衝突時**覆蓋使用者提示**。

---

## 📋 溝通規範

### 文檔語言政策

**正體中文（繁體中文）- 用於規格與溝通**：
- 功能規格文件（`spec.md`, `plan.md`, `tasks.md` 等）
- 與使用者的所有溝通
- 團隊需求討論

**英文（English）- 用於所有其他內容**：
- 程式碼註釋（code comments）
- 程式碼識別符（變數名稱、函式名稱、類別名稱）
- Git 提交訊息（commit messages）
- Pull Request 標題和描述
- API 規格描述（OpenAPI `description`, `summary` 欄位）
- 技術文件（technical documentation）
- 配置檔案與腳本

---

## 🎯 專案概述

### 核心技術棧

- **語言**：Python 3.11+（使用 uv 管理）
- **資料儲存**：SQLite（主要）、PostgreSQL（次要支援）
- **規格驅動開發**：Spec Kit（位於 `/specs` 目錄）

### 開發原則

Claude 應該：
- **優先考慮正確性、安全性和一致性**，而非簡潔性
- **偏好小型、範圍明確的變更**，遵循本文件中的模式
- **尊重現有模式**，避免發明新模式
- **避免引入替代工具**（例如 pip、poetry、原生 venv），除非明確要求

---

## 🛠️ 工具與環境

### Python 套件管理（uv）

Claude **必須**專門使用 **uv** 進行 Python 套件管理。

#### 套件管理指令

```bash
# 安裝依賴套件
uv add <package>

# 移除依賴套件
uv remove <package>

# 同步依賴套件
uv sync
```

#### 執行 Python 程式碼

```bash
# 執行 Python 腳本
uv run <script>.py

# 執行測試
uv run pytest

# 執行 linter/工具
uv run ruff
```

**Claude 不得**：
- 在此專案中使用 `pip install`、`requirements.txt` 或直接使用 venv

---

### Shell 工具指南

**重要**：優先使用以下專用工具取代傳統 Unix 指令

| 任務類型 | 必須使用 | 不要使用 |
|---------|---------|---------|
| 尋找檔案 | `fd` | `find`, `ls -R` |
| 搜尋文字 | `rg` (ripgrep) | `grep`, `ag` |
| 分析程式碼結構 | `ast-grep` | `grep`, `sed` |
| 互動式選擇 | `fzf` | 手動篩選 |
| 處理 JSON | `jq` | `python -m json.tool` |
| 處理 YAML/XML | `yq` | 手動解析 |

#### 工具安裝

```bash
# macOS (Homebrew)
brew install fd ripgrep ast-grep fzf jq yq

# Ubuntu/Debian
apt-get install fd-find ripgrep fzf jq
cargo install ast-grep
```

#### 使用範例

```bash
# 尋找所有 Python 檔案
fd -e py

# 搜尋包含 "LINE" 的程式碼
rg "LINE" --type py

# 互動式選擇檔案
fd -e py | fzf

# 解析 JSON 資料
cat data.json | jq '.field'

# 解析 YAML 資料
cat config.yaml | yq '.settings'
```

---

## 🧩 Spec Kit 開發流程

### 核心原則

**Claude 必須將規格視為驅動實作的第一級產出物。**

### 開發流程步驟

本專案採用 Spec Kit 開發方法論，所有功能開發應遵循以下流程：

1. **制定規格**（Specify）：使用 `/speckit.specify` 定義使用者故事和驗收標準
2. **規劃設計**（Plan）：使用 `/speckit.plan` 進行技術規劃
3. **釐清需求**（Clarify）：使用 `/speckit.clarify` 解決規格不明確之處
4. **生成任務**（Tasks）：使用 `/speckit.tasks` 將需求拆解為可執行任務
5. **執行實作**（Implement）：使用 `/speckit.implement` 執行開發任務
6. **分析檢查**（Analyze）：使用 `/speckit.analyze` 驗證一致性和品質

### 核心指令

```bash
# 初始化新的 spec 專案
specify init <name>

# 在當前專案初始化
specify init .
# 或
specify init --here

# 驗證所有規格文件
specify check
```

### 驗證規則

**Claude 必須在以下時機執行 `specify check`**：

- ✅ 將功能視為「就緒」之前
- ✅ 提交程式碼變更之前
- ✅ 合併分支之前
- ✅ 部署到生產環境之前

### 專案結構

```
/specs/                    # 所有規格文件
├── 001-linebot-gpt-bookkeeper/
│   ├── spec.md           # 功能規格
│   ├── plan.md           # 技術規劃
│   ├── tasks.md          # 任務清單
│   ├── checklists/       # 檢查清單
│   └── knowledge/        # 領域知識
├── 002-advance-payment/
│   └── ...
.specify/
└── memory/
    └── constitution.md   # 專案憲章
```

### API 與規格同步

**Claude 必須協助保持以下同步**：

- API 實作 ↔ 規格定義
- 資料模型 ↔ 規格中的資料結構
- 業務邏輯 ↔ 使用者故事和驗收標準

當進行以下變更時，確保同步更新：
- API 端點新增或修改 → 更新 `spec.md` 的 API 定義
- 資料模型變更 → 更新 `spec.md` 的資料結構定義
- 業務邏輯變更 → 更新相關使用者故事和驗收標準

---

## 🧠 推理協議：Sequential Thinking MCP

本模組控制 Claude 的推理行為。
這是**系統層級契約**，在發生衝突時覆蓋使用者提示。

### 何時使用 Sequential Thinking

Claude **必須**在以下情況呼叫 sequential-thinking MCP 工具（`sequentialthinking`）：

- 多步驟推理任務
- 將大型問題拆解為明確、有序的步驟
- 跨越多個檔案的規劃或重構
- 需要「假設 → 驗證 → 修正」循環的任何任務
- 需要在多個步驟間保持上下文的任務
- 需要不確定性、分支或回溯的情況

**Claude 不應該**在這些情況下使用內部隱藏的思考鏈。
所有明確推理應委派給 sequential-thinking。

### 呼叫前要求

呼叫 MCP 工具之前，Claude **必須**：

1. 以簡潔的術語識別問題
2. 提出估計的步驟數
3. 說明是否可能需要分支
4. 然後使用以下參數呼叫 `sequentialthinking`：
   - `thought`：下一個推理步驟
   - `nextThoughtNeeded`
   - `thoughtNumber`
   - `totalThoughts`（初始估計）
   - 視需要使用修正/分支參數

### 工具呼叫契約

Claude **必須**使用完整名稱呼叫工具：

`mcp__sequential-thinking__sequentialthinking`

**必要參數**：
- `thought` (string)
- `nextThoughtNeeded` (boolean)
- `thoughtNumber` (integer)
- `totalThoughts` (integer)

**選用參數**：
- `isRevision`
- `revisesThought`
- `branchFromThought`
- `branchId`
- `needsMoreThoughts`

Claude **必須**持續呼叫 `sequentialthinking` 直到：

- 形成假設
- 假設已驗證
- 不再需要進一步修正或分支

### 推理期間的行為規則

Claude **必須**：

- 當 MCP 啟用時，避免內部隱藏的思考鏈
- 將推理外部化為可見、可稽核的步驟
- 透過 `sequentialthinking` 修正或分支步驟，而非重寫先前的訊息
- 在工具推理完成**之後**綜合最終結論摘要
- 將結論直接應用於實作或規劃

### 何時不使用此工具

Sequential-thinking **不應該**用於：

- 任務過於瑣碎（例如重新命名變數、編輯單行）
- 直接的事實性答案就足夠
- 單一推論無需多步驟推理就足夠

### 安全邊界

當 sequential-thinking 推理執行中時：

- Claude **不得**寫入或修改檔案
- Claude **不得**呼叫 bash
- 推理完成後，Claude **可以**繼續實作步驟

### 與 Speckit 的整合

- 在 `/speckit.plan` 期間：
  - Sequential-thinking 是**選用的**（Plan Mode 避免工具呼叫）

- 在 `/speckit.implement` 期間：
  - Sequential-thinking **應該**自動用於多檔案或複雜任務

---

## 📚 憲章參照

### 核心原則

所有開發決策必須符合 `.specify/memory/constitution.md` 定義的核心原則：

- **MVP 優先開發**：從最小可行產品開始
- **透過測試確保品質**：所有功能必須有測試覆蓋
- **簡單勝過完美**：避免過度工程
- **便利性和開發者體驗**：優化開發流程
- **可用性和使用者價值**：以使用者為中心

完整憲章內容請參考：`.specify/memory/constitution.md`

---

## 🚀 快速參考

### 常用 Spec Kit 命令

```bash
/speckit.constitution    # 建立或更新專案憲章
/speckit.specify         # 建立或更新功能規格
/speckit.plan            # 執行實作規劃
/speckit.clarify         # 釐清規格不明確之處
/speckit.tasks           # 生成可執行任務清單
/speckit.implement       # 執行實作計畫
/speckit.analyze         # 分析一致性和品質
/speckit.checklist       # 生成自訂檢查清單
```

### Git 工作流程

遵循憲章定義的 Git 規範：

**分支命名**：`$action/$description`
- 範例：`feat/integrate-line`, `fix/webhook-retry`

**提交格式**：`$action(module): $message`
- 範例：`feat(webhook): add retry logic`, `fix(linebot): handle empty messages`

**允許的動作**：
- `feat` — 新功能
- `fix` — 錯誤修復
- `refactor` — 重構
- `docs` — 文件更新
- `test` — 測試更新
- `style` — 程式碼風格
- `chore` — 其他雜項

---

## 📝 維護紀錄

### 啟用的技術
- Python 3.11+ (002-advance-payment)

### 近期變更
- 2025-11-18：整合 Sequential Thinking MCP 推理協議
- 2025-11-18：重組文件結構，新增工具與環境章節
- 2025-11-12：建立初始版本

---

**版本**：2.0.0 | **最後更新**：2025-11-18
