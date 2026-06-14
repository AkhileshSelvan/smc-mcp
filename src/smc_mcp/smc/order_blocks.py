"""Order block detection.

An **order block** is the last opposite-colour candle before an impulsive move
that breaks structure — the footprint institutions leave when they fill orders
before driving price away. A *bullish* order block is the last down-candle before
an up-move that breaks a swing high; a *bearish* order block is the last
up-candle before a down-move that breaks a swing low.

This module ties order blocks to the structure breaks produced by
``structure.detect_structure`` so that only blocks backed by a genuine
displacement are returned, and reports whether each block has since been
*mitigated* (revisited by price).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from .structure import StructureEvent


@dataclass
class OrderBlock:
    """A zone left by the last opposite candle before a structure break."""

    index: int                                  # candle that forms the block
    top: float                                  # upper bound of the zone
    bottom: float                               # lower bound of the zone
    kind: Literal["bullish", "bearish"]
    break_index: int                            # candle where structure broke
    mitigated: bool                             # has price returned into it?
    mitigated_index: int | None                 # when, if so

    def to_dict(self) -> dict:
        return asdict(self)


def find_order_blocks(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    events: list[StructureEvent],
    use_body: bool = False,
) -> list[OrderBlock]:
    """Find order blocks anchored to structure breaks.

    For each structure event, scan backwards from the breaking candle for the
    most recent candle of the opposite colour. That candle's range becomes the
    order block zone.

    Args:
        opens, highs, lows, closes: OHLC arrays, oldest first, equal length.
        events: Structure breaks from :func:`structure.detect_structure`.
        use_body: If True, the zone spans the candle body (open..close); if
            False (default) it spans the full candle range (low..high). Full
            range is more conservative and the common SMC convention.

    Returns:
        Order blocks in chronological order, each flagged with mitigation state.
    """
    blocks: list[OrderBlock] = []
    n = len(closes)

    for ev in events:
        anchor: int | None = None
        if ev.direction == "bullish":
            # last bearish (down) candle before the up-break
            for j in range(ev.index - 1, -1, -1):
                if closes[j] < opens[j]:
                    anchor = j
                    break
        else:
            # last bullish (up) candle before the down-break
            for j in range(ev.index - 1, -1, -1):
                if closes[j] > opens[j]:
                    anchor = j
                    break
        if anchor is None:
            continue

        if use_body:
            top = max(opens[anchor], closes[anchor])
            bottom = min(opens[anchor], closes[anchor])
        else:
            top = highs[anchor]
            bottom = lows[anchor]

        # Mitigation: after the break, did price trade back into the zone?
        mitigated = False
        mitigated_index: int | None = None
        for k in range(ev.index + 1, n):
            if lows[k] <= top and highs[k] >= bottom:
                mitigated = True
                mitigated_index = k
                break

        blocks.append(
            OrderBlock(
                index=anchor, top=top, bottom=bottom, kind=ev.direction,
                break_index=ev.index, mitigated=mitigated,
                mitigated_index=mitigated_index,
            )
        )

    # De-duplicate blocks that share the same anchor candle (multiple breaks can
    # point at the same originating candle); keep the earliest break.
    seen: dict[int, OrderBlock] = {}
    for b in blocks:
        if b.index not in seen or b.break_index < seen[b.index].break_index:
            seen[b.index] = b
    return sorted(seen.values(), key=lambda b: b.index)
