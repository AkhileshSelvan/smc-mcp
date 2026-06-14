"""Core smart-money-concepts analysis primitives.

Pure functions over OHLC arrays — no MCP, no I/O — so they can be unit-tested,
reused in a backtester, or wrapped by any interface.
"""

from .structure import (
    SwingPoint,
    StructureEvent,
    find_swings,
    detect_structure,
)
from .order_blocks import OrderBlock, find_order_blocks
from .fvg import FairValueGap, find_fair_value_gaps
from .liquidity import LiquiditySweep, find_liquidity_sweeps

__all__ = [
    "SwingPoint",
    "StructureEvent",
    "find_swings",
    "detect_structure",
    "OrderBlock",
    "find_order_blocks",
    "FairValueGap",
    "find_fair_value_gaps",
    "LiquiditySweep",
    "find_liquidity_sweeps",
]
