"""Fair value gap (FVG) detection.

A **fair value gap** is a three-candle imbalance — a price range that the middle
candle's impulse skipped over so fast that buyers and sellers never transacted
there. Price often returns to "rebalance" these gaps, which makes them useful
entry and target zones.

- **Bullish FVG:** the low of candle 3 is above the high of candle 1 (a gap left
  during an up-move).
- **Bearish FVG:** the high of candle 3 is below the low of candle 1 (a gap left
  during a down-move).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal


@dataclass
class FairValueGap:
    """A three-candle imbalance zone."""

    index: int                       # index of the middle (impulse) candle
    top: float                       # upper bound of the gap
    bottom: float                    # lower bound of the gap
    kind: Literal["bullish", "bearish"]
    filled: bool                     # has price fully traded back through it?
    filled_index: int | None         # when, if so

    def to_dict(self) -> dict:
        return asdict(self)


def find_fair_value_gaps(
    highs: list[float],
    lows: list[float],
) -> list[FairValueGap]:
    """Detect all three-candle fair value gaps and their fill state.

    Args:
        highs: Candle high prices, oldest first.
        lows: Candle low prices, oldest first (same length as ``highs``).

    Returns:
        Fair value gaps in chronological order. ``filled`` is True if any later
        candle has fully closed the gap (traded through the far boundary).
    """
    gaps: list[FairValueGap] = []
    n = len(highs)

    for i in range(1, n - 1):
        # Bullish FVG: gap between candle i-1 high and candle i+1 low.
        if lows[i + 1] > highs[i - 1]:
            top, bottom, kind = lows[i + 1], highs[i - 1], "bullish"
        # Bearish FVG: gap between candle i+1 high and candle i-1 low.
        elif highs[i + 1] < lows[i - 1]:
            top, bottom, kind = lows[i - 1], highs[i + 1], "bearish"
        else:
            continue

        # Fill check: a bullish gap fills when a later low pierces ``bottom``;
        # a bearish gap fills when a later high pierces ``top``.
        filled = False
        filled_index: int | None = None
        for k in range(i + 2, n):
            if (kind == "bullish" and lows[k] <= bottom) or (
                kind == "bearish" and highs[k] >= top
            ):
                filled = True
                filled_index = k
                break

        gaps.append(
            FairValueGap(index=i, top=top, bottom=bottom, kind=kind,
                         filled=filled, filled_index=filled_index)
        )

    return gaps
