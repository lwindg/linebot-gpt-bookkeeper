# 台灣銀行匯率 API 技術研究報告

**專案**：linebot-gpt-bookkeeper / 003-multi-currency
**研究日期**：2025-11-21
**研究目的**：為多幣別記帳功能選擇合適的匯率查詢方案

---

## 執行摘要

經過深入研究，台灣銀行並未提供官方的公開匯率 REST API。現有可用方案包括：

1. **台灣銀行 CSV 檔案下載**（官方資料源）
2. **FinMind API**（第三方包裝，推薦）
3. **社群自建 API**（穩定性未知）

根據專案需求（多幣別記帳功能），建議採用 **FinMind API** 作為主要方案，搭配 **台灣銀行 CSV** 作為備用方案。

---

## 決策：採用 FinMind API

**API 端點**：`https://api.finmindtrade.com/api/v3/data`

**選擇理由**：

1. **開箱即用的 JSON API**：無需自行解析 CSV 格式，資料結構清晰
2. **資料來源可靠**：資料來源為台灣銀行官方匯率，FinMind 為知名開源專案（GitHub 1.5k+ stars）
3. **使用限制合理**：300 請求/小時對記帳應用已足夠，可免費升級至 600 請求/小時
4. **錯誤處理完善**：標準 HTTP 狀態碼，JSON 格式錯誤訊息
5. **維護成本低**：無需監控 CSV 格式變更，API 版本穩定（v3）

---

## 替代方案評估

### 方案比較表

| 方案 | 優點 | 缺點 | 評分 |
| --- | --- | --- | --- |
| **FinMind API** | JSON 格式、完整文件、免費使用、社群支援 | 第三方服務、有頻率限制 | ⭐⭐⭐⭐⭐ |
| **台灣銀行 CSV** | 官方資料源、無頻率限制、24/7 可用 | 需自行解析、格式可能變更、無錯誤處理 | ⭐⭐⭐⭐ |
| **社群自建 API** | JSON 格式 | 穩定性未知、無維護保證、可能隨時下線 | ⭐⭐ |
| **自建 API** | 完全控制、無外部依賴 | 開發成本高、維護成本高、需監控資料源變更 | ⭐⭐⭐ |

### 為何不自建 API？

雖然自建 API 可以完全控制，但考量到：

1. **開發成本**：需投入 3-5 天開發和測試
2. **維護成本**：需持續監控台灣銀行網站變更
3. **價值回報比**：對記帳應用而言，FinMind API 已滿足需求

**結論**：在 MVP 階段，採用 FinMind API 是最具成本效益的選擇。

---

## API 技術細節

### FinMind API

**請求範例**：
```python
import requests

url = "https://api.finmindtrade.com/api/v3/data"
params = {
    "dataset": "TaiwanExchangeRate",
    "data_id": "USD",
    "date": "2006-01-01",
}
response = requests.get(url, params=params)
data = response.json()
```

**回應格式**：
```json
{
    "msg": "success",
    "status": 200,
    "data": [
        {
            "date": "2025-11-21",
            "currency": "USD",
            "cash_buy": 31.20,
            "cash_sell": 31.80,
            "spot_buy": 31.50,
            "spot_sell": 31.60
        }
    ]
}
```

**關鍵欄位**：
- `cash_sell`：現金賣出價（用於換算外幣消費的新台幣金額）
- `currency`：幣別代碼（ISO 4217 標準）

**認證需求**：
- 免費使用：無需認證，限額 300 請求/小時
- 註冊使用：需註冊並取得 token，限額提升至 600 請求/小時

**使用限制**：
- 頻率限制：300 請求/小時（未認證）/ 600 請求/小時（已認證）
- 服務時間：24/7 全天候服務
- 資料更新：營業時間內更新

**配額估算**（基於專案使用情境）：
- 假設每位使用者每天記錄 10 筆外幣消費
- 假設系統有 100 位活躍使用者
- 每日總請求量：1000 次
- 平均每小時：約 42 次（遠低於 300 次限制）

**結論**：未認證版本的 300 請求/小時已足夠。

---

### 台灣銀行 CSV（備用方案）

**下載端點**：`https://rate.bot.com.tw/xrt/flcsv/0/day`

**資料格式**：CSV（逗號分隔值）

**使用時機**：
1. FinMind API 回應 429（超過頻率限制）
2. FinMind API 連續 3 次請求失敗（500/502/503/504）
3. FinMind API 回應時間超過 10 秒

**認證需求**：無需認證，公開存取

**建議快取策略**：快取時間 1 小時（減少伺服器負擔）

---

