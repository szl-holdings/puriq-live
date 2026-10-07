"""Meaningful offline checks for the modeled reference estimator."""
from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import json

import pytest

from puriq_reference import estimate_reference, synthetic_demo


def row(venue, price="100", **changes):
    return {"venue": venue, "symbol": "BTC-USD", "quote": "USD",
            "price": price, "observed_at": 1000, **changes}


def estimate(rows, **kwargs):
    return estimate_reference(rows, symbol="BTC-USD", now=1000, **kwargs)


def reasons(result):
    return {reason for item in result["receipt"]["rejected"] for reason in item["reasons"]}


def test_one_extreme_price_does_not_dominate_group_median():
    result = estimate([row("a", "99"), row("b", "100"), row("c", "101"), row("d", "99999999")])
    assert result["reference_price_usd"] == "100.5"
    assert Decimal("99") < Decimal(result["group_mad_bps"]) < Decimal("100")
    assert result["truth_label"] == "MODELED"
    assert result["trading_enabled"] is False


def test_correlated_venue_replication_does_not_add_group_weight():
    independent = [row("a", "99"), row("b", "100"), row("c", "101")]
    one = estimate(independent + [row("replica-0", "1000", group="shared")])
    many = estimate(independent + [row(f"replica-{i}", "1000", group="shared") for i in range(7)])
    assert one["reference_price_usd"] == many["reference_price_usd"] == "100.5"
    assert one["effective_groups"] == many["effective_groups"] == 4
    assert many["venue_median_usd"] == "1000"
    assert many["group_independence_verified"] is False


def test_duplicate_venue_rejects_all_occurrences_without_selecting_favorable_row():
    result = estimate([row("A", "99"), row("a", "1000", observed_at=900), row("b"), row("c")])
    assert result["state"] == "ABSTAIN" and result["reference_price_usd"] is None
    assert result["accepted_venues"] == 2 and result["rejected_observations"] == 2
    assert reasons(result) == {"DUPLICATE_VENUE", "STALE_OBSERVATION"}


@pytest.mark.parametrize("change,reason", [
    ({"observed_at": 989}, "STALE_OBSERVATION"),
    ({"observed_at": 1001}, "FUTURE_OBSERVATION"),
    ({"observed_at": float("nan")}, "INVALID_OBSERVED_AT"),
    ({"observed_at": float("inf")}, "INVALID_OBSERVED_AT"),
    ({"observed_at": True}, "INVALID_OBSERVED_AT"),
    ({"price": "NaN"}, "INVALID_PRICE"),
    ({"price": "Infinity"}, "INVALID_PRICE"),
    ({"price": "0"}, "INVALID_PRICE"),
    ({"price": "-1"}, "INVALID_PRICE"),
    ({"price": 100.0}, "INVALID_PRICE"),
    ({"symbol": "ETH-USD"}, "SYMBOL_MISMATCH"),
    ({"quote": "USDT"}, "QUOTE_NOT_USD"),
    ({"group": None}, "INVALID_GROUP"),
    ({"venue": ""}, "INVALID_VENUE"),
    ({"unexpected": "field"}, "UNKNOWN_FIELDS"),
])
def test_invalid_observations_never_enter_estimator(change, reason):
    invalid = row("c", "999"); invalid.update(change)
    result = estimate([row("a"), row("b"), invalid])
    assert result["state"] == "ABSTAIN"
    assert result["reference_price_usd"] is None and result["group_mad_bps"] is None
    assert result["accepted_venues"] == 2
    assert reason in reasons(result)
    json.dumps(result, allow_nan=False)


def test_usd_quote_must_be_explicit_and_symbol_must_match():
    missing = row("c"); del missing["quote"]
    result = estimate([row("a"), row("b"), missing, row("d", symbol="ETH-USD")])
    assert reasons(result) == {"MISSING_QUOTE", "SYMBOL_MISMATCH"}
    assert result["state"] == "ABSTAIN"


