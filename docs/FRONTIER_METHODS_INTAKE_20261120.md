# PURIQ frontier methods: research intake and safety boundaries

**State:** source-only integration map; no deployed feature or live trading.
**Source anchor:** `szl-holdings/puriq-live/main@be6ae6fb490c842c0dd9074757315e7180773a44`.
**Evidence date:** 2026-11-20 UTC. This note documents public research and the
exact-source binary-quote negative control, not an independently reviewed performance claim.

## Three research inputs from the owner-supplied screenshots

1. **Causal multi-asset workstation / Public API post.** The screenshots describe
   higher-timeframe causal regime checks, a 60-second passive-limit loop,
   preflight leases for SPXW options, server-side risk controls and round-trip
   attribution. The illustrated screen and text are a *third-party claim*, not an
   SZL implementation or audited profitable strategy. Official public docs:
   https://public.com/api/docs and https://public.com/api .
   The API supports orders, but those endpoints and broker-account data are
   **out of PURIQ scope**. Its Individual API has non-commercial use limitations.
   Adapt only event-time discipline, instrument/quote integrity, latency bounds,
   reconciliation and negative controls in read-only research or mocks.

2. **Rhino.ai social card / low-cost writer and frozen reader.** The image claims
   a 1.7B writer, a 27B frozen reader, 12 x 65,536 engram tables and
   **more than 15x** lower fine-tuning cost. This is *unverified marketing
   evidence*, not an SZL benchmark, model authorization or reproduced result.
   A research baseline is DeepSeek's *Conditional Memory via Scalable Lookup*
   (arXiv:2601.07372, https://github.com/deepseek-ai/Engram).
   Evaluate memory lookup vs independent retrieval/LoRA against locked data
   rights, stable train/holdout splits, total GPU hours, host memory, inference
   latency, model quality and an equal-quality cost denominator. Source demo
   code, model licenses and published performance are distinct.

3. **Google Research PaperOrchestra** (arXiv:2604.05018,
   https://github.com/google-research/paper-orchestra, Apache-2.0).
   The photographed paper describes outline, literature, section writing,
   plotting and refinement agents. Its authors report improvements on a
   benchmark derived from 200 papers; this is *their* evaluation, not ours.
   Adapt the separation of roles, citation verification and plot provenance,
   but never allow a model to synthesize missing experiment results, sign its
   own receipt or represent an unverified manuscript as peer-reviewed.

## Existing SZL ownership — no duplicate vertical authority

| Surface | Appropriate next independent admission |
| --- | --- |
| **PURIQ horizontal formula/governance capability** | Consume the canonical PurIQ formula and Yuyay receipts; preserve Λ as Conjecture 1. |
| **puriq-live** | Read-only Polymarket, SEC, Treasury and Coinbase observations; enforce source/query/time pins and quote completeness; market metrics remain descriptive only. |
| **A11oy / finance** | Project the source-pinned public observations into finance and research tabs with explicit MEASURED / REPORTED / MODELED / UNAVAILABLE indicators; no fabricated live stream. |
| **Killinchu** | Consume attested PurIQ receipt handles as typed inputs to its existing safety gates; **do not** import financial order effectors or reimplement the corpus. |
| **Hatun** | Independent advisory REVIEW / ABSTAIN and provenance; no LLM-generated approval or production action. |
| **Future robotics / other verticals** | Reuse the *boundary pattern* (event time, actor, asset, lease, signer, rights, human authority); require separate evidence schemas, benchmarks and safety review. |

The canonical Hugging Face finance projection is `SZLHOLDINGS/finance`,
published through A11oy's reviewed workflow. A passing source test does not
establish that the Space runs this source or that A11oy/Cloudflare/PyPI is aligned.

## Exact-source negative control in this branch

A Yes/No Polymarket record previously accepted `Yes=0.6` as a valid derived
binary probability while the complementary No price was malformed. Because
binary entropy and probability displacement depend on `yes_probability`,
that incomplete pair could produce plausible-looking modeled signals.

A complete binary observation requires the *two* aligned Yes and No prices
to be individually finite, non-boolean and in the `[0,1]` domain.
If either is invalid, retain individually valid source fields, mark
`INVALID_OUTCOME_OR_PRICE` and `INCOMPLETE_BINARY_OUTCOME_PRICE`, and leave
`yes_probability`, entropy and displacement `null`. Do **not** infer
No as `1 - Yes`. The two market prices need not sum exactly to 1 because
provider quoting semantics and rounding have not been independently authenticated.

Regression tests include seven malformed complementary prices, an actual
zero-price complement, reversed label order and a reversed invalid complement.
They are synthetic tests; neither model assertions nor their agreement are a
signer, venue feed, return forecast or production release receipt.

## Bounded follow-on execution criteria

- **Paper research**: pin raw evidence, search/index identifiers, bibliography
  verification, experiment results and figure-generating code; include an
  unsupported-claim and missing-figure refusal, and require human authorship
  review and explicit usage rights.
- **Conditional memory**: keep lookup artifacts out of inference authority until
  rights-cleared train/holdout isolation, reproducible baseline, device budget
  and independently measured downstream quality are available. No 15x claim.
- **Trading research**: maintain fixed publicly licensed sources and completed
  candle timing; no broker credentials, orders, custody, paper-to-live switch,
  or unattended actuator in PURIQ. Future trading software requires a separate
  licensed account-owner and risk-control process.
- **Production rollout**: separate source/CI, exact HF revision, app/API canary,
  route/paywall behavior, Cloudflare settlement, provenance, rollback and
  operator admission. A HTTP 200, signed-but-untrusted hash or green CI alone
  does not prove the product operational.

**No third-party implementation code copied.** Research linked for attribution;
upstream license, model weights and market-data redistribution permissions
require review before any software reuse or public dataset publication.
