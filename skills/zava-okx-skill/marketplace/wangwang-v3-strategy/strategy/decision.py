"""
汪汪汪·V3稳健趋势策略

ADX动量趋势追踪，专注稳健复利。
核心逻辑：
- ADX+EMA双确认入场（ADX>25，EMA快线上穿慢线）
- 多空双向，18x杠杆
- 2.5x ATR止损 + 移动止损（浮盈5.5%激活）
- 滚仓复利：浮盈10%触发，50%加仓，最多3次
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import numpy as np
import pandas as pd

from .indicators import ema, rsi, macd, bollinger_bands, atr, adx, supertrend


@dataclass
class V3StrategyParams:
    """V3策略完整参数集"""
    
    # --- 信号权重 ---
    trend_weight: float = 0.7          # 趋势信号权重
    momentum_weight: float = 0.2       # 动量信号权重
    volatility_weight: float = 0.1     # 波动率权重
    volume_weight: float = 0.0         # 成交量权重
    mean_revert_weight: float = 0.0    # 均值回归权重
    
    # --- 入场阈值 ---
    entry_threshold: float = 0.28      # 入场信号阈值
    exit_threshold: float = 0.24       # 出场信号阈值
    
    # --- 方向偏好 ---
    long_bias: float = 0.5             # 0=只做空, 0.5=双向, 1=只做多
    
    # --- 趋势参数 ---
    fast_ma_period: int = 20           # 快线周期
    slow_ma_period: int = 55           # 慢线周期
    trend_strength_min: float = 25.0   # ADX最小值（趋势强度）
    supertrend_mult: float = 2.5       # Supertrend倍数
    
    # --- 动量参数 ---
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # --- 布林带参数 ---
    bb_period: int = 20
    bb_std: float = 2.0
    
    # --- 杠杆与仓位 ---
    base_leverage: float = 15.0        # 基础杠杆
    max_leverage: float = 18.0         # 最大杠杆
    risk_per_trade: float = 0.08       # 单笔风险资金比例
    max_position_pct: float = 0.18     # 最大仓位占比
    
    # --- 止损止盈 ---
    sl_atr_mult: float = 2.5           # 止损ATR倍数
    tp_rr_ratio: float = 4.0           # 盈亏比
    
    # --- 移动止损 ---
    trailing_enabled: bool = True
    trailing_activation_pct: float = 0.055   # 浮盈5.5%激活
    trailing_distance_atr: float = 2.0       # 移动止损ATR距离
    
    # --- 滚仓复利 ---
    rolling_enabled: bool = True
    rolling_trigger_pct: float = 0.10        # 浮盈10%触发
    rolling_reinvest_pct: float = 0.5        # 50%浮盈再投入
    rolling_max_times: int = 3               # 最多滚仓3次
    rolling_move_stop: bool = True           # 滚仓后止损移到成本价
    
    # --- 市场环境 ---
    regime_sensitivity: float = 0.5
    exit_on_regime_change: bool = False
    
    def normalize_weights(self):
        """归一化权重"""
        total = (self.trend_weight + self.momentum_weight + 
                 self.volatility_weight + self.volume_weight + 
                 self.mean_revert_weight)
        if total > 0:
            self.trend_weight /= total
            self.momentum_weight /= total
            self.volatility_weight /= total
            self.volume_weight /= total
            self.mean_revert_weight /= total
        
        # 钳制参数范围
        self.entry_threshold = np.clip(self.entry_threshold, 0.05, 0.60)
        self.exit_threshold = np.clip(self.exit_threshold, 0.02, 0.40)
        self.long_bias = np.clip(self.long_bias, 0.0, 1.0)
        self.base_leverage = max(1.0, min(self.base_leverage, 150.0))
        self.max_leverage = max(self.base_leverage, min(self.max_leverage, 150.0))
        self.sl_atr_mult = np.clip(self.sl_atr_mult, 0.3, 8.0)
        self.tp_rr_ratio = np.clip(self.tp_rr_ratio, 0.5, 10.0)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, d: dict) -> "V3StrategyParams":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid})
    
    @classmethod
    def from_json(cls, path: str) -> "V3StrategyParams":
        with open(path) as f:
            return cls.from_dict(json.load(f))


# ============ 信号计算 ============

def _trend_signal(df: pd.DataFrame, p: V3StrategyParams, i: int, cache: dict) -> float:
    """趋势信号：EMA交叉 + ADX强度 + Supertrend方向"""
    if "ema_fast" not in cache:
        cache["ema_fast"] = ema(df, p.fast_ma_period)
        cache["ema_slow"] = ema(df, p.slow_ma_period)
        adx_val, plus_di, minus_di = adx(df, 14)
        cache["adx"] = adx_val
        cache["plus_di"] = plus_di
        cache["minus_di"] = minus_di
        _, st_dir = supertrend(df, period=max(p.fast_ma_period, 7), multiplier=p.supertrend_mult)
        cache["st_dir"] = st_dir
    
    ef = cache["ema_fast"].iloc[i]
    es = cache["ema_slow"].iloc[i]
    adx_v = cache["adx"].iloc[i]
    st_d = cache["st_dir"].iloc[i]
    plus_di = cache["plus_di"].iloc[i]
    minus_di = cache["minus_di"].iloc[i]
    
    if np.isnan(ef) or np.isnan(es) or es == 0:
        return 0.0
    
    # EMA方向
    ema_diff = (ef - es) / es
    ema_sig = np.clip(ema_diff * 80, -1, 1)
    
    # Supertrend方向
    st_sig = 1.0 if st_d == 1 else -1.0
    
    # DI方向
    di_sig = 0.0
    if not (np.isnan(plus_di) or np.isnan(minus_di)):
        di_diff = plus_di - minus_di
        di_sig = np.clip(di_diff / 30, -1, 1)
    
    # ADX趋势强度过滤（ADX>25才全额信号）
    if not np.isnan(adx_v):
        adx_pass = adx_v >= p.trend_strength_min
        confidence = 1.0 if adx_pass else 0.3
    else:
        confidence = 0.5
    
    # 三票加权：EMA 40% + Supertrend 30% + DI 30%
    raw = ema_sig * 0.40 + st_sig * 0.30 + di_sig * 0.30
    return np.clip(raw * confidence, -1, 1)


def _momentum_signal(df: pd.DataFrame, p: V3StrategyParams, i: int, cache: dict) -> float:
    """动量信号：RSI + MACD"""
    if "rsi" not in cache:
        cache["rsi"] = rsi(df, p.rsi_period)
        ml, sl, hist = macd(df, p.macd_fast, p.macd_slow, p.macd_signal)
        cache["macd_hist"] = hist
    
    rsi_v = cache["rsi"].iloc[i]
    hist_v = cache["macd_hist"].iloc[i]
    
    if np.isnan(rsi_v):
        return 0.0
    
    # RSI信号（50为中性）
    rsi_sig = np.clip((rsi_v - 50) / 50 * 1.5, -1, 1)
    
    # MACD histogram
    price = df["close"].iloc[i]
    if price > 0 and not np.isnan(hist_v):
        macd_sig = np.clip(hist_v / (price * 0.002), -1, 1)
    else:
        macd_sig = 0.0
    
    return np.clip(rsi_sig * 0.5 + macd_sig * 0.5, -1, 1)


def _volatility_signal(df: pd.DataFrame, p: V3StrategyParams, i: int, cache: dict) -> float:
    """波动率信号：ATR变化"""
    if "atr" not in cache:
        cache["atr"] = atr(df, 14)
        cache["atr_ma"] = cache["atr"].rolling(50, min_periods=14).mean()
    
    atr_v = cache["atr"].iloc[i]
    atr_m = cache["atr_ma"].iloc[i]
    
    if np.isnan(atr_v) or np.isnan(atr_m) or atr_m == 0:
        return 0.0
    
    # ATR扩张→突破信号
    expansion = (atr_v - atr_m) / atr_m
    return np.clip(expansion, -1, 1)


def compute_signals(df: pd.DataFrame, params: V3StrategyParams, regime: pd.Series = None) -> pd.Series:
    """
    计算交易信号
    
    Returns:
        pd.Series: 1=做多, -1=做空, 0=观望
    """
    params.normalize_weights()
    n = len(df)
    signals = pd.Series(0, index=df.index)
    cache = {}
    
    start_idx = max(params.slow_ma_period, 50)
    
    for i in range(start_idx, n):
        trend = _trend_signal(df, params, i, cache)
        momentum = _momentum_signal(df, params, i, cache)
        volatility = _volatility_signal(df, params, i, cache)
        
        composite = (
            params.trend_weight * trend +
            params.momentum_weight * momentum +
            params.volatility_weight * volatility
        )
        
        # 方向偏好过滤
        if params.long_bias > 0.7 and composite < 0:
            composite *= (1 - params.long_bias) * 2
        elif params.long_bias < 0.3 and composite > 0:
            composite *= params.long_bias * 2
        
        # 市场环境调制
        if regime is not None and params.regime_sensitivity > 0:
            r = regime.iloc[i] if i < len(regime) else "SIDEWAYS"
            s = params.regime_sensitivity
            if r == "BULL":
                if composite < 0:
                    composite *= (1 - s)
                else:
                    composite *= (1 + s * 0.3)
            elif r == "BEAR":
                if composite > 0:
                    composite *= (1 - s)
                else:
                    composite *= (1 + s * 0.3)
        
        # 信号判定
        if composite > params.entry_threshold:
            signals.iloc[i] = 1
        elif composite < -params.entry_threshold:
            signals.iloc[i] = -1
    
    return signals
