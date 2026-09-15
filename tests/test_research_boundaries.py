"""Regression contracts for request-time bar admission and decimal domains."""
from decimal import Decimal
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import app as application
import puriq_research_routes as routes
from puriq_market import SourceUnavailable
from puriq_research import ResearchClient, money, normalize_candles, research_replay

STEP = 3600
START = 1782000000 - 1782000000 % STEP


def rows(count=60, price=100):
    return [[START + i * STEP, price, price, price, price, 0] for i in range(count)]


@pytest.mark.parametrize('price', [1e-300, 0.000000009999999, '1e-30'])
def test_subminimum_price_is_explicitly_unavailable(price):
    with pytest.raises(SourceUnavailable, match='invalid price'):
        normalize_candles(rows(price=price), granularity=STEP, observed_at=START + 100 * STEP)


def test_minimum_price_and_large_mark_are_serializable():
    series = rows(price=1e-8)
    series[-1] = [START + 59 * STEP, 1e15, 1e15, 1e15, 1e15, 0]
    history = normalize_candles(series, granularity=STEP, observed_at=START + 100 * STEP)
    result = research_replay(history['bars'], gaps=history['gaps'])
    assert result['state'] == 'MODELED'
    assert Decimal(result['benchmark_final_equity_usd']) > Decimal('1e20')
    json.dumps(result, allow_nan=False)


def test_money_quantization_has_explicit_bounded_precision():
    value = Decimal('123456789012345678901234567890.125')
    assert money(value) == '123456789012345678901234567890.125000'


def test_candle_closing_while_request_in_flight_remains_excluded():
    before = START + 60 * STEP - 1
    after = START + 60 * STEP + 1
    now = [before]

    def transport(_request):
        now[0] = after
        return httpx.Response(200, json=rows())

    client = ResearchClient(httpx.MockTransport(transport), clock=lambda: now[0])
    result = client.history('BTC-USD', STEP)
    assert len(result['history']['bars']) == 59
    assert result['history']['excluded_unclosed_or_future'] == 1
    assert result['source']['request_started_at'] == before
    assert result['source']['observed_at'] == after
    assert result['history']['newest_completed_at'] <= before
    assert result['replay']['reason'] == 'INSUFFICIENT_HISTORY'


def test_minimum_price_violation_is_503_not_unhandled_accounting_error(monkeypatch):
    client = ResearchClient(httpx.MockTransport(lambda _r: httpx.Response(200, json=rows(price=1e-300))),
                            clock=lambda: START + 100 * STEP)
    monkeypatch.setattr(routes, 'client', client)
    response = TestClient(application.app).get('/api/puriq/v1/research?pair=BTC-USD&granularity=3600')
    assert response.status_code == 503
    assert response.json()['status'] == 'UNAVAILABLE'
    assert response.json()['trading_enabled'] is False
