"""Transport/route boundary tests, separate from cryptographic fixture tests."""
import httpx
import pytest
from fastapi.testclient import TestClient

import app as application
import puriq_price_routes as routes
from puriq_market import SourceUnavailable, sha256_json


def fake_verified(*args, **kwargs):
    return {"core_valid": True, "record_valid": True, "fresh": True,
            "freshness": "FRESH", "verification_scope": "full-record", "reasons": [],
            "can_authorize": False}


def make_client(handler):
    return routes.SignedPriceClient(httpx.MockTransport(handler), clock=lambda: 100.0)


def test_bounded_fixed_destinations_and_distinct_receipt(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"symbol": "BTC", "priceText": "100.00",
            "at": "1970-01-01T00:01:40Z", "grade": "consensus", "sources": 4})
    monkeypatch.setattr(routes, "verify_print", fake_verified)
    output = make_client(handler).observe("BTC")
    assert output["status"] == "REVIEW" and output["price_text"] == "100.00"
    assert [str(r.url).split("?")[0] for r in calls] == [routes.KEY_URL, routes.SAMPLE_URL]
    assert all("authorization" not in r.headers for r in calls)
    receipt = dict(output["receipt"])
    digest = receipt.pop("receipt_id"); receipt.pop("receipt_algorithm")
    assert digest == sha256_json(receipt)
    assert receipt["local_signature_claimed"] is False
    assert output["can_authorize"] is False


@pytest.mark.parametrize("changes", [
    {"record_valid": False, "verification_scope": "price-only"},
    {"fresh": False, "freshness": "STALE"},
    {"record_valid": False, "core_valid": False, "verification_scope": "invalid"},
])
def test_withhold_price_when_checks_fail(monkeypatch, changes):
    monkeypatch.setattr(routes, "verify_print", lambda *a, **k: {**fake_verified(), **changes})
    result = make_client(lambda r: httpx.Response(200, json={
        "priceText": "999", "grade": "consensus", "sources": 35})).observe()
    assert result["status"] == "ABSTAIN" and result["price_text"] is None


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"Location": "https://other.invalid"}),
    httpx.Response(429), httpx.Response(503),
    httpx.Response(200, content=b"x" * 65_537),
    httpx.Response(200, content=b'{"price": 1,"price": 2}'),
    httpx.Response(200, content=b'{"price": NaN}'),
    httpx.Response(200, content=b'{"at": 1e999}'),
    httpx.Response(200, json={"success": False}),
    httpx.Response(200, json=[]),
])
def test_source_failures_no_fallback(response):
    with pytest.raises(SourceUnavailable):
        make_client(lambda r: response).observe()


def test_symbol_rejected_before_transport():
    with pytest.raises(ValueError):
        make_client(lambda r: pytest.fail("must not fetch")).observe("BTC&url=evil")


def test_route_fail_closed_and_literal_symbol(monkeypatch):
    class Unavailable:
        def observe(self, symbol):
            raise SourceUnavailable("upstream confidential details")
    monkeypatch.setattr(routes, "client", Unavailable())
    client = TestClient(application.app)
    response = client.get("/api/puriq/v1/signed-price")
    assert response.status_code == 503 and response.json()["price_text"] is None
    assert "confidential" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/puriq/v1/signed-price?symbol=XRP").status_code == 422


def test_price_page_and_local_assets():
    client = TestClient(application.app)
    response = client.get("/signed-prices")
    assert response.status_code == 200
    for name in ("signed-prices.js", "signed-prices.css"):
        assert client.get("/static/signed-prices/" + name).status_code == 200
