"""
汪汪汪·V3稳健趋势策略

Usage:
    from strategy import V3StrategyParams, run_backtest, compute_signals
    params = V3StrategyParams.from_json("config/v3_default.json")
"""
from .decision import V3StrategyParams, compute_signals
from .backtest import run_backtest
from .engine import BacktestResult, Trade
from .indicators import ema, sma, rsi, macd, bollinger_bands, atr, adx, supertrend

__all__ = [
    "V3StrategyParams",
    "compute_signals",
    "run_backtest",
    "BacktestResult",
    "Trade",
    "ema", "sma", "rsi", "macd", "bollinger_bands", "atr", "adx", "supertrend",
]
