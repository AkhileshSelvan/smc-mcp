"""smc_mcp — a Model Context Protocol server for smart-money-concepts analysis.

Gives any MCP client (Claude Desktop, Claude Code, Cursor, ...) the ability to
read price action the way a smart-money trader does: market structure (BOS /
CHoCH), order blocks, fair value gaps, and liquidity sweeps — for stocks, forex,
gold, indices, and crypto, with no API key.

Run locally over stdio:  ``python -m smc_mcp``
"""

from __future__ import annotations

import json
from enum import Enum

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from .data import fetch_candles, Candles
from .smc import (
    find_swings,
    detect_structure,
    find_order_blocks,
    find_fair_value_gaps,
    find_liquidity_sweeps,
)

mcp = FastMCP("smc_mcp")

# --------------------------------------------------------------------------- #
# Shared input pieces                                                         #
# --------------------------------------------------------------------------- #


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class _BaseInput(BaseModel):
    """Common parameters shared by every analysis tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    symbol: str = Field(
        ...,
        description="Ticker or trader shorthand. Examples: 'AAPL', 'XAUUSD', "
        "'EURUSD', 'BTCUSD', 'SPX'.",
        min_length=1, max_length=20,
    )
    interval: str = Field(
        default="1h",
        description="Candle size: '5m','15m','30m','1h','1d','1wk'. Intraday "
        "history is limited by the data provider.",
    )
    limit: int = Field(
        default=300,
        description="Number of most-recent candles to analyze.",
        ge=20, le=1000,
    )
    lookback: int = Field(
        default=2,
        description="Fractal size for swing detection. Higher = fewer, major "
        "swings only.",
        ge=1, le=10,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' for a human-readable read, 'json' for "
        "machine-readable zones.",
    )


def _err(symbol: str, exc: Exception) -> str:
    return (
        f"Error analyzing '{symbol}': {exc}\n\n"
        "Tips: verify the symbol, try a larger interval (e.g. '1d'), or reduce "
        "'limit'. Intraday data only goes back a limited window."
    )


def _load(params: _BaseInput) -> Candles:
    return fetch_candles(params.symbol, params.interval, params.limit)


def _ts(candles: Candles, idx: int) -> str:
    """Human-readable timestamp for a candle index, guarding bounds."""
    return candles.timestamps[idx] if 0 <= idx < len(candles.timestamps) else "?"


# --------------------------------------------------------------------------- #
# Tools                                                                       #
# --------------------------------------------------------------------------- #


@mcp.tool(
    name="smc_get_market_structure",
    annotations={
        "title": "Market Structure (BOS / CHoCH)",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def smc_get_market_structure(params: _BaseInput) -> str:
    """Read market structure: swing points, BOS/CHoCH events, and trend bias.

    Returns the chronological sequence of structure breaks and the current
    directional bias (bullish / bearish / neutral) for the requested instrument
    and timeframe.

    Returns (JSON mode): {"symbol", "interval", "bias",
        "events": [{"index","price","event","direction","time"}],
        "swing_count"}.
    """
    try:
        c = _load(params)
        swings = find_swings(c.highs, c.lows, params.lookback)
        events, bias = detect_structure(c.closes, swings, params.lookback)
    except Exception as e:  # noqa: BLE001 - surface a helpful message to the agent
        return _err(params.symbol, e)

    if params.response_format is ResponseFormat.JSON:
        return json.dumps({
            "symbol": c.symbol, "interval": c.interval, "bias": bias,
            "swing_count": len(swings),
            "events": [{**e.to_dict(), "time": _ts(c, e.index)} for e in events],
        }, indent=2)

    lines = [
        f"# Market structure — {c.symbol} ({c.interval})",
        f"**Current bias:** {bias.upper()}  ·  {len(swings)} swings  ·  "
        f"{len(c)} candles\n",
    ]
    if not events:
        lines.append("_No structure breaks in this window._")
    for e in events[-12:]:
        arrow = "▲" if e.direction == "bullish" else "▼"
        lines.append(
            f"- {arrow} **{e.event}** {e.direction} @ {e.price:.5g} "
            f"({_ts(c, e.index)})"
        )
    return "\n".join(lines)


@mcp.tool(
    name="smc_find_order_blocks",
    annotations={
        "title": "Order Blocks",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def smc_find_order_blocks(params: _BaseInput) -> str:
    """Find order blocks — the last opposite candle before a structure break.

    Each block is the institutional footprint before an impulsive move, reported
    with its zone (top/bottom), direction, and whether price has since mitigated
    (revisited) it. Unmitigated blocks are the ones traders usually watch.

    Returns (JSON mode): {"symbol","interval",
        "order_blocks": [{"index","top","bottom","kind","break_index",
        "mitigated","mitigated_index","time"}]}.
    """
    try:
        c = _load(params)
        swings = find_swings(c.highs, c.lows, params.lookback)
        events, _ = detect_structure(c.closes, swings, params.lookback)
        blocks = find_order_blocks(c.opens, c.highs, c.lows, c.closes, events)
    except Exception as e:  # noqa: BLE001
        return _err(params.symbol, e)

    if params.response_format is ResponseFormat.JSON:
        return json.dumps({
            "symbol": c.symbol, "interval": c.interval,
            "order_blocks": [
                {**b.to_dict(), "time": _ts(c, b.index)} for b in blocks
            ],
        }, indent=2)

    lines = [f"# Order blocks — {c.symbol} ({c.interval})\n"]
    if not blocks:
        lines.append("_No structure-backed order blocks in this window._")
    for b in blocks[-12:]:
        state = "mitigated" if b.mitigated else "**unmitigated**"
        arrow = "▲" if b.kind == "bullish" else "▼"
        lines.append(
            f"- {arrow} {b.kind} OB  {b.bottom:.5g} – {b.top:.5g}  "
            f"({state}, formed {_ts(c, b.index)})"
        )
    return "\n".join(lines)


@mcp.tool(
    name="smc_find_fair_value_gaps",
    annotations={
        "title": "Fair Value Gaps",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def smc_find_fair_value_gaps(params: _BaseInput) -> str:
    """Find fair value gaps — three-candle imbalances price tends to rebalance.

    Reports each gap's zone, direction, and whether it has been filled. Unfilled
    gaps act as magnets and make natural entry or target zones.

    Returns (JSON mode): {"symbol","interval",
        "fair_value_gaps": [{"index","top","bottom","kind","filled",
        "filled_index","time"}]}.
    """
    try:
        c = _load(params)
        gaps = find_fair_value_gaps(c.highs, c.lows)
    except Exception as e:  # noqa: BLE001
        return _err(params.symbol, e)

    if params.response_format is ResponseFormat.JSON:
        return json.dumps({
            "symbol": c.symbol, "interval": c.interval,
            "fair_value_gaps": [
                {**g.to_dict(), "time": _ts(c, g.index)} for g in gaps
            ],
        }, indent=2)

    unfilled = [g for g in gaps if not g.filled]
    lines = [
        f"# Fair value gaps — {c.symbol} ({c.interval})",
        f"{len(gaps)} total · {len(unfilled)} unfilled\n",
    ]
    for g in (unfilled or gaps)[-12:]:
        state = "filled" if g.filled else "**open**"
        arrow = "▲" if g.kind == "bullish" else "▼"
        lines.append(
            f"- {arrow} {g.kind} FVG  {g.bottom:.5g} – {g.top:.5g}  "
            f"({state}, {_ts(c, g.index)})"
        )
    return "\n".join(lines)


@mcp.tool(
    name="smc_find_liquidity_sweeps",
    annotations={
        "title": "Liquidity Sweeps",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def smc_find_liquidity_sweeps(params: _BaseInput) -> str:
    """Find liquidity sweeps — swing highs/lows wicked through and rejected.

    A sweep takes stops resting beyond an obvious swing, then price closes back
    on the original side. Often precedes a reversal, and distinct from a BOS
    (which closes *through* the level).

    Returns (JSON mode): {"symbol","interval",
        "liquidity_sweeps": [{"index","swept_level","swept_swing_index",
        "kind","time"}]}.
    """
    try:
        c = _load(params)
        swings = find_swings(c.highs, c.lows, params.lookback)
        sweeps = find_liquidity_sweeps(c.highs, c.lows, c.closes, swings)
    except Exception as e:  # noqa: BLE001
        return _err(params.symbol, e)

    if params.response_format is ResponseFormat.JSON:
        return json.dumps({
            "symbol": c.symbol, "interval": c.interval,
            "liquidity_sweeps": [
                {**s.to_dict(), "time": _ts(c, s.index)} for s in sweeps
            ],
        }, indent=2)

    lines = [f"# Liquidity sweeps — {c.symbol} ({c.interval})\n"]
    if not sweeps:
        lines.append("_No liquidity sweeps in this window._")
    for s in sweeps[-12:]:
        side = "sell-side (high taken)" if s.kind == "bearish" else \
               "buy-side (low taken)"
        lines.append(f"- {s.kind} sweep — {side} @ {s.swept_level:.5g} "
                     f"({_ts(c, s.index)})")
    return "\n".join(lines)


@mcp.tool(
    name="smc_full_analysis",
    annotations={
        "title": "Full SMC Read",
        "readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True,
    },
)
async def smc_full_analysis(params: _BaseInput) -> str:
    """Run every SMC tool and return one combined, plain-English read.

    Combines market structure, order blocks, fair value gaps, and liquidity
    sweeps into a single narrative plus the current price and bias — the fastest
    way to get a complete picture in one call.

    Returns (JSON mode): {"symbol","interval","last_price","bias",
        "events","order_blocks","fair_value_gaps","liquidity_sweeps"} where each
        list matches the per-tool JSON schema.
    """
    try:
        c = _load(params)
        swings = find_swings(c.highs, c.lows, params.lookback)
        events, bias = detect_structure(c.closes, swings, params.lookback)
        blocks = find_order_blocks(c.opens, c.highs, c.lows, c.closes, events)
        gaps = find_fair_value_gaps(c.highs, c.lows)
        sweeps = find_liquidity_sweeps(c.highs, c.lows, c.closes, swings)
    except Exception as e:  # noqa: BLE001
        return _err(params.symbol, e)

    last = c.closes[-1]

    if params.response_format is ResponseFormat.JSON:
        return json.dumps({
            "symbol": c.symbol, "interval": c.interval,
            "last_price": last, "bias": bias,
            "events": [{**e.to_dict(), "time": _ts(c, e.index)} for e in events],
            "order_blocks": [
                {**b.to_dict(), "time": _ts(c, b.index)} for b in blocks],
            "fair_value_gaps": [
                {**g.to_dict(), "time": _ts(c, g.index)} for g in gaps],
            "liquidity_sweeps": [
                {**s.to_dict(), "time": _ts(c, s.index)} for s in sweeps],
        }, indent=2)

    unmit = [b for b in blocks if not b.mitigated]
    open_fvg = [g for g in gaps if not g.filled]
    last_event = events[-1] if events else None

    lines = [
        f"# SMC read — {c.symbol} ({c.interval})",
        f"**Last price:** {last:.5g}  ·  **Bias:** {bias.upper()}\n",
        "## Structure",
    ]
    if last_event:
        lines.append(
            f"Most recent: **{last_event.event} {last_event.direction}** @ "
            f"{last_event.price:.5g} ({_ts(c, last_event.index)})."
        )
    else:
        lines.append("No structure breaks in this window.")

    lines.append("\n## Unmitigated order blocks")
    if unmit:
        for b in unmit[-4:]:
            arrow = "▲" if b.kind == "bullish" else "▼"
            lines.append(f"- {arrow} {b.kind}  {b.bottom:.5g} – {b.top:.5g}")
    else:
        lines.append("None — all order blocks have been mitigated.")

    lines.append("\n## Open fair value gaps")
    if open_fvg:
        for g in open_fvg[-4:]:
            arrow = "▲" if g.kind == "bullish" else "▼"
            lines.append(f"- {arrow} {g.kind}  {g.bottom:.5g} – {g.top:.5g}")
    else:
        lines.append("None — no open imbalances.")

    lines.append("\n## Recent liquidity sweeps")
    if sweeps:
        for s in sweeps[-3:]:
            lines.append(f"- {s.kind} sweep @ {s.swept_level:.5g} "
                         f"({_ts(c, s.index)})")
    else:
        lines.append("None detected.")

    lines.append(
        "\n_Analysis only — not financial advice. Validate on your own charts._"
    )
    return "\n".join(lines)


def main() -> None:
    """Entry point for ``python -m smc_mcp`` and the ``smc-mcp`` script."""
    mcp.run()


if __name__ == "__main__":
    main()
