"""Tests for the market data cache (app/services/yfinance_service.py). Yahoo is mocked."""
import threading
import time

import pandas as pd
import pytest

from app.services import yfinance_service as md


class FakeTicker:
    """Stands in for yf.Ticker; counts calls and can be told to fail."""
    calls = 0
    fail_next = False
    closes = [100.0, 110.0, 99.0, 121.0]

    def __init__(self, symbol):
        self.symbol = symbol

    @property
    def info(self):
        FakeTicker.calls += 1
        time.sleep(0.05)  # a slow network call, so concurrent callers overlap
        if FakeTicker.fail_next:
            FakeTicker.fail_next = False
            raise ConnectionError("Yahoo timeout")
        if self.symbol == "BAD":
            raise ConnectionError("Yahoo timeout")
        return {"currentPrice": 42.0, "marketCap": 1e9, "trailingPegRatio": None}

    def history(self, period, interval):
        FakeTicker.calls += 1
        return pd.DataFrame({"Close": FakeTicker.closes})


@pytest.fixture(autouse=True)
def fake_yahoo(monkeypatch):
    monkeypatch.setattr(md.yf, "Ticker", FakeTicker)
    FakeTicker.calls, FakeTicker.fail_next = 0, False
    for cache in (md._info_cache, md._history_cache, md._cashflow_cache):
        cache.clear()


def test_concurrent_requests_for_one_symbol_make_one_yahoo_call():
    threads = [threading.Thread(target=md.get_info, args=("AAPL",)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert FakeTicker.calls == 1


def test_failures_are_not_cached():
    FakeTicker.fail_next = True
    with pytest.raises(ConnectionError):
        md.get_info("AAPL")
    assert md.get_info("AAPL")["currentPrice"] == 42.0  # retried, not a cached failure
    assert FakeTicker.calls == 2


def test_performance_metrics():
    # 100 -> 110 -> 99 -> 121: total return +21%, worst peak-to-trough 110 -> 99 = -10%
    perf = md.get_performance("AAPL", "1mo")
    daily = pd.Series(FakeTicker.closes).pct_change().dropna()
    assert perf["return"] == pytest.approx(0.21)
    assert perf["maxDrawdown"] == pytest.approx(-0.10)
    assert perf["volatility"] == pytest.approx(daily.std(ddof=1) * 252 ** 0.5)


def test_rows_keep_order_and_one_bad_symbol_does_not_break_the_table():
    rows, cache_hit = md.yfinance_service.get_relative(
        ["MSFT", "BAD", "AAPL"], fields=["sharePrice", "forwardPE"],
        perf_metrics=["return"], perf_period="1y",
    )
    assert [r["symbol"] for r in rows] == ["MSFT", "BAD", "AAPL"]
    assert rows[0]["snapshot"] == {"sharePrice": 42.0, "forwardPE": None}
    assert rows[0]["missingFields"] == ["forwardPE"]
    assert rows[0]["performance"]["return"] == pytest.approx(0.21)
    assert "Yahoo timeout" in rows[1]["error"]
    assert cache_hit is False

    _, cache_hit = md.yfinance_service.get_relative(
        ["MSFT", "AAPL"], fields=["sharePrice"], perf_metrics=["return"], perf_period="1y",
    )
    assert cache_hit is True
