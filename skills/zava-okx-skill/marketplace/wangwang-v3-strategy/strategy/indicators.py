"""
技术指标计算模块
"""
import pandas as pd
import numpy as np


def ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """指数移动平均"""
    return df[col].ewm(span=period, adjust=False).mean()


def sma(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """简单移动平均"""
    return df[col].rolling(window=period).mean()


def rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.Series:
    """相对强弱指标"""
    delta = df[col].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, col: str = "close") -> tuple:
    """MACD指标，返回 (macd_line, signal_line, histogram)"""
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, col: str = "close") -> tuple:
    """布林带，返回 (upper, middle, lower)"""
    middle = df[col].rolling(window=period).mean()
    std = df[col].rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """平均真实波幅"""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> tuple:
    """ADX指标，返回 (adx, plus_di, minus_di)"""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    
    atr_val = atr(df, period)
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr_val)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(span=period, adjust=False).mean()
    return adx_val, plus_di, minus_di


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> tuple:
    """Supertrend指标，返回 (supertrend_line, direction)"""
    atr_val = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val
    
    st = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)
    
    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
        
        if direction.iloc[i] == 1:
            if direction.iloc[i-1] == 1:
                st.iloc[i] = max(lower_band.iloc[i], st.iloc[i-1])
            else:
                st.iloc[i] = lower_band.iloc[i]
        else:
            if direction.iloc[i-1] == -1:
                st.iloc[i] = min(upper_band.iloc[i], st.iloc[i-1])
            else:
                st.iloc[i] = upper_band.iloc[i]
    
    return st, direction


def obv(df: pd.DataFrame) -> pd.Series:
    """能量潮指标"""
    sign = np.sign(df["close"].diff())
    return (sign * df["volume"]).cumsum()


def vwap(df: pd.DataFrame) -> pd.Series:
    """成交量加权平均价"""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumvol = df["volume"].cumsum()
    cumtp = (typical_price * df["volume"]).cumsum()
    return cumtp / cumvol.replace(0, np.nan)
