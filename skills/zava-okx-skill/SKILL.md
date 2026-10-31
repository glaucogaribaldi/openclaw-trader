---
name: zava-okx-skill
description: "Use when working with OKX trading, TRE OS v18.1, EEA USD_UM_XPERP futures, Spot, Grid/DCA bots, technical analysis, order execution, position sizing, smart money, sentiment, or post-trade review; master hub aggregating all 76 OKX skills (10 Official v1.5.0 + 63 Marketplace + 3 Custom EEA/TRE OS)."
---

# ZAVA OKX SKILL — Master Aggregated Quant & Execution Hub (76 Skills)

This skill is the unified master hub (`zava-okx-skill`) for Giacomo's OpenClaw & TRE OS v18.1 system on OKX Europe (`eea.okx.com` / `my.okx.com`) and Global. It aggregates **all 76 OKX skills** without omission:
- **3 Custom Zava / EEA & TRE OS Skills** (`custom/`)
- **10 Official OKX Agent Skills v1.5.0** (`official/` + `_shared/preflight.md`)
- **63 OKX Skills Marketplace Community Skills** (`marketplace/` + raw archives in `zips/`)
- **Full 930 KB Searchable Compendium**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/references/ALL_SKILLS_COMPENDIUM.md`
- **Catalog JSON Metadata**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/catalog_index.json`

---

## 1. Core Architecture & EEA Regulated Futures (`okx-eea-futures-and-funding` + `TRE OS v18.1`)

1. **Dual-Account Balance & Funding Sweep Check**:
   - Always check both Trading Account (`18`, `GET /api/v5/account/balance`) and Funding Account (`6`, `GET /api/v5/asset/balances`).
   - Transfer idle USDC from Funding (`6`) to Trading (`18`) via `POST /api/v5/asset/transfer`.
2. **EEA Regulated Perpetual Futures (`instType=FUTURES`, `ruleType=xperp`)**:
   - On OKX Europe (`https://eea.okx.com`), standard `SWAP` returns `50124`. Always use `*-USD_UM_XPERP-*` under `instType=FUTURES` settled in USDC (`settleCcy="USD"`), including crypto (`BTC`, `ETH`, `SOL`, `LINK`, `UNI`, `AVAX`, `SUI`, `XRP`, `NEAR`, `HYPE`, `ZEC`) and macro/commodities (`XAU-USD_UM_XPERP-*` Gold, `CL-USD_UM_XPERP-*` Crude Oil).
   - Convert USD notional to contracts via `ctVal`, `lotSz`, and `minSz`: `raw_contracts = notional_usd / (px * ctVal)`.
3. **TRE OS v18.1 Positive-Expectancy & Auto-Strategy Switcher Rules**:
   - **Never arm micro-shields below `+52 bps`**: Shield arms only at `>= +52.0 bps` with floor at `+32.0 bps` (guaranteeing net profit after `2 bps` Maker / `5 bps` Taker fees).
   - **Runner Trail**: Above `+85 bps` up to `+160 bps` full TP Maker. Hard stop at `-135 bps` attached natively via `attachAlgoOrds`.
   - **Single Unshielded Slot Cap & Green/Red 1h Candle Gate**: Max 1 unshielded position at a time; never short when real 1h candle > `-5.0 bps`.
   - **3-Mode Automatic Strategy Switcher (`strategy_mode`)**:
     - `TREND_SWING_RUNNER`: 7-horizon trend alignment holding for `+52..+160 bps`.
     - `SNIPER_PULLBACK_LIMIT`: Triggered automatically after 2-trade drawdown (`<= -$0.80 / -$1.20`) — enters only via discounted Limit Maker orders (`-25 bps` on LONG, `+25 bps` on SHORT) to capture wicks and save Maker fees (`okx-maker-entry`).
     - `CRISIS_RECOVERY_FORTRESS`: Operates only on Top 3 scoreboard winners with active Bollinger Squeeze (`bb-momentum-breakout`).

---

## 2. Official OKX Agent Skills Suite v1.5.0 (`official/` & `~/.openclaw/workspace/skills/`)

Requires `@okx_ai/okx-trade-cli@1.5.0` (`/Users/zava/.local/bin/okx` / `/opt/homebrew/bin/okx`). Follow `official/_shared/preflight.md` once per session:
1. `okx-cex-auth`: OAuth 2.0 device flow & `~/.okx/config.toml` profile verification (`site = "eea"`).
2. `okx-cex-market`: Read-only market data, orderbook, candles, funding rates, OI, screener, stock tokens, Gold/Oil/Forex, and 70+ indicators (`RSI`, `MACD`, `EMA`, `Bollinger`, `SuperTrend`, `KDJ`, `AHR999`).
3. `okx-cex-trade`: Spot, Swap, Futures, Options, Event Contracts, and conditional/OCO/trailing/TWAP/iceberg algo orders.
4. `okx-cex-portfolio`: Account balances, open/closed positions, PnL, bills, fee tiers (`GET /api/v5/account/trade-fee`), transfers.
5. `okx-cex-bot`: Spot/Contract Grid Bots, Spot/Contract DCA Martingale Bots, Smart Portfolio Bots.
6. `okx-cex-earn` & `earn-hunter`: Simple Earn, Flash Earn scanner, On-chain staking, Dual Investment (`DCD`), AutoEarn.
7. `okx-cex-smartmoney`: Top trader leaderboard, position conviction, long/short ratio, consensus signals, capital flow.
8. `okx-sentiment-tracker`: Crypto news, coin bull/bear sentiment, trending topics, macro economic calendar (CPI, FOMC, NFP, GDP).
9. `okx-cex-skill-mp`: OKX Skills Marketplace management & Ed25519 signature verification.

