"""
回测执行器 - V3策略专用

支持：
- 全仓复利模式
- 滚仓加仓（浮盈触发）
- 移动止损
- 爆仓检测
"""
import numpy as np
import pandas as pd
from datetime import timezone

from .decision import V3StrategyParams, compute_signals
from .indicators import atr as compute_atr
from .engine import Trade, BacktestResult


DEFAULT_MAINTENANCE_RATE = 0.004


def _unrealized_pnl_pct(pos: Trade, current_price: float) -> float:
    """计算未实现盈亏百分比"""
    if pos.direction == 1:
        return (current_price - pos.entry_price) / pos.entry_price * pos.leverage
    else:
        return (pos.entry_price - current_price) / pos.entry_price * pos.leverage


def _position_qty(pos: Trade) -> float:
    """计算持仓数量"""
    if pos.entry_price <= 0 or pos.leverage <= 0 or pos.margin <= 0:
        return 0.0
    return pos.margin * pos.leverage / pos.entry_price


def _position_unrealized_pnl(pos: Trade, current_price: float) -> float:
    """计算未实现盈亏金额"""
    qty = _position_qty(pos)
    if pos.direction == 1:
        return (current_price - pos.entry_price) * qty
    return (pos.entry_price - current_price) * qty


def _used_margin(positions: list) -> float:
    """计算已用保证金"""
    return float(sum(max(pos.margin, 0.0) for pos in positions))


def _account_equity(wallet_balance: float, positions: list, current_price: float) -> float:
    """计算账户权益"""
    unrealized = sum(_position_unrealized_pnl(pos, current_price) for pos in positions)
    return wallet_balance + unrealized


def _free_margin(wallet_balance: float, positions: list, current_price: float) -> float:
    """计算可用保证金"""
    return _account_equity(wallet_balance, positions, current_price) - _used_margin(positions)


