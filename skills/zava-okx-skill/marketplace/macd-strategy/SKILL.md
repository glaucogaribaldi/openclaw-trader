---
name: macd-strategy
description: Execute OKX CEX open/close decisions using MACD pivot rules (4h, MACD 12/26/9, threshold gate, pivot-based entry/exit, one-signal-per-candle). Use when user asks to open or close positions on OKX according to this logic only (no portfolio/earn tasks). Requires OKX skills from `npx skills add okx/agent-skills` to be installed.
---

# OKX Open/Close

Apply only open/close logic. Do not handle earn, portfolio analytics, or unrelated tasks.

## Dependency
Require these skills installed from `okx/agent-skills`:
- `okx-cex-market` (candles/price data)
- `okx-cex-trade` (order execution)

If unavailable, stop and report dependency missing.

## Strategy Rules
- Timeframe: `4h`
- MACD params: `12/26/9`
- Threshold gate: `abs(hist) >= MACD_ABS_ENTRY_MIN`
- Pivot detection:
  - `peak` if `h2 > h3 and h2 > h1`
  - `valley` if `h2 < h3 and h2 < h1`
- Entry side:
  - `peak` + `hist > 0` => open short
  - `valley` + `hist < 0` => open long
- If pivot exists but entry side is not eligible => close existing position (full close).
- One signal per candle: if candle already processed, do nothing.

## Execution Workflow
1. Read symbol config (`instId`, leverage, margin USDT, threshold).
2. Pull latest 4h candles from OKX market skill.
3. Compute MACD histogram and detect pivot on closed candle.
4. Enforce one-signal-per-candle lock.
5. Determine target action:
   - no action
   - open/rebalance same direction (delta adjust)
   - flip (close opposite then open target)
   - full close
6. Execute through OKX trade skill.
7. Return concise execution result: side, qty, reference price, order id, reject code if any.

## Output Contract
Always include:
- `symbol`
- `action` (`open_long`, `open_short`, `reduce`, `close_full`, `no_action`)
- `reason` (pivot/threshold/lock)
- `order_id` (if placed)
- `error_code` and `error_message` (if failed)

## Risk/Guardrails
- Never submit duplicate order on same candle signal.
- If exchange rejects (`max position`, leverage constraint, etc.), do not loop retry.
- Report rejection and ask whether to reduce, change leverage, or skip.

## Reference
See `references/parameters.md` for default parameters and tuning ranges.
