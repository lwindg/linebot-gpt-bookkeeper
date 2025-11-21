# API Contract: FinMind Exchange Rate API

**API Provider**: FinMind
**Base URL**: `https://api.finmindtrade.com`
**Version**: v3
**Authentication**: Optional (Token-based for higher limits)
**Documentation**: https://finmind.github.io/v3/tutor/ExchangeRate/

---

## Endpoint: Get Taiwan Exchange Rate

### Request

**Method**: `GET`
**URL**: `/api/v3/data`

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
| --- | --- | --- | --- | --- |
| `dataset` | string | ✅ | Dataset name (fixed value) | `"TaiwanExchangeRate"` |
| `data_id` | string | ✅ | Currency code (ISO 4217) | `"USD"`, `"EUR"`, `"JPY"` |
| `date` | string | - | Start date (YYYY-MM-DD) | `"2006-01-01"` (get all data) |
| `token` | string | - | API token (optional, for higher limits) | `"your_token_here"` |

**Request Example**:

```http
GET /api/v3/data?dataset=TaiwanExchangeRate&data_id=USD&date=2006-01-01 HTTP/1.1
Host: api.finmindtrade.com
Accept: application/json
```

**cURL Example**:

```bash
curl -X GET "https://api.finmindtrade.com/api/v3/data?dataset=TaiwanExchangeRate&data_id=USD&date=2006-01-01" \
  -H "Accept: application/json"
```

**Python Example**:

```python
import requests

url = "https://api.finmindtrade.com/api/v3/data"
params = {
    "dataset": "TaiwanExchangeRate",
    "data_id": "USD",
    "date": "2006-01-01",
}
response = requests.get(url, params=params, timeout=10)
data = response.json()
```

---

### Response

**Success Response** (HTTP 200):

```json
{
  "msg": "success",
  "status": 200,
  "data": [
    {
      "date": "2025-11-20",
      "currency": "USD",
      "cash_buy": 31.20,
      "cash_sell": 31.80,
      "spot_buy": 31.50,
      "spot_sell": 31.60
    },
    {
      "date": "2025-11-21",
      "currency": "USD",
      "cash_buy": 31.25,
      "cash_sell": 31.85,
      "spot_buy": 31.55,
      "spot_sell": 31.65
    }
  ]
}
```

**Response Fields**:

| Field | Type | Description |
| --- | --- | --- |
| `msg` | string | Response message (`"success"` or error message) |
| `status` | integer | HTTP status code |
| `data` | array | Array of exchange rate records |
| `data[].date` | string | Date (YYYY-MM-DD) |
| `data[].currency` | string | Currency code (ISO 4217) |
| `data[].cash_buy` | float | 現金買入價（銀行買入） |
| `data[].cash_sell` | float | **現金賣出價（銀行賣出，用於換算）** |
| `data[].spot_buy` | float | 即期買入價 |
| `data[].spot_sell` | float | 即期賣出價 |

**Key Field for Implementation**: `cash_sell` (現金賣出價)

---

### Error Responses

**Rate Limit Exceeded** (HTTP 429):

```json
{
  "msg": "Too Many Requests",
  "status": 429,
  "data": []
}
```

**Invalid Parameters** (HTTP 400):

```json
{
  "msg": "Invalid parameters",
  "status": 400,
  "data": []
}
```

**Currency Not Found** (HTTP 200, but empty data):

```json
{
  "msg": "success",
  "status": 200,
  "data": []
}
```

**Server Error** (HTTP 500):

```json
{
  "msg": "Internal Server Error",
  "status": 500,
  "data": []
}
```

---

## Rate Limits

| Tier | Requests per Hour | Authentication Required |
| --- | --- | --- |
| Free (Unauthenticated) | 300 | ❌ No |
| Registered | 600 | ✅ Yes (token required) |

**Recommendation**: Start with free tier (300 req/hour). Upgrade if needed.

---

## Supported Currencies

All 19 currencies supported by Taiwan Bank:

`USD`, `EUR`, `JPY`, `GBP`, `AUD`, `CAD`, `CNY`, `HKD`, `CHF`, `SGD`, `NZD`, `ZAR`, `SEK`, `THB`, `PHP`, `IDR`, `KRW`, `MYR`, `VND`

---

## Implementation Notes

### 1. Get Latest Rate

To get the latest exchange rate, fetch all data and take the last entry:

```python
def get_latest_rate(currency: str) -> Optional[float]:
    """Get latest cash sell rate for currency"""
    url = "https://api.finmindtrade.com/api/v3/data"
    params = {
        "dataset": "TaiwanExchangeRate",
        "data_id": currency.upper(),
        "date": "2006-01-01",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not data.get("data"):
            return None

        # Get latest entry
        latest = data["data"][-1]
        return latest.get("cash_sell")

    except Exception as e:
        logger.error(f"Failed to get rate for {currency}: {e}")
        return None
```

### 2. Error Handling

```python
def get_rate_with_retry(currency: str, max_retries: int = 3) -> Optional[float]:
    """Get rate with exponential backoff retry"""
    for attempt in range(max_retries):
        rate = get_latest_rate(currency)

        if rate is not None:
            return rate

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # 1s, 2s, 4s

    return None  # All retries failed
```

### 3. Caching Strategy

Cache key format: `exchange_rate:{currency}:{date}`

```python
def get_rate_cached(currency: str, kv_store: KVStore) -> Optional[float]:
    """Get rate with cache"""
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"exchange_rate:{currency}:{today}"

    # Check cache
    cached = kv_store.get(cache_key)
    if cached:
        return float(cached["rate"])

    # Fetch from API
    rate = get_latest_rate(currency)
    if rate:
        # Cache for 1 hour
        kv_store.set(cache_key, {
            "currency": currency,
            "rate": rate,
            "queried_at": datetime.now().isoformat(),
            "source": "finmind"
        }, ttl=3600)

    return rate
```

---

## Testing

### Test Cases

1. **Valid Currency Request**:
   - Input: `currency="USD"`
   - Expected: `cash_sell` value (float, > 0)

2. **Invalid Currency**:
   - Input: `currency="XXX"`
   - Expected: Empty `data` array

3. **Rate Limit**:
   - Input: 301 requests within 1 hour
   - Expected: HTTP 429

4. **Network Timeout**:
   - Input: Slow network
   - Expected: Timeout exception after 10s

### Mock Response (for testing)

```python
MOCK_FINMIND_RESPONSE = {
    "msg": "success",
    "status": 200,
    "data": [
        {
            "date": "2025-11-21",
            "currency": "USD",
            "cash_buy": 31.20,
            "cash_sell": 31.50,
            "spot_buy": 31.35,
            "spot_sell": 31.40
        }
    ]
}
```

---

## SLA & Monitoring

**Expected Availability**: 99%+
**Expected Response Time**: < 3 seconds (p95)

**Monitoring Metrics**:
- Success rate
- Response time (p50, p95, p99)
- Rate limit errors (HTTP 429)
- Fallback usage rate

---

## Changelog

| Date | Version | Changes |
| --- | --- | --- |
| 2025-11-21 | 1.0 | Initial contract definition |
