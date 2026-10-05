# PURIQ dependency coherence repair — 2026-10-05

## Source and demonstrated failure

This proposal derives from PR #25, exact source `51fb50de0d14b8184697e7c194facb64be2de657`. Hosted job `111757370020` failed resolution: Pydantic 2.13.5 requires exactly pydantic-core 2.46.5, while the grouped update constrained 2.49.0. PyPI parent metadata confirms that exact requirement.

## Repair

Retain the reviewed FastAPI 0.142.2, python-dotenv 1.2.4 and uvloop 0.23.0 updates; restore the core version required by the unchanged Pydantic parent. Pin FastAPI's new opentelemetry-api runtime dependency to the observed 1.45.0 closure. Update the installed-version security regression witness to the actual upgraded FastAPI version. Constraint provenance now distinguishes the previous production observation from this unqualified update.

## Local observations

In a fresh isolated Python 3.12.14 environment, install of runtime plus test requirements completed successfully. `python -m pip check` passed. The unchanged vendor tool acquired and authenticated the exact Vela 0.7.3 archive and browser assets. With the source revision supplied, `python -m pytest tests -q` passed all 98 tests. Static range behavior, traversal denial and the explicit installed patched-framework witness remain enforced. One upstream Starlette deprecation warning remains.

The initial local run intentionally exposed the stale version witness and absent vendor assets (4 failed, 94 passed); after updating the witness and running the existing verified asset acquisition, the complete suite passed. No failing test was skipped or weakened.

## Qualification limits

Local Python is 3.12.14; hosted/image policy uses 3.12.13. Docker/image/browser qualification and the strict actual-container vulnerability audit are not locally verified. This proposal requires fresh hosted checks, including those unchanged gates. API-created commits are unsigned; this receipt is not a signed release, production rollout or live market-data witness.
