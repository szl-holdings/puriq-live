"""Offline research tests use explicit fixtures, never claimed market evidence."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import app as application
from puriq_market import SourceUnavailable, sha256_json
from puriq_research import ResearchClient, normalize_candles, research_replay
import puriq_research_routes as routes

STEP = 3600
START = 1782000000
START -= START % STEP
NOW = START + 301 * STEP


def fixture_rows(count=180):
    rows = []
    for i in range(count):
        close = 100 + (i if i < 90 else 180-i) / 2
        opened = close - .1
        rows.append([START+i*STEP, opened-1, close+1, opened, close, 20+i])
    return rows


def normalized(rows=None):
    return normalize_candles(rows or fixture_rows(), granularity=STEP, observed_at=NOW)


def client_fixture(rows=None, clock=lambda: NOW):
    return ResearchClient(httpx.MockTransport(lambda request: httpx.Response(200, json=rows or fixture_rows())), clock)


def test_order_reversed_seconds_to_milliseconds():
    result = normalized(list(reversed(fixture_rows())))
    assert len(result['bars']) == 180
    assert result['bars'][0]['time'] == START*1000
    assert result['bars'][0]['low'] < result['bars'][0]['open'] < result['bars'][0]['close'] < result['bars'][0]['high']
    assert result['gaps'] == []


@pytest.mark.parametrize('field,value', [(0,True),(0,-1),(0,START+1),(1,0),(2,-1),(3,float('nan')),(4,float('inf')),(5,-3),(5,False),(3,{}),(4,'bad')])
def test_bad_numeric_fields_fail_closed(field,value):
    rows = fixture_rows();rows[0][field] = value
    with pytest.raises(SourceUnavailable): normalized(rows)


@pytest.mark.parametrize('payload', [[],{},[None],[[1,2,3]], fixture_rows(301)])
def test_invalid_collection(payload):
    with pytest.raises(SourceUnavailable): normalize_candles(payload,granularity=STEP,observed_at=NOW)


def test_duplicate_is_not_implicitly_deduplicated():
    rows=fixture_rows();rows.append(deepcopy(rows[0]))
    with pytest.raises(SourceUnavailable): normalized(rows)


def test_invalid_ohlc():
    rows=fixture_rows();rows[0][1]=rows[0][4]+10
    with pytest.raises(SourceUnavailable): normalized(rows)


def test_open_and_future_candles_are_excluded():
    rows=fixture_rows(60)
    result=normalize_candles(rows,granularity=STEP,observed_at=START+59.5*STEP)
    assert len(result['bars'])==59
    assert result['excluded_unclosed_or_future']==1
    assert result['newest_completed_at']<=START+59.5*STEP


def test_gaps_block_replay_without_hiding_reported_bars():
    rows=fixture_rows();del rows[75]
    h=normalized(rows)
    assert h['gaps'][0]['missing_intervals']==1
    replay=research_replay(h['bars'],gaps=h['gaps'])
    assert replay['state']=='UNAVAILABLE' and replay['reason']=='GAPPED_HISTORY'
    assert replay['curve']==[]


def test_insufficient_replay():
    h=normalized(fixture_rows(59))
    assert research_replay(h['bars'],gaps=[])['reason']=='INSUFFICIENT_HISTORY'


def test_accounting_constraints_and_net_round_trip():
    h=normalized();r=research_replay(h['bars'],gaps=[])
    assert r['state']=='MODELED' and r['trading_enabled'] is False
    assert r['virtual_starting_cash_usd']=='1000.000000'
    assert r['closed_round_trips']==1
    assert all(Decimal(f['cash_after_usd'])>=0 for f in r['fills'])
    assert all(f['signal_last_time']<f['time'] for f in r['fills'])
    assert r['fills'][0]['time']==h['bars'][50]['time']
    assert 0 < Decimal(r['fills'][0]['fee_usd'])
    assert Decimal(r['fills'][0]['cash_after_usd'])>=900
    assert r['curve'][0]['equity_usd']==1000
    assert r['digest_is_signature'] is False
    digest=r.pop('result_sha256')
    assert sha256_json(r)==digest


def test_prefix_invariance_no_future_information_enters_earlier_fills():
    h=normalized();full=research_replay(h['bars'],gaps=[])
    shorter=research_replay(h['bars'][:110],gaps=[])
    assert full['curve'][:110]==shorter['curve']
    assert [f for f in full['fills'] if f['time']<=h['bars'][109]['time']]==shorter['fills']


def test_fill_bar_close_does_not_change_same_bar_signal_or_fill():
    h=normalized();baseline=research_replay(h['bars'],gaps=[])
    changed=deepcopy(h['bars']);changed[50]['close']=1
    varied=research_replay(changed,gaps=[])
    assert baseline['fills'][0]==varied['fills'][0]


def test_flat_prices_avoid_spurious_entries():
    bars=normalized()['bars']
    for b in bars:b.update(open=100,close=100,high=101,low=99)
    r=research_replay(bars,gaps=[])
    assert r['filled_sides']==0 and r['win_rate'] is None
    assert Decimal(r['final_equity_usd'])==1000
    assert Decimal(r['benchmark_final_equity_usd'])<1000


def test_determinism_and_input_is_not_mutated():
    h=normalized();before=deepcopy(h)
    assert research_replay(h['bars'],gaps=[])==research_replay(h['bars'],gaps=[])
    assert before==h


def test_cache_separates_event_time_from_fetch_time_and_copies_values():
    now=[NOW];calls=[]
    def transport(request):
        calls.append(request)
        assert request.url.host=='api.exchange.coinbase.com'
        assert request.url.path=='/products/BTC-USD/candles'
        return httpx.Response(200,json=fixture_rows())
    c=ResearchClient(httpx.MockTransport(transport),lambda:now[0])
    first=c.history('BTC-USD',STEP);first['history']['bars'].clear()
    now[0]+=20
    second=c.history('BTC-USD',STEP)
    assert len(calls)==1 and second['freshness']['cached']
    assert second['freshness']['fetch_age_seconds']==20
    assert second['freshness']['newest_completed_bar_age_seconds']>20
    assert len(second['history']['bars'])==180
    assert second['freshness']['realtime_quote_claim'] is False


def test_refresh_failure_does_not_relabel_stale_values():
    now=[NOW];calls=[0]
    def transport(request):
        calls[0]+=1
        return httpx.Response(200,json=fixture_rows()) if calls[0]==1 else httpx.Response(503)
    c=ResearchClient(httpx.MockTransport(transport),lambda:now[0])
    c.history('BTC-USD',STEP);now[0]+=61
    with pytest.raises(SourceUnavailable): c.history('BTC-USD',STEP)


@pytest.mark.parametrize('response', [httpx.Response(302,headers={'location':'https://evil.invalid/'}),httpx.Response(200,content=b'x'*250001),httpx.Response(200,content=b'not json'),httpx.Response(200,json=[])])
def test_bad_source_responses_fail_closed(response):
    c=ResearchClient(httpx.MockTransport(lambda _:response),lambda:NOW)
    with pytest.raises(SourceUnavailable):c.history('BTC-USD',STEP)


@pytest.mark.parametrize('pair,interval', [('https://evil.invalid',3600),('BTC-USD',60),('BTC-USD',True)])
def test_fixed_allowlist(pair,interval):
    with pytest.raises(ValueError):client_fixture().history(pair,interval)


def test_api_and_exported_truth_boundaries(monkeypatch):
    monkeypatch.setattr(routes,'client',client_fixture())
    c=TestClient(application.app)
    response=c.get('/api/puriq/v1/research?pair=BTC-USD&granularity=3600')
    assert response.status_code==200,response.text
    result=response.json()
    assert result['source']['truth_label']=='REPORTED' and result['replay']['truth_label']=='MODELED'
    assert result['trading_enabled'] is False and result['capital_transferred'] is False
    assert c.get('/api/puriq/v1/research?pair=INVALID').status_code==422
    assert c.get('/api/puriq/v1/research?granularity=60').status_code==422
    assert c.post('/api/puriq/v1/research',json={'live':True}).status_code==405
    for route in ('/orders','/wallet','/api/puriq/v1/orders','/api/puriq/v1/trade'):
        assert c.post(route,json={}).status_code==404
    assert c.get('/research').status_code==200
    assert c.get('/static/research/research.js').status_code==200
    assert "connect-src 'self'" in response.headers['Content-Security-Policy']


def test_unavailable_api_uses_503_not_fake_success(monkeypatch):
    c=ResearchClient(httpx.MockTransport(lambda _:httpx.Response(503)))
    monkeypatch.setattr(routes,'client',c)
    response=TestClient(application.app).get('/api/puriq/v1/research')
    assert response.status_code==503 and response.json()['status']=='UNAVAILABLE'
    assert 'history' not in response.json()


def test_renderer_pin_manifest():
    text=(Path(__file__).parents[1]/'tools/vendor_vela.py').read_text()
    assert 'ea73dafeffb2f0aa14ca6163e7e427810ead692a29a552a426a774de62e520dd' in text
    assert 'NoRedirect' in text and 'refusing to overwrite' in text
    page=(Path(__file__).parents[1]/'static/research/index.html').read_text()
    assert 'Charts by Vela' in page and 'https://luxalgo.com/vela' in page
    assert 'No out-of-sample skill claim' in page


def test_missing_renderer_is_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "STATIC", tmp_path / "research")
    c = TestClient(application.app)
    response = c.get("/api/puriq/v1/research/readiness")
    assert response.status_code == 503 and response.json()["missing"]
    assert c.get("/readyz").status_code == 503


def test_tampered_renderer_blocks_readiness(monkeypatch, tmp_path):
    import shutil
    actual = routes.STATIC.parent
    copy = tmp_path / "static"
    shutil.copytree(actual, copy)
    (copy / "vendor/vela/vela.global.min.js").write_text("tampered")
    monkeypatch.setattr(routes, "STATIC", copy / "research")
    response = TestClient(application.app).get("/api/puriq/v1/research/readiness")
    assert response.status_code == 503
    assert "vendor/vela/vela.global.min.js" in response.json()["invalid"]


def test_verified_assets_are_not_live_market_admission():
    response = TestClient(application.app).get("/api/puriq/v1/research/readiness")
    assert response.status_code == 200
    assert response.json()["live_source_observation"] is False
    assert response.json()["trading_enabled"] is False
