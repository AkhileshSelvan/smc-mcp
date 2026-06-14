"""Tests for the SMC core logic using hand-built price series.

These run without any network — they validate the algorithms, not the data
feed. Run with:  python -m pytest tests/ -q   (or just: python tests/test_smc.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from smc_mcp.smc import (  # noqa: E402
    find_swings,
    detect_structure,
    find_order_blocks,
    find_fair_value_gaps,
    find_liquidity_sweeps,
)


def test_find_swings_basic():
    # A clear peak at index 3 and a clear trough at index 7.
    highs = [1, 2, 3, 5, 3, 2, 2, 1, 2, 3]
    lows = [1, 1, 2, 4, 2, 1, 1, 0, 1, 2]
    swings = find_swings(highs, lows, lookback=2)
    kinds = {(s.index, s.kind) for s in swings}
    assert (3, "high") in kinds, "should detect the swing high at index 3"
    assert (7, "low") in kinds, "should detect the swing low at index 7"


def test_structure_bullish_break():
    # Price forms a swing high, pulls back, then closes above it -> bullish.
    highs = [5, 7, 6, 6, 9]
    lows = [4, 6, 5, 5, 7]
    closes = [5, 7, 6, 6, 9]  # index 4 closes above swing high (7) at index 1
    swings = find_swings(highs, lows, lookback=1)
    events, bias = detect_structure(closes, swings, lookback=1)
    assert any(e.direction == "bullish" for e in events)
    assert bias == "bullish"


def test_structure_bearish_break():
    # Price forms a swing low, bounces, then closes below it -> bearish.
    highs = [7, 6, 7, 7, 6]
    lows = [6, 4, 5, 5, 2]
    closes = [7, 5, 6, 6, 2]  # index 4 closes below swing low (4) at index 1
    swings = find_swings(highs, lows, lookback=1)
    events, bias = detect_structure(closes, swings, lookback=1)
    assert any(e.direction == "bearish" for e in events)
    assert bias == "bearish"


def test_fair_value_gap_bullish():
    # Candle 0 high = 2; candle 2 low = 3 -> bullish gap (2..3) at index 1.
    highs = [2, 5, 6]
    lows = [1, 3, 3]
    gaps = find_fair_value_gaps(highs, lows)
    assert len(gaps) == 1
    g = gaps[0]
    assert g.kind == "bullish" and g.bottom == 2 and g.top == 3
    assert g.filled is False


def test_fair_value_gap_fill():
    # Same bullish gap, then a later candle trades back down through it.
    highs = [2, 5, 6, 4, 3]
    lows = [1, 3, 3, 2, 1]  # index 4 low = 1 <= gap bottom 2 -> filled
    gaps = find_fair_value_gaps(highs, lows)
    assert gaps[0].filled is True


def test_liquidity_sweep_bearish():
    # Swing high forms, then a candle wicks above it but closes back below.
    highs = [3, 5, 3, 3, 6]
    lows = [2, 4, 2, 2, 3]
    closes = [3, 5, 3, 3, 4]  # index 4 high 6 > swing high 5, close 4 < 5
    swings = find_swings(highs, lows, lookback=1)
    sweeps = find_liquidity_sweeps(highs, lows, closes, swings)
    assert any(s.kind == "bearish" for s in sweeps), "expected a bearish sweep"


def test_order_block_bullish():
    # Swing high forms at idx 1 (high 8). idx 2 is the last bearish candle
    # before price closes above that high at idx 6 -> bullish order block.
    opens = [5, 5, 7, 6, 6, 6, 7]
    highs = [6, 8, 7, 7, 7, 8, 12]
    lows = [4, 5, 5, 5, 5, 6, 7]
    closes = [5, 7, 6, 6, 6, 7, 11]
    swings = find_swings(highs, lows, lookback=1)
    events, _ = detect_structure(closes, swings, lookback=1)
    blocks = find_order_blocks(opens, highs, lows, closes, events)
    assert any(b.kind == "bullish" for b in blocks), "expected a bullish OB"


def _run_all():
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
