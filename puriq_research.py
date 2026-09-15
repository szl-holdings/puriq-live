"""PURIQ historical research: public candles and a non-authorizing virtual replay.

This stateless laboratory is not the canonical szl-quant paper book. No broker,
wallet, account, order, signed-ledger write, user script, or learned model exists
here. Real source observations and modeled fills have separate truth labels.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import hashlib
import math
import threading
import time
from typing import Any

import httpx

from puriq_market import SourceUnavailable, _bounded_get_json, sha256_json

PAIRS = frozenset({"BTC-USD", "ETH-USD", "SOL-USD"})
GRANULARITIES = frozenset({900, 3600, 86400})
STARTING_CASH = Decimal("1000")
ALLOCATION_CAP = Decimal("100")
FEE = Decimal("0.002")
SLIPPAGE = Decimal("0.001")
QTY_STEP = Decimal("0.00000001")
CANDLE_MAX = 300


def finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SourceUnavailable("candle contains a non-numeric field")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise SourceUnavailable("candle contains an invalid number") from exc
    if not math.isfinite(number) or abs(number) > 1e15:
        raise SourceUnavailable("candle exceeds the finite numeric domain")
    return number


def normalize_candles(payload: Any, *, granularity: int, observed_at: float) -> dict:
    if granularity not in GRANULARITIES or isinstance(granularity, bool):
        raise ValueError("unsupported candle granularity")
    if not isinstance(payload, list) or not 1 <= len(payload) <= CANDLE_MAX:
        raise SourceUnavailable("candle collection is empty or outside the 300-bar bound")
    bars, seen, excluded = [], set(), 0
    for row in payload:
        if not isinstance(row, list) or len(row) != 6:
            raise SourceUnavailable("candle must contain exactly six fields")
        stamp, low, high, opened, close, volume = [finite_number(v) for v in row]
        if stamp < 0 or stamp != int(stamp) or int(stamp) % granularity:
            raise SourceUnavailable("candle timestamp is not an aligned epoch second")
        if stamp in seen:
            raise SourceUnavailable("duplicate candle timestamp")
        seen.add(stamp)
        if min(low, high, opened, close) <= 0 or volume < 0:
            raise SourceUnavailable("candle has an invalid price or volume")
        if not low <= min(opened, close) <= max(opened, close) <= high:
            raise SourceUnavailable("candle violates OHLC ordering")
        if stamp + granularity > observed_at:
            excluded += 1
            continue
        bars.append({"time": int(stamp) * 1000, "open": opened, "high": high,
                     "low": low, "close": close, "volume": volume})
    bars.sort(key=lambda b: b["time"])
    if not bars:
        raise SourceUnavailable("no completed candles were observed")
    interval_ms = granularity * 1000
    gaps = [{"after_time": a["time"], "before_time": b["time"],
             "missing_intervals": (b["time"] - a["time"]) // interval_ms - 1}
            for a, b in zip(bars, bars[1:]) if b["time"] - a["time"] != interval_ms]
    return {"bars": bars, "gaps": gaps, "excluded_unclosed_or_future": excluded,
            "newest_completed_at": bars[-1]["time"] / 1000 + granularity,
            "truth_label": "REPORTED", "timestamps": "epoch_milliseconds",
            "interpolation": "NONE"}


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")


def research_replay(bars: list[dict], *, gaps: list[dict]) -> dict:
    """Fixed 20/50 SMA benchmark. Prior closed bars -> next bar open fills.

    This routine only accepts internally normalized bars. Public APIs never
    accept caller bars or parameters. Decimal accounting includes costs on both
    sides; final equity is a mark, not an assumed final liquidation.
    """
    base = {"schema": "szl.puriq.research-replay/v1", "truth_label": "MODELED",
            "canonical_paper_engine": "szl-holdings/szl-quant",
            "strategy": "FIXED_SMA_20_50_RESEARCH_BASELINE", "trained_model": False,
            "virtual_starting_cash_usd": "1000.000000", "capital_transferred": False,
            "trading_enabled": False, "autonomous_authority": False,
            "signal_timing": "previous completed candles only; fill at next open",
            "cost_model": {"fee_bps_each_side": 20, "slippage_bps_each_side": 10,
                           "status": "ILLUSTRATIVE_NOT_VENUE_FEE_QUOTE"},
            "allocation": {"max_entry_spend_usd": "100", "leverage": False,
                           "shorting": False, "pyramiding": False},
            "qualification": "NOT_OUT_OF_SAMPLE_QUALIFIED; NOT_EXPECTED_RETURN",
            "curve": [], "fills": []}
    if gaps or len(bars) < 60:
        return {**base, "state": "UNAVAILABLE", "reason": "GAPPED_HISTORY" if gaps else "INSUFFICIENT_HISTORY"}
    cash, qty, benchmark_cash, benchmark_qty = STARTING_CASH, Decimal(0), STARTING_CASH, Decimal(0)
    peak, drawdown, fees, entry_spend = STARTING_CASH, Decimal(0), Decimal(0), Decimal(0)
    wins, rounds = 0, 0
    for i, bar in enumerate(bars):
        opened, close = Decimal(str(bar["open"])), Decimal(str(bar["close"]))
        if i >= 50:
            # No close/high/low from the fill bar participates in the signal.
            prior = [Decimal(str(b["close"])) for b in bars[i - 50:i]]
            fast, slow = sum(prior[-20:]) / 20, sum(prior) / 50
            if i == 50:
                execution = opened * (1 + SLIPPAGE)
                benchmark_qty = (ALLOCATION_CAP / (execution * (1 + FEE))).quantize(QTY_STEP, rounding=ROUND_DOWN)
                benchmark_cash -= benchmark_qty * execution * (1 + FEE)
            side = None
            if fast > slow and qty == 0:
                execution = opened * (1 + SLIPPAGE)
                spend_cap = min(ALLOCATION_CAP, cash)
                new_qty = (spend_cap / (execution * (1 + FEE))).quantize(QTY_STEP, rounding=ROUND_DOWN)
                if new_qty > 0:
                    qty = new_qty
                    notional = qty * execution
                    fee = notional * FEE
                    entry_spend = notional + fee
                    cash -= entry_spend
                    filled_qty = qty
                    side = "SIMULATED_BUY"
            elif fast < slow and qty > 0:
                execution = opened * (1 - SLIPPAGE)
                notional = qty * execution
                fee = notional * FEE
                proceeds = notional - fee
                cash += proceeds
                wins += int(proceeds > entry_spend)
                rounds += 1
                filled_qty, qty = qty, Decimal(0)
                side = "SIMULATED_SELL"
            if side:
                fees += fee
                base["fills"].append({"time": bar["time"], "side": side,
                    "signal_last_time": bars[i-1]["time"], "quantity": str(filled_qty),
                    "price": money(execution), "fee_usd": money(fee),
                    "cash_after_usd": money(cash), "truth_label": "MODELED"})
        equity = cash + qty * close
        benchmark = benchmark_cash + benchmark_qty * close
        peak = max(peak, equity)
        current_dd = (peak - equity) / peak
        drawdown = max(drawdown, current_dd)
        if cash < 0 or qty < 0:
            raise ArithmeticError("paper accounting invariant violated")
        base["curve"].append({"time": bar["time"], "equity_usd": float(equity),
            "cash_usd": float(cash), "benchmark_usd": float(benchmark),
            "drawdown_fraction": float(current_dd)})
    base.update(state="MODELED", final_equity_usd=money(equity),
        final_cash_usd=money(cash), open_quantity=str(qty),
        final_mark_includes_unrealized_pnl=True, final_liquidation_cost_included=False,
        modeled_pnl_usd=money(equity - STARTING_CASH), fees_usd=money(fees),
        return_fraction=float(equity / STARTING_CASH - 1), max_drawdown_fraction=float(drawdown),
        filled_sides=len(base["fills"]), closed_round_trips=rounds,
        net_winning_round_trips=wins, win_rate=(wins / rounds if rounds else None),
        benchmark_final_equity_usd=money(benchmark),
        benchmark_definition="same $100 allocation and entry costs; buy at first eligible open, mark without liquidation",
        limitations=["Short descriptive window; no parameter selection or out-of-sample skill claim.",
                     "No fill probability, order-book depth, market impact, latency, tax, or funding model.",
                     "Illustrative costs can materially understate actual costs.",
                     "No stops, insurance, or assurance that losses are limited to the modeled drawdown.",
                     "Source data are reported by the venue, not independently cross-validated."])
    base["digest_is_signature"] = False
    base["result_sha256"] = sha256_json(base)
    return base


class ResearchClient:
    """A bounded, process-local acquisition cache; no persistent trading state."""
    def __init__(self, transport: httpx.BaseTransport | None = None, clock=time.time):
        self.transport, self.clock = transport, clock
        self._cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
        self._lock = threading.Lock()

    def history(self, pair: str, granularity: int) -> dict:
        if pair not in PAIRS or granularity not in GRANULARITIES or isinstance(granularity, bool):
            raise ValueError("unsupported pair or granularity")
        key = (pair, granularity)
        if not self._lock.acquire(timeout=2):
            raise SourceUnavailable("public history acquisition is busy")
        try:
            now = self.clock()
            cached = self._cache.get(key)
            cache_hit = bool(cached and 0 <= now - cached[0] < 60)
            if cache_hit:
                result = deepcopy(cached[1])
            else:
                # Failed refresh never converts a stale cache into a fresh observation.
                url = f"https://api.exchange.coinbase.com/products/{pair}/candles"
                _, raw, payload, source_url = _bounded_get_json(url,
                    query={"granularity": str(granularity)}, max_bytes=250_000,
                    transport=self.transport)
                now = self.clock()
                history = normalize_candles(payload, granularity=granularity, observed_at=now)
                result = {"schema": "szl.puriq.research-observation/v1", "status": "OBSERVED",
                    "pair": pair, "granularity_seconds": granularity, "history": history,
                    "source": {"authority": "Coinbase Exchange public candles", "url": source_url,
                        "observed_at": now, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                        "normalized_sha256": sha256_json(history), "truth_label": "REPORTED",
                        "digest_is_signature": False},
                    "replay": research_replay(history["bars"], gaps=history["gaps"]),
                    "trading_enabled": False, "capital_transferred": False}
                self._cache[key] = (now, deepcopy(result))
                self._cache.move_to_end(key)
                while len(self._cache) > 9:
                    self._cache.popitem(last=False)
        finally:
            self._lock.release()
        result["freshness"] = {"cached": cache_hit,
            "fetch_age_seconds": max(0, now - result["source"]["observed_at"]),
            "newest_completed_bar_age_seconds": max(0, now - result["history"]["newest_completed_at"]),
            "market_event_time_is_fetch_time": False, "realtime_quote_claim": False}
        return result
