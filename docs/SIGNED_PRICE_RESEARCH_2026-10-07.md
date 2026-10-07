# Signed market data: research and PURIQ build direction

Research date: **October 7, 2026**. Scope: selected primary publications, official documentation, public repositories, and the Pulse Verity sample observed during this work. This is a focused engineering review, not an exhaustive web survey, audited vendor ranking, or demonstration of a new pricing theorem.

The practical opportunity is a reproducible evidence and risk layer: authenticate what a provider actually signed, preserve its provenance, compare compatible observations, quantify disagreement, and abstain when evidence is insufficient. A valid signature establishes message authenticity relative to a trusted key. It does not establish correct economics, independent venues, executable liquidity, calibrated confidence, or permission to redistribute data.

## What the supplied material actually establishes

The screenshots concern Pulse Verity. The pictured BTC value **83,461.53** and “33 exchanges” belong to that marketing material; neither is a current market observation. Only the first name **Justin** was verified; no surname, employer biography, or GitHub identity is inferred.

The public [PulseBet/pulse-verity client repository](https://github.com/PulseBet/pulse-verity/tree/a2921897f220a25e3733b9bddf6bcfe79a0f6171) was inspected at commit `a2921897f220a25e3733b9bddf6bcfe79a0f6171`. Its MIT-licensed client material does not expose the pricing engine. Studying the verifier is not an engine audit.

The run fetched the [public key/schema](https://mcp.thepulse.markets/api/index/v1/pubkey) and [BTC sample](https://mcp.thepulse.markets/api/index/v1/sample?symbol=BTC). The observed print timestamp was `2026-10-07T16:48:45.646Z`; it reported 35 sources. That count is a provider assertion, not independently established venue diversity.

The observed v1 format covers symbol, exact price text, timestamp, and grade. The observed v2 index format covers **18 fields**, including engine, source count, confidence, dispersion, interval, and cadence. Verification must authenticate the exact supplied canonical UTF-8 bytes and compare every expected canonical field with the response. Checking the signature while displaying unchecked outer JSON is insufficient. The declared P-256/SHA-256 signature encoding is IEEE-P1363, not DER. Archived prints have different quality/cadence coverage; older records can lack recorded quality. Preserve endpoint, schema version, key ID, signed-field coverage, and raw bytes. Fail closed on an unsupported schema instead of extending trust by assumption.

## Research map

These twelve entries cover complementary engineering problems. Named people below are authors or publicly identified contributors, not a complete maintainer census.

| Project / people | Primary publication or documentation | Code and lesson |
| --- | --- | --- |
| Pulse Verity / PulseBet; Justin, first name only | [Developer documentation](https://thepulse.markets/developers), public schema above | [Pinned client](https://github.com/PulseBet/pulse-verity/tree/a2921897f220a25e3733b9bddf6bcfe79a0f6171): distinguish signed coverage from unsigned envelope fields; engine unavailable. |
| Chainlink Labs / Lorenz Breidenbach, Christian Cachin, Alex Coventry and OCR3 coauthors | [OCR 3.0, May 2025](https://research.chain.link/ocr3.pdf) | [libocr](https://github.com/smartcontractkit/libocr): BFT observation, outcome, report, and quorum-attestation lifecycle. |
| Pyth / Douro Labs; Mike Cahill, Jayant Krishnamurthy, Ciaran Cronin | [Current Pro architecture](https://docs.pyth.network/price-feeds/pro/how-lazer-works); [contributor history](https://www.pyth.network/blog/where-pyth-is-now-q3-2023) | [pyth-crosschain](https://github.com/pyth-network/pyth-crosschain): publisher data, median/IQR, staleness handling, SDKs. |
| RedStone / Jakub Wojciechowski, Marcin Kazmierczak, Alex Suvorov | [Team](https://www.redstone.finance/team); [AVS components](https://docs.redstone.finance/docs/network-tokenomics/restaking-avs/service-components/) | [Monorepo](https://github.com/redstone-finance/redstone-oracles-monorepo): signed packages, signer thresholds, timestamps, median, separate transport. |
| Chronicle / Niklas Kunkel and Chronicle developers | [Scribe specification](https://github.com/chronicleprotocol/scribe/blob/main/docs/Scribe.md); [founder interview](https://chroniclelabs.org/blog/the-importance-of-data-verifiability-an-interview-with-the-founder-of-chronicle-protocol-niklas) | [Scribe](https://github.com/chronicleprotocol/scribe): Schnorr multisignatures over value/age and explicit validator assumptions. |
| API3 / Burak Benligiray, Saša Milić, Heikki Vanttinen | [Whitepaper](https://old-docs.api3.org/api3-whitepaper-v1.0.3.pdf); [current feeds](https://docs.api3.org/oev/in-depth/data-feeds/) | [signed-api](https://github.com/api3dao/signed-api), [contracts](https://github.com/api3dao/contracts): provider signatures and onchain aggregation. |
| CME CF / Andrew Paine, William J. Knottenbelt; CF Benchmarks | [2016 analysis](https://www.cmegroup.com/trading/files/bitcoin-white-paper.pdf); [methodology v17.4, August 2026](https://docs.cfbenchmarks.com/CME%20CF%20Reference%20Rates%20Methodology.pdf) | Methodology reference: volume-weighted medians within time partitions, then equal partition averaging; explicit contingency rules. |
| Coin Metrics research and engineering | [Published prices methodology](https://github.com/coinmetrics/docs-website/blob/master/market-data/methodologies/coin-metrics-prices-methodology.md?plain=1) | Reference-rate timing, currency conversion, missing-data rules, and real-time weighting are distinct design decisions. |
| Kaiko Indices team | [ETF rates methodology overview](https://www.kaiko.com/indices/reference-rates/etf-rates) | Volume-weighted medians followed by recency-weighted time averaging; benchmark construction reference, not reusable engine code. |
| Gábor Lugosi / Shahar Mendelson | [Heavy-tailed estimation survey](https://arxiv.org/abs/1906.04280); [trimmed-mean paper](https://arxiv.org/abs/1907.11391) | Mathematical starting points for robust estimation; assumptions must be restated for asynchronous, dependent financial observations. |
| CCXT contributors | [Repository and manual](https://github.com/ccxt/ccxt) | Multi-exchange normalization reference. Restrict any integration to public observations; library capability is broader than PURIQ authority. |
| Cryptofeed / bmoscon and contributors | [Repository](https://github.com/bmoscon/cryptofeed); [current license](https://github.com/bmoscon/cryptofeed/blob/master/LICENSE) | Streaming exchange adapters; inspect event semantics and licensing before reuse. |

## Current architecture and license findings

Avoid outdated Pyth descriptions: its [current Core notice](https://docs.pyth.network/price-feeds/core/how-pyth-works) says Pythnet is shutting down and directs readers to Pro. Pro is documented as permissioned, with a Douro-operated relayer. The [August 26 upgrade](https://docs.pyth.network/price-feeds/core/upgrade/preparing) introduced required Hermes API-key authentication. Its 50/200/1000 ms channels do not guarantee end-to-end execution latency.

Chainlink separates data-source, node, and network aggregation. API3 documents onchain provider-feed medians alongside technical-team multisig control of upgrades and source configuration. RedStone's AVS verifies calculations offchain and submits BLS attestations. Chronicle's Scribe specification warns that adequate rogue-key protection depends on its external ValidatorRegistry. None of these details can be reduced to a single decentralization score.

Verified repository-level licenses: libocr, API3 signed-api/contracts, and CCXT show MIT; Pyth crosschain's root license shows Apache-2.0. RedStone's current monorepo is BUSL-1.1, with restricted production reuse. Scribe's [license](https://github.com/chronicleprotocol/scribe/blob/main/LICENSE) specifies a September 12, 2026 change date and MIT change license: the retrieved version appears past that date, although its README retains BUSL wording. Cryptofeed's current license is AGPL, not the permissive license sometimes recalled from earlier versions. Pin exact versions, examine file-level exceptions and dependencies, and preserve notices. Code licenses do not supply market-data redistribution rights or service access.

## Prioritized reading and implementation

1. Read Pulse's observed key/schema response beside its pinned client. Write failure tests for altered outer fields, missing signed fields, wrong key, wrong encoding, and schema changes.
2. Read CME CF and Coin Metrics methodology before tuning an estimator. Define instrument, time window, eligible observations, and late/missing-data treatment first.
3. Read OCR3, API3 Signed APIs, and Scribe for the separation between source trust, agreement, signature verification, and delivery.
4. Read Pyth's current architecture and integration practices for uncertainty and staleness; compare RedStone's package/transport design.
5. Use robust-estimation papers to formulate falsifiable experiments. Their statistical guarantees do not automatically transfer to correlated exchange feeds.

## Proposed PURIQ architecture

**Sense:** fixed, allowlisted public adapters with bounded responses, timeouts, and rate limits. Record provider event time and local receive time separately. A provider-signed aggregate is one provider observation; it does not become 35 independently observed exchange records because its metadata says 35.

**Normalize and verify:** retain exact source bytes, canonical bytes, signature, key fingerprint, schema, symbol, quote currency, instrument type, and provenance. Reject nonfinite values, ambiguous units, unsupported schemas, and contradictory signed/unsigned fields. Keep USD, USDT, USDC, spot, perpetual, last trade, and midpoint distinct until an explicit conversion or comparison rule applies. Fetching a key from the same provider establishes a bootstrap dependency; define pinning, rotation, and revocation separately.

**Context and formula:** attach signed-field coverage and separate local verification facts from provider quality claims. Apply staleness and adequacy gates before aggregation. Emit a modeled estimate with input IDs, exclusions, method/version, dispersion, and declared grouping assumptions.

**Policy and receipt:** preserve PURIQ's `MEASURED`, `REPORTED`, `MODELED`, and `UNAVAILABLE` distinctions. Invalid evidence cannot become a green result. Hatun remains `REVIEW`/`ABSTAIN`; Lambda remains Conjecture 1 and advisory. Hashes commit bytes, not truth. [JCS](https://www.rfc-editor.org/rfc/rfc8785) informs any new canonical envelope; [RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html) informs future inclusion/consistency proofs. Neither replaces the provider's existing signing format.

## Mathematical hypotheses, not performance claims

Start with eligible observations `E(t)` selected using only information received by decision time `t`. Baseline `m(t)` is their median. Report dispersion in basis points, for example `10,000 × median(|p_i − m|) / m`, with a positive-price precondition. This is descriptive cross-source spread, not automatically a probabilistic confidence interval.

**H1 — declared-group aggregation:** compute a median within each documented dependency group, then an equal-weight median across group medians. Hypothesis: this reduces domination by duplicated or related feeds. Compare with the ordinary venue median. Group labels are assumptions requiring evidence; they do not prove independence, and a wrongly merged group can discard useful information.

**H2 — constrained quality weights:** compare uniform weights with capped weights derived from historical availability, age, and documented liquidity. Tune exclusively on past data. A reported volume can be misleading; inverse-variance weighting can overreward a stale, unnaturally quiet feed. Evaluate these failure modes explicitly.

**H3 — selective abstention:** require adequate fresh coverage and bounded disagreement, returning unavailable otherwise. Hypothesis: error conditional on publication improves, with an explicitly measured availability cost. Do not improve an error headline by silently dropping difficult periods.

Use deterministic decimal arithmetic and explicit tie/rounding rules. Keep these candidate experiments outside shared “proven” formula identities until admitted through `szl-formulas`.

## Walk-forward evaluation

Use chronological training, validation, and untouched test windows, followed by rolling evaluation. Hold out venues and volatility/outage regimes. Define when each benchmark was actually available: Coin Metrics' published daily/hourly methodology includes a 61-minute window ending one minute after its nominal calculation time. Treating that finalized value as contemporaneously available would introduce look-ahead.

Report median/p95 absolute basis-point deviation from a named reference, response lag, stale acceptance, publication availability, abstention rate, source/group concentration, signature rejection correctness, and exact replay agreement. A reference is a comparison target, not unquestionable ground truth. Report uncertainty using time-aware resampling rather than pretending ticks are independent.

Stress tests should include missing venues, delayed and reordered records, duplicated observations, manipulated outliers, correlated group failures, stablecoin depegs, clock skew, and signature/field tampering. Measure both published errors and suppressed outputs. Archive input hashes, configuration, code revision, exclusions, benchmark availability times, and results. No return, superiority, or frontier claim follows from passing unit tests or a single live sample.

## Finance roadmap and concrete blockers

**Now:** land the read-only verifier, source receipts, explicit signed-field labels, offline estimator, and negative-path tests in `puriq-live`. The observed baseline is `2809f84acc002fced84df6809af0a1e9eee50f97`; compare changes against that revision. This report defines the research direction; test results and promotion status need their own receipts.

**Next:** collect a licensed, timestamped observation corpus; preregister baselines and metrics; run the walk-forward study; publish results and counterexamples. Add provider adapters only when authentication, access terms, rate limits, key lifecycle, and schema handling are concrete.

**Then:** propose any successful formula changes to `szl-holdings/szl-formulas`; project the admitted behavior through `szl-holdings/a11oy:verticals/finance` to canonical `SZLHOLDINGS/finance`. `SOURCE_PIN.md` and `SZL_ESTATE_BINDING.json` distinguish backend, formula, presentation, and publication authorities. A Git commit does not establish that a product or Hub projection is live.

Outstanding blockers are the unavailable Pulse engine/raw constituent audit trail, unverified source-dependency relationships, absent benchmark corpus/results, provider data-use terms, key-rotation policy, and exact-revision deployment evidence. Production admission requires the estate's provenance approval and receipt. The current product remains market intelligence: no wallet, custody, order placement, or autonomous capital allocation is introduced by this research.
