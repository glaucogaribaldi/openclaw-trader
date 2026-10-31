"""
回测引擎
"""
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from .decision import V3StrategyParams, compute_signals
from .indicators import atr as compute_atr


@dataclass
class Trade:
    """单笔交易记录"""
    entry_idx: int
    entry_price: float
    direction: int              # 1=多, -1=空
    margin: float               # 保证金
    leverage: float
    exit_idx: Optional[int] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    trailing_high: Optional[float] = None
    trailing_low: Optional[float] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    roll_count: int = 0         # 滚仓次数


@dataclass
class BacktestResult:
    """回测结果"""
    trades: list = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    blowup_count: int = 0
    total_deposited: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "total_return": round(self.total_return, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "total_trades": self.total_trades,
            "avg_trade_pnl": round(self.avg_trade_pnl, 4),
            "avg_win": round(self.avg_win, 4),
            "avg_loss": round(self.avg_loss, 4),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "blowup_count": self.blowup_count,
            "total_deposited": round(self.total_deposited, 2),
        }
