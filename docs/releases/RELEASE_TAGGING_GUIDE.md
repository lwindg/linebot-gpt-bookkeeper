# Release Tagging Guide

本文件說明如何為各版本打 Git Tags 和建立 GitHub Releases。

---

## 📋 版本 Commit 清單

| 版本 | Commit | 日期 | 主要功能 |
|------|--------|------|---------|
| v1.2.0 | `35b19ff` | 2025-11-15 | Vision API Foundation |
| v1.3.0 | `8bccc22` | 2025-11-15 | Enhanced Classification & Error Handling |
| v1.5.0 | `f6ee7ce` | 2025-11-15 | Multi-Item Expense & Receipt Recognition |
| v1.7.0 | `90c227b` | 2025-11-19 | Advance Payment & Need-to-Pay Tracking |

---

## 🏷️ 快速執行：創建所有 Tags

```bash
# v1.2.0
git tag -a v1.2.0 35b19ff -m "Release v1.2.0: Vision API Foundation

Major Features:
- GPT-4 Vision API integration for receipt recognition
- Image download and processing
- Receipt information extraction

Release Date: 2025-11-15"

# v1.3.0
git tag -a v1.3.0 8bccc22 -m "Release v1.3.0: Enhanced Classification & Error Handling

Major Features:
- Image compression to reduce Vision API token usage
- Enhanced classification rules
- Improved error handling

Release Date: 2025-11-15"

# v1.5.0
git tag -a v1.5.0 f6ee7ce -m "Release v1.5.0: Multi-Item Expense & Receipt Recognition

Major Features:
- Multi-item expense processing from single message
- Complete receipt image recognition
- Update last entry functionality with Vercel KV
- Unified prompt architecture

Release Date: 2025-11-15"

# v1.7.0
git tag -a v1.7.0 90c227b -m "Release v1.7.0: Advance Payment & Need-to-Pay Tracking

Major Features:
- Advance payment tracking (money lent to others)
- Need-to-pay tracking (money owed to others)
- Non-collectible advance (gifts/family support)
- Date extraction restoration
- Compound item name preservation
- Comprehensive test suite (21 test cases)

Release Date: 2025-11-19
Status: Ready for Testing"
```

---

## 📤 推送 Tags 到遠端

```bash
# 方法 1: 推送單一 tag
git push origin v1.2.0
git push origin v1.3.0
git push origin v1.5.0
git push origin v1.7.0

# 方法 2: 一次推送所有 tags (推薦)
git push origin --tags
```

---

## 🔍 驗證 Tags

```bash
# 列出所有 local tags
git tag -l

# 查看特定 tag 的詳細資訊
git show v1.5.0

# 查看 tag 指向的 commit
git rev-list -n 1 v1.5.0

# 查看遠端 tags
git ls-remote --tags origin
```

---

## 📝 GitHub Release 建立指南

### Step 1: 前往 GitHub Releases 頁面

```
https://github.com/YOUR_USERNAME/linebot-gpt-bookkeeper/releases/new
```

### Step 2: 選擇 Tag 並填寫資訊

#### v1.2.0

**Tag**: `v1.2.0`
**Title**: `v1.2.0: Vision API Foundation`
**Description**: 複製 `RELEASE_NOTES_v1.2.0.md` 的內容

#### v1.3.0

**Tag**: `v1.3.0`
**Title**: `v1.3.0: Enhanced Classification & Error Handling`
**Description**: 複製 `RELEASE_NOTES_v1.3.0.md` 的內容

#### v1.5.0

**Tag**: `v1.5.0`
**Title**: `v1.5.0: Multi-Item Expense & Receipt Recognition`
**Description**: 複製 `RELEASE_NOTES_v1.5.0.md` 的內容
**Attachments**:
- `run_tests.sh`（`--suite multi_expense`）
- `tests/test_cases_v1.5.md`

#### v1.7.0

**Tag**: `v1.7.0`
**Title**: `v1.7.0: Advance Payment & Need-to-Pay Tracking`
**Description**: 複製 `RELEASE_NOTES_v1.7.0.md` 的內容
**Pre-release**: ✅ (勾選，因為尚未合併到主分支)
**Attachments**:
- `run_tests.sh`（`--suite advance_payment`、`--suite date`）
- `tests/TEST_GUIDE_V17.md`

---

## ⚠️ 重要注意事項

### v1.7.0 特別說明

v1.7.0 目前在 `002-advance-payment` 分支，建議：

**選項 1: 標記為 Pre-release**
- 在 GitHub 上勾選 "This is a pre-release"
- 等待測試完成後再正式 release

**選項 2: 先合併到主分支**
```bash
# 切換到主分支
git checkout main

# 合併 002-advance-payment
git merge 002-advance-payment

# 推送到遠端
git push origin main

# 然後再打 v1.7.0 tag
```

### 建議流程

1. **先創建 local tags** (v1.2.0, v1.3.0, v1.5.0)
2. **驗證 tags 正確**
3. **推送 tags 到遠端**
4. **在 GitHub 上建立 Releases**
5. **v1.7.0 等測試完成後再處理**

---

## 📋 檢查清單

創建 Release 前的檢查：

- [ ] 所有 Release Notes 檔案都存在
  - [ ] `RELEASE_NOTES_v1.2.0.md`
  - [ ] `RELEASE_NOTES_v1.3.0.md`
  - [ ] `RELEASE_NOTES_v1.5.0.md`
  - [ ] `RELEASE_NOTES_v1.7.0.md`

- [ ] 測試腳本都存在且可執行
  - [ ] `run_tests.sh --suite expense`
  - [ ] `run_tests.sh --suite multi_expense`
  - [ ] `run_tests.sh --suite advance_payment`

- [ ] Commit 都已推送到遠端
  - [ ] `35b19ff` (v1.2.0)
  - [ ] `8bccc22` (v1.3.0)
  - [ ] `f6ee7ce` (v1.5.0)
  - [ ] `90c227b` (v1.7.0)

- [ ] Tags 已創建並推送
  - [ ] v1.2.0
  - [ ] v1.3.0
  - [ ] v1.5.0
  - [ ] v1.7.0

- [ ] GitHub Releases 已建立
  - [ ] v1.2.0
  - [ ] v1.3.0
  - [ ] v1.5.0
  - [ ] v1.7.0 (Pre-release)

---

## 🚀 一鍵執行腳本

已移除 `create_tags.sh`。請改用本指南的手動步驟建立 tag。

**文件更新日期**: 2025-11-19
**當前分支**: 002-advance-payment