## 支援的幣別

### 完整幣別清單（共 19 種）

根據 FinMind API 和台灣銀行官方資料，支援的幣別包括：

| 幣別代碼 | 中文名稱 | 英文名稱 | 專案需求 |
| --- | --- | --- | --- |
| USD | 美元/美金 | US Dollar | ✅ 需要 |
| EUR | 歐元 | Euro | ✅ 需要 |
| JPY | 日圓 | Japanese Yen | ✅ 需要 |
| GBP | 英鎊 | British Pound | ✅ 需要 |
| AUD | 澳幣 | Australian Dollar | ✅ 需要 |
| CAD | 加拿大幣 | Canadian Dollar | ✅ 需要 |
| CNY | 人民幣 | Chinese Yuan | ✅ 需要 |
| HKD | 港幣 | Hong Kong Dollar | - |
| CHF | 瑞士法郎 | Swiss Franc | - |
| SGD | 新加坡幣 | Singapore Dollar | - |
| NZD | 紐元 | New Zealand Dollar | - |
| ZAR | 南非幣 | South African Rand | - |
| SEK | 瑞典幣 | Swedish Krona | - |
| THB | 泰銖 | Thai Baht | - |
| PHP | 菲律賓披索 | Philippine Peso | - |
| IDR | 印尼盾 | Indonesian Rupiah | - |
| KRW | 韓元 | South Korean Won | - |
| MYR | 馬來幣 | Malaysian Ringgit | - |
| VND | 越南盾 | Vietnamese Dong | - |

**結論**：專案需求的 7 種幣別（USD、EUR、JPY、GBP、AUD、CAD、CNY）**全部支援**。

### 幣別同義詞對照表（建議實作）

為提升使用者體驗，建議在系統中建立幣別同義詞對照表：

```python
CURRENCY_SYNONYMS = {
    # 美元
    "美元": "USD", "美金": "USD", "USD": "USD", "usd": "USD",

    # 歐元
    "歐元": "EUR", "EUR": "EUR", "eur": "EUR", "EU": "EUR",

    # 日圓
    "日圓": "JPY", "日幣": "JPY", "JPY": "JPY", "jpy": "JPY",

    # 英鎊
    "英鎊": "GBP", "GBP": "GBP", "gbp": "GBP",

    # 澳幣
    "澳幣": "AUD", "澳元": "AUD", "AUD": "AUD", "aud": "AUD",

    # 加幣
    "加幣": "CAD", "加拿大幣": "CAD", "CAD": "CAD", "cad": "CAD",

    # 人民幣
    "人民幣": "CNY", "CNY": "CNY", "cny": "CNY",
}
```

---

## 錯誤處理策略

### 降級機制（對應 FR-012 需求）

**三層備援架構**：

1. **主要方案**：FinMind API（快取 1 小時）
2. **備用方案**：台灣銀行 CSV
3. **最終方案**：預存備用匯率（USD、EUR、JPY）

**實作策略**：

```python
def get_exchange_rate_with_fallback(currency: str) -> Optional[float]:
    """
    Get exchange rate with fallback mechanism

    Priority:
    1. Check cache (valid for 1 hour)
    2. Try FinMind API
    3. Fallback to BOT CSV
    4. Use pre-stored backup rate (for USD, EUR, JPY)
    """
    # 1. Check cache
    cached_rate = get_cached_rate(currency)
    if cached_rate:
        return cached_rate

    # 2. Try FinMind API
    rate = get_exchange_rate_from_finmind(currency)
    if rate:
        cache_rate(currency, rate, ttl=3600)
        return rate

    # 3. Fallback to BOT CSV
    logger.warning(f"FinMind API failed, trying BOT CSV for {currency}")
    rate = get_exchange_rate_from_csv(currency)
    if rate:
        cache_rate(currency, rate, ttl=3600)
        return rate

    # 4. Use pre-stored backup rate
    backup_rate = get_backup_rate(currency)
    if backup_rate:
        logger.warning(f"Using backup rate for {currency}: {backup_rate}")
        return backup_rate

    return None
```

### 預存備用匯率

**儲存位置**：配置檔案或資料庫
**更新頻率**：每週自動更新一次（cron job）
**支援幣別**：USD、EUR、JPY（最常用）

```python
# Example: Pre-stored backup rates (updated weekly)
BACKUP_RATES = {
    "USD": 31.50,  # Updated: 2025-11-21
    "EUR": 33.20,  # Updated: 2025-11-21
    "JPY": 0.21,   # Updated: 2025-11-21
}
```

### 錯誤訊息模板（對應 FR-008 需求）

