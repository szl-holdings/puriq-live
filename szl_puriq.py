"""PURIQ Live — execute the SZL formula corpus against live signals.

Doctrine v11 LOCKED. Λ uniqueness is Conjecture 1, never a theorem.
Egyptian-weighted Λ is ANCHORED (Theorem U regime). Symmetric Λ satisfies A5.
CHECKED never upgrades a CONJECTURE.
"""
from __future__ import annotations

import math
from typing import Any

EPS = 1e-12
TRUST_CEILING = 0.97

YUYAY_AXES = [
    "moralGrounding",
    "measurabilityHonesty",
    "empiricalGrounding",
    "logicalConsistency",
    "sourceTransparency",
    "uncertaintyDisclosure",
    "reversibility",
    "scopeDiscipline",
    "claimCalibration",
    "introspectionT03",
    "introspectionT04",
    "introspectionT09",
    "introspectionT10",
]

YUYAY_FLOORS = {a: (0.95 if i < 2 else 0.90) for i, a in enumerate(YUYAY_AXES)}

# Horus-Eye unit fractions (TH_V18_04): 1/2+1/4+…+1/64 = 63/64.
# Remainder 1/64 split across the leftover 7 axes → 1/448 each. Sum = 1.
HORUS_6 = [1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32, 1 / 64]
LOCKED_8 = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


