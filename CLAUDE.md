# Claude 開發指南

本文件定義 Claude AI 助手在本專案的開發規範和工作流程。

## 📋 溝通規範

**總是使用正體中文回覆**

所有與使用者的溝通、規格文件、規劃文件和內部討論都必須使用正體中文（繁體中文）。

**例外情況**：
- 程式碼、變數名稱、函式名稱必須使用英文
- 提交訊息（commit messages）使用英文
- Pull Request 標題和描述使用英文
- 技術術語和 API 參考使用英文

## 🎯 開發流程

### Spec Kit 優先

**盡量使用 Spec Kit 進行開發**

本專案採用 Spec Kit 開發方法論，所有功能開發應遵循以下流程：

1. **制定規格**（Specify）：使用 `/speckit.specify` 定義使用者故事和驗收標準
2. **規劃設計**（Plan）：使用 `/speckit.plan` 進行技術規劃
3. **釐清需求**（Clarify）：使用 `/speckit.clarify` 解決規格不明確之處
4. **生成任務**（Tasks）：使用 `/speckit.tasks` 將需求拆解為可執行任務
5. **執行實作**（Implement）：使用 `/speckit.implement` 執行開發任務
6. **分析檢查**（Analyze）：使用 `/speckit.analyze` 驗證一致性和品質

### 憲章參照

**遵循專案憲章原則**

所有開發決策必須符合 `.specify/memory/constitution.md` 定義的核心原則：

- **MVP 優先開發**：從最小可行產品開始
- **透過測試確保品質**：所有功能必須有測試覆蓋
- **簡單勝過完美**：避免過度工程
- **便利性和開發者體驗**：優化開發流程
- **可用性和使用者價值**：以使用者為中心

完整憲章內容請參考：`.specify/memory/constitution.md`

## 🛠️ Shell 工具使用指南

**重要**：使用以下專用工具取代傳統 Unix 命令（若缺少請先安裝）

| 任務類型 | 必須使用 | 不要使用 |
|---------|---------|---------|
| 尋找檔案 | `fd` | `find`, `ls -R` |
| 搜尋文字 | `rg` (ripgrep) | `grep`, `ag` |
| 分析程式碼結構 | `ast-grep` | `grep`, `sed` |
| 互動式選擇 | `fzf` | 手動篩選 |
| 處理 JSON | `jq` | `python -m json.tool` |
| 處理 YAML/XML | `yq` | 手動解析 |

### 工具安裝

```bash
# macOS (Homebrew)
brew install fd ripgrep ast-grep fzf jq yq

# Ubuntu/Debian
apt-get install fd-find ripgrep fzf jq
cargo install ast-grep

# 其他系統請參考各工具官方文件
```

### 使用範例

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

## 🧩 Spec Kit 整合

### 初始化專案

```bash
# 初始化新的 spec 專案
specify init <project-name>

# 在當前目錄初始化
specify init .
# 或
specify init --here
```

### 驗證規格

```bash
# 驗證所有規格文件
specify check
```

### 自動化檢查

**Claude 應該在以下時機自動執行 `specify check`**：

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
.specify/
└── memory/
    └── constitution.md   # 專案憲章
```

### API 與規格同步

**Claude 應該協助保持 API 實作與規格定義同步**

當進行以下變更時，確保同步更新：
- API 端點新增或修改 → 更新 spec.md 的 API 定義
- 資料模型變更 → 更新 spec.md 的資料結構定義
- 業務邏輯變更 → 更新相關使用者故事和驗收標準

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

**版本**：1.0.0 | **建立日期**：2025-11-12