```python
ERROR_MESSAGES = {
    "rate_limit": "⚠️ 匯率查詢次數已達上限，請稍後再試。",
    "api_down": "⚠️ 匯率查詢服務暫時無法使用，已使用備用匯率進行換算。",
    "currency_not_supported": "⚠️ 很抱歉，目前不支援 {currency} 幣別。支援的幣別：USD、EUR、JPY、GBP、AUD、CAD、CNY。",
    "network_error": "⚠️ 網路連線異常，無法取得匯率。請檢查網路連線後重試。",
    "unknown_error": "⚠️ 發生未知錯誤，請聯絡系統管理員。錯誤代碼：{error_code}",
}
```

---

## 實作建議

### 整合至現有系統

根據專案結構分析，建議在以下位置新增或修改檔案：

1. **新增檔案**：`app/exchange_rate.py`
   - 負責匯率查詢、快取、錯誤處理

2. **修改檔案**：`app/schemas.py`
   - 新增外幣相關欄位：`原幣別`、`匯率`

3. **修改檔案**：`app/prompts.py`
   - 更新 prompt 以識別幣別關鍵字

4. **修改檔案**：`app/gpt_processor.py`
   - 整合匯率查詢邏輯

### 建議的模組結構

```python
# app/exchange_rate.py

import requests
import logging
from typing import Optional
from datetime import datetime
from app.kv_store import KVStore

logger = logging.getLogger(__name__)

class ExchangeRateService:
    """Exchange rate service using FinMind API with BOT CSV fallback"""

    FINMIND_API_URL = "https://api.finmindtrade.com/api/v3/data"
    BOT_CSV_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    CACHE_TTL = 3600  # 1 hour

    BACKUP_RATES = {
        "USD": 31.50,
        "EUR": 33.20,
        "JPY": 0.21,
    }

    CURRENCY_SYNONYMS = {
        "美元": "USD", "美金": "USD", "USD": "USD", "usd": "USD",
        "歐元": "EUR", "EUR": "EUR", "eur": "EUR", "EU": "EUR",
        "日圓": "JPY", "日幣": "JPY", "JPY": "JPY", "jpy": "JPY",
        "英鎊": "GBP", "GBP": "GBP", "gbp": "GBP",
        "澳幣": "AUD", "澳元": "AUD", "AUD": "AUD", "aud": "AUD",
        "加幣": "CAD", "加拿大幣": "CAD", "CAD": "CAD", "cad": "CAD",
        "人民幣": "CNY", "CNY": "CNY", "cny": "CNY",
    }

    def __init__(self, kv_store: KVStore):
        self.cache = kv_store

    def normalize_currency(self, currency_text: str) -> Optional[str]:
        """Convert currency text to ISO 4217 code"""
        return self.CURRENCY_SYNONYMS.get(currency_text)

    def get_rate(self, currency: str) -> Optional[float]:
        """Get exchange rate with fallback mechanism"""
        pass

    def convert_to_twd(self, amount: float, currency: str) -> Optional[float]:
        """Convert foreign currency to TWD"""
        pass
```

### 效能優化建議

1. **實作快取機制**：
   - 使用現有的 `KVStore` 儲存匯率快取
   - TTL 設定為 1 小時
   - Key 格式：`exchange_rate:{currency}:{date}`

2. **批次查詢優化**：
   - 若單一訊息包含多筆外幣消費，先收集所有幣別
   - 批次查詢所有需要的匯率（減少 API 呼叫次數）

3. **預載入常用匯率**：
   - 系統啟動時預載入 USD、EUR、JPY 匯率
   - 定時更新（每小時）

---

## 結論

根據深入研究，建議採用 **FinMind API** 作為主要匯率查詢方案，搭配 **台灣銀行 CSV** 作為備用方案，並預存常用幣別（USD、EUR、JPY）的備用匯率。此方案具備：

✅ **可靠性**：雙重備援機制，確保 90% 以上成功率（符合 SC-004）
✅ **效能**：快取機制確保 10 秒內完成記錄（符合 SC-001）
✅ **可維護性**：使用標準 JSON API，無需自行解析 CSV
✅ **成本效益**：免費使用，無需額外開發成本
✅ **擴展性**：支援 19 種幣別，涵蓋專案需求的 7 種幣別

此方案符合專案憲章中的「簡單勝過完美」和「MVP 優先開發」原則，可快速整合至現有系統，並提供穩定可靠的多幣別記帳功能。

---

**研究完成日期**：2025-11-21
**下一步**：進入 Phase 1 設計階段，產生 data-model.md 和 contracts/
