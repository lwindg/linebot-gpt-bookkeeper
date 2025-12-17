# -*- coding: utf-8 -*-
"""
Test Exchange Rate Service

Tests for multi-currency bookkeeping feature (v003-multi-currency)
"""

from unittest.mock import Mock, patch
from app.exchange_rate import ExchangeRateService


class TestCurrencyNormalization:
    """Test currency synonym normalization (T020)"""

    def test_normalize_us_dollar_synonyms(self):
        """Test US dollar synonyms (美元, 美金, USD)"""
        service = ExchangeRateService()

        assert service.normalize_currency("美元") == "USD"
        assert service.normalize_currency("美金") == "USD"
        assert service.normalize_currency("USD") == "USD"
        assert service.normalize_currency("usd") == "USD"

    def test_normalize_euro_synonyms(self):
        """Test Euro synonyms (歐元, EUR, EU)"""
        service = ExchangeRateService()

        assert service.normalize_currency("歐元") == "EUR"
        assert service.normalize_currency("EUR") == "EUR"
        assert service.normalize_currency("eur") == "EUR"
        assert service.normalize_currency("EU") == "EUR"

    def test_normalize_jpy_synonyms(self):
        """Test Japanese Yen synonyms (日圓, 日幣, JPY)"""
        service = ExchangeRateService()

        assert service.normalize_currency("日圓") == "JPY"
        assert service.normalize_currency("日幣") == "JPY"
        assert service.normalize_currency("JPY") == "JPY"
        assert service.normalize_currency("jpy") == "JPY"

    def test_normalize_gbp_synonyms(self):
        """Test British Pound synonyms (英鎊, GBP)"""
        service = ExchangeRateService()

        assert service.normalize_currency("英鎊") == "GBP"
        assert service.normalize_currency("GBP") == "GBP"
        assert service.normalize_currency("gbp") == "GBP"

    def test_normalize_aud_synonyms(self):
        """Test Australian Dollar synonyms (澳幣, 澳元, AUD)"""
        service = ExchangeRateService()

        assert service.normalize_currency("澳幣") == "AUD"
        assert service.normalize_currency("澳元") == "AUD"
        assert service.normalize_currency("AUD") == "AUD"
        assert service.normalize_currency("aud") == "AUD"

    def test_normalize_cad_synonyms(self):
        """Test Canadian Dollar synonyms (加幣, 加拿大幣, CAD)"""
        service = ExchangeRateService()

        assert service.normalize_currency("加幣") == "CAD"
        assert service.normalize_currency("加拿大幣") == "CAD"
        assert service.normalize_currency("CAD") == "CAD"
        assert service.normalize_currency("cad") == "CAD"

    def test_normalize_cny_synonyms(self):
        """Test Chinese Yuan synonyms (人民幣, CNY)"""
        service = ExchangeRateService()

        assert service.normalize_currency("人民幣") == "CNY"
        assert service.normalize_currency("CNY") == "CNY"
        assert service.normalize_currency("cny") == "CNY"

    def test_normalize_unknown_currency(self):
        """Test unknown currency returns None"""
        service = ExchangeRateService()

        assert service.normalize_currency("未知幣別") is None
        assert service.normalize_currency("UNKNOWN") is None
        assert service.normalize_currency("") is None


