"""PURIQ Market Chamber — bounded public-market observations and receipts.

This module is read-only by construction. It contains no wallet, key, account,
order, custody, or trade endpoint. Every upstream destination is fixed, every
response is size-bounded, redirects are rejected, and unavailable sources stay
UNAVAILABLE rather than being replaced with sample data.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from szl_puriq import TRUST_CEILING, lambda_weighted

VERSION = "2.0.0"
SOURCE_REPOSITORY = "szl-holdings/puriq-live"
VERTICAL_FABRIC_REPOSITORY = "szl-holdings/vertical-services"
SESSION_TOKEN = re.compile(r"^[A-Za-z0-9._~-]{32,128}$")
CIK = re.compile(r"^\d{1,10}$")
CURRENCY = re.compile(r"^[A-Z0-9]{2,10}$")

ALLOWED_HOSTS = {
    "gamma-api.polymarket.com",
    "api.coinbase.com",
    "api.fiscaldata.treasury.gov",
    "data.sec.gov",
}
COINBASE_BASES = {"BTC", "ETH", "SOL", "ADA", "AVAX", "LINK", "LTC"}
COINBASE_QUOTES = {"USD", "EUR", "GBP"}
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SZL-PURIQ-Market-Chamber/2.0 (+https://a-11-oy.com)",
}
SEC_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": "SZL Holdings PURIQ research https://a-11-oy.com",
    "Accept-Encoding": "gzip, deflate",
}


class SourceUnavailable(RuntimeError):
    """An allowlisted public source did not produce a valid observation."""


@dataclass(frozen=True)
class SourceSpec:
    id: str
    authority: str
    url: str
    freshness_seconds: int
    max_bytes: int
    required: bool
    description: str


SOURCES = {
    "polymarket": SourceSpec(
        id="polymarket",
        authority="Polymarket Gamma API",
        url="https://gamma-api.polymarket.com/markets",
        freshness_seconds=60,
        max_bytes=8_000_000,
        required=True,
        description=(
            "Public market-discovery metadata and quoted outcome prices in "
            "read-only mode."
        ),
    ),
    "coinbase": SourceSpec(
        id="coinbase",
        authority="Coinbase public prices API",
        url="https://api.coinbase.com/v2/prices/{pair}/spot",
        freshness_seconds=60,
        max_bytes=1_000_000,
        required=False,
        description="Public crypto spot reference; no account or trading access.",
    ),
    "treasury": SourceSpec(
        id="treasury",
        authority="U.S. Department of the Treasury FiscalData",
        url=(
            "https://api.fiscaldata.treasury.gov/services/api/"
            "fiscal_service/v2/accounting/od/avg_interest_rates"
        ),
        freshness_seconds=3600,
        max_bytes=4_000_000,
        required=False,
        description="Official average interest rates on Treasury securities.",
    ),
    "sec": SourceSpec(
        id="sec",
        authority="U.S. Securities and Exchange Commission",
        url="https://data.sec.gov/submissions/CIK{cik}.json",
        freshness_seconds=900,
        max_bytes=12_000_000,
        required=True,
        description="Real-time EDGAR company submissions history.",
    ),
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def clamp01(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        return 0.0
    return min(1.0, max(0.0, numeric))


def binary_entropy(probability: float) -> float:
    """Normalized binary Shannon entropy in [0, 1]."""
    p = clamp01(probability)
    if p in {0.0, 1.0}:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def probability_edge(probability: float, reference: float = 0.5) -> float:
    """Descriptive displacement from a bounded reference probability."""
    return round(clamp01(probability) - clamp01(reference), 8)


def liquidity_quality(
    *,
    spread: float | None,
    liquidity: float | None,
    volume_24h: float | None,
) -> dict[str, Any]:
    """Transparent market-microstructure quality indicator.

    This is a data-quality heuristic, not expected return, fair value, or a
    recommendation. Missing inputs reduce the score instead of being imputed.
    """
    axes: dict[str, float] = {}
    if spread is not None:
        axes["spread"] = clamp01(1.0 - max(0.0, spread) / 0.20)
    if liquidity is not None:
        axes["liquidity"] = clamp01(math.log10(1.0 + max(0.0, liquidity)) / 7.0)
    if volume_24h is not None:
        axes["volume"] = clamp01(math.log10(1.0 + max(0.0, volume_24h)) / 7.0)
    score = sum(axes.values()) / len(axes) if axes else 0.0
    return {
        "score": round(score, 6),
        "axes": axes,
        "label": "MODELED_DATA_QUALITY",
        "can_authorize": False,
    }


def session_scope(token: str) -> str:
    value = token.strip()
    if SESSION_TOKEN.fullmatch(value) is None:
        raise ValueError(
            "X-SZL-Session must be 32-128 characters using A-Z, a-z, 0-9, . _ ~ or -"
        )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_url(url: str, query: Mapping[str, str]) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=False),
            "",
        )
    )


def _assert_destination(url: str) -> None:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_HOSTS
        or parts.username
        or parts.password
    ):
        raise SourceUnavailable("source destination failed the fixed allowlist")


def _bounded_get_json(
    url: str,
    *,
    query: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    max_bytes: int,
    transport: httpx.BaseTransport | None = None,
) -> tuple[int, bytes, Any, str]:
    _assert_destination(url)
    query = dict(query or {})
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            transport=transport,
        ) as client:
            with client.stream(
                "GET",
                url,
                params=query,
                headers=dict(headers or DEFAULT_HEADERS),
            ) as response:
                if 300 <= response.status_code < 400:
                    raise SourceUnavailable("upstream redirect rejected")
                if response.status_code < 200 or response.status_code >= 300:
                    raise SourceUnavailable(
                        f"upstream returned HTTP {response.status_code}"
                    )
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise SourceUnavailable("upstream response exceeds byte budget")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise SourceUnavailable("upstream response exceeds byte budget")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                try:
                    payload = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SourceUnavailable("upstream returned invalid JSON") from exc
                return response.status_code, raw, payload, _safe_url(url, query)
    except SourceUnavailable:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise SourceUnavailable(f"source transport failed: {type(exc).__name__}") from exc


def _number(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def normalize_polymarket(payload: Any, *, limit: int) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise SourceUnavailable("Polymarket payload schema is not recognized")
    rows: list[dict[str, Any]] = []
    volume_total = 0.0
    liquidity_total = 0.0
    for item in payload[:limit]:
        if not isinstance(item, dict):
            continue
        outcomes = [str(value)[:100] for value in _json_list(item.get("outcomes"))]
        raw_prices = _json_list(item.get("outcomePrices"))
        probabilities = [
            clamp01(value)
            for value in (_number(item) for item in raw_prices)
            if value is not None
        ]
        outcome_prices = [
            {"outcome": outcome, "probability": probability}
            for outcome, probability in zip(outcomes, probabilities)
        ]
        yes_probability: float | None = None
        for pair in outcome_prices:
            if pair["outcome"].strip().casefold() == "yes":
                yes_probability = pair["probability"]
                break
        if yes_probability is None and len(probabilities) == 2:
            yes_probability = probabilities[0]
        best_bid = _number(item.get("bestBid"))
        best_ask = _number(item.get("bestAsk"))
        spread = (
            max(0.0, best_ask - best_bid)
            if best_bid is not None and best_ask is not None
            else None
        )
        volume = _number(
            item.get("volume24hr")
            or item.get("volume24Hr")
            or item.get("volume")
        )
        liquidity = _number(item.get("liquidityNum") or item.get("liquidity"))
        volume_total += volume or 0.0
        liquidity_total += liquidity or 0.0
        rows.append(
            {
                "id": item.get("id"),
                "condition_id": item.get("conditionId"),
                "slug": item.get("slug"),
                "question": item.get("question"),
                "active": bool(item.get("active")),
                "closed": bool(item.get("closed")),
                "end_date": item.get("endDate") or item.get("end_date_iso"),
                "outcomes": outcome_prices,
                "yes_probability": yes_probability,
                "binary_entropy": (
                    round(binary_entropy(yes_probability), 8)
                    if yes_probability is not None
                    else None
                ),
                "probability_edge_from_50": (
                    probability_edge(yes_probability)
                    if yes_probability is not None
                    else None
                ),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 8) if spread is not None else None,
                "volume_24h": volume,
                "liquidity": liquidity,
                "liquidity_quality": liquidity_quality(
                    spread=spread,
                    liquidity=liquidity,
                    volume_24h=volume,
                ),
                "market_url": (
                    f"https://polymarket.com/event/{item.get('slug')}"
                    if item.get("slug")
                    else None
                ),
            }
        )
    return {
        "markets": rows,
        "returned": len(rows),
        "volume_24h_total": round(volume_total, 6),
        "liquidity_total": round(liquidity_total, 6),
        "mode": "PUBLIC_READ_ONLY",
        "quoted_probability_is_market_price": True,
        "trading_enabled": False,
        "custody_enabled": False,
        "investment_advice": False,
    }


def normalize_coinbase(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise SourceUnavailable("Coinbase payload schema is not recognized")
    data = payload["data"]
    amount = _number(data.get("amount"))
    if amount is None:
        raise SourceUnavailable("Coinbase spot amount is unavailable")
    return {
        "base": data.get("base"),
        "currency": data.get("currency"),
        "amount": amount,
        "mode": "PUBLIC_SPOT_REFERENCE",
        "trading_enabled": False,
        "custody_enabled": False,
    }


def normalize_treasury(payload: Any, *, limit: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise SourceUnavailable("Treasury payload schema is not recognized")
    rows: list[dict[str, Any]] = []
    for item in payload["data"][:limit]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "record_date": item.get("record_date"),
                "security_type": item.get("security_type_desc"),
                "security_description": item.get("security_desc"),
                "average_interest_rate_pct": _number(
                    item.get("avg_interest_rate_amt")
                ),
                "source_line_number": item.get("src_line_nbr"),
            }
        )
    rates = [
        row["average_interest_rate_pct"]
        for row in rows
        if row["average_interest_rate_pct"] is not None
    ]
    return {
        "rates": rows,
        "returned": len(rows),
        "latest_record_date": rows[0]["record_date"] if rows else None,
        "rate_min_pct": min(rates) if rates else None,
        "rate_max_pct": max(rates) if rates else None,
        "mode": "OFFICIAL_PUBLIC_REFERENCE",
    }


def normalize_sec(payload: Any, *, limit: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SourceUnavailable("SEC submissions payload schema is not recognized")
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        recent = {}
    keys = [key for key, value in recent.items() if isinstance(value, list)]
    length = min(min([len(recent[key]) for key in keys] or [0]), limit)
    filings = [
        {key: recent[key][index] for key in keys}
        for index in range(length)
    ]
    return {
        "cik": payload.get("cik"),
        "name": payload.get("name"),
        "tickers": payload.get("tickers", []),
        "exchanges": payload.get("exchanges", []),
        "sic": payload.get("sic"),
        "sic_description": payload.get("sicDescription"),
        "fiscal_year_end": payload.get("fiscalYearEnd"),
        "recent_filings": filings,
        "returned": len(filings),
        "mode": "OFFICIAL_PUBLIC_FILING_REFERENCE",
    }


def observation_receipt(
    *,
    source: SourceSpec,
    source_url: str,
    raw: bytes,
    observation: Mapping[str, Any],
    observed_at: float,
) -> dict[str, Any]:
    body = {
        "schema": "szl.puriq-observation/v2",
        "source_id": source.id,
        "authority": source.authority,
        "source_url": source_url,
        "http_status": 200,
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "observation_sha256": sha256_json(observation),
        "observed_at": observed_at,
        "expires_at": observed_at + source.freshness_seconds,
        "state": "OBSERVED",
        "truth_label": "REPORTED",
        "signature_claimed": False,
    }
    return {
        **body,
        "receipt_id": sha256_json(body),
        "receipt_algorithm": "SHA-256",
    }


class SessionLedger:
    """Bounded process-memory projection keyed only by hashed caller sessions."""

    def __init__(self, max_sessions: int = 128, per_session: int = 64) -> None:
        self.max_sessions = max_sessions
        self.per_session = per_session
        self._rows: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._lock = threading.RLock()

    def append(self, scope: str, item: Mapping[str, Any]) -> None:
        safe = {
            "receipt_id": item.get("receipt_id"),
            "source_id": item.get("source_id"),
            "observed_at": item.get("observed_at"),
            "expires_at": item.get("expires_at"),
            "truth_label": item.get("truth_label"),
            "state": item.get("state"),
        }
        with self._lock:
            rows = self._rows.pop(scope, [])
            rows.append(safe)
            self._rows[scope] = rows[-self.per_session :]
            while len(self._rows) > self.max_sessions:
                self._rows.popitem(last=False)

    def recent(self, scope: str, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._rows.get(scope, []))
        return list(reversed(rows[-max(1, min(limit, self.per_session)) :]))

    def status(self) -> dict[str, Any]:
        with self._lock:
            sessions = len(self._rows)
            observations = sum(len(rows) for rows in self._rows.values())
        return {
            "durability": "EPHEMERAL_PROCESS_MEMORY",
            "session_scope": "SHA256_CALLER_TOKEN",
            "sessions": sessions,
            "observations": observations,
            "raw_session_tokens_recorded": False,
            "max_sessions": self.max_sessions,
            "max_observations_per_session": self.per_session,
        }


LEDGER = SessionLedger()


class PuriqClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def polymarket(self, limit: int = 16) -> tuple[dict[str, Any], dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        spec = SOURCES["polymarket"]
        query = {
            "limit": str(limit),
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        }
        _, raw, payload, source_url = _bounded_get_json(
            spec.url,
            query=query,
            max_bytes=spec.max_bytes,
            transport=self.transport,
        )
        observation = normalize_polymarket(payload, limit=limit)
        receipt = observation_receipt(
            source=spec,
            source_url=source_url,
            raw=raw,
            observation=observation,
            observed_at=time.time(),
        )
        return observation, receipt

    def coinbase(
        self,
        base: str = "BTC",
        currency: str = "USD",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        base = base.strip().upper()
        currency = currency.strip().upper()
        if (
            CURRENCY.fullmatch(base) is None
            or base not in COINBASE_BASES
            or currency not in COINBASE_QUOTES
        ):
            raise ValueError("base or currency is not in the public spot allowlist")
        spec = SOURCES["coinbase"]
        url = spec.url.format(pair=f"{base}-{currency}")
        _, raw, payload, source_url = _bounded_get_json(
            url,
            max_bytes=spec.max_bytes,
            transport=self.transport,
        )
        observation = normalize_coinbase(payload)
        receipt = observation_receipt(
            source=spec,
            source_url=source_url,
            raw=raw,
            observation=observation,
            observed_at=time.time(),
        )
        return observation, receipt

    def treasury(self, limit: int = 12) -> tuple[dict[str, Any], dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        spec = SOURCES["treasury"]
        query = {
            "sort": "-record_date",
            "page[size]": str(limit),
            "fields": (
                "record_date,security_type_desc,security_desc,"
                "avg_interest_rate_amt,src_line_nbr"
            ),
        }
        _, raw, payload, source_url = _bounded_get_json(
            spec.url,
            query=query,
            max_bytes=spec.max_bytes,
            transport=self.transport,
        )
        observation = normalize_treasury(payload, limit=limit)
        receipt = observation_receipt(
            source=spec,
            source_url=source_url,
            raw=raw,
            observation=observation,
            observed_at=time.time(),
        )
        return observation, receipt

    def sec(
        self,
        cik: str = "320193",
        limit: int = 12,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        cik = str(cik).strip()
        if CIK.fullmatch(cik) is None:
            raise ValueError("cik must contain 1 to 10 digits")
        limit = max(1, min(100, int(limit)))
        spec = SOURCES["sec"]
        url = spec.url.format(cik=cik.zfill(10))
        _, raw, payload, source_url = _bounded_get_json(
            url,
            headers=SEC_HEADERS,
            max_bytes=spec.max_bytes,
            transport=self.transport,
        )
        observation = normalize_sec(payload, limit=limit)
        receipt = observation_receipt(
            source=spec,
            source_url=source_url,
            raw=raw,
            observation=observation,
            observed_at=time.time(),
        )
        return observation, receipt

    def brief(
        self,
        *,
        scope: str | None = None,
        market_limit: int = 16,
        cik: str = "320193",
        crypto_base: str = "BTC",
        crypto_currency: str = "USD",
    ) -> dict[str, Any]:
        calls = {
            "polymarket": lambda: self.polymarket(market_limit),
            "coinbase": lambda: self.coinbase(crypto_base, crypto_currency),
            "treasury": lambda: self.treasury(12),
            "sec": lambda: self.sec(cik, 12),
        }
        observations: dict[str, Any] = {}
        receipts: dict[str, Any] = {}
        failures: dict[str, str] = {}
        for source_id, call in calls.items():
            try:
                observation, receipt = call()
            except (SourceUnavailable, ValueError) as exc:
                observations[source_id] = {
                    "state": "UNAVAILABLE",
                    "truth_label": "UNAVAILABLE",
                }
                failures[source_id] = f"{type(exc).__name__}: {exc}"
                continue
            observations[source_id] = observation
            receipts[source_id] = receipt
            if scope is not None:
                LEDGER.append(scope, receipt)

        required = [source.id for source in SOURCES.values() if source.required]
        required_observed = sum(source_id in receipts for source_id in required)
        all_observed = len(receipts)
        axes = {
            "required_source_coverage": required_observed / len(required),
            "total_source_coverage": all_observed / len(SOURCES),
            "receipt_integrity": 1.0 if all(
                len(item.get("receipt_id", "")) == 64 for item in receipts.values()
            ) else 0.0,
            "source_policy": 1.0,
        }
        lambda_score = lambda_weighted(
            list(axes.values()),
            [1.0 / len(axes)] * len(axes),
        )
        complete = required_observed == len(required)
        return {
            "schema": "szl.puriq-market-brief/v2",
            "version": VERSION,
            "source_repository": SOURCE_REPOSITORY,
            "vertical_fabric_repository": VERTICAL_FABRIC_REPOSITORY,
            "status": "READY" if complete else "DEGRADED",
            "complete": complete,
            "observations": observations,
            "receipts": receipts,
            "source_failures": failures,
            "source_summary": {
                "required": required,
                "required_observed": required_observed,
                "total": len(SOURCES),
                "observed": all_observed,
            },
            "lambda_advisory": {
                "score": round(min(TRUST_CEILING, max(0.0, lambda_score)), 6),
                "axes": axes,
                "status": "CONJECTURE_1_ADVISORY",
                "can_authorize": False,
            },
            "boundaries": {
                "trading_enabled": False,
                "custody_enabled": False,
                "wallet_connections_enabled": False,
                "investment_advice": False,
                "effectors_enabled": False,
                "human_review_required": True,
            },
            "truth_label": "REPORTED" if receipts else "UNAVAILABLE",
        }
