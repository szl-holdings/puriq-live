"""Replay a normalized USD venue snapshot, without network access or execution.

Run from the repository root:
python tools/replay_reference.py observations.json --symbol BTC --now 1791392000
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from puriq_reference import estimate_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--now", type=float, required=True, help="Replay clock: Unix seconds")
    args = parser.parse_args()
    if args.input.stat().st_size > 1_000_000:
        parser.error("Input exceeds one megabyte")
    rows = json.loads(args.input.read_text())
    result = estimate_reference(rows, symbol=args.symbol, now=args.now)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
