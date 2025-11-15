# 本地圖片識別測試指南

本文件說明如何在本地測試 Phase 2 的圖片識別功能，不需要透過 LINE Bot。

## 前置準備

### 1. 設置環境變數

創建 `.env` 檔案（如果還沒有的話）：

```bash
cp .env.example .env
```

編輯 `.env` 並設置以下必要變數：

```env
# OpenAI API Key（必要）
OPENAI_API_KEY=sk-your-openai-api-key-here

# GPT Vision 模型（可選，預設為 gpt-4o）
GPT_VISION_MODEL=gpt-4o

# LINE 相關（本地測試不需要，但必須存在避免 config.py 報錯）
LINE_CHANNEL_ACCESS_TOKEN=test_token
LINE_CHANNEL_SECRET=test_secret
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

## 測試方法

### 方法 1：使用測試腳本（推薦）

使用本地圖片檔案測試：

```bash
# 基本用法
python test_local_vision.py <圖片路徑>

# 範例
python test_local_vision.py ~/Downloads/receipt.jpg
python test_local_vision.py /path/to/receipt.png
```

**輸出範例**：

```
📸 讀取圖片: receipt.jpg
✅ 圖片載入成功 (0.85 MB)

🤖 初始化 OpenAI client...
🔍 開始分析收據...

============================================================
✅ 識別成功！共 2 個項目

📋 識別到的項目:
  1. 美式咖啡 - 50.0 元
     付款方式: 現金
  2. 三明治 - 80.0 元
     付款方式: 現金

🔄 轉換為記帳資料...
✅ 轉換成功！

記帳項目 #1:
  品項: 美式咖啡
  金額: 50.0 TWD
  付款方式: 現金
  分類: 家庭／飲品
  日期: 2025-11-15
  交易ID: 20251115-143052

記帳項目 #2:
  品項: 三明治
  金額: 80.0 TWD
  付款方式: 現金
  分類: 家庭／餐飲／早餐
  日期: 2025-11-15
  交易ID: 20251115-143052
============================================================
```

### 方法 2：使用 Python 互動式測試

```python
# 啟動 Python
python

# 執行測試程式碼
from app.image_handler import process_receipt_image, ReceiptItem
from app.gpt_processor import process_receipt_data
from openai import OpenAI
from app.config import OPENAI_API_KEY

# 讀取圖片
with open('receipt.jpg', 'rb') as f:
    image_data = f.read()

# 初始化 OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# 處理圖片
receipt_items, error_code, error_message = process_receipt_image(image_data, client)

# 顯示結果
if error_code:
    print(f"錯誤: {error_code} - {error_message}")
else:
    print(f"成功識別 {len(receipt_items)} 個項目:")
    for item in receipt_items:
        print(f"  - {item.品項}: {item.原幣金額} 元")

# 轉換為記帳資料
result = process_receipt_data(receipt_items)
print(f"\n記帳結果: {result.intent}")
for entry in result.entries:
    print(f"  {entry.品項} - {entry.原幣金額} TWD - {entry.分類}")
```

### 方法 3：使用單元測試

執行已經寫好的測試案例：

```bash
# 設置環境變數
export LINE_CHANNEL_ACCESS_TOKEN=test_token
export LINE_CHANNEL_SECRET=test_secret
export OPENAI_API_KEY=your-api-key

# 執行所有圖片處理測試
python -m pytest tests/test_image_handler.py -v

# 執行特定測試
python -m pytest tests/test_image_handler.py::TestProcessReceiptImage::test_process_receipt_success_single_item -v
```

## 測試收據圖片準備

### 建議的測試圖片

1. **清晰的台幣收據**
   - 超商收據（7-11、全家）
   - 咖啡店收據（星巴克、路易莎）
   - 餐廳收據

2. **測試不同情況**
   - 單筆項目收據
   - 多筆項目收據
   - 模糊的收據（測試錯誤處理）
   - 非收據圖片（測試錯誤處理）
   - 外幣收據（測試錯誤處理）

### 拍攝收據建議

- 光線充足
- 對焦清晰
- 收據平整
- 包含完整的品項和金額資訊

## 測試案例範例

### 測試 1：正常台幣收據

```bash
python test_local_vision.py receipt_tw.jpg
```

**預期結果**：成功識別品項、金額、付款方式

### 測試 2：多項目收據

```bash
python test_local_vision.py receipt_multi.jpg
```

**預期結果**：識別出多個項目，共用同一個交易 ID

### 測試 3：模糊收據

```bash
python test_local_vision.py receipt_blur.jpg
```

**預期結果**：回傳 `unclear` 錯誤

### 測試 4：非收據圖片

```bash
python test_local_vision.py landscape.jpg
```

**預期結果**：回傳 `not_receipt` 錯誤

### 測試 5：外幣收據

```bash
python test_local_vision.py receipt_jpy.jpg
```

**預期結果**：回傳 `unsupported_currency` 錯誤

## 錯誤處理測試

測試腳本會顯示不同的錯誤訊息和建議：

- **not_receipt**: 非收據圖片
- **unsupported_currency**: 非台幣收據
- **unclear**: 圖片模糊
- **incomplete**: 資訊不完整

## 成本估算

使用 GPT-4o Vision API 的成本：

- **每次圖片分析**：約 $0.006 USD
- **測試 10 張圖片**：約 $0.06 USD
- **測試 100 張圖片**：約 $0.60 USD

建議在充分測試後再部署到生產環境。

## 進階測試

### 測試分類推斷

驗證 `_infer_category()` 函式的分類邏輯：

```python
from app.gpt_processor import _infer_category

# 測試不同品項的分類
test_items = [
    "咖啡",      # 應該分類為 家庭／飲品
    "早餐",      # 應該分類為 家庭／餐飲／早餐
    "午餐便當",  # 應該分類為 家庭／餐飲／午餐
    "計程車",    # 應該分類為 交通／接駁
    "加油",      # 應該分類為 交通／加油
]

for item in test_items:
    category = _infer_category(item)
    print(f"{item:10s} → {category}")
```

### 測試 Webhook 發送（可選）

如果想測試完整流程包含 webhook 發送：

1. 設置 `.env` 中的 `WEBHOOK_URL`
2. 使用 webhook.site 或 ngrok 建立測試端點
3. 執行測試並驗證 webhook 接收

## 疑難排解

### 問題 1：ModuleNotFoundError

```bash
pip install -r requirements.txt
```

### 問題 2：OpenAI API Key 錯誤

確認 `.env` 中的 `OPENAI_API_KEY` 設置正確

### 問題 3：圖片過大

壓縮圖片到 10MB 以下：

```bash
# macOS
sips -Z 2048 receipt.jpg

# Linux (需要 ImageMagick)
convert receipt.jpg -resize 2048x2048\> receipt_resized.jpg
```

## 下一步

測試完成後，可以：

1. 部署到 Vercel 進行線上測試
2. 透過 LINE Bot 上傳真實收據測試
3. 收集使用者回饋並優化 Vision Prompt

---

**版本**: v1.5.0 Phase 2
**更新日期**: 2025-11-15
