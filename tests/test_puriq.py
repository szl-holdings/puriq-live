"""PURIQ corpus + Λ — fail the build on FAILED or uniqueness overclaim."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from szl_puriq import (  # noqa: E402
    LOCKED_8,
    egyptian_weights,
    execute_corpus,
    lambda_geomean,
    lambda_weighted,
    max_agg,
    score_yuyay,
    yuyay_weights,
)


def test_corpus_no_failed() -> None:
    c = execute_corpus()
    assert c["count"] == 30
    assert c["tallies"]["FAILED"] == 0
    assert c["tallies"]["CHECKED"] >= 15
    assert any(i["id"] == "TH_L1-lambda-uniqueness" and i["status"] == "UNCHECKABLE" for i in c["items"])


def test_egyptian_sums() -> None:
    w = egyptian_weights(13)
    assert abs(sum(w) - 1.0) < 1e-9
    assert abs(sum(yuyay_weights(13)) - 1.0) < 1e-12


def test_maxagg_is_not_lambda() -> None:
    axes = [0.97, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]
    L = lambda_geomean(axes)
    M = max_agg(axes)
    assert M > L + 0.05
    assert L <= 0.97


def test_yuyay_fail_closed() -> None:
    y = score_yuyay(
        {
            "github_ok": False,
            "hf_ok": False,
            "honest_ok": False,
            "genome_ok": False,
            "ledger_ok": False,
            "mesh_ok": False,
            "readiness_ok": False,
            "empirical_ok": False,
            "locked": [],
            "genome_n": 0,
            "lambda_is_conjecture": False,
            "corpus_failed": 1,
            "measured_n": 0,
            "probe_n": 10,
        }
    )
    assert y["allow"] is False
    assert y["uniqueness"] == "CONJECTURE"
    assert math.isfinite(y["lambdaSymmetric"])


def test_locked_identity() -> None:
    assert list(LOCKED_8) == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    Le = lambda_weighted([0.9] * 13, egyptian_weights(13))
    Ls = lambda_geomean([0.9] * 13)
    assert abs(Le - Ls) < 1e-9  # A3 diagonal: both return 0.9 (capped)


if __name__ == "__main__":
    test_corpus_no_failed()
    test_egyptian_sums()
    test_maxagg_is_not_lambda()
    test_yuyay_fail_closed()
    test_locked_identity()
    print("ok")