def test_freshness_boundary_and_minimum_are_explicit():
    rows = [row("a", observed_at=990), row("b"), row("c")]
    assert estimate(rows)["state"] == "MODELED"
    assert estimate(rows, max_age_seconds="9.999")["state"] == "ABSTAIN"
    assert estimate(rows, min_groups=4)["state"] == "ABSTAIN"
    with pytest.raises(ValueError): estimate(rows, min_groups=2)


def test_group_mad_is_exact_and_can_be_zero_despite_an_outlier():
    spread = estimate([row("a", "99"), row("b", "100"), row("c", "101")])
    assert spread["group_mad_bps"] == "100"
    concentrated = estimate([row("a"), row("b"), row("c", "1000")])
    assert concentrated["group_mad_bps"] == "0"


def test_input_order_context_and_object_mutation_do_not_change_receipt():
    rows = [row("a", "99"), row("b", "100"), row("c", "101"), row("bad", observed_at=float("inf"))]
    before = deepcopy(rows)
    first = estimate(rows)
    with localcontext() as ctx:
        ctx.prec = 4
        second = estimate(list(reversed(rows)))
    assert first == second
    assert rows == before
    serialized = json.dumps(first["receipt"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    assert first["receipt_sha256"] == hashlib.sha256(serialized.encode("ascii")).hexdigest()


def test_receipt_commits_clock_recipe_rejected_input_and_outputs():
    rows = [row("a"), row("b"), row("c"), row("bad", "999", observed_at=900)]
    first = estimate(rows)
    changed = deepcopy(rows); changed[-1]["price"] = "998"
    assert estimate(changed)["receipt_sha256"] != first["receipt_sha256"]
    assert estimate(rows, max_age_seconds=11)["receipt_sha256"] != first["receipt_sha256"]
    assert estimate_reference(rows, symbol="BTC-USD", now=1001)["receipt_sha256"] != first["receipt_sha256"]
    assert first["receipt"]["outputs"]["reference_price_usd"] == "100"
    assert first["digest_is_signature"] is False and first["digest_proves_market_truth"] is False


def test_group_identity_is_case_normalized_and_namespace_separated():
    result = estimate([row("a", group="A"), row("b", group="a"), row("c"), row("d")])
    assert result["effective_groups"] == 3
    result = estimate([row("a"), row("b", group="a"), row("c")])
    assert result["effective_groups"] == 3


def test_many_venues_in_one_declared_group_still_abstain():
    result = estimate([row(f"venue-{i}", group="shared") for i in range(12)])
    assert result["accepted_venues"] == 12 and result["effective_groups"] == 1
    assert result["state"] == "ABSTAIN" and result["reference_price_usd"] is None


@pytest.mark.parametrize("rows", [None, {}, [row(str(i)) for i in range(257)],
                                 [row("a", price="1" * 129)],
                                 [row("a", observed_at=10 ** 1000)], [object()]])
def test_unbounded_or_unrepresentable_envelopes_fail_before_price(rows):
    with pytest.raises(ValueError): estimate(rows)


def test_bounded_individual_fields_cannot_exceed_record_byte_budget():
    payload = {str(i): {str(j): "x" * 128 for j in range(16)} for i in range(16)}
    with pytest.raises(ValueError, match="INPUT_RECORD_SIZE_LIMIT"):
        estimate([payload])


@pytest.mark.parametrize("now", [None, True, float("nan"), float("inf"), -1, "1e999999"])
def test_invalid_clock_fails_closed(now):
    with pytest.raises(ValueError):
        estimate_reference([row("a"), row("b"), row("c")], symbol="BTC-USD", now=now)


def test_empty_and_malformed_rows_abstain_with_receipts():
    assert estimate([])["state"] == "ABSTAIN"
    result = estimate([None, {}])
    assert result["effective_groups"] == 0 and result["venue_median_usd"] is None
    assert "ROW_NOT_OBJECT" in reasons(result)


def test_synthetic_demo_is_explicit_and_repeatable():
    demo = synthetic_demo()
    assert demo == synthetic_demo()
    assert demo["data_kind"] == "SYNTHETIC"
    cluster = demo["cases"]["correlated_venue_cluster"]
    assert cluster["reference_price_usd"] == "100.5" and cluster["venue_median_usd"] == "1000"
