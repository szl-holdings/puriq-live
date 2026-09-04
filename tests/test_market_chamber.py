"""PURIQ Market Chamber application and boundary contracts."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PURIQ_SOURCE_REVISION", "7" * 40)

import app as market_app  # noqa: E402
from puriq_market import (  # noqa: E402
    PuriqClient,
    SourceUnavailable,
    _bounded_get_json,
    binary_entropy,
    liquidity_quality,
    probability_edge,
)

SESSION = "puriq-unit-test-session-01234567890123456789"


def response(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode("utf-8"),
    )


def source_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "gamma-api.polymarket.com":
        return response(
            [
                {
                    "id": "market-1",
                    "conditionId": "condition-1",
                    "slug": "example-event",
                    "question": "Will the example event occur?",
                    "active": True,
                    "closed": False,
                    "endDate": "2026-12-31T00:00:00Z",
                    "outcomes": '["Yes","No"]',
                    "outcomePrices": '["0.63","0.37"]',
                    "bestBid": "0.62",
                    "bestAsk": "0.64",
                    "volume24hr": "12500",
                    "liquidityNum": "9000",
                }
            ]
        )
    if host == "api.coinbase.com":
        return response(
            {"data": {"base": "BTC", "currency": "USD", "amount": "61234.50"}}
        )
    if host == "api.fiscaldata.treasury.gov":
        return response(
            {
                "data": [
                    {
                        "record_date": "2026-08-31",
                        "security_type_desc": "Marketable",
                        "security_desc": "Treasury Notes",
                        "avg_interest_rate_amt": "4.125",
                        "src_line_nbr": "1",
                    }
                ]
            }
        )
    if host == "data.sec.gov":
        return response(
            {
                "cik": "0000320193",
                "name": "Issuer",
                "tickers": ["TEST"],
                "exchanges": ["NASDAQ"],
                "sic": "3571",
                "sicDescription": "Electronic Computers",
                "fiscalYearEnd": "0926",
                "filings": {
                    "recent": {
                        "accessionNumber": ["0001"],
                        "filingDate": ["2026-08-01"],
                        "form": ["10-Q"],
                        "primaryDocument": ["q.htm"],
                    }
                },
            }
        )
    return response({"error": "unexpected host"}, status=500)


@pytest.fixture()
def client() -> TestClient:
    market_app.CLIENT = PuriqClient(httpx.MockTransport(source_handler))
    return TestClient(
        market_app.app,
        headers={"X-SZL-Session": SESSION},
    )


def test_health_readiness_source_and_front_door(client: TestClient) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["trading_enabled"] is False
    assert health.json()["custody_enabled"] is False
    assert health.json()["formula_corpus"]["FAILED"] == 0

    readiness = client.get("/readyz")
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
    assert (
        readiness.json()["build"]["revision"]
        == os.environ["PURIQ_SOURCE_REVISION"]
    )

    build = client.get("/api/build-info")
    assert build.status_code == 200
    assert build.json()["source_binding"]["bindings_agree"] is True
    assert build.json()["receipt_minted"] is False

    front = client.get("/")
    assert front.status_code == 200
    assert "PURIQ Market Chamber" in front.text
    assert "Probability Orbit" in front.text
    assert "viewport-fit=cover" in front.text
    assert "@media(prefers-reduced-motion:reduce)" in front.text
    assert "@media(forced-colors:active)" in front.text
    assert "wallet_connections_enabled" not in front.text


def test_anatomy_formulas_and_sources_are_explicit(client: TestClient) -> None:
    anatomy = client.get("/api/puriq/v1/anatomy").json()
    assert len(anatomy["organs"]) == 9
    assert anatomy["hatun_decisions"] == ["REVIEW", "ABSTAIN"]

    formulas = client.get("/api/puriq/v1/formulas").json()
    assert formulas["formula_count"] == 5
    assert formulas["locked_proven_ids"] == [
        "F1",
        "F4",
        "F7",
        "F11",
        "F12",
        "F18",
        "F19",
        "F22",
    ]
    assert "Conjecture 1" in formulas["lambda_status"]
    assert formulas["can_authorize"] is False

    sources = client.get("/api/puriq/v1/sources").json()
    assert {item["id"] for item in sources["sources"]} == {
        "polymarket",
        "coinbase",
        "treasury",
        "sec",
    }
    assert sources["caller_supplied_urls_allowed"] is False
    assert sources["redirects_allowed"] is False


def test_full_brief_closes_four_source_receipts(client: TestClient) -> None:
    result = client.get(
        "/api/puriq/v1/brief",
        params={
            "market_limit": 5,
            "cik": "320193",
            "crypto_base": "BTC",
            "crypto_currency": "USD",
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["complete"] is True
    assert body["status"] == "READY"
    assert body["source_summary"] == {
        "required": ["polymarket", "sec"],
        "required_observed": 2,
        "total": 4,
        "observed": 4,
    }
    assert body["boundaries"]["trading_enabled"] is False
    assert body["boundaries"]["wallet_connections_enabled"] is False
    assert set(body["receipts"]) == {"polymarket", "coinbase", "treasury", "sec"}
    assert all(len(item["receipt_id"]) == 64 for item in body["receipts"].values())
    assert body["observations"]["coinbase"]["amount"] == 61234.5
    assert body["observations"]["treasury"]["rate_max_pct"] == 4.125
    assert body["observations"]["sec"]["recent_filings"][0]["form"] == "10-Q"

    market = body["observations"]["polymarket"]["markets"][0]
    assert market["yes_probability"] == 0.63
    assert market["probability_edge_from_50"] == 0.13
    assert market["spread"] == 0.02
    assert 0.0 < market["binary_entropy"] < 1.0
    assert market["liquidity_quality"]["can_authorize"] is False


def test_markets_endpoint_populates_second_brain_and_hatun_review(client: TestClient) -> None:
    observed = client.get("/api/puriq/v1/markets", params={"limit": 1})
    assert observed.status_code == 200
    receipt_id = observed.json()["receipt"]["receipt_id"]

    memory = client.get("/api/puriq/v1/second-brain")
    assert memory.status_code == 200
    body = memory.json()
    assert any(item["receipt_id"] == receipt_id for item in body["memory"])
    assert body["raw_session_token_recorded"] is False
    assert body["effectors_enabled"] is False

    review = client.post(
        "/api/puriq/v1/hatun/evaluate",
        json={
            "intent": "review public market evidence",
            "requested_action": "market.review",
            "axes": {
                "evidence": 0.95,
                "freshness": 0.92,
                "reversibility": 0.97,
            },
            "evidence_receipt_ids": [receipt_id],
        },
    )
    assert review.status_code == 200
    decision = review.json()
    assert decision["decision"] == "REVIEW"
    assert decision["can_authorize"] is False
    assert decision["can_execute"] is False
    assert decision["trading_enabled"] is False
    assert decision["receipt"]["session_token_recorded"] is False
    assert "CONJECTURE_1" in decision["lambda_status"]


def test_hatun_abstains_on_unknown_evidence(client: TestClient) -> None:
    result = client.post(
        "/api/puriq/v1/hatun/evaluate",
        json={
            "intent": "review unknown evidence",
            "axes": {"evidence": 0.99, "freshness": 0.99},
            "evidence_receipt_ids": ["a" * 64],
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["decision"] == "ABSTAIN"
    assert "UNKNOWN_EVIDENCE_RECEIPT" in body["blockers"]
    assert body["can_authorize"] is False


def test_session_is_required_and_invalid_sessions_fail_closed() -> None:
    anonymous = TestClient(market_app.app)
    assert anonymous.get("/api/puriq/v1/brief").status_code == 422
    invalid = anonymous.get(
        "/api/puriq/v1/brief",
        headers={"X-SZL-Session": "short"},
    )
    assert invalid.status_code == 400


def test_transport_rejects_redirects_and_unlisted_destinations() -> None:
    redirect = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://evil.invalid"})
    )
    with pytest.raises(SourceUnavailable, match="redirect"):
        _bounded_get_json(
            "https://gamma-api.polymarket.com/markets",
            max_bytes=1024,
            transport=redirect,
        )
    with pytest.raises(SourceUnavailable, match="allowlist"):
        _bounded_get_json(
            "https://evil.invalid/data",
            max_bytes=1024,
        )


def test_formula_transforms_are_bounded_and_descriptive() -> None:
    assert binary_entropy(0.5) == 1.0
    assert binary_entropy(0.0) == 0.0
    assert probability_edge(0.8) == 0.3
    quality = liquidity_quality(spread=0.02, liquidity=10000, volume_24h=20000)
    assert 0.0 <= quality["score"] <= 1.0
    assert quality["label"] == "MODELED_DATA_QUALITY"
    assert quality["can_authorize"] is False
