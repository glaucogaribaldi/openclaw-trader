# Parameters

## Defaults
- timeframe: `4h`
- macd_fast: `12`
- macd_slow: `26`
- macd_signal: `9`
- macd_abs_entry_min: typically `150` for BTC-like high-vol symbols (tune per symbol)
- one_signal_per_candle: `true`

## Symbol-level examples
- BTC swap: `macd_abs_entry_min` usually higher (100~200)
- PAXG swap: lower threshold often needed (10~40)

## Position sizing
- target_notional = `position_margin_usdt * leverage`
- open amount = `target_notional / reference_price`
- use precision from exchange market metadata

## Close policy
- if pivot appears but entry side not eligible -> close existing position (full)
- manual override paths (user explicit request) can bypass signal gate

## Rejection handling
- max position / leverage constraint: return code and current position snapshot
- reduce-only mismatch: correct side/flag and retry once at most
