"""
Exchange Rate Service Module

This module provides exchange rate query services with fallback mechanisms:
1. FinMind API (primary)
2. Taiwan Bank CSV (fallback)
3. Pre-stored backup rates (final fallback for USD, EUR, JPY)
"""

import requests
import logging
import time
import csv
import io
from typing import Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo
from app.kv_store import KVStore

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Exchange rate service with multi-tier fallback mechanism"""

    # FinMind API endpoint
    FINMIND_API_URL = "https://api.finmindtrade.com/api/v3/data"

    # Taiwan Bank CSV endpoint
    BOT_CSV_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"

    # Cache TTL: 1 hour
    CACHE_TTL = 3600

    # Backup rates for USD, EUR, JPY (updated: 2025-11-21)
    BACKUP_RATES = {
        "USD": 31.50,
        "EUR": 33.20,
        "JPY": 0.21,
    }

    # Currency synonyms mapping (Chinese to ISO 4217 codes)
    CURRENCY_SYNONYMS = {
        # US Dollar
        "美元": "USD",
        "美金": "USD",
        "USD": "USD",
        "usd": "USD",

        # Euro
        "歐元": "EUR",
        "EUR": "EUR",
        "eur": "EUR",
        "EU": "EUR",

        # Japanese Yen
        "日圓": "JPY",
        "日幣": "JPY",
        "JPY": "JPY",
        "jpy": "JPY",

        # British Pound
        "英鎊": "GBP",
        "GBP": "GBP",
        "gbp": "GBP",

        # Australian Dollar
        "澳幣": "AUD",
        "澳元": "AUD",
        "AUD": "AUD",
        "aud": "AUD",

        # Canadian Dollar
        "加幣": "CAD",
        "加拿大幣": "CAD",
        "CAD": "CAD",
        "cad": "CAD",

        # Chinese Yuan
        "人民幣": "CNY",
        "CNY": "CNY",
        "cny": "CNY",
    }

    # Supported currencies
    SUPPORTED_CURRENCIES = {"TWD", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CNY"}

    def __init__(self, kv_store: Optional[KVStore] = None):
        """
        Initialize exchange rate service

        Args:
            kv_store: Optional KV store for caching (uses in-memory dict if not provided)
        """
        self.kv_store = kv_store
        self._memory_cache: Dict[str, Dict] = {}  # Fallback to memory cache if KV not available

    def normalize_currency(self, currency_text: str) -> Optional[str]:
        """
        Convert currency text to ISO 4217 code

        Args:
            currency_text: Currency text (e.g., "美金", "USD", "歐元")

        Returns:
            ISO 4217 currency code (e.g., "USD", "EUR") or None if not recognized

        Examples:
            >>> service = ExchangeRateService()
            >>> service.normalize_currency("美金")
            'USD'
            >>> service.normalize_currency("EUR")
            'EUR'
            >>> service.normalize_currency("unknown")
            None
        """
        normalized = self.CURRENCY_SYNONYMS.get(currency_text)

        if normalized and normalized in self.SUPPORTED_CURRENCIES:
            return normalized

        return None

    def get_rate_from_finmind(self, currency: str, max_retries: int = 3) -> Optional[float]:
        """
        Get exchange rate from FinMind API with retry mechanism

        Args:
            currency: Currency code (ISO 4217)
            max_retries: Maximum retry attempts

        Returns:
            Cash selling rate (float) or None if failed
        """
        params = {
            "dataset": "TaiwanExchangeRate",
            "data_id": currency.upper(),
            "date": "2006-01-01",  # Get all historical data
        }

        for attempt in range(max_retries):
            try:
                logger.info(f"Querying FinMind API for {currency} (attempt {attempt + 1}/{max_retries})")

                response = requests.get(
                    self.FINMIND_API_URL,
                    params=params,
                    timeout=10
                )

                # Check for rate limit
                if response.status_code == 429:
                    logger.warning(f"FinMind API rate limit exceeded for {currency}")
                    return None

                response.raise_for_status()

                data = response.json()

                # Check if data exists
                if not data.get("data"):
                    logger.error(f"Currency {currency} not found in FinMind API")
                    return None

                # Get the latest rate (last entry)
                latest = data["data"][-1]
                cash_sell = latest.get("cash_sell")

                if cash_sell is None:
                    logger.error(f"Cash sell rate not found for {currency}")
                    return None

                logger.info(f"Got rate for {currency} from FinMind: {cash_sell}")
                return float(cash_sell)

            except requests.Timeout:
                logger.warning(f"FinMind API timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                else:
                    logger.error(f"FinMind API timeout after {max_retries} retries")
                    return None

            except requests.RequestException as e:
                logger.error(f"FinMind API request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

            except (KeyError, ValueError, TypeError, IndexError) as e:
                logger.error(f"FinMind API data parsing error: {e}")
                return None

        return None

    def get_rate_from_csv(self, currency: str) -> Optional[float]:
        """
        Get exchange rate from Taiwan Bank CSV (fallback)

        Args:
            currency: Currency code (ISO 4217)

        Returns:
            Cash selling rate (float) or None if failed
        """
        try:
            logger.info(f"Querying Taiwan Bank CSV for {currency}")

            response = requests.get(self.BOT_CSV_URL, timeout=10)
            response.raise_for_status()

            # Parse CSV
            csv_content = response.content.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content))

            # Skip header row
            next(csv_reader, None)

            # Find currency row and extract cash sell rate
            for row in csv_reader:
                if len(row) < 3:
                    continue

                # Row format: [Currency Name, Buy Rate, Sell Rate, ...]
                # We need the "Cash Sell" rate (position varies, typically column 12)
                # Currency codes are typically in the first column or currency name

                # Check if this row contains our currency
                row_currency = row[0].strip() if row else ""

                # Map currency names to codes (simplified matching)
                currency_mapping = {
                    "USD": ["美元", "US"],
                    "EUR": ["歐元", "EUR"],
                    "JPY": ["日圓", "JPY"],
                    "GBP": ["英鎊", "GBP"],
                    "AUD": ["澳幣", "AUD"],
                    "CAD": ["加拿大", "CAD"],
                    "CNY": ["人民幣", "CNY"],
                }

                # Check if row matches our currency
                matches = False
                if currency in currency_mapping:
                    for name_variant in currency_mapping[currency]:
                        if name_variant in row_currency:
                            matches = True
                            break

                if matches:
                    # Cash sell rate is typically at index 12 (0-indexed column 12)
                    # Format varies, but generally: columns 0-11 contain various rates
                    # Column 12 is usually "Cash Sell" (現金賣出)
                    try:
                        # Try to extract numeric value from column 12
                        if len(row) > 12:
                            rate_str = row[12].strip().replace(',', '')
                            if rate_str and rate_str not in ['-', '']:
                                rate = float(rate_str)
                                logger.info(f"Got rate for {currency} from Taiwan Bank CSV: {rate}")
                                return rate
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse rate from CSV row: {e}")
                        continue

            logger.error(f"Currency {currency} not found in Taiwan Bank CSV")
            return None

        except requests.Timeout:
            logger.error("Taiwan Bank CSV request timeout")
            return None

        except requests.RequestException as e:
            logger.error(f"Taiwan Bank CSV request error: {e}")
            return None

        except Exception as e:
            logger.error(f"Taiwan Bank CSV parsing error: {e}")
            return None

    def get_rate(self, currency: str) -> Optional[float]:
        """
        Get exchange rate with multi-tier fallback mechanism

        Priority:
        1. Check cache (valid for 1 hour)
        2. Try FinMind API
        3. Fallback to Taiwan Bank CSV
        4. Use pre-stored backup rate (for USD, EUR, JPY)

        Args:
            currency: Currency code (ISO 4217)

        Returns:
            Cash selling rate (float) or None if all attempts failed
        """
        # TWD always has rate of 1.0
        if currency == "TWD":
            return 1.0

        # Validate currency
        if currency not in self.SUPPORTED_CURRENCIES:
            logger.error(f"Unsupported currency: {currency}")
            return None

        # 1. Check cache
        cached_rate = self._get_cached_rate(currency)
        if cached_rate is not None:
            logger.info(f"Cache hit for {currency}: {cached_rate}")
            return cached_rate

        # 2. Try FinMind API
        logger.info(f"Cache miss for {currency}, trying FinMind API")
        rate = self.get_rate_from_finmind(currency)
        if rate is not None:
            self._cache_rate(currency, rate, "finmind")
            return rate

        # 3. Fallback to Taiwan Bank CSV
        logger.warning(f"FinMind API failed for {currency}, trying Taiwan Bank CSV")
        rate = self.get_rate_from_csv(currency)
        if rate is not None:
            self._cache_rate(currency, rate, "bot_csv")
            return rate

        # 4. Use backup rate (USD, EUR, JPY only)
        if currency in self.BACKUP_RATES:
            rate = self.BACKUP_RATES[currency]
            logger.warning(f"Using backup rate for {currency}: {rate}")
            return rate

        logger.error(f"All rate query methods failed for {currency}")
        return None

    def convert_to_twd(self, amount: float, currency: str) -> Optional[float]:
        """
        Convert foreign currency amount to TWD

        Args:
            amount: Amount in original currency
            currency: Currency code (ISO 4217)

        Returns:
            Amount in TWD (rounded to 2 decimal places) or None if rate unavailable

        Examples:
            >>> service = ExchangeRateService()
            >>> service.convert_to_twd(4.99, "USD")  # Assuming rate is 31.50
            157.19
        """
        # TWD to TWD is 1:1
        if currency == "TWD":
            return round(amount, 2)

        rate = self.get_rate(currency)
        if rate is None:
            logger.error(f"Cannot convert {amount} {currency} to TWD: rate unavailable")
            return None

        twd_amount = amount * rate
        return round(twd_amount, 2)

    def _get_cache_key(self, currency: str) -> str:
        """Generate cache key for currency and date"""
        today = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
        return f"exchange_rate:{currency}:{today}"

    def _get_cached_rate(self, currency: str) -> Optional[float]:
        """Get rate from cache (KV store or memory)"""
        cache_key = self._get_cache_key(currency)

        # Try KV store first if available
        if self.kv_store:
            try:
                cached_data = self.kv_store.get(cache_key)
                if cached_data and isinstance(cached_data, dict):
                    rate = cached_data.get("rate")
                    if rate is not None:
                        return float(rate)
            except Exception as e:
                logger.warning(f"Failed to get from KV store: {e}, falling back to memory cache")

        # Fallback to memory cache
        cached_data = self._memory_cache.get(cache_key)
        if cached_data:
            # Check if cache is still valid (within TTL)
            cached_at = cached_data.get("cached_at", 0)
            if time.time() - cached_at < self.CACHE_TTL:
                return cached_data.get("rate")

        return None

    def _cache_rate(self, currency: str, rate: float, source: str) -> None:
        """Cache rate to KV store or memory"""
        cache_key = self._get_cache_key(currency)
        cache_data = {
            "currency": currency,
            "rate": rate,
            "queried_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
            "source": source,
            "cached_at": time.time(),
        }

        # Try to cache in KV store if available
        if self.kv_store:
            try:
                self.kv_store.set(cache_key, cache_data, ttl=self.CACHE_TTL)
                logger.info(f"Cached rate for {currency} in KV store (source: {source})")
            except Exception as e:
                logger.warning(f"Failed to cache in KV store: {e}, using memory cache instead")
                self._memory_cache[cache_key] = cache_data
        else:
            # Use memory cache as fallback
            self._memory_cache[cache_key] = cache_data
            logger.info(f"Cached rate for {currency} in memory (source: {source})")
