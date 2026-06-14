# SMC-MCP — Smart-Money-Concepts for AI agents

Give Claude, Cursor, or any MCP client the ability to read price action like a
smart-money trader — **market structure (BOS / CHoCH), order blocks, fair value
gaps, and liquidity sweeps** — for stocks, forex, gold, indices, and crypto.

**No API key. No paid data feed.** Ask in plain English:

> "Run a full SMC read on XAUUSD on the 1h."
> "Are there any unmitigated bullish order blocks on EURUSD?"
> "Did BTCUSD sweep liquidity above the recent high?"

Every other finance MCP server fetches stock prices and standard indicators.
This one speaks the language traders actually use: order blocks, FVGs, BOS,
CHoCH, liquidity grabs.

---

## 30-second setup (Claude Desktop)

```bash
git clone https://github.com/YOUR_USERNAME/smc-mcp.git
cd smc-mcp
pip install -e .
```

Add this to your `claude_desktop_config.json`
(Claude → Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "smc": {
      "command": "python",
      "args": ["-m", "smc_mcp"]
    }
  }
}
```

Restart Claude Desktop. You'll see the `smc` tools appear. Done.

> Works the same in any MCP client (Cursor, Claude Code, etc.) — point it at
> `python -m smc_mcp` over stdio.

---

## Tools

| Tool | What it does |
| --- | --- |
| `smc_get_market_structure` | Swing points, BOS / CHoCH events, current trend bias |
| `smc_find_order_blocks` | Order blocks tied to structure breaks, with mitigation state |
| `smc_find_fair_value_gaps` | Three-candle imbalances and whether they're filled |
| `smc_find_liquidity_sweeps` | Swing highs/lows wicked through and rejected (stop hunts) |
| `smc_full_analysis` | All of the above in one combined, plain-English read |

Every tool accepts:

- `symbol` — `AAPL`, `XAUUSD`, `EURUSD`, `BTCUSD`, `SPX` … (trader shorthand is
  auto-translated)
- `interval` — `5m`, `15m`, `30m`, `1h`, `1d`, `1wk`
- `limit` — number of recent candles (20–1000)
- `lookback` — swing sensitivity (higher = only major swings)
- `response_format` — `markdown` (human read) or `json` (machine-readable zones)

---

## What the concepts mean

- **BOS (Break of Structure)** — price closes through a swing *with* the trend: a
  continuation signal.
- **CHoCH (Change of Character)** — price closes through a swing *against* the
  trend: the first hint of a reversal.
- **Order block** — the last opposite-colour candle before an impulsive move; an
  institutional footprint and a common entry zone.
- **Fair value gap** — a three-candle imbalance price often returns to rebalance.
- **Liquidity sweep** — a wick beyond an obvious swing that takes stops, then
  closes back (distinct from a BOS, which closes *through*).

---

## Run the tests

```bash
pip install -e ".[dev]"
python tests/test_smc.py     # or: python -m pytest tests/ -q
```

The core logic is pure Python over OHLC arrays (in `src/smc_mcp/smc/`), unit-
tested with hand-built series, and free of look-ahead bias — swings are only
used once their fractal has fully formed.

---

## Roadmap

- [ ] Multi-timeframe confluence (HTF bias + LTF entry)
- [ ] Premium/discount (equilibrium) zones
- [ ] `ccxt` data source for exchange-native crypto candles
- [ ] Optional MT5 data bridge for broker-accurate forex
- [ ] Prop-firm risk-gate tool (position size vs. drawdown rules)

Contributions and issues welcome.

---

## Disclaimer

This software provides **data analysis, not financial advice**. Markets carry
risk; validate every signal on your own charts and never trade on a tool's
output alone.

## License

MIT — see [LICENSE](LICENSE).
