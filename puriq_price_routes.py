"""Bounded public signed-price observation; no account or execution surface."""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from puriq_market import SourceUnavailable, sha256_json
from puriq_verity import verify_print

router = APIRouter()
ORIGIN = "https://mcp.thepulse.markets"
KEY_URL = ORIGIN + "/api/index/v1/pubkey"
SAMPLE_URL = ORIGIN + "/api/index/v1/sample"
STATIC = Path(__file__).resolve().parent / "static" / "signed-prices"
POLICY = {
    "id": "puriq.signed-price-review/v1",
    "max_age_seconds": 30,
    "require_full_record": True,
    "allowed_grades": ["consensus", "blended"],
    "min_reported_sources": 3,
    "market_accuracy_verified": False,
    "source_independence_verified": False,
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _not_finite(_):
    raise ValueError("nonfinite JSON value")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    return value


class SignedPriceClient:
    def __init__(self, transport=None, clock=time.time):
        self.transport, self.clock = transport, clock

    def _get(self, client, url, *, params=None, limit=65_536):
        # Destinations originate only in this module, never a request URL.
        if url not in (KEY_URL, SAMPLE_URL):
            raise SourceUnavailable("Unsupported signed-price destination")
        started = time.monotonic()
        try:
            with client.stream("GET", url, params=params) as response:
                if response.status_code != 200:
                    raise SourceUnavailable("Signed-price source unavailable")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > 15:
                        raise SourceUnavailable("Signed-price response deadline exceeded")
                    size += len(chunk)
                    if size > limit:
                        raise SourceUnavailable("Signed-price response too large")
                    chunks.append(chunk)
            raw = b"".join(chunks)
            data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_not_finite,
                              parse_float=_finite_float)
            if not isinstance(data, dict) or data.get("success") is False:
                raise ValueError("invalid source response")
            return raw, data
        except (httpx.HTTPError, ValueError, RecursionError) as error:
            raise SourceUnavailable("Signed-price source unavailable") from error

    def observe(self, symbol="BTC"):
        if symbol not in ("BTC", "ETH", "SOL"):
            raise ValueError("Only public BTC, ETH and SOL samples are supported")
        with httpx.Client(transport=self.transport, timeout=10, follow_redirects=False,
                          headers={"Accept": "application/json",
                          "User-Agent": "SZL-PURIQ-Signed-Price/1.0"}) as http:
            key_raw, ring = self._get(http, KEY_URL)
            raw, print_data = self._get(http, SAMPLE_URL, params={"symbol": symbol})
        observed_at = self.clock()
        verification = verify_print(print_data, ring, now=observed_at,
                                    expected_symbol=symbol,
                                    max_age_seconds=POLICY["max_age_seconds"])
        reasons = list(verification["reasons"])
        if not verification["record_valid"]:
            reasons.append("FULL_RECORD_REQUIRED")
        if not verification["fresh"]:
            reasons.append("FRESH_PRINT_REQUIRED")
        if print_data.get("grade") not in POLICY["allowed_grades"]:
            reasons.append("GRADE_NOT_ELIGIBLE")
        count = print_data.get("sources")
        if type(count) is not int or count < POLICY["min_reported_sources"]:
            reasons.append("INSUFFICIENT_REPORTED_SOURCES")
        eligible = not reasons
        body = {
            "schema": "szl.puriq-signed-price-observation/v1",
            "source_url": SAMPLE_URL + "?symbol=" + symbol,
            "key_source_url": KEY_URL,
            "key_trust": "HTTPS_PROVIDER_KEYRING_NOT_INDEPENDENTLY_PINNED",
            "observed_at": observed_at,
            "source_at": print_data.get("at"),
            "raw_payload_sha256": hashlib.sha256(raw).hexdigest(),
            "keyring_sha256": hashlib.sha256(key_raw).hexdigest(),
            "verification": verification,
            "policy": POLICY,
            "decision": "REVIEW" if eligible else "ABSTAIN",
            "decision_reasons": sorted(set(reasons)),
            "local_signature_claimed": False,
        }
        return {
            "status": body["decision"], "truth_label": "REPORTED", "symbol": symbol,
            "price_text": print_data.get("priceText") if eligible else None,
            "provider_print": print_data,
            "verification": verification,
            "decision_reasons": body["decision_reasons"],
            "receipt": {**body, "receipt_id": sha256_json(body), "receipt_algorithm": "SHA-256"},
            "trading_enabled": False, "capital_transferred": False, "can_authorize": False,
        }


client = SignedPriceClient()


@router.get("/signed-prices", include_in_schema=False)
def signed_prices_page():
    return FileResponse(STATIC / "index.html", media_type="text/html")


@router.get("/api/puriq/v1/signed-price")
def signed_price(symbol: Literal["BTC", "ETH", "SOL"] = "BTC"):
    try:
        result = client.observe(symbol)
        return JSONResponse(content=result, headers={"Cache-Control": "no-store"})
    except SourceUnavailable:
        return JSONResponse(status_code=503, headers={"Cache-Control": "no-store"}, content={
            "status": "UNAVAILABLE", "truth_label": "UNAVAILABLE",
            "reason": "The public signed-price source or keyring is unavailable.",
            "price_text": None, "can_authorize": False,
            "trading_enabled": False, "capital_transferred": False,
        })
