---
name: dragon-regret
description: Use when analyzing, tuning, backtesting, or extending the Dragon's Regret mean-reversion strategy, especially for ATR/z-score normalized entry logic, higher-timeframe trend filtering, execution-cost modeling, parameter scans, and walk-forward validation.
---

# 亢龙有悔 (Dragon's Regret)

This publishable skill package includes these core files:

- `spring_reversion_strategy.py`
- `tests/test_spring_reversion_strategy.py`

Use this skill when working on the included Dragon's Regret strategy or when porting the same workflow to another workspace.

## What This Strategy Does

- Trades short-term mean reversion, typically on `BTC/USDT 15m`
- Uses normalized exhaustion signals instead of a fixed candle percent trigger
- Requires `body_atr_ratio`, `return_zscore`, `RSI`, `volume spike`, and `momentum deceleration`
- Uses a higher-timeframe regime filter to avoid fading strong trends
- Models maker/taker fees and slippage in both realized PnL and equity curve
- Supports `run_backtest()`, `run_parameter_scan()`, and `run_walk_forward()`

## Default Workflow

1. Read `spring_reversion_strategy.py` first to confirm config keys, signal flow, execution-cost assumptions, and state transitions.
2. If the task changes behavior, update `tests/test_spring_reversion_strategy.py` in the same package.
3. Validate with:

```bash
python3 -m unittest -q tests/test_spring_reversion_strategy.py
```

4. Only move from backtest to live data or trading after checking risk rules and tool availability.

## OKX Integration

Prefer MCP tools when they are available in the current Codex session.

### Market Data

- If a tool named `okx-cex-market` is available, use it for read-only tasks first:
  - latest ticker
  - order book
  - recent candles / OHLCV
  - funding or mark-price context if supported
- Convert live market data into the same schema expected by `spring_reversion_strategy.py` before running signal checks or backtests.

### Trading

- If a tool named `okx-cex-trade` is available, use it only after:
  - the strategy has been backtested
  - the user explicitly asks for live or paper execution
  - current credentials and account mode are confirmed
- Default to paper / simulated execution when the tool supports it.
- Never place live orders silently.

### CLI Fallback

If MCP tools are unavailable but OpenClaw CLI is installed, inspect available integrations first and do not invent flags. In OpenClaw environments, relevant plugin surfaces may appear as `OpenClaw Trading` and `OKX Trade MCP`.

```bash
openclaw plugins list
openclaw docs okx
openclaw docs trading
```

If neither MCP tools nor a documented CLI integration is available, stop at analysis/backtest mode and report the missing OKX execution surface.

### Credentials

Authenticated OKX workflows may require environment variables such as:

- `OKX_API_KEY`
- `OKX_SECRET_KEY`
- `OKX_PASSPHRASE`

Do not print secret values, do not hardcode them, and do not proceed with authenticated trading if they are missing.

## Implementation Guardrails

- Do not reintroduce a fixed `5%` candle trigger. Entry logic should stay normalized around `body_atr_ratio` and `return_zscore`.
- Keep realized PnL, unrealized PnL, and equity curve on the same execution-cost model.
- Do not bypass the higher-timeframe trend filter unless explicitly requested.
- Keep strategy-core functions deterministic. Avoid network calls or exchange-specific live execution logic inside the backtest core.
- Preserve isolated state resets so parameter scans and walk-forward runs do not leak positions, balances, or trade logs across runs.

## Change Map

- Signal logic: indicator calculation and entry checks
- Position sizing and execution costs: sizing, slippage, maker/taker fees, open/close accounting
- Exit logic: ATR stop, trailing logic, and time stop
- Analytics: backtest, parameter scan, walk-forward, export helpers

## Trading Risk Notice

- This strategy can lose money in persistent trends, thin liquidity, fast gaps, and execution-quality degradation.
- Backtest results do not guarantee live performance.
- Live trading should be treated as high risk even when walk-forward results look acceptable.
- If execution is requested, enforce small size, clear stop logic, and explicit user confirmation before order placement.

## Expected Outputs

When asked for analysis, report:

- current signal definition
- trend filter behavior
- execution-cost assumptions
- backtest or walk-forward validity
- missing risks, fragile assumptions, or accounting inconsistencies

When asked for code changes, aim for:

- atomic diffs
- matching test updates
- deterministic outputs
- no silent changes to accounting or performance metric definitions
