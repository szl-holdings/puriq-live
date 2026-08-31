# PURIQ Live


## Packet 8 source pin

Puriq Markets product logic lives in canonical [`szl-holdings/a11oy/verticals/puriq-markets`](https://github.com/szl-holdings/a11oy/tree/main/verticals/puriq-markets).

- Kernel: [`verticals/_kernel/a11oy_kernel.py`](https://github.com/szl-holdings/a11oy/blob/main/verticals/_kernel/a11oy_kernel.py)
- Hugging Face Space `SZLHOLDINGS/puriq-markets` — **ROADMAP, not yet created** (no public or private Space exists today; verified 2026-08-30)
- This repo is a generated thin adapter. See [`SOURCE_PIN.md`](SOURCE_PIN.md).
- Formula authority: **NONE**. Models, formulas and market signals never authorize.
- Canonical land PR: [szl-holdings/a11oy#1438](https://github.com/szl-holdings/a11oy/pull/1438)
- Canonical land SHA: [`2b67b63624a3f4bf35787cfa5260d7960f1a76d5`](https://github.com/szl-holdings/a11oy/commit/2b67b63624a3f4bf35787cfa5260d7960f1a76d5)


Execute the SZL formula corpus against **live public signals**. No simulated Λ.

**Λ uniqueness is Conjecture 1.** CHECKED never upgrades a conjecture.

| Aggregator | Meaning |
| --- | --- |
| Symmetric Λ | Uniform 1/13 weights. Satisfies A5 (permutation invariance). |
| Egyptian Λ | Horus-Eye 1/2+…+1/64 = 63/64, remainder on leftover axes. Anchored — Theorem U regime. |
| maxAgg | Live counterexample: same 13-axis vector, different score. Unconditional uniqueness is OPEN and false as stated. |

Locked-8 (lutar-lean kernel `c7c0ba17`): `{F1, F4, F7, F11, F12, F18, F19, F22}`.

Doctrine v11 LOCKED · 749 / 14 / 163 · Apache-2.0.

## Run

```bash
python3 tests/test_puriq.py
python3 -c "from szl_puriq import execute_corpus; print(execute_corpus()['tallies'])"
```

Hugging Face Space entrypoint: `app.py` (Gradio). The `SZLHOLDINGS/puriq-live` Space is **ROADMAP, not yet created** (verified 2026-08-30) — this repo is the source that will publish to it.

## Live feeds (fail closed)

GitHub `szl-holdings` · Hugging Face `SZLHOLDINGS` · a-11-oy.com honest/genome/ledger/mesh/readiness · USGS earthquakes · Open-Meteo NYC · ISS · NYC PLUTO · CISA KEV.

A missing feed is **UNAVAILABLE**, never painted green.

## Author

Stephen P. Lutar Jr. · SZL Holdings · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

Thesis concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) · Lean [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308)

[a-11-oy.com](https://a-11-oy.com) · [huggingface.co/SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS)
