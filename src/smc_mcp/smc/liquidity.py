"""Liquidity sweep detection.

Stops cluster just beyond obvious swing highs and lows. A **liquidity sweep**
(a.k.a. stop hunt or liquidity grab) is when price spikes past one of those
swing levels to trigger those stops, then closes back on the original side —
a wick through the level rather than a clean break.

- **Sell-side sweep (bearish):** a candle's high pierces a prior swing high but
  it closes back below — buy-stops above the high were taken, often before a
  move down.
- **Buy-side sweep (bullish):** a candle's low pierces a prior swing low but it
  closes back above — sell-stops below the low were taken, often before a move
  up.

Sweeps are distinct from a Break of Structure: a sweep *rejects* the level
(close stays on the original side), whereas a BOS *closes through* it.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from .structure import SwingPoint


@dataclass
class LiquiditySweep:
    """A swing level that was wicked through and rejected."""

    index: int                       # candle that performed the sweep
    swept_level: float               # the swing price that was taken
    swept_swing_index: int           # index of the swing that was swept
    kind: Literal["bullish", "bearish"]   # bullish = low swept, bearish = high swept

    def to_dict(self) -> dict:
        return asdict(self)


def find_liquidity_sweeps(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    swings: list[SwingPoint],
) -> list[LiquiditySweep]:
    """Detect liquidity sweeps of prior swing highs and lows.

    For every candle, check whether it wicked beyond the most recent prior swing
    high (then closed below it) or prior swing low (then closed above it).

    Args:
        highs, lows, closes: OHLC arrays, oldest first, equal length.
        swings: Output of :func:`structure.find_swings` for the same series.

    Returns:
        Liquidity sweeps in chronological order.
    """
    sweeps: list[LiquiditySweep] = []
    swing_highs = [s for s in swings if s.kind == "high"]
    swing_lows = [s for s in swings if s.kind == "low"]

    def most_recent_before(points: list[SwingPoint], i: int) -> SwingPoint | None:
        recent: SwingPoint | None = None
        for s in points:
            if s.index < i:
                recent = s
            else:
                break
        return recent

    n = len(closes)
    for i in range(n):
        # Bearish sweep: take out a prior swing high, close back below it.
        sh = most_recent_before(swing_highs, i)
        if sh is not None and highs[i] > sh.price and closes[i] < sh.price:
            sweeps.append(
                LiquiditySweep(index=i, swept_level=sh.price,
                               swept_swing_index=sh.index, kind="bearish")
            )
            continue

        # Bullish sweep: take out a prior swing low, close back above it.
        sl = most_recent_before(swing_lows, i)
        if sl is not None and lows[i] < sl.price and closes[i] > sl.price:
            sweeps.append(
                LiquiditySweep(index=i, swept_level=sl.price,
                               swept_swing_index=sl.index, kind="bullish")
            )

    return sweeps
