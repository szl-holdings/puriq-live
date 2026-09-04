"""PURIQ Market Chamber — governed public-market intelligence.

The service exposes public market observations, source receipts, Living Anatomy,
session-scoped Second-Brain memory, and non-authorizing Hatun review. It has no
wallet, account, order, custody, or unattended effector surface.
"""
from __future__ import annotations

import html
import math
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from puriq_market import (
    LEDGER,
    SOURCES,
    SOURCE_REPOSITORY,
    VERSION,
    PuriqClient,
    session_scope,
    sha256_json,
)
from szl_puriq import (
    LOCKED_8,
    TRUST_CEILING,
    egyptian_weights,
    execute_corpus,
    lambda_weighted,
    yuyay_weights,
)

app = FastAPI(
    title="PURIQ Market Chamber",
    version=VERSION,
    description=(
        "Read-only public-market intelligence with source receipts, Living "
        "Anatomy, session memory, and non-authorizing Hatun review."
    ),
)
CLIENT = PuriqClient()
SHA40 = re.compile(r"^[0-9a-f]{40}$")
AXIS_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
ACTION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{1,63}$")

ANATOMY = (
    ("sense", "Acquire only fixed, allowlisted public-market observations."),
    ("normalize", "Validate schemas, numbers, identifiers, and source boundaries."),
    ("context", "Bind observations to source, time, query, and session scope."),
    ("formula", "Apply explicit PURIQ formulas with maturity boundaries."),
    ("policy", "Deny wallet, custody, trading, and unattended execution paths."),
    ("decide", "Produce review or abstention; never an autonomous order."),
    ("verify", "Check source identity, digests, freshness, and invariants."),
    ("remember", "Retain bounded receipt handles under a hashed session."),
    ("receipt", "Mint deterministic SHA-256 observation and review receipts."),
)

