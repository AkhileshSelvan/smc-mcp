"""Market data access.

Thin wrapper over yfinance that returns clean OHLCV arrays for stocks, indices,
forex, gold, and crypto — no API key required. The friendly-symbol helper lets
users write ``XAUUSD`` or ``EURUSD`` instead of yfinance's ``XAUUSD=X`` quirks.

If you later want tick-level forex or broker data (e.g. MT5), this is the single
module to swap out; nothing else in the package touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

# Map common trader shorthand to yfinance tickers.
_FOREX_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY",
}
_FRIENDLY = {
    "XAUUSD": "GC=F",   # gold futures (continuous)
    "GOLD": "GC=F",
    "XAGUSD": "SI=F",   # silver
    "WTI": "CL=F",      # crude oil
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SPX": "^GSPC",
    "NAS100": "^NDX",
    "US30": "^DJI",
}

# yfinance accepts these interval strings; map a few friendly aliases.
_VALID_INTERVALS = {
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h",
    "1d", "5d", "1wk", "1mo", "3mo",
}


@dataclass
class Candles:
    """OHLCV series as parallel lists, oldest first."""

    symbol: str
    interval: str
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
    timestamps: list[str]

    def __len__(self) -> int:
        return len(self.closes)


def normalize_symbol(symbol: str) -> str:
    """Translate trader shorthand into a yfinance-compatible ticker.

    Examples: ``XAUUSD`` -> ``GC=F``, ``EURUSD`` -> ``EURUSD=X``,
    ``BTCUSD`` -> ``BTC-USD``. Anything already valid (e.g. ``AAPL``) passes
    through unchanged.
    """
    s = symbol.strip().upper()
    if s in _FRIENDLY:
        return _FRIENDLY[s]
    if s in _FOREX_PAIRS:
        return f"{s}=X"
    return symbol.strip()


def fetch_candles(symbol: str, interval: str = "1h", limit: int = 300) -> Candles:
    """Fetch recent OHLCV candles for ``symbol``.

    Args:
        symbol: Ticker or trader shorthand (e.g. ``AAPL``, ``XAUUSD``,
            ``EURUSD``, ``BTCUSD``). Normalized via :func:`normalize_symbol`.
        interval: Candle size (e.g. ``5m``, ``15m``, ``1h``, ``1d``). yfinance
            limits how far intraday data goes back.
        limit: Maximum number of most-recent candles to return (1-1000).

    Returns:
        A :class:`Candles` object with parallel OHLCV arrays, oldest first.

    Raises:
        ValueError: If the interval is invalid or no data is returned (bad
            symbol, market closed with no history, or interval/range mismatch).
    """
    interval = "60m" if interval == "1h" else interval
    if interval not in _VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval '{interval}'. Valid: {sorted(_VALID_INTERVALS)}"
        )
    limit = max(1, min(int(limit), 1000))

    ticker = normalize_symbol(symbol)
    # Pick a period generous enough to yield `limit` candles for this interval.
    period = _period_for(interval, limit)
    df = yf.download(
        ticker, period=period, interval=interval,
        auto_adjust=False, progress=False,
    )
    if df is None or df.empty:
        raise ValueError(
            f"No data for '{symbol}' (resolved to '{ticker}') at interval "
            f"'{interval}'. Check the symbol, or try a larger interval — "
            f"intraday history is limited by the data provider."
        )

    # yfinance may return a MultiIndex column frame for a single ticker.
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    df = df.tail(limit)
    return Candles(
        symbol=ticker,
        interval=interval,
        opens=[float(x) for x in df["Open"]],
        highs=[float(x) for x in df["High"]],
        lows=[float(x) for x in df["Low"]],
        closes=[float(x) for x in df["Close"]],
        volumes=[float(x) for x in df["Volume"]],
        timestamps=[str(t) for t in df.index],
    )


def _period_for(interval: str, limit: int) -> str:
    """Choose a yfinance ``period`` large enough to cover ``limit`` candles."""
    if interval.endswith("m") or interval in {"60m", "90m", "1h"}:
        # Intraday: yfinance caps history (~60d for minutes). Stay within it.
        if interval in {"1m", "2m"}:
            return "7d"
        if interval in {"5m", "15m", "30m"}:
            return "60d"
        return "60d"  # 60m / 90m
    if interval in {"1d", "5d"}:
        return "2y" if limit > 250 else "1y"
    return "10y"  # weekly / monthly