---

## 3. Best Curated Marketplace Skills for Our System (`marketplace/` & Top 20 Installed in `skills/`)

### A. Quantitative Signal & Multi-Factor Analysis
- **`kline-indicator` (Technical Analysis Master)**: 3-pillar weighted scoring (0–100) combining Macro Cycle (`AHR999`, `MVRV`, `Rainbow`) × Volume-Price (130+ WorldQuant Alpha 101/191 factors, RSI/MACD/OBV divergence, 30+ candle patterns) × Derivatives (funding depth, OI, liquidation heatmap).
- **`qtx-alpha` (QTX Quantitative Signal Engine)**: Institutional multi-factor perpetual scanner & backtester across momentum, funding dislocation, and volatility.
- **`trading-plan-generator`**: 6-dimensional signal score (`-100` to `+100`) combining OKX candles/OI/funding with long-short ratios & liquidation heatmaps; outputs 3-tier plans (Conservative, Moderate, Aggressive) with exact entry and SL levels.
- **`NeuroGrid_V4_Milestone`**: Multi-level `SuperTrend + MACD` momentum breakthrough & compounding engine.
- **`tri-asset-adaptive-fusion`**: Cross-asset horizontal scoring across **Gold (`XAU`) + `BTC` + `ETH`** using EMA trends and Bollinger Band breakouts.
- **`dragon-regret`**: ATR / z-score normalized mean-reversion entry & exit tuning.
- **`bb-momentum-breakout` & `stochrsi-mdi-trend-v1`**: Bollinger squeeze breakout confirmed by MACD, and 15-minute StochRSI + MDI divergence trend following.
- **`crypto-swing-signal-analyst` & `quadruple-filter-trend-hunter`**: EMA20/EMA60/RSI14/MACD/ATR14 swing signals and 1W/1D/4H/1H EMA30 alignment.

### B. Order Execution, Fee Reduction & Position Risk Control
- **`okx-maker-entry` (Maker Automatic Order Placement)**: Replaces taker market orders with multi-tier liquidity-scanning limit orders, eliminating taker fee drag (`2 bps` vs `5 bps`) and slippage.
- **`position-sizer` (Position Risk Control Calculator)**: Pre-trade contract count, margin, liquidation price distance check, Fixed Ratio, ATR volatility stop-loss, and fractional Kelly criterion.
- **`okx-execution-vortex`**: Safe execution actuator for OCO, trailing stop, split/iceberg orders, and position state synchronization.
- **`resilience-trader` & `okx-600u-pnl-percent-v1`**: Small-account (`250–600 USDC`) single-position risk control, drawdown circuit breakers, and capital preservation rules.
- **`rolling-position`**: Trend rolling position & pyramid add-on only from locked unrealized profit.

### C. Smart Money, Whale & Funding Arbitrage Intelligence
- **`whale-tracker`**: Institutional Order Block detection, whale sweeps, and large fill tracking.
- **`funding-rate-scanner`**: Scans all perpetuals sorted by funding rate dislocation and 8h annualized yield.
- **`market-intel` & `fear-hunter-sentiment-alpha`**: Real-time narrative surges and sentiment-funding divergence contrarian alpha.

### D. Post-Trade Audit, Loss Attribution & Counterfactual Replay
- **`okx-trade-review-suite` (Trading Review All-in-One Pro)**: 8 review dimensions — PnL attribution breakdown, fee drag ratio, equity curve playback, max drawdown, expectancy, holding time vs return.
- **`hindsight-reviewer` & `pnl-loss-reviewer`**: Counterfactual post-mortem judge (*"What if entry was discounted -25 bps / what if shield was +52 bps?"*) and loss root-cause classification.
- **`okx-review` & `okx-review-prism`**: Trade tagging by strategy mode and structured reflection.

---

## 4. How to Inspect Any of the 76 Skills in Detail

- **Single Skill Directory**:
  - Official: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/<skill-name>/SKILL.md`
  - Marketplace (all 63): `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/<skill-name>/SKILL.md`
  - Custom EEA/TRE OS: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/custom/<skill-name>/SKILL.md`
- **Search Across All 76 Skills at Once**:
  ```bash
  grep -n -C 5 "<query>" /Users/zava/.openclaw/workspace/skills/zava-okx-skill/references/ALL_SKILLS_COMPENDIUM.md
  ```