class TestFinMindAPI:
    """Test FinMind API integration (T021)"""

    @patch('app.exchange_rate.requests.get')
    def test_get_rate_from_finmind_success(self, mock_get):
        """Test successful FinMind API query"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"date": "2025-11-20", "cash_sell": "31.50"},
                {"date": "2025-11-21", "cash_sell": "31.55"}
            ]
        }
        mock_get.return_value = mock_response

        service = ExchangeRateService()
        rate = service.get_rate_from_finmind("USD")

        assert rate == 31.55  # Latest rate
        mock_get.assert_called_once()

    @patch('app.exchange_rate.requests.get')
    def test_get_rate_from_finmind_rate_limit(self, mock_get):
        """Test FinMind API rate limit (429) handling"""
        # Mock rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        service = ExchangeRateService()
        rate = service.get_rate_from_finmind("USD")

        assert rate is None

    @patch('app.exchange_rate.requests.get')
    def test_get_rate_from_finmind_timeout(self, mock_get):
        """Test FinMind API timeout handling"""
        # Mock timeout
        import requests
        mock_get.side_effect = requests.Timeout()

        service = ExchangeRateService()
        rate = service.get_rate_from_finmind("USD", max_retries=1)

        assert rate is None

    @patch('app.exchange_rate.requests.get')
    def test_get_rate_from_finmind_no_data(self, mock_get):
        """Test FinMind API with empty data"""
        # Mock empty data response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        service = ExchangeRateService()
        rate = service.get_rate_from_finmind("INVALID")

        assert rate is None


class TestCacheMechanism:
    """Test exchange rate caching (T022)"""

    def test_cache_hit_memory(self):
        """Test cache hit with memory cache (no KV store)"""
        service = ExchangeRateService(kv_store=None)

        # First call: should call API
        with patch.object(service, 'get_rate_from_finmind', return_value=31.50) as mock_api:
            rate1 = service.get_rate("USD")
            assert rate1 == 31.50
            mock_api.assert_called_once()

        # Second call: should use cache
        with patch.object(service, 'get_rate_from_finmind', return_value=31.50) as mock_api:
            rate2 = service.get_rate("USD")
            assert rate2 == 31.50
            mock_api.assert_not_called()  # Should use cache

    def test_cache_miss(self):
        """Test cache miss triggers API call"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate_from_finmind', return_value=31.50) as mock_api:
            rate = service.get_rate("USD")
            assert rate == 31.50
            mock_api.assert_called_once_with("USD")

    def test_twd_no_cache_needed(self):
        """Test TWD always returns 1.0 without cache"""
        service = ExchangeRateService(kv_store=None)

        rate = service.get_rate("TWD")
        assert rate == 1.0


class TestFallbackMechanism:
    """Test fallback mechanism (T023)"""

    def test_fallback_to_csv_when_finmind_fails(self):
        """Test fallback to CSV when FinMind API fails"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate_from_finmind', return_value=None):
            with patch.object(service, 'get_rate_from_csv', return_value=31.60) as mock_csv:
                rate = service.get_rate("USD")
                assert rate == 31.60
                mock_csv.assert_called_once_with("USD")

    def test_fallback_to_backup_when_all_fail(self):
        """Test fallback to backup rate when both FinMind and CSV fail"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate_from_finmind', return_value=None):
            with patch.object(service, 'get_rate_from_csv', return_value=None):
                # USD is in BACKUP_RATES
                rate = service.get_rate("USD")
                assert rate == service.BACKUP_RATES["USD"]

    def test_fallback_returns_none_when_no_backup(self):
        """Test returns None when currency has no backup rate"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate_from_finmind', return_value=None):
            with patch.object(service, 'get_rate_from_csv', return_value=None):
                # GBP is not in BACKUP_RATES
                rate = service.get_rate("GBP")
                assert rate is None

    def test_unsupported_currency(self):
        """Test unsupported currency returns None"""
        service = ExchangeRateService(kv_store=None)

        rate = service.get_rate("INVALID")
        assert rate is None


class TestConversion:
    """Test currency conversion"""

    def test_convert_to_twd(self):
        """Test foreign currency to TWD conversion"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate', return_value=31.50):
            twd = service.convert_to_twd(4.99, "USD")
            assert twd == 157.19  # 4.99 * 31.50 = 157.185 → 157.19

    def test_convert_twd_to_twd(self):
        """Test TWD to TWD conversion (identity)"""
        service = ExchangeRateService(kv_store=None)

        twd = service.convert_to_twd(100.0, "TWD")
        assert twd == 100.0

    def test_convert_fails_when_rate_unavailable(self):
        """Test conversion fails when rate is unavailable"""
        service = ExchangeRateService(kv_store=None)

        with patch.object(service, 'get_rate', return_value=None):
            twd = service.convert_to_twd(4.99, "USD")
            assert twd is None