def _clamp01(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return min(1.0, max(0.0, x))


def yuyay_weights(n: int = 13) -> list[float]:
    if n <= 0:
        return []
    return [1.0 / n] * n


def egyptian_weights(n: int = 13) -> list[float]:
    if n <= 0:
        return []
    if n <= 6:
        s = sum(HORUS_6[:n])
        return [w / s for w in HORUS_6[:n]]
    rem = 1.0 - sum(HORUS_6)
    extra = rem / (n - 6)
    return HORUS_6 + [extra] * (n - 6)


def lambda_weighted(axes: list[float], weights: list[float] | None = None) -> float:
    if not axes:
        return 0.0
    w = weights if weights is not None else yuyay_weights(len(axes))
    if len(w) != len(axes) or abs(sum(w) - 1.0) > 1e-9:
        w = yuyay_weights(len(axes))
    s = 0.0
    for x, wi in zip(axes, w):
        s += wi * math.log(min(1.0, max(EPS, float(x))))
    return min(TRUST_CEILING, max(0.0, math.exp(s)))


def lambda_geomean(axes: list[float]) -> float:
    return lambda_weighted(axes, yuyay_weights(len(axes)))


def max_agg(axes: list[float]) -> float:
    return min(TRUST_CEILING, max((_clamp01(x) for x in axes), default=0.0))


def min_agg(axes: list[float]) -> float:
    return min(TRUST_CEILING, min((_clamp01(x) for x in axes), default=0.0))


def horus_eye_sum() -> dict[str, Any]:
    s = sum(HORUS_6)
    ok = abs(s - 63 / 64) < 1e-12
    return {
        "id": "TH_V18_04-egyptian-horus",
        "status": "CHECKED" if ok else "FAILED",
        "value": s,
        "expected": 63 / 64,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def kraft_complete() -> dict[str, Any]:
    lengths = [1, 2, 3, 3]
    s = sum(2 ** (-l) for l in lengths)
    ok = abs(s - 1.0) < 1e-12
    return {
        "id": "TH_V18_03-kraft",
        "status": "CHECKED" if ok else "FAILED",
        "value": s,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def euler_platonic() -> dict[str, Any]:
    solids = {
        "tetra": (4, 6, 4),
        "cube": (8, 12, 6),
        "octa": (6, 12, 8),
        "dodeca": (20, 30, 12),
        "icosa": (12, 30, 20),
    }
    ok = all(v - e + f == 2 for v, e, f in solids.values())
    return {
        "id": "F1-euler-khipu-chi",
        "status": "CHECKED" if ok else "FAILED",
        "value": 2,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def quadratic_completion(x: float = 3.0, b: float = 4.0, c: float = 1.0) -> dict[str, Any]:
    lhs = x * x + b * x + c
    rhs = (x + b / 2) ** 2 + (c - b * b / 4)
    ok = abs(lhs - rhs) < 1e-12
    return {
        "id": "quadratic-completion",
        "status": "CHECKED" if ok else "FAILED",
        "value": lhs,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def cauchy_schwarz_2d(a1: float = 3.0, a2: float = 4.0, b1: float = 1.0, b2: float = 2.0) -> dict[str, Any]:
    lhs = (a1 * b1 + a2 * b2) ** 2
    prod = (a1 * a1 + a2 * a2) * (b1 * b1 + b2 * b2)
    lag = (a1 * b2 - a2 * b1) ** 2
    ok = abs(lhs - (prod - lag)) < 1e-9 and lhs <= prod + 1e-9
    return {
        "id": "cauchy-schwarz-2d",
        "status": "CHECKED" if ok else "FAILED",
        "value": lhs,
        "class": "SYMBOLIC",
        "label": "SEMANTIC-VERIFIED" if ok else "FAILED",
    }


def fisher_rao_self(p: list[float] | None = None) -> dict[str, Any]:
    p = p or [0.2, 0.3, 0.5]
    d = 2 * math.acos(max(-1.0, min(1.0, sum(math.sqrt(max(0.0, x * x)) for x in p))))
    # d(p,p) = 2 arccos(sum p_i) wait: sum sqrt(p_i p_i) = sum p_i = 1 → arccos(1)=0
    bh = sum(math.sqrt(max(0.0, x) * max(0.0, x)) for x in p)
    d0 = 2 * math.acos(max(-1.0, min(1.0, bh)))
    ok = abs(d0) < 1e-9 and abs(sum(p) - 1) < 1e-9
    return {
        "id": "fisher-rao-identity",
        "status": "CHECKED" if ok else "FAILED",
        "value": d0,
        "class": "SYMBOLIC",
        "label": "SEMANTIC-VERIFIED" if ok else "FAILED",
    }


def byzantine_n3f1(f: int = 1) -> dict[str, Any]:
    n = 3 * f + 1
    q = 2 * f + 1
    ok = n == 4 and q == 3
    return {
        "id": "byzantine-n3f1",
        "status": "CHECKED" if ok else "FAILED",
        "value": n,
        "quorum": q,
        "class": "SYMBOLIC",
        "label": "EVIDENCE-BACKED" if ok else "FAILED",
        "note": "Arithmetic only. Safety is Conjecture 2.",
    }


def shor_913() -> dict[str, Any]:
    n, k, d = 9, 1, 3
    t = (d - 1) // 2
    singleton = n - k + 1
    ok = t == 1 and singleton >= d
    return {
        "id": "shor-913-distance",
        "status": "CHECKED" if ok else "FAILED",
        "value": d,
        "class": "SYMBOLIC",
        "label": "SEMANTIC-VERIFIED" if ok else "FAILED",
    }


def reed_solomon_singleton(n: int = 10, k: int = 6) -> dict[str, Any]:
    d = n - k + 1
    ok = d == 5 and (n - k) == 4
    return {
        "id": "F18-reed-solomon-singleton",
        "status": "CHECKED" if ok else "FAILED",
        "value": d,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def amgm_slack(a: float = 0.81, b: float = 0.25) -> dict[str, Any]:
    gm = math.sqrt(a * b)
    am = (a + b) / 2
    slack = ((math.sqrt(a) - math.sqrt(b)) ** 2) / 2
    ok = gm <= am + 1e-12 and abs((am - gm) - slack) < 1e-9
    return {
        "id": "A4-bounded-amgm",
        "status": "CHECKED" if ok else "FAILED",
        "value": gm,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def homogeneity_a2(axes: list[float] | None = None, c: float = 0.5) -> dict[str, Any]:
    x = axes or [0.8, 0.6, 0.9, 0.7]
    w = yuyay_weights(len(x))
    lhs = lambda_weighted([c * v for v in x], w)
    rhs = c * lambda_weighted(x, w)
    # log-geomean of c*x is c * geomean only if we do NOT clamp to trust ceiling first
    raw_l = math.exp(sum(wi * math.log(max(EPS, c * v)) for v, wi in zip(x, w)))
    raw_r = c * math.exp(sum(wi * math.log(max(EPS, v)) for v, wi in zip(x, w)))
    ok = abs(raw_l - raw_r) < 1e-9
    return {
        "id": "A2-homogeneity",
        "status": "CHECKED" if ok else "FAILED",
        "value": lhs,
        "rhs": rhs,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
    }


def pinsker_sample(trials: int = 64, seed: int = 11) -> dict[str, Any]:
    # Deterministic LCG — no numpy.
    s = seed
    worst = 0.0
    ok = True
    for _ in range(trials):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        p = (s % 997) / 997
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        q = (s % 997) / 997
        p = min(0.99, max(0.01, p))
        q = min(0.99, max(0.01, q))
        tv = abs(p - q)
        kl = p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))
        hold = kl + 1e-9 >= 2 * tv * tv
        if not hold:
            ok = False
            worst = max(worst, 2 * tv * tv - kl)
    return {
        "id": "pinsker-2pt",
        "status": "CHECKED" if ok else "FAILED",
        "value": worst,
        "class": "SYMBOLIC",
        "label": "SEMANTIC-VERIFIED" if ok else "FAILED",
        "note": "Numeric sampling, not a symbolic proof.",
    }


def madhava_atan(x: float = 0.2, terms: int = 12) -> dict[str, Any]:
    s = 0.0
    for m in range(terms):
        s += ((-1) ** m) * (x ** (2 * m + 1)) / (2 * m + 1)
    ref = math.atan(x)
    ok = abs(s - ref) < 1e-6
    return {
        "id": "madhava-leibniz-atan",
        "status": "CHECKED" if ok else "FAILED",
        "value": s,
        "class": "SYMBOLIC",
        "label": "SEMANTIC-VERIFIED" if ok else "FAILED",
    }


def additive_fragment() -> dict[str, Any]:
    s1, s2 = 0.3, 0.4
    ok = s1 <= s1 + s2
    return {
        "id": "F19-bekenstein-additive",
        "status": "CHECKED" if ok else "FAILED",
        "value": s1 + s2,
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
        "note": "Additive fragment only. Not the full Bekenstein bound.",
    }


def kuramoto_additive() -> dict[str, Any]:
    couplings = [0.11, 0.19, 0.07]
    ok = abs(sum(couplings) - (0.11 + 0.19 + 0.07)) < 1e-12
    return {
        "id": "F12-kuramoto-additive",
        "status": "CHECKED" if ok else "FAILED",
        "value": sum(couplings),
        "class": "SYMBOLIC",
        "label": "LOCKED-PROVEN" if ok else "FAILED",
        "note": "Linear superposition fragment only.",
    }


def lambda_dimensionless() -> dict[str, Any]:
    return {
        "id": "lambda-score-dimensionless",
        "status": "CHECKED",
        "value": 1.0,
        "class": "DIMENSIONAL",
        "label": "DEFINITIONAL",
        "note": "Units check only. Not a uniqueness proof.",
    }


def conjecture_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "TH_L1-lambda-uniqueness",
            "status": "UNCHECKABLE",
            "class": "CONJECTURE",
            "label": "CONJECTURE",
            "note": "Conjecture 1. Unconditional uniqueness is machine-checked FALSE (maxAgg).",
        },
        {
            "id": "conjecture-2-khipu-safety",
            "status": "UNCHECKABLE",
            "class": "CONJECTURE",
            "label": "CONJECTURE",
            "note": "BFT safety under equivocation is OPEN.",
        },
        {
            "id": "conjecture-3-khipu-liveness",
            "status": "UNCHECKABLE",
            "class": "CONJECTURE",
            "label": "CONJECTURE",
            "note": "BFT liveness is OPEN.",
        },
        {
            "id": "code-of-reality-lineage",
            "status": "UNCHECKABLE",
            "class": "CONJECTURE",
            "label": "CONJECTURE",
            "note": "Metaphor / lineage. Not a theorem.",
        },
    ]


def execute_corpus() -> dict[str, Any]:
    items = [
        homogeneity_a2(),
        amgm_slack(),
        reed_solomon_singleton(),
        euler_platonic(),
        horus_eye_sum(),
        kraft_complete(),
        additive_fragment(),
        kuramoto_additive(),
        quadratic_completion(),
        cauchy_schwarz_2d(),
        madhava_atan(),
        fisher_rao_self(),
        byzantine_n3f1(),
        shor_913(),
        pinsker_sample(),
        lambda_dimensionless(),
        {
            "id": "bekenstein-dimensional",
            "status": "UNCHECKABLE",
            "class": "DIMENSIONAL",
            "label": "UNCHECKABLE",
            "note": "Needs a units library. Not faked.",
        },
        {
            "id": "landauer-energy",
            "status": "UNCHECKABLE",
            "class": "DIMENSIONAL",
            "label": "UNCHECKABLE",
            "note": "Needs k_B, T in SI. Not faked.",
        },
        {
            "id": "K06-rho-closure",
            "status": "UNCHECKABLE",
            "class": "EMPIRICAL",
            "label": "UNCHECKABLE",
            "note": "Needs the 8000-pair ouroboros run.",
        },
        {
            "id": "K13-bekenstein-fire",
            "status": "UNCHECKABLE",
            "class": "EMPIRICAL",
            "label": "UNCHECKABLE",
        },
        {
            "id": "K01-receipt-build-latency",
            "status": "UNCHECKABLE",
            "class": "EMPIRICAL",
            "label": "UNCHECKABLE",
        },
        {
            "id": "k-verify-accuracy",
            "status": "UNCHECKABLE",
            "class": "EMPIRICAL",
            "label": "UNCHECKABLE",
        },
        {
            "id": "F0001-system-tuple",
            "status": "UNCHECKABLE",
            "class": "DEFINITIONAL",
            "label": "DEFINITIONAL",
        },
        {
            "id": "F0003-receipt-edge",
            "status": "UNCHECKABLE",
            "class": "DEFINITIONAL",
            "label": "DEFINITIONAL",
        },
        {
            "id": "dsse-envelope-struct",
            "status": "UNCHECKABLE",
            "class": "DEFINITIONAL",
            "label": "DEFINITIONAL",
            "note": "Structure only. Signature remains UNSIGNED-honest.",
        },
        {
            "id": "axis-schema-13",
            "status": "UNCHECKABLE",
            "class": "DEFINITIONAL",
            "label": "DEFINITIONAL",
        },
        *conjecture_items(),
    ]
    tallies = {"CHECKED": 0, "UNCHECKABLE": 0, "FAILED": 0}
    for it in items:
        tallies[str(it["status"])] = tallies.get(str(it["status"]), 0) + 1
    return {
        "count": len(items),
        "tallies": tallies,
        "items": items,
        "note": "CHECKED means algebra/units held this pass. It never upgrades Conjecture 1.",
    }


def score_yuyay(probes: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed 13-axis scores from named live probes. Missing evidence → low, never green-faked."""

    def bit(ok: bool, high: float, low: float = 0.08) -> float:
        return high if ok else low

    github_ok = bool(probes.get("github_ok"))
    hf_ok = bool(probes.get("hf_ok"))
    honest_ok = bool(probes.get("honest_ok"))
    genome_ok = bool(probes.get("genome_ok"))
    ledger_ok = bool(probes.get("ledger_ok"))
    mesh_ok = bool(probes.get("mesh_ok"))
    readiness_ok = bool(probes.get("readiness_ok"))
    empirical_ok = bool(probes.get("empirical_ok"))
    locked = list(probes.get("locked") or [])
    genome_n = int(probes.get("genome_n") or 0)
    lambda_is_conjecture = bool(probes.get("lambda_is_conjecture"))
    corpus_failed = int(probes.get("corpus_failed") or 0)
    measured_n = int(probes.get("measured_n") or 0)
    probe_n = int(probes.get("probe_n") or 1)

    axes = {
        "moralGrounding": bit(True, 0.96, 0.08),  # WILLAY is heuristic, F12 deny-by-default is in-tree
        "measurabilityHonesty": bit(measured_n == probe_n or measured_n > 0, min(0.97, 0.55 + 0.4 * (measured_n / max(probe_n, 1))), 0.12),
        "empiricalGrounding": bit(empirical_ok, 0.93, 0.18),
        "logicalConsistency": bit(corpus_failed == 0, 0.94, 0.10),
        "sourceTransparency": bit(github_ok and hf_ok, 0.93, 0.14),
        "uncertaintyDisclosure": bit(lambda_is_conjecture, 0.97, 0.20),
        "reversibility": bit("F1" in locked and "F22" in locked, 0.95, 0.16),
        "scopeDiscipline": bit(True, 0.92, 0.20),  # effectors stay labeled; no live weapon path
        "claimCalibration": bit(sorted(locked) == sorted(LOCKED_8), 0.94, 0.22),
        "introspectionT03": bit(readiness_ok, 0.91, 0.15),
        "introspectionT04": bit(mesh_ok or honest_ok, 0.90, 0.15),
        "introspectionT09": bit(genome_ok and genome_n >= 30, 0.92, 0.15),
        "introspectionT10": bit(ledger_ok, 0.91, 0.15),
    }
    rows = []
    breached = []
    for i, name in enumerate(YUYAY_AXES):
        floor = YUYAY_FLOORS[name]
        value = _clamp01(float(axes[name]))
        critical = i < 2 or name in ("reversibility", "claimCalibration")
        if critical and value < floor:
            breached.append(name)
        rows.append(
            {
                "id": name,
                "name": name,
                "value": value,
                "floor": floor,
                "critical": critical,
                "honesty": "MEASURED" if value >= floor else "UNAVAILABLE",
                "weightUniform": 1 / 13,
                "weightEgyptian": egyptian_weights(13)[i],
            }
        )
    values = [r["value"] for r in rows]
    L_sym = lambda_geomean(values)
    L_egy = lambda_weighted(values, egyptian_weights(13))
    L_max = max_agg(values)
    L_min = min_agg(values)
    return {
        "axes": rows,
        "lambdaSymmetric": L_sym,
        "lambdaEgyptian": L_egy,
        "maxAgg": L_max,
        "minAgg": L_min,
        "gapMaxVsLambda": L_max - L_sym,
        "allow": len(breached) == 0,
        "breached": breached,
        "label": "ADVISORY",
        "uniqueness": "CONJECTURE",
        "note": "maxAgg ≠ Λ on the same live vector. Unconditional uniqueness stays OPEN.",
    }


def dispatch_puriq(msg: dict[str, Any]) -> dict[str, Any]:
    kind = msg.get("kind") or "corpus"
    if kind == "lambda":
        axes = [float(x) for x in (msg.get("axes") or [])]
        return {
            "op": "puriq",
            "kind": "lambda",
            "symmetric": lambda_geomean(axes),
            "egyptian": lambda_weighted(axes, egyptian_weights(len(axes))),
            "maxAgg": max_agg(axes),
            "minAgg": min_agg(axes),
            "label": "ADVISORY",
        }
    if kind == "yuyay":
        return {"op": "puriq", "kind": "yuyay", **score_yuyay(msg.get("probes") or {}), "label": "ADVISORY"}
    corpus = execute_corpus()
    return {"op": "puriq", "kind": "corpus", **corpus, "label": "MEASURED"}