def _format_ts(value) -> Optional[str]:
    """格式化时间戳"""
    if value is None:
        return None
    if hasattr(value, "tzinfo"):
        if value.tzinfo is None:
            value = value.tz_localize(timezone.utc) if hasattr(value, "tz_localize") else value.replace(tzinfo=timezone.utc)
        else:
            value = value.tz_convert(timezone.utc) if hasattr(value, "tz_convert") else value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def run_backtest(
    df: pd.DataFrame,
    params: V3StrategyParams,
    initial_capital: float = 10000.0,
    maintenance_rate: float = DEFAULT_MAINTENANCE_RATE,
) -> BacktestResult:
    """
    执行V3策略回测
    
    Args:
        df: DataFrame with columns [timestamp, open, high, low, close, volume]
        params: V3策略参数
        initial_capital: 初始资金
        maintenance_rate: 维持保证金率
    
    Returns:
        BacktestResult: 回测结果
    """
    df = df.copy().reset_index(drop=True)
    has_ts = "timestamp" in df.columns
    
    # 计算信号
    signals = compute_signals(df, params, None)
    atr_series = compute_atr(df, 14)
    atr_pct_series = (atr_series / df["close"]).fillna(0.02)
    
    # 账户状态
    wallet_balance = initial_capital
    total_deposited = initial_capital
    blowup_count = 0
    equity = [initial_capital]
    trades: list[Trade] = []
    positions: list[Trade] = []
    
    for i in range(1, len(df)):
        price = df["close"].iloc[i]
        high = df["high"].iloc[i]
        low = df["low"].iloc[i]
        signal = signals.iloc[i]
        atr_pct = atr_pct_series.iloc[i] if not np.isnan(atr_pct_series.iloc[i]) else 0.02
        atr_val = atr_series.iloc[i] if not np.isnan(atr_series.iloc[i]) else price * 0.02
        
        # 爆仓检测与恢复
        if wallet_balance < initial_capital * 0.01 and not positions:
            blowup_count += 1
            wallet_balance = initial_capital
            total_deposited += initial_capital
        
        # 强平检测
        if positions:
            total_qty = sum(_position_qty(p) for p in positions)
            if total_qty > 0:
                avg_entry = sum(p.entry_price * _position_qty(p) for p in positions) / total_qty
                direction = positions[0].direction
                
                if direction == 1:
                    liq_price = avg_entry * (1 - 1/params.max_leverage + maintenance_rate)
                    if low <= liq_price:
                        for pos in positions:
                            pnl_pct = -1.0  # 爆仓
                            pnl = pos.margin * pnl_pct
                            pos.exit_idx = i
                            pos.exit_price = liq_price
                            pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                            pos.pnl = pnl
                            pos.pnl_pct = pnl_pct
                            pos.exit_reason = "LIQUIDATION"
                            trades.append(pos)
                            wallet_balance = max(0.0, wallet_balance + pnl)
                        positions = []
                        continue
                else:
                    liq_price = avg_entry * (1 + 1/params.max_leverage - maintenance_rate)
                    if high >= liq_price:
                        for pos in positions:
                            pnl_pct = -1.0
                            pnl = pos.margin * pnl_pct
                            pos.exit_idx = i
                            pos.exit_price = liq_price
                            pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                            pos.pnl = pnl
                            pos.pnl_pct = pnl_pct
                            pos.exit_reason = "LIQUIDATION"
                            trades.append(pos)
                            wallet_balance = max(0.0, wallet_balance + pnl)
                        positions = []
                        continue
        
        # 更新持仓（移动止损、止盈、滚仓）
        for pos in positions:
            unrealized_pct = _unrealized_pnl_pct(pos, price)
            
            # 更新最高/最低价（用于移动止损）
            if pos.direction == 1:
                if pos.trailing_high is None or high > pos.trailing_high:
                    pos.trailing_high = high
            else:
                if pos.trailing_low is None or low < pos.trailing_low:
                    pos.trailing_low = low
            
            # 止盈检查
            if pos.tp_price:
                if pos.direction == 1 and high >= pos.tp_price:
                    pos.exit_idx = i
                    pos.exit_price = pos.tp_price
                    pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                    pos.pnl = pos.margin * (pos.tp_price - pos.entry_price) / pos.entry_price * pos.leverage
                    pos.pnl_pct = pos.pnl / pos.margin
                    pos.exit_reason = "TAKE_PROFIT"
                    trades.append(pos)
                    wallet_balance += pos.pnl
                    positions.remove(pos)
                    continue
                elif pos.direction == -1 and low <= pos.tp_price:
                    pos.exit_idx = i
                    pos.exit_price = pos.tp_price
                    pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                    pos.pnl = pos.margin * (pos.entry_price - pos.tp_price) / pos.entry_price * pos.leverage
                    pos.pnl_pct = pos.pnl / pos.margin
                    pos.exit_reason = "TAKE_PROFIT"
                    trades.append(pos)
                    wallet_balance += pos.pnl
                    positions.remove(pos)
                    continue
            
            # 移动止损检查
            if params.trailing_enabled and pos.trailing_high and pos.trailing_low:
                trailing_active = False
                if pos.direction == 1:
                    profit_pct = (pos.trailing_high - pos.entry_price) / pos.entry_price * pos.leverage
                    if profit_pct >= params.trailing_activation_pct:
                        trailing_active = True
                        stop_price = pos.trailing_high - params.trailing_distance_atr * atr_val
                        if low <= stop_price:
                            pos.exit_idx = i
                            pos.exit_price = stop_price
                            pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                            pos.pnl = pos.margin * (stop_price - pos.entry_price) / pos.entry_price * pos.leverage
                            pos.pnl_pct = pos.pnl / pos.margin
                            pos.exit_reason = "TRAILING_STOP"
                            trades.append(pos)
                            wallet_balance += pos.pnl
                            positions.remove(pos)
                            continue
                else:
                    profit_pct = (pos.entry_price - pos.trailing_low) / pos.entry_price * pos.leverage
                    if profit_pct >= params.trailing_activation_pct:
                        trailing_active = True
                        stop_price = pos.trailing_low + params.trailing_distance_atr * atr_val
                        if high >= stop_price:
                            pos.exit_idx = i
                            pos.exit_price = stop_price
                            pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                            pos.pnl = pos.margin * (pos.entry_price - stop_price) / pos.entry_price * pos.leverage
                            pos.pnl_pct = pos.pnl / pos.margin
                            pos.exit_reason = "TRAILING_STOP"
                            trades.append(pos)
                            wallet_balance += pos.pnl
                            positions.remove(pos)
                            continue
            
            # 固定止损检查
            if pos.sl_price:
                if pos.direction == 1 and low <= pos.sl_price:
                    pos.exit_idx = i
                    pos.exit_price = pos.sl_price
                    pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                    pos.pnl = pos.margin * (pos.sl_price - pos.entry_price) / pos.entry_price * pos.leverage
                    pos.pnl_pct = pos.pnl / pos.margin
                    pos.exit_reason = "STOP_LOSS"
                    trades.append(pos)
                    wallet_balance += pos.pnl
                    positions.remove(pos)
                    continue
                elif pos.direction == -1 and high >= pos.sl_price:
                    pos.exit_idx = i
                    pos.exit_price = pos.sl_price
                    pos.exit_time = _format_ts(df["timestamp"].iloc[i]) if has_ts else None
                    pos.pnl = pos.margin * (pos.entry_price - pos.sl_price) / pos.entry_price * pos.leverage
                    pos.pnl_pct = pos.pnl / pos.margin
                    pos.exit_reason = "STOP_LOSS"
                    trades.append(pos)
                    wallet_balance += pos.pnl
                    positions.remove(pos)
                    continue
            
            # 滚仓逻辑
            if params.rolling_enabled and pos.roll_count < params.rolling_max_times:
                if unrealized_pct >= params.rolling_trigger_pct:
                    # 计算可用保证金
                    free = _free_margin(wallet_balance, positions, price)
                    # 用浮盈的 reinvest_pct 作为新保证金
                    unrealized_pnl = _position_unrealized_pnl(pos, price)
                    new_margin = unrealized_pnl * params.rolling_reinvest_pct
                    
                    if new_margin > 0 and free >= new_margin * 0.5:
                        # 创建新仓位（滚仓）
                        new_pos = Trade(
                            entry_idx=i,
                            entry_price=price,
                            direction=pos.direction,
                            margin=new_margin,
                            leverage=params.base_leverage,
                            entry_time=_format_ts(df["timestamp"].iloc[i]) if has_ts else None,
                            roll_count=pos.roll_count + 1
                        )
                        # 设置止损止盈
                        sl_dist = price * atr_pct * params.sl_atr_mult
                        new_pos.sl_price = price - sl_dist if pos.direction == 1 else price + sl_dist
                        new_pos.tp_price = price + sl_dist * params.tp_rr_ratio if pos.direction == 1 else price - sl_dist * params.tp_rr_ratio
                        positions.append(new_pos)
                        
                        # 原仓位止损移到成本价
                        if params.rolling_move_stop:
                            pos.sl_price = pos.entry_price
                        
                        pos.roll_count += 1
        
        # 开新仓
        if signal != 0 and not positions:
            direction = int(signal)
            
            # 检查方向偏好
            if params.long_bias > 0.7 and direction == -1:
                continue
            if params.long_bias < 0.3 and direction == 1:
                continue
            
            # 计算仓位大小
            margin = wallet_balance * params.risk_per_trade
            max_margin = wallet_balance * params.max_position_pct
            margin = min(margin, max_margin)
            
            if margin > 100:  # 最小保证金检查
                pos = Trade(
                    entry_idx=i,
                    entry_price=price,
                    direction=direction,
                    margin=margin,
                    leverage=params.base_leverage,
                    entry_time=_format_ts(df["timestamp"].iloc[i]) if has_ts else None,
                    roll_count=0
                )
                
                # 设置止损止盈
                sl_dist = price * atr_pct * params.sl_atr_mult
                if direction == 1:
                    pos.sl_price = price - sl_dist
                    pos.tp_price = price + sl_dist * params.tp_rr_ratio
                else:
                    pos.sl_price = price + sl_dist
                    pos.tp_price = price - sl_dist * params.tp_rr_ratio
                
                positions.append(pos)
        
        # 记录权益
        current_equity = _account_equity(wallet_balance, positions, price)
        equity.append(current_equity)
    
    # 平仓所有剩余持仓
    final_price = df["close"].iloc[-1]
    for pos in positions:
        pos.exit_idx = len(df) - 1
        pos.exit_price = final_price
        pos.exit_time = _format_ts(df["timestamp"].iloc[-1]) if has_ts else None
        pos.pnl = _position_unrealized_pnl(pos, final_price)
        pos.pnl_pct = pos.pnl / pos.margin if pos.margin > 0 else 0
        pos.exit_reason = "END_OF_DATA"
        trades.append(pos)
        wallet_balance += pos.pnl
    
    # 计算回测统计
    equity_series = pd.Series(equity)
    returns = equity_series.pct_change().dropna()
    
    total_return = (equity[-1] - initial_capital) / initial_capital
    
    # Sharpe (年化，假设每天24小时交易，15分钟K线 = 96根/天)
    periods_per_year = 96 * 365
    if len(returns) > 1 and returns.std() > 0:
        sharpe = (returns.mean() * periods_per_year) / (returns.std() * np.sqrt(periods_per_year))
    else:
        sharpe = 0.0
    
    # 最大回撤
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_dd = drawdown.min()
    
    # 交易统计
    total_trades = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    avg_trade_pnl = sum(t.pnl for t in trades) / total_trades if total_trades > 0 else 0
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
    
    # 连续盈亏
    max_consec_wins = 0
    max_consec_losses = 0
    curr_wins = 0
    curr_losses = 0
    for t in trades:
        if t.pnl > 0:
            curr_wins += 1
            curr_losses = 0
            max_consec_wins = max(max_consec_wins, curr_wins)
        else:
            curr_losses += 1
            curr_wins = 0
            max_consec_losses = max(max_consec_losses, curr_losses)
    
    return BacktestResult(
        trades=trades,
        equity_curve=equity_series,
        total_return=total_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        avg_trade_pnl=avg_trade_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_consecutive_wins=max_consec_wins,
        max_consecutive_losses=max_consec_losses,
        blowup_count=blowup_count,
        total_deposited=total_deposited,
    )
