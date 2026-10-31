---
name: okx-eea-futures-and-funding
description: Use when trading OKX Europe (eea.okx.com), fixing empty Trading balances, or resolving code 50124 on SWAP; trades regulated USD_UM_XPERP futures.
---

# OKX Europe (EEA) Perpetual Futures (USD_UM_XPERP) & Funding Account Transfer

Use this procedure when working with OKX Europe (https://eea.okx.com) REST v5 APIs for perpetual futures or account balance checks.

## 1. Check Both Trading (18) and Funding (6) Balances

When GET /api/v5/account/balance returns empty details ([]) or zero equity, check the Funding Account (6) because OKX sweeps can move idle USDC out of the Trading Account (18).

1. Query both endpoints:
   - Trading Account (18): GET /api/v5/account/balance
   - Funding Account (6): GET /api/v5/asset/balances
2. Verify recent internal transfers if needed via GET /api/v5/asset/bills.
3. To make funds available for order placement, transfer USDC from Funding (6) to Trading (18) via POST /api/v5/asset/transfer with body {"ccy": "USDC", "amt": "<amount>", "from": "6", "to": "18"}.
4. Re-check GET /api/v5/account/balance and confirm details lists the USDC balance (availBal > 0).

## 2. Discover Regulated EEA Perpetual Futures (instType=FUTURES, ruleType=xperp)

On OKX Europe (https://eea.okx.com under MiCA/MiFID II), standard instType=SWAP (*-USDT-SWAP and *-USD-SWAP) returns code 50124 ("This API Key does not have trading permission for the market") and maxBuy="0". Regulated European perpetual futures are listed under instType=FUTURES with ruleType="xperp" (*-USD_UM_XPERP-*), settled 1:1 against USDC (settleCcy="USD").

1. Query GET /api/v5/public/instruments?instType=FUTURES and filter for live xperp contracts (e.g., BTC-USD_UM_XPERP-310404, ETH-USD_UM_XPERP-310404, SOL-USD_UM_XPERP-310404) where ruleType == "xperp" and state == "live".
2. Inspect each contract's sizing fields before placing orders because sz is in contracts, not base units (including commodity/macro XPERP contracts such as `XAU-USD_UM_XPERP-310502` Gold with `ctVal=0.001, tickSz=0.1` and `CL-USD_UM_XPERP-310509` WTI Crude Oil with `ctVal=0.1, tickSz=0.01`):
   - ctVal: base units per contract (e.g., 0.0001 BTC, 0.01 SOL, 0.001 XAU, 0.1 CL, 1 SUI/XRP/NEAR, 10 DOGE/AVAX/FET/SEI)
   - minSz, lotSz, tickSz, and max lever
3. Check fee tier with GET /api/v5/account/trade-fee?instType=FUTURES (typically maker: -0.0002 / 2 bps, taker: -0.0005 / 5 bps).
4. For HTTP error inspection in Python requests, use resp.text if resp is not None else str(e) rather than bool(resp) because Response.__bool__() evaluates to False on HTTP 4xx/5xx.

## 3. Configure Leverage and Verify Buying Power on *-USD_UM_XPERP-*

1. Set isolated or cross leverage on the exact *-USD_UM_XPERP-* instId via POST /api/v5/account/set-leverage with {"instId": "SOL-USD_UM_XPERP-310404", "lever": "2.5", "mgnMode": "isolated"}.
2. Verify buying/selling capacity in contracts via GET /api/v5/account/max-size?instId=SOL-USD_UM_XPERP-310404&tdMode=isolated and confirm maxBuy > 0 and maxSell > 0.
3. Place and cancel a far-from-mid post_only order via POST /api/v5/trade/order (tdMode="isolated", ordType="post_only") and POST /api/v5/trade/cancel-order to confirm sCode="0".

## 4. Calculate Contract Size and Reconcile Live XPERP Positions

1. Convert target USD notional into contract count sz using ctVal and lotSz because XPERP order sz is in contracts (`raw_contracts = notional_usd / (px * ctVal)`, rounded to lotSz decimals and clamped to `>= minSz`).
2. Query open positions and pending orders with `instType=FUTURES` (`GET /api/v5/account/positions?instType=FUTURES` and `GET /api/v5/trade/orders-pending?instType=FUTURES`) rather than `instType=SWAP`.
3. Do not insert a `post_only` entry order into local open positions until `GET /api/v5/account/positions?instType=FUTURES` reports `abs(float(pos)) > 0`, and count live `orders-pending` toward your concurrency/slot limit so multiple orders do not fire in the same cycle before filling.
4. Import any live exchange position (`abs(float(pos)) > 0`) missing from local state using its `avgPx`, `pos` sign (`>0` LONG, `<0` SHORT), `margin`, and trailing/shield flags initialized to `0` (disarmed) so the next cycle does not immediately trigger a false protective exit.
5. Attach exchange-native take-profit and stop-loss triggers directly inside every entry `POST /api/v5/trade/order` payload via `"attachAlgoOrds": [{"tpTriggerPx": "<tp_px>", "tpOrdPx": "-1", "tpTriggerPxType": "last", "slTriggerPx": "<sl_px>", "slOrdPx": "-1", "slTriggerPxType": "last"}]` so OKX's matching engine enforces the hard stop even if the client host goes offline.
6. When a previously open position disappears from `GET /api/v5/account/positions?instType=FUTURES` (closed by exchange-side `attachAlgoOrds` or a software `reduceOnly` order), do not delete the local row; match its latest filled `reduceOnly="true"` order in `GET /api/v5/trade/orders-history?instType=FUTURES` and update the row to closed with the exchange's `avgPx`, `pnl`, and `fee` so post-stop cooldowns trigger and realized PnL matches exchange equity.
7. To ratchet the exchange-side stop-loss to break-even once a position reaches profit, query `GET /api/v5/trade/orders-algo-pending?instType=FUTURES&ordType=conditional,oco&instId=<instId>` to get the active `algoId`, then call `POST /api/v5/trade/amend-algos` with `{"instId": "<instId>", "algoId": "<algoId>", "newSlTriggerPx": "<breakeven_px>"}` and verify `sCode == "0"`.
8. To read Open Interest deltas on EEA XPERP contracts, call `GET /api/v5/public/open-interest?instType=FUTURES&instId=<instId>` (`instType=FUTURES`, not `SWAP`) and compare `oi` against a 15-minute rolling anchor `(anchor_ts, anchor_oi)` rather than the previous 15-second poll because OKX updates public Open Interest every 1–5 minutes.