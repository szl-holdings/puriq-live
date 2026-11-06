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

<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

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

Two read-only research surfaces add one fixed source each: the Evidence Market Lab (`/research`) reads completed public candles from the **Coinbase Exchange** API for BTC-USD, ETH-USD and SOL-USD, and the signed-price page (`/signed-prices`) reads **The Pulse** public Verity sample and its public key from `mcp.thepulse.markets` (see [Signed price research](#signed-price-research)).

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
GET  /research
GET  /api/puriq/v1/research?pair=BTC-USD&granularity=3600
GET  /api/puriq/v1/research/readiness
GET  /signed-prices
GET  /api/puriq/v1/signed-price?symbol=BTC
GET  /openapi.json
```

`/openapi.json` is the generated OpenAPI schema. FastAPI's `/docs` and `/redoc` pages are also served (the front door's API link opens `/docs`), but they load their scripts and styles from public CDNs that the service's own Content-Security-Policy blocks, so in a browser they render blank. The research and signed-price routes need no session header and keep nothing about the caller; the research route reuses a public candle response for at most 60 seconds from a bounded process-local cache.

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

## Signed price research

Open `/signed-prices` for manually refreshed BTC, ETH and SOL public Verity
samples. `GET /api/puriq/v1/signed-price?symbol=BTC` returns a provider record,
separate signature/freshness evidence, the review policy, and a local digest
receipt. No account or API key is needed for these three sample symbols.

PURIQ independently verifies P-256/SHA-256 signatures using `cryptography`,
checks the exact 18-field live v2 record against its signed canonical bytes,
and withholds the usable price unless both signatures, freshness and the
reported-source/grade policy pass. A missing v2 is price-only; tampering is
invalid. The provider keyring is acquired over HTTPS, not independently pinned.
The local receipt is a SHA-256 digest, not a PURIQ digital signature.
The page expires its displayed price locally and never polls or trades.

The separate offline `puriq_reference.estimate_reference` experiment compares
an equal-venue median with a median across declared source groups. It requires
explicit USD observations and a replay clock, records every exclusion, reports
descriptive MAD, and abstains below three groups. Group labels do not establish
independence. This model is not connected to the live provider as if one
provider's source-count metadata were raw exchange observations.

```sh
python puriq_reference.py
python tools/replay_reference.py observations.json --symbol BTC --now 1791392000
```

Each input row has `venue`, `symbol`, `quote` (`USD`), `price` (plain decimal
text), `observed_at` (Unix seconds), and optional `group`. The explicit replay
clock and methodology are included in the deterministic research receipt.

See [the research map](docs/SIGNED_PRICE_RESEARCH_2026-10-07.md) for developers,
GitHub repositories, primary publications, license findings, and falsifiable
research hypotheses. These additions remain read-only research and review;
they do not promote Lambda beyond Conjecture 1, assert market accuracy or
superiority, or establish a live HF deployment.

## Run locally

```bash
python -m pip install --require-hashes -r requirements.txt -r requirements-test.txt
python tools/vendor_vela.py
export PURIQ_SOURCE_REVISION="$(git rev-parse HEAD)"
python -m pytest tests -q
uvicorn app:app --host 0.0.0.0 --port 7860
```

`requirements.txt` is the hash-locked runtime closure the image installs and `requirements-test.txt` is the hash-locked pytest closure; pip checks every download against the committed SHA-256 digests. `tools/vendor_vela.py` downloads the pinned `@luxalgo/vela` 0.7.3 tarball from registry.npmjs.org, checks its SHA-512 and per-file SHA-256 pins, and writes the git-ignored `static/vendor/vela/` (it refuses to overwrite an existing directory). Without that step `/research` has no renderer, `/readyz` returns 503, and three tests fail. The suite itself needs no network access.

For an editable development install with the same direct pins: `python -m pip install -e '.[test]' -c constraints-runtime.txt`.

Container:

```bash
docker build \
  --build-arg PURIQ_SOURCE_REVISION="$(git rev-parse HEAD)" \
  -t puriq-market-chamber .
docker run --rm -p 7860:7860 puriq-market-chamber
```

The build needs PyPI and registry.npmjs.org; both of its pip installs run in hash-checking mode. `/readyz` closes only when source identity is a full observed Git SHA, the formula corpus has zero failures, and the vendored Vela files match their pinned digests.

## Verification

`.github/workflows/puriq.yml` runs on every push and pull request to `main`: `pip check`, byte-compilation, the full suite on the runner, a source-bound non-root image build, the full suite again inside that image, route and Playwright browser checks against the running container, and a strict `pip-audit` of the image's exact Python closure. CodeQL and OpenSSF Scorecard run from the organization's SHA-pinned reusable workflows.

## Truth and safety boundaries

- `MEASURED` — local contract, source identity, or deterministic computation directly observed by the runtime.
- `REPORTED` — normalized content returned by a named external authority.
- `MODELED` — explicit descriptive transform such as entropy, probability displacement, liquidity quality, or Lambda advisory score.
- `UNAVAILABLE` — source or evidence not observed; never painted green.

Trading, wallet connections, custody, personalized investment advice, and unattended effectors are disabled.

## Links

- Source: [szl-holdings/puriq-live](https://github.com/szl-holdings/puriq-live), the backend source for PURIQ Finance (authority split in `SOURCE_PIN.md`).
- Canonical Hugging Face projection: [SZLHOLDINGS/finance](https://huggingface.co/spaces/SZLHOLDINGS/finance), published from `szl-holdings/a11oy` by `.github/workflows/hf-publish-vertical-flagships.yml`. This repository publishes no Space, and a revision here is not proof that the Space runs it.
- As of 2026-11-06, `szl-holdings/a11oy` also embeds `puriq_verity.py` and `puriq_reference.py` from this repository, pinned by SHA-256 in `verticals/puriq-markets/runtime/components/puriq_verity/source.json`; change those files together with that pin.
- Hugging Face organization: estate models, datasets and Spaces are published under [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS).
- Product: [a-11-oy.com](https://a-11-oy.com) · Proof registry: [a11oy.net](https://a11oy.net)

## Author

Stephen P. Lutar Jr. · SZL Holdings · ORCID `0009-0001-0110-4173`

Apache-2.0. See `NOTICE` and `CITATION.cff`.
