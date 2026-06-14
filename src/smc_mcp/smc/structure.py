"""Market structure detection: swing points, BOS, and CHoCH.

The smart-money-concepts (SMC) reading of price action is built on *market
structure* — the sequence of swing highs and swing lows. From that sequence we
derive two key events:

- **BOS (Break of Structure):** price breaks a swing point *in the direction of
  the existing trend* — a continuation signal.
- **CHoCH (Change of Character):** price breaks a swing point *against* the
  existing trend — the first hint of a possible reversal.

These same swings are the foundation the order-block and liquidity modules build
on, so this module is intentionally dependency-light and pure-Python over plain
lists/arrays. Pass in OHLC arrays; get back structured results.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal


@dataclass
class SwingPoint:
    """A confirmed swing high or swing low."""

    index: int
    price: float
    kind: Literal["high", "low"]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StructureEvent:
    """A break of structure (BOS) or change of character (CHoCH)."""

    index: int                       # candle index where the break was confirmed
    price: float                     # the swing level that was broken
    event: Literal["BOS", "CHoCH"]
    direction: Literal["bullish", "bearish"]

    def to_dict(self) -> dict:
        return asdict(self)


def find_swings(
    highs: list[float],
    lows: list[float],
    lookback: int = 2,
) -> list[SwingPoint]:
    """Detect swing highs and lows using a symmetric fractal of size ``lookback``.

    A swing high at index ``i`` is a candle whose high is strictly greater than
    the highs of the ``lookback`` candles on either side. Swing lows are the
    mirror image. ``lookback=2`` is the classic Williams fractal and a sensible
    default; raise it to filter out minor swings on noisy timeframes.

    Args:
        highs: Candle high prices, oldest first.
        lows: Candle low prices, oldest first (same length as ``highs``).
        lookback: Number of candles required on each side. Must be >= 1.

    Returns:
        Swing points in chronological order. Highs and lows may interleave in
        any order depending on the price action.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    n = len(highs)
    swings: list[SwingPoint] = []
    for i in range(lookback, n - lookback):
        is_high = all(
            highs[i] > highs[i - j] and highs[i] > highs[i + j]
            for j in range(1, lookback + 1)
        )
        if is_high:
            swings.append(SwingPoint(index=i, price=highs[i], kind="high"))
            continue  # a single candle is not both a high and a low
        is_low = all(
            lows[i] < lows[i - j] and lows[i] < lows[i + j]
            for j in range(1, lookback + 1)
        )
        if is_low:
            swings.append(SwingPoint(index=i, price=lows[i], kind="low"))
    return swings


def detect_structure(
    closes: list[float],
    swings: list[SwingPoint],
    lookback: int = 2,
) -> tuple[list[StructureEvent], Literal["bullish", "bearish", "neutral"]]:
    """Walk forward through closes and label each structure break as BOS or CHoCH.

    The logic tracks the most recent *confirmed* swing high and swing low. When a
    candle closes beyond one of them, it is a structure break; whether it counts
    as BOS (with-trend) or CHoCH (counter-trend) depends on the trend that was in
    force just before the break.

    A swing at index ``j`` is only treated as known once ``lookback`` further
    candles have formed (i.e. from candle ``j + lookback`` onward), which avoids
    look-ahead bias — you could not have seen the swing in real time before its
    fractal completed.

    Args:
        closes: Candle close prices, oldest first.
        swings: Output of :func:`find_swings` for the same series.
        lookback: The same fractal size passed to :func:`find_swings`, used to
            delay each swing's confirmation realistically.

    Returns:
        A tuple of (events in chronological order, current trend bias). Bias is
        "neutral" until the first structure break establishes a direction.
    """
    events: list[StructureEvent] = []
    trend: Literal["bullish", "bearish", "neutral"] = "neutral"

    # Most recent confirmed swing levels available *as of* a given candle.
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    swing_cursor = 0
    n = len(closes)

    for i in range(n):
        # Promote swings only once their fractal has fully formed (index +
        # lookback <= i), so we never use information from the future.
        while (
            swing_cursor < len(swings)
            and swings[swing_cursor].index + lookback <= i
        ):
            sp = swings[swing_cursor]
            if sp.kind == "high":
                last_high = sp
            else:
                last_low = sp
            swing_cursor += 1

        # Bullish break: close above the last swing high.
        if last_high is not None and closes[i] > last_high.price:
            event = "BOS" if trend == "bullish" else "CHoCH"
            events.append(
                StructureEvent(index=i, price=last_high.price,
                               event=event, direction="bullish")
            )
            trend = "bullish"
            last_high = None  # consumed; wait for a new swing high to form

        # Bearish break: close below the last swing low.
        elif last_low is not None and closes[i] < last_low.price:
            event = "BOS" if trend == "bearish" else "CHoCH"
            events.append(
                StructureEvent(index=i, price=last_low.price,
                               event=event, direction="bearish")
            )
            trend = "bearish"
            last_low = None

    return events, trend
