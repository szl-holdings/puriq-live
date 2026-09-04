---
title: PURIQ Market Chamber
emoji: 🔮
colorFrom: purple
colorTo: yellow
sdk: docker
app_port: 7860
license: apache-2.0
short_description: Receipted public-market intelligence with no trading path
tags:
  - finance
  - prediction-markets
  - sec-edgar
  - market-intelligence
  - observability
  - governed-ai
---

# PURIQ Market Chamber

PURIQ is SZL Holdings' source-bound, read-only market-intelligence surface. It observes public prediction-market quotes, SEC filings, U.S. Treasury rates, and public crypto spot references; applies explicit descriptive formulas; stores bounded receipt handles under a hashed caller session; and produces non-authorizing Hatun review envelopes.

**PURIQ contains no wallet connection, custody, account, order, or trading endpoint.** It does not provide personalized investment advice. External observations can be delayed, incomplete, revised, or unavailable.

## Product contract

| Layer | Operational behavior |
| --- | --- |
| Public front door | Original PURIQ probability-orbit interface; responsive, keyboard visible, reduced-motion aware, and forced-colors compatible |
| Sense | Fixed HTTPS sources only; no caller-supplied URLs, redirects, or unbounded response bodies |
| Normalize | Strict numeric and schema normalization with explicit `UNAVAILABLE` degradation |
| Formula | Locked-8 maturity context, binary entropy, probability displacement, liquidity data-quality scoring, and Lambda advisory roll-up |
| Second Brain | Bounded process-memory receipt handles keyed by SHA-256 of a caller-held session token |
| Hatun | `REVIEW` or `ABSTAIN` only; evidence receipts must already exist in the same caller session |
| Proof | Source-byte digest, normalized-observation digest, source URL, observation time, expiry, and deterministic receipt ID |
| Effectors | Disabled |

## Fixed public authorities

- **Polymarket Gamma API** — active public market discovery and quoted outcome prices; public read-only mode.
- **U.S. Securities and Exchange Commission** — EDGAR submissions by CIK.
- **U.S. Department of the Treasury FiscalData** — average interest rates on Treasury securities.
- **Coinbase public prices API** — allowlisted public spot references.

A failed source stays `UNAVAILABLE`; it is never replaced with fabricated or unlabeled sample data.

## API

```text
GET  /
GET  /healthz
GET  /readyz
GET  /api/build-info
GET  /.well-known/szl-source.json
GET  /api/puriq/v1/anatomy
GET  /api/puriq/v1/formulas
GET  /api/puriq/v1/sources
GET  /api/puriq/v1/markets
GET  /api/puriq/v1/brief
GET  /api/puriq/v1/second-brain
POST /api/puriq/v1/hatun/evaluate
```

Stateful routes require a high-entropy `X-SZL-Session` header. The raw token is never recorded; only its SHA-256 scope is used internally.

### Observe the chamber

```bash
SESSION="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

curl -sS \
  -H "X-SZL-Session: ${SESSION}" \
  'http://127.0.0.1:7860/api/puriq/v1/brief?market_limit=12&cik=320193&crypto_base=BTC&crypto_currency=USD'
```

### Ask Hatun for review

First observe one or more sources, then pass receipt IDs from the same session:

```bash
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -H "X-SZL-Session: ${SESSION}" \
  http://127.0.0.1:7860/api/puriq/v1/hatun/evaluate \
  -d '{
    "intent": "review a public market evidence brief",
    "requested_action": "market.review",
    "axes": {"evidence": 0.95, "freshness": 0.90, "reversibility": 0.97},
    "evidence_receipt_ids": ["<64-lowercase-hex-receipt-id>"]
  }'
```

Hatun cannot authorize or execute. Lambda remains **Conjecture 1** and advisory only.

## Formula authority

The existing `szl_puriq.py` corpus remains intact and must report zero `FAILED` entries. Locked-proven identity remains exactly:

```text
F1, F4, F7, F11, F12, F18, F19, F22
```

The Market Chamber adds descriptive runtime transforms:

- binary Shannon entropy for a quoted binary probability;
- displacement from an explicit reference probability;
- transparent spread/liquidity/volume data-quality scoring;
- source-coverage Lambda advisory roll-up.

These formulas can organize review. They cannot establish guaranteed outcomes, fair value, expected return, or autonomous authority.

## Living Anatomy

PURIQ follows the nine-organ operating contract:

```text
Sense → Normalize → Context → Formula → Policy → Decide → Verify → Remember → Receipt
```

The shared six-vertical fabric lives in `szl-holdings/vertical-services`; PURIQ is its dedicated finance-facing product surface. The shared fabric resolves the aliases `puriq` and `markets` to its canonical `finance` runtime, avoiding duplicate authority.

## Run locally

```bash
python -m pip install -r requirements.txt -r requirements-test.txt
export PURIQ_SOURCE_REVISION=0000000000000000000000000000000000000000
python -m pytest tests -q
uvicorn app:app --host 0.0.0.0 --port 7860
```

Container:

```bash
docker build \
  --build-arg PURIQ_SOURCE_REVISION="$(git rev-parse HEAD)" \
  -t puriq-market-chamber .
docker run --rm -p 7860:7860 puriq-market-chamber
```

`/readyz` closes only when source identity is a full observed Git SHA and the formula corpus has zero failures.

## Truth and safety boundaries

- `MEASURED` — local contract, source identity, or deterministic computation directly observed by the runtime.
- `REPORTED` — normalized content returned by a named external authority.
- `MODELED` — explicit descriptive transform such as entropy, probability displacement, liquidity quality, or Lambda advisory score.
- `UNAVAILABLE` — source or evidence not observed; never painted green.

Trading, wallet connections, custody, personalized investment advice, and unattended effectors are disabled.

## Author

Stephen P. Lutar Jr. · SZL Holdings · ORCID `0009-0001-0110-4173`

Apache-2.0. See `NOTICE` and `CITATION.cff`.