FORMULAS = (
    {
        "id": "puriq.lambda_symmetric",
        "name": "Symmetric Lambda",
        "equation": "Λ(x)=∏xᵢ^(1/n)",
        "status": "CONJECTURE_1_ADVISORY",
        "can_authorize": False,
    },
    {
        "id": "puriq.lambda_egyptian",
        "name": "Egyptian-weighted Lambda",
        "equation": "Λ_w(x)=∏xᵢ^wᵢ, Σwᵢ=1",
        "status": "ANCHORED_CONDITIONAL_REGIME",
        "can_authorize": False,
    },
    {
        "id": "puriq.binary_entropy",
        "name": "Binary market entropy",
        "equation": "H(p)=-p·log₂p-(1-p)·log₂(1-p)",
        "status": "TESTED_TRANSFORM",
        "can_authorize": False,
    },
    {
        "id": "puriq.probability_edge",
        "name": "Probability displacement",
        "equation": "edge(p,r)=clamp(p)-clamp(r)",
        "status": "TESTED_TRANSFORM",
        "can_authorize": False,
    },
    {
        "id": "puriq.liquidity_quality",
        "name": "Market microstructure quality",
        "equation": "mean(spread_quality, liquidity_depth, volume_depth)",
        "status": "MODELED_DATA_QUALITY",
        "can_authorize": False,
    },
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HatunRequest(StrictModel):
    intent: str = Field(min_length=1, max_length=240)
    requested_action: str = Field(default="market.review", min_length=2, max_length=64)
    axes: dict[str, float]
    evidence_receipt_ids: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("intent must not be blank")
        return value

    @field_validator("requested_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        value = value.strip()
        if ACTION_ID.fullmatch(value) is None:
            raise ValueError("requested_action is invalid")
        return value

    @field_validator("axes")
    @classmethod
    def validate_axes(cls, value: dict[str, float]) -> dict[str, float]:
        if not 2 <= len(value) <= 16:
            raise ValueError("axes must contain between 2 and 16 values")
        clean: dict[str, float] = {}
        for key, item in value.items():
            name = key.strip().lower()
            numeric = float(item)
            if AXIS_ID.fullmatch(name) is None:
                raise ValueError(f"invalid axis: {key!r}")
            if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
                raise ValueError(f"axis {name!r} must be finite and in [0,1]")
            clean[name] = numeric
        return clean

    @field_validator("evidence_receipt_ids")
    @classmethod
    def validate_receipts(cls, value: list[str]) -> list[str]:
        clean = [item.strip().lower() for item in value]
        if any(re.fullmatch(r"[0-9a-f]{64}", item) is None for item in clean):
            raise ValueError("evidence receipt IDs must be 64 lowercase hex characters")
        if len(clean) != len(set(clean)):
            raise ValueError("evidence receipt IDs must be unique")
        return clean


def _source_observation() -> dict[str, Any]:
    candidates: list[tuple[str, str]] = []
    for env_name in ("PURIQ_SOURCE_REVISION", "SZL_SOURCE_REVISION"):
        value = os.environ.get(env_name, "").strip().lower()
        if SHA40.fullmatch(value):
            candidates.append((f"env:{env_name}", value))
    for label, path in (
        ("repository-file", Path(__file__).resolve().parent / "source_revision.txt"),
        ("container-file", Path("/app/source_revision.txt")),
    ):
        try:
            value = path.read_text(encoding="ascii").strip().lower()
        except OSError:
            continue
        if SHA40.fullmatch(value):
            candidates.append((label, value))
    revisions = sorted({value for _, value in candidates})
    if not revisions:
        state, revision = "UNBOUND", "UNAVAILABLE"
    elif len(revisions) == 1:
        state, revision = "OBSERVED", revisions[0]
    else:
        state, revision = "MISMATCH", revisions[0]
    return {
        "state": state,
        "revision": revision,
        "bindings_agree": len(revisions) <= 1,
        "evidence_sources": sorted({label for label, _ in candidates}),
    }


def build_info() -> dict[str, Any]:
    source = _source_observation()
    return {
        "schema": "szl.build-info/v1",
        "service": "puriq-market-chamber",
        "version": VERSION,
        "source_repository": SOURCE_REPOSITORY,
        "build": {"state": source["state"], "revision": source["revision"]},
        "source_binding": {
            "bindings_agree": source["bindings_agree"],
            "evidence_sources": source["evidence_sources"],
        },
        "receipt_minted": False,
        "truth_label": "MEASURED",
    }


def _require_scope(value: str) -> str:
    try:
        return session_scope(value)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.middleware("http")
async def harden_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self' https://huggingface.co"
    )
    if request.url.path != "/":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def health() -> dict[str, Any]:
    corpus = execute_corpus()
    return {
        "ok": corpus["tallies"]["FAILED"] == 0,
        "service": "puriq-market-chamber",
        "version": VERSION,
        "sources": list(SOURCES),
        "formula_corpus": corpus["tallies"],
        "locked_formula_ids": list(LOCKED_8),
        "lambda_status": "Conjecture 1 (advisory only)",
        "memory": LEDGER.status(),
        "trading_enabled": False,
        "custody_enabled": False,
        "wallet_connections_enabled": False,
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }


@app.get("/readyz")
def readiness() -> JSONResponse:
    build = build_info()
    corpus = execute_corpus()
    ready = (
        build["build"]["state"] == "OBSERVED"
        and build["source_binding"]["bindings_agree"] is True
        and corpus["tallies"]["FAILED"] == 0
    )
    return JSONResponse(
        {
            "ready": ready,
            "service": "puriq-market-chamber",
            "version": VERSION,
            "build": build["build"],
            "source_binding": build["source_binding"],
            "formula_corpus": corpus["tallies"],
            "network_sources_wired": True,
            "live_observations_require_explicit_request": True,
            "trading_enabled": False,
            "effectors_enabled": False,
            "truth_label": "MEASURED",
        },
        status_code=200 if ready else 503,
    )


@app.get("/api/build-info")
def build_info_route() -> dict[str, Any]:
    return build_info()


@app.get("/.well-known/szl-source.json")
def source_document() -> dict[str, Any]:
    return build_info()


@app.get("/api/puriq/v1/anatomy")
def anatomy() -> dict[str, Any]:
    return {
        "schema": "szl.living-anatomy.puriq/v2",
        "product": "PURIQ Market Chamber",
        "domain": "financial-and-prediction-market-intelligence",
        "organs": [
            {"order": index, "id": organ_id, "contract": contract}
            for index, (organ_id, contract) in enumerate(ANATOMY, start=1)
        ],
        "second_brain_scope": "SHA256_CALLER_SESSION",
        "hatun_decisions": ["REVIEW", "ABSTAIN"],
        "truth_label": "MEASURED",
    }


@app.get("/api/puriq/v1/formulas")
def formulas() -> dict[str, Any]:
    corpus = execute_corpus()
    return {
        "schema": "szl.formula-binding.puriq/v2",
        "formulas": FORMULAS,
        "formula_count": len(FORMULAS),
        "locked_proven_ids": list(LOCKED_8),
        "corpus": corpus["tallies"],
        "symmetric_weights": yuyay_weights(13),
        "egyptian_weights": egyptian_weights(13),
        "lambda_status": "Conjecture 1 (open) — advisory only",
        "can_authorize": False,
        "truth_label": "MEASURED",
    }


@app.get("/api/puriq/v1/sources")
def sources() -> dict[str, Any]:
    return {
        "schema": "szl.source-catalog.puriq/v2",
        "sources": [
            {
                "id": source.id,
                "authority": source.authority,
                "authority_url": source.url,
                "freshness_seconds": source.freshness_seconds,
                "max_bytes": source.max_bytes,
                "required": source.required,
                "description": source.description,
                "state": "WIRED",
            }
            for source in SOURCES.values()
        ],
        "caller_supplied_urls_allowed": False,
        "redirects_allowed": False,
        "secrets_required": False,
        "truth_label": "MEASURED",
    }


@app.get("/api/puriq/v1/markets")
def markets(
    limit: int = Query(16, ge=1, le=100),
    x_szl_session: str = Header(..., alias="X-SZL-Session"),
) -> dict[str, Any]:
    scope = _require_scope(x_szl_session)
    try:
        observation, receipt = CLIENT.polymarket(limit)
    except Exception as exc:
        raise HTTPException(
            502,
            f"Polymarket observation unavailable: {type(exc).__name__}",
        ) from exc
    LEDGER.append(scope, receipt)
    return {
        "schema": "szl.puriq-markets/v2",
        "observation": observation,
        "receipt": receipt,
        "session_token_recorded": False,
        "truth_label": "REPORTED",
    }


@app.get("/api/puriq/v1/brief")
def market_brief(
    market_limit: int = Query(16, ge=1, le=100),
    cik: str = Query("320193", min_length=1, max_length=10),
    crypto_base: str = Query("BTC", min_length=2, max_length=10),
    crypto_currency: str = Query("USD", min_length=2, max_length=10),
    x_szl_session: str = Header(..., alias="X-SZL-Session"),
) -> dict[str, Any]:
    scope = _require_scope(x_szl_session)
    try:
        return CLIENT.brief(
            scope=scope,
            market_limit=market_limit,
            cik=cik,
            crypto_base=crypto_base,
            crypto_currency=crypto_currency,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/puriq/v1/second-brain")
def second_brain(
    limit: int = Query(25, ge=1, le=64),
    x_szl_session: str = Header(..., alias="X-SZL-Session"),
) -> dict[str, Any]:
    scope = _require_scope(x_szl_session)
    return {
        "schema": "szl.second-brain.puriq/v2",
        "scope": "SHA256_CALLER_SESSION",
        "memory": LEDGER.recent(scope, limit=limit),
        "memory_status": LEDGER.status(),
        "anatomy": anatomy(),
        "formula_binding": formulas(),
        "raw_session_token_recorded": False,
        "effectors_enabled": False,
        "human_review_required": True,
        "truth_label": "MEASURED",
    }


@app.post("/api/puriq/v1/hatun/evaluate")
def hatun_evaluate(
    review: HatunRequest,
    x_szl_session: str = Header(..., alias="X-SZL-Session"),
) -> dict[str, Any]:
    scope = _require_scope(x_szl_session)
    memory = LEDGER.recent(scope, limit=64)
    known_receipts = {item["receipt_id"] for item in memory}
    evidence_known = bool(review.evidence_receipt_ids) and set(
        review.evidence_receipt_ids
    ).issubset(known_receipts)
    weights = [1.0 / len(review.axes)] * len(review.axes)
    score = lambda_weighted(list(review.axes.values()), weights)
    blockers: list[str] = []
    if not memory:
        blockers.append("NO_SESSION_OBSERVATIONS")
    if not review.evidence_receipt_ids:
        blockers.append("NO_EVIDENCE_RECEIPTS")
    elif not evidence_known:
        blockers.append("UNKNOWN_EVIDENCE_RECEIPT")
    if score < 0.80:
        blockers.append("LAMBDA_BELOW_REVIEW_FLOOR")
    decision = "REVIEW" if not blockers else "ABSTAIN"
    basis = {
        "schema": "szl.hatun-puriq-review/v1",
        "intent": review.intent,
        "requested_action": review.requested_action,
        "axes": review.axes,
        "lambda_score": round(min(TRUST_CEILING, max(0.0, score)), 6),
        "lambda_status": "CONJECTURE_1_ADVISORY",
        "evidence_receipt_ids": review.evidence_receipt_ids,
        "evidence_known_in_session": evidence_known,
        "decision": decision,
        "blockers": blockers,
        "can_authorize": False,
        "can_execute": False,
        "human_approval_required": True,
    }
    return {
        **basis,
        "receipt": {
            "schema": "szl.hatun-puriq-review-receipt/v1",
            "algorithm": "SHA-256",
            "basis_sha256": sha256_json(basis),
            "signature_claimed": False,
            "session_token_recorded": False,
        },
        "trading_enabled": False,
        "effectors_enabled": False,
        "truth_label": "MODELED",
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en" data-puriq="market-chamber-v2">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>PURIQ Market Chamber · SZL Holdings</title>
<style>
:root{color-scheme:dark;--bg:#07050c;--deep:#030207;--panel:#151020;--ink:#f7f3ff;--muted:#aa9fb7;--violet:#b989ff;--gold:#f5c86b;--line:color-mix(in srgb,var(--violet) 25%,transparent);--good:#6ee7b7;--bad:#ff7d95}
*{box-sizing:border-box;min-inline-size:0}html{overflow-x:clip;background:var(--deep);scroll-padding-top:84px}body{margin:0;min-height:100vh;overflow-x:clip;color:var(--ink);font:15px/1.5 Inter,"Segoe UI",system-ui,sans-serif;background:radial-gradient(circle at 76% 7%,rgb(185 137 255/.16),transparent 34rem),radial-gradient(circle at 8% 62%,rgb(245 200 107/.08),transparent 26rem),linear-gradient(180deg,var(--deep),var(--bg) 44%,var(--deep))}
a,button,input,select{font:inherit}a{color:inherit;min-height:44px;display:inline-flex;align-items:center}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--gold);outline-offset:3px}button{min-height:46px;border:1px solid var(--violet);border-radius:999px;padding:0 18px;background:linear-gradient(120deg,var(--violet),#7d5ce8);color:#08040f;font-weight:800;cursor:pointer}button[disabled]{opacity:.55;cursor:wait}input,select{min-height:46px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--ink);padding:0 12px;max-width:100%}
.skip{position:fixed;left:12px;top:-80px;z-index:10;background:#fff;color:#000;padding:10px 14px}.skip:focus{top:12px}.ambient{position:fixed;inset:0;pointer-events:none;overflow:hidden;opacity:.62}.orbit{position:absolute;border:1px solid var(--line);border-radius:50%;filter:drop-shadow(0 0 20px rgb(185 137 255/.16));animation:orbit 20s ease-in-out infinite alternate}.o1{width:48vmin;height:48vmin;right:2vw;top:9vh;box-shadow:0 0 0 7vmin transparent,0 0 0 calc(7vmin + 1px) var(--line),0 0 0 15vmin transparent,0 0 0 calc(15vmin + 1px) var(--line)}.o2{width:17vmin;height:17vmin;left:5vw;bottom:9vh;animation-delay:-8s}@keyframes orbit{to{transform:translate3d(0,22px,0) rotate(8deg)}}
.shell{position:relative;width:min(1260px,100%);margin:auto;padding:clamp(20px,5vw,70px)}.top{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.brand,.eyebrow,.mono,.formula span{font:750 11px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.13em;text-transform:uppercase}.brand,.eyebrow,.formula span{color:var(--violet)}.nav{display:flex;gap:12px;flex-wrap:wrap}.nav a{text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:0 14px;background:rgb(21 16 32/.76)}
.hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr);gap:clamp(28px,6vw,82px);padding:clamp(56px,9vw,116px) 0 48px;align-items:end}h1{font-size:clamp(56px,9vw,122px);line-height:.82;letter-spacing:-.065em;margin:16px 0 24px;max-width:8.6ch}.lede{font-size:clamp(17px,2vw,23px);color:var(--muted);max-width:67ch}.proof{display:flex;gap:8px;flex-wrap:wrap;margin-top:28px}.pill{border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:rgb(21 16 32/.7)}.pill.good{color:var(--good)}
.chamber{border:1px solid var(--line);border-radius:30px;padding:22px;background:linear-gradient(145deg,rgb(185 137 255/.1),transparent 42%),rgb(21 16 32/.88);box-shadow:0 34px 100px rgb(0 0 0/.38)}.dial{position:relative;aspect-ratio:1;border:1px solid var(--line);border-radius:50%;display:grid;place-items:center;background:conic-gradient(from -90deg,rgb(185 137 255/.18),transparent 32%,rgb(245 200 107/.10),transparent 70%)}.dial::before,.dial::after{content:"";position:absolute;border:1px solid var(--line);border-radius:50%;inset:17%}.dial::after{inset:35%;background:var(--panel)}.dial strong{position:relative;z-index:2;font-size:clamp(34px,5vw,70px);letter-spacing:-.05em}.chamber small{display:block;color:var(--muted);margin-top:16px}
.controls{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;border:1px solid var(--line);border-radius:18px;padding:16px;background:rgb(21 16 32/.72)}.control{display:grid;gap:7px}.control label{font-size:12px;color:var(--muted)}.control.action{align-self:end}.status{margin:14px 0 0;color:var(--muted)}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:26px 0}.metric,.source,.market,.formula,.receipt{border:1px solid var(--line);border-radius:16px;padding:17px;background:rgb(21 16 32/.78)}.metric span,.source span,.market span,.receipt span{color:var(--muted);font-size:12px}.metric strong{display:block;font-size:clamp(26px,4vw,46px);line-height:1;margin-top:8px}.section{padding:28px 0}.section-head{display:flex;justify-content:space-between;gap:18px;align-items:end;flex-wrap:wrap;margin-bottom:18px}.section h2{font-size:clamp(32px,5vw,64px);line-height:.92;letter-spacing:-.05em;margin:0}.section-head p{max-width:66ch;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.market{min-height:300px;display:flex;flex-direction:column;gap:13px}.market h3{font-size:20px;line-height:1.16;margin:0}.market .prob{font-size:42px;letter-spacing:-.04em}.bar{height:8px;border-radius:999px;background:#2a2037;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--violet),var(--gold));width:0}.market dl{display:grid;grid-template-columns:1fr auto;gap:8px 14px;margin:auto 0 0}.market dt{color:var(--muted)}.market dd{margin:0;text-align:right}.market a{margin-top:8px;text-decoration:none;color:var(--gold)}
.sources{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.source strong,.formula strong,.receipt strong{display:block;font-size:17px;margin:10px 0}.source small,.formula small,.receipt small{color:var(--muted)}.formula-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.formula{min-height:168px;display:flex;flex-direction:column}.formula small{margin-top:auto}.boundary{margin-top:30px;padding:20px;border:1px solid var(--line);border-radius:17px;color:var(--muted);background:rgb(21 16 32/.72)}.error{color:var(--bad)}footer{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-top:44px;padding-top:22px;border-top:1px solid var(--line);color:var(--muted)}
@media(max-width:980px){.hero{grid-template-columns:1fr}.chamber{max-width:560px}.controls{grid-template-columns:repeat(2,minmax(0,1fr))}.metrics,.sources{grid-template-columns:repeat(2,minmax(0,1fr))}.formula-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:650px){.shell{padding-inline:18px}h1{font-size:clamp(54px,18vw,82px)}.nav{width:100%}.nav a{flex:1;justify-content:center}.controls,.metrics,.grid,.sources,.formula-grid{grid-template-columns:1fr}.control.action button{width:100%}}@media(pointer:coarse){a,button,input,select{min-height:48px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}@media(forced-colors:active){.ambient{display:none}*{forced-color-adjust:auto}}
</style></head>
<body><a class="skip" href="#main">Skip to market chamber</a><div class="ambient" aria-hidden="true"><div class="orbit o1"></div><div class="orbit o2"></div></div>
<main id="main" class="shell"><header class="top"><div class="brand">SZL / PURIQ</div><nav class="nav" aria-label="Product links"><a href="/docs">API</a><a href="/api/puriq/v1/anatomy">Anatomy</a><a href="/api/puriq/v1/formulas">Math</a><a href="/api/build-info">Source</a></nav></header>
<section class="hero"><div><div class="eyebrow">PUBLIC-MARKET INTELLIGENCE / READ-ONLY</div><h1>Market Chamber.</h1><p class="lede">Prediction markets, SEC filings, Treasury rates, crypto spot references, Living Anatomy, Second-Brain receipt memory, and Hatun review—without a wallet, order path, custody surface, or fabricated feed.</p><div class="proof"><span class="pill good">SOURCE-BOUND CONTRACT</span><span class="pill">REV @@REVISION@@</span><span class="pill">LOCKED 8</span><span class="pill">Λ CONJECTURE 1</span></div></div><aside class="chamber"><div class="dial"><strong id="coverageDial">0/4</strong></div><small id="chamberState">Run the live chamber to observe public sources.</small></aside></section>
<section aria-label="Market controls"><div class="controls"><div class="control"><label for="marketLimit">Prediction markets</label><input id="marketLimit" type="number" min="1" max="50" value="12"></div><div class="control"><label for="cik">SEC CIK</label><input id="cik" inputmode="numeric" pattern="[0-9]*" maxlength="10" value="320193"></div><div class="control"><label for="cryptoBase">Crypto base</label><select id="cryptoBase"><option>BTC</option><option>ETH</option><option>SOL</option><option>ADA</option><option>AVAX</option><option>LINK</option><option>LTC</option></select></div><div class="control"><label for="cryptoCurrency">Quote</label><select id="cryptoCurrency"><option>USD</option><option>EUR</option><option>GBP</option></select></div><div class="control action"><button id="run" type="button">Observe live chamber</button></div></div><p id="status" class="status" role="status" aria-live="polite">No live observation requested yet.</p></section>
<section class="metrics" aria-label="Live summary"><article class="metric"><span>SOURCES OBSERVED</span><strong id="sourcesObserved">—</strong></article><article class="metric"><span>MARKETS RETURNED</span><strong id="marketsReturned">—</strong></article><article class="metric"><span>BTC SPOT</span><strong id="spotPrice">—</strong></article><article class="metric"><span>Λ DATA QUALITY</span><strong id="lambdaScore">—</strong></article></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">Probability Orbit</div><h2>Markets with receipts.</h2></div><p>Quoted probabilities are market prices, not guarantees. Entropy and liquidity quality are descriptive transforms, never trade instructions.</p></div><div id="markets" class="grid"><article class="market"><span>UNAVAILABLE</span><h3>Run the chamber to observe current public markets.</h3></article></div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">SOURCE CONSTELLATION</div><h2>Four fixed authorities.</h2></div><p>Destinations are allowlisted, redirects are rejected, responses are bounded, and every successful observation carries a SHA-256 receipt.</p></div><div id="sources" class="sources"></div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">FORMULA ORGAN</div><h2>Math with limits.</h2></div><p>Formula status and non-authority are visible. Checked computation never upgrades Lambda uniqueness beyond Conjecture 1.</p></div><div class="formula-grid">@@FORMULAS@@</div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">RECEIPT TAPE</div><h2>Proof of this pass.</h2></div><p>Receipts establish source bytes, normalization identity, and observation time. They do not prove every property of the world.</p></div><div id="receipts" class="grid"><article class="receipt"><span>NO RECEIPTS</span><strong>Run a live observation.</strong></article></div></section>
<section class="boundary"><strong>Operational boundary.</strong> PURIQ is research and review infrastructure. Trading, wallet connections, custody, personalized investment advice, and unattended effectors are disabled. Hatun may return <code>REVIEW</code> or <code>ABSTAIN</code> only. External data can be delayed, incomplete, revised, or unavailable.</section>
<footer class="mono"><span>PURIQ MARKET CHAMBER · VERSION @@VERSION@@</span><span>SECOND BRAIN: HASHED SESSION RECEIPTS</span><span><a href="/healthz">HEALTH</a></span></footer></main>
<script>
(function(){
 const $=function(id){return document.getElementById(id)};
 const sessionKey='szl-puriq-session-v2';
 let session=sessionStorage.getItem(sessionKey);
 if(!session){const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);session=Array.from(bytes,function(b){return b.toString(16).padStart(2,'0')}).join('');sessionStorage.setItem(sessionKey,session)}
 const safe=function(value){return value===null||value===undefined?'UNAVAILABLE':String(value)};
 const money=function(value){const n=Number(value);return Number.isFinite(n)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n):'UNAVAILABLE'};
 const pct=function(value){const n=Number(value);return Number.isFinite(n)?(n*100).toFixed(1)+'%':'UNAVAILABLE'};
 const node=function(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el};
 function renderSources(brief){const root=$('sources');root.replaceChildren();const observations=brief.observations||{};const receipts=brief.receipts||{};['polymarket','sec','treasury','coinbase'].forEach(function(id){const card=node('article','source');card.append(node('span','',id.toUpperCase()));card.append(node('strong','',observations[id]&&observations[id].state==='UNAVAILABLE'?'UNAVAILABLE':'OBSERVED'));card.append(node('small','',receipts[id]?'receipt '+receipts[id].receipt_id.slice(0,12):'No receipt closed'));root.append(card)})}
 function renderMarkets(brief){const root=$('markets');root.replaceChildren();const rows=brief.observations&&brief.observations.polymarket?brief.observations.polymarket.markets||[]:[];if(!rows.length){const card=node('article','market');card.append(node('span','','UNAVAILABLE'));card.append(node('h3','','No current market rows were observed.'));root.append(card);return}rows.forEach(function(m){const card=node('article','market');card.append(node('span','',m.active&&!m.closed?'ACTIVE PUBLIC MARKET':'MARKET RECORD'));card.append(node('h3','',safe(m.question)));card.append(node('div','prob',pct(m.yes_probability)));const bar=node('div','bar');const fill=node('i');fill.style.width=Math.max(0,Math.min(100,Number(m.yes_probability||0)*100))+'%';bar.append(fill);card.append(bar);const dl=node('dl');[['Entropy',m.binary_entropy],['24h volume',money(m.volume_24h)],['Liquidity',money(m.liquidity)],['Spread',m.spread],['Data quality',m.liquidity_quality?m.liquidity_quality.score:null]].forEach(function(pair){dl.append(node('dt','',pair[0]));dl.append(node('dd','',safe(pair[1]))});card.append(dl);if(m.market_url){const a=node('a','','Open public market');a.href=m.market_url;a.target='_blank';a.rel='noopener noreferrer';card.append(a)}root.append(card)})}
 function renderReceipts(brief){const root=$('receipts');root.replaceChildren();const entries=Object.entries(brief.receipts||{});if(!entries.length){const card=node('article','receipt');card.append(node('span','','NO RECEIPTS'));card.append(node('strong','','All sources unavailable.'));root.append(card);return}entries.forEach(function(entry){const id=entry[0],r=entry[1];const card=node('article','receipt');card.append(node('span','',id.toUpperCase()));card.append(node('strong','',r.receipt_id.slice(0,16)));card.append(node('small','',new Date(r.observed_at*1000).toISOString()+' · '+r.truth_label));root.append(card)})}
 async function run(){const button=$('run');button.disabled=true;$('status').textContent='Observing fixed public sources and closing receipts…';$('status').classList.remove('error');const params=new URLSearchParams({market_limit:$('marketLimit').value,cik:$('cik').value,crypto_base:$('cryptoBase').value,crypto_currency:$('cryptoCurrency').value});try{const response=await fetch('/api/puriq/v1/brief?'+params.toString(),{headers:{'X-SZL-Session':session,'Accept':'application/json'},cache:'no-store'});const body=await response.json();if(!response.ok)throw new Error(body.detail||('HTTP '+response.status));$('sourcesObserved').textContent=safe(body.source_summary&&body.source_summary.observed)+'/'+safe(body.source_summary&&body.source_summary.total);$('marketsReturned').textContent=safe(body.observations&&body.observations.polymarket&&body.observations.polymarket.returned);$('spotPrice').textContent=money(body.observations&&body.observations.coinbase&&body.observations.coinbase.amount);$('lambdaScore').textContent=safe(body.lambda_advisory&&body.lambda_advisory.score);$('coverageDial').textContent=safe(body.source_summary&&body.source_summary.observed)+'/'+safe(body.source_summary&&body.source_summary.total);$('chamberState').textContent=body.status+' · '+Object.keys(body.receipts||{}).length+' source receipts · trading disabled';renderSources(body);renderMarkets(body);renderReceipts(body);$('status').textContent=body.complete?'Required public sources observed. Review the receipt tape below.':'Chamber degraded: '+Object.keys(body.source_failures||{}).join(', ');if(!body.complete)$('status').classList.add('error')}catch(error){$('status').textContent='Observation failed closed: '+error.message;$('status').classList.add('error')}finally{button.disabled=false}}
 $('run').addEventListener('click',run);renderSources({observations:{},receipts:{}});
})();
</script></body></html>"""


def landing_page() -> str:
    build = build_info()
    revision = build["build"]["revision"]
    revision_short = revision[:12] if revision != "UNAVAILABLE" else revision
    formula_rows = "".join(
        '<article class="formula"><span>'
        + html.escape(item["id"])
        + "</span><strong>"
        + html.escape(item["name"])
        + "</strong><small>"
        + html.escape(item["status"])
        + "</small></article>"
        for item in FORMULAS
    )
    return (
        HTML_TEMPLATE.replace("@@REVISION@@", html.escape(revision_short))
        .replace("@@VERSION@@", html.escape(VERSION))
        .replace("@@FORMULAS@@", formula_rows)
    )


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(landing_page())
