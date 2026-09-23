# Source authority — PURIQ Finance

This repository is the **backend source** for the PURIQ Finance public body. It owns the read-only market-intelligence runtime implemented here; it does **not** own the shared formula registry, the A11oy presentation layer, or Hugging Face publication authority.

The current estate contract is `szl-holdings/.github/estate/alignment.v1.json`. The local `SZL_ESTATE_BINDING.json` mirrors the fields relevant to this repository.

| Field | Current authority |
| --- | --- |
| backend source | `szl-holdings/puriq-live` |
| formula authority | `szl-holdings/szl-formulas` |
| governed fabric | `szl-holdings/a11oy` |
| presentation source | `szl-holdings/a11oy:verticals/finance` |
| canonical Hub surface | `SZLHOLDINGS/finance` |
| Hub publisher | `szl-holdings/a11oy:.github/workflows/hf-publish-vertical-flagships.yml` |
| public product origin | `https://a-11-oy.com` |
| proof / evaluation registry | `https://a11oy.net` |
| Λ | Conjecture 1 / advisory only |

`puriq-live` must not publish a competing Hub Space or redefine shared formula IDs. A source-qualified GitHub revision is not proof that the Hugging Face projection, product runtime, or proof registry has been promoted. Those stages require their own exact-revision publication and readback evidence.

The runtime remains read-only: no wallet connection, custody, order placement, autonomous trading, or personalized investment advice.
