"""Tests for the yfinance price lookup, including its cache."""
import pytest

import tracker


@pytest.fixture(autouse=True)
def clear_cache():
    tracker._price_cache.clear()
    yield
    tracker._price_cache.clear()


class FakeFastInfo:
    def __init__(self, price):
        self.last_price = price


class FakeTicker:
    def __init__(self, price):
        self.fast_info = FakeFastInfo(price)


def fake_search(price, symbol="AAPL"):
    """Build stand-ins for yf.Search / yf.Ticker returning a fixed price."""
    class Search:
        def __init__(self, *a, **k):
            self.quotes = [{"symbol": symbol}] if symbol else []
    return Search, lambda sym: FakeTicker(price)


class TestGetPriceInfo:
    def test_returns_current_and_ten_percent_below_target(self, monkeypatch):
        Search, Ticker = fake_search(200.0)
        monkeypatch.setattr(tracker.yf, "Search", Search)
        monkeypatch.setattr(tracker.yf, "Ticker", Ticker)

        out = tracker.get_price_info("APPLE INC")

        assert out["current"] == "$200.00"
        assert out["target"] == "$180.00"

    def test_formats_large_prices_with_thousands_separator(self, monkeypatch):
        Search, Ticker = fake_search(650000.0, "BRK-A")
        monkeypatch.setattr(tracker.yf, "Search", Search)
        monkeypatch.setattr(tracker.yf, "Ticker", Ticker)

        out = tracker.get_price_info("BERKSHIRE HATHAWAY")

        assert out["current"] == "$650,000.00"

    def test_no_search_result_yields_na(self, monkeypatch):
        Search, Ticker = fake_search(1.0, symbol=None)
        monkeypatch.setattr(tracker.yf, "Search", Search)
        monkeypatch.setattr(tracker.yf, "Ticker", Ticker)

        assert tracker.get_price_info("NOT A REAL CO") == {
            "current": "N/A", "target": "N/A"}

    def test_zero_price_yields_na(self, monkeypatch):
        Search, Ticker = fake_search(0.0)
        monkeypatch.setattr(tracker.yf, "Search", Search)
        monkeypatch.setattr(tracker.yf, "Ticker", Ticker)

        assert tracker.get_price_info("DELISTED CO")["current"] == "N/A"

    def test_exception_is_swallowed_and_returns_na(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("yahoo is down")
        monkeypatch.setattr(tracker.yf, "Search", boom)

        assert tracker.get_price_info("ANY")["current"] == "N/A"

    def test_result_is_cached_so_yahoo_is_hit_once_per_name(self, monkeypatch):
        calls = []

        class Search:
            def __init__(self, *a, **k):
                calls.append(a)
                self.quotes = [{"symbol": "AAPL"}]

        monkeypatch.setattr(tracker.yf, "Search", Search)
        monkeypatch.setattr(tracker.yf, "Ticker", lambda s: FakeTicker(100.0))

        tracker.get_price_info("APPLE INC")
        tracker.get_price_info("APPLE INC")
        tracker.get_price_info("APPLE INC")

        assert len(calls) == 1, "cache should prevent repeat Yahoo lookups"

    def test_failures_are_cached_too(self, monkeypatch):
        calls = []

        def boom(*a, **k):
            calls.append(a)
            raise RuntimeError("down")

        monkeypatch.setattr(tracker.yf, "Search", boom)

        tracker.get_price_info("BAD")
        tracker.get_price_info("BAD")

        assert len(calls) == 1, "a failed lookup should not be retried per row"
