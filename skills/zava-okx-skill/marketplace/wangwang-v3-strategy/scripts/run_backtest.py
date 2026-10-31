#!/usr/bin/env python3
"""
run_backtest.py — 汪汪汪·V3稳健趋势策略 回测 CLI

Usage:
    python run_backtest.py --params config/v3_default.json --data data.csv --capital 10000
    python run_backtest.py --params my_params.json --symbol BTCUSDT --timeframe 15m
"""
import json, os, sys, argparse
from pathlib import Path

# 添加策略目录到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
STRATEGY_DIR = SCRIPT_DIR.parent / "strategy"
sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(STRATEGY_DIR))

import pandas as pd
import numpy as np

from strategy import V3StrategyParams, run_backtest


def fetch_data(symbol: str, timeframe: str, days: int = 148) -> pd.DataFrame:
    """从 Binance 获取K线数据"""
    import requests
    
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    binance_interval = interval_map.get(timeframe, "15m")
    
    limit = min(days * 24 * 60 // {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}[binance_interval], 1500)
    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol.upper(),
        "interval": binance_interval,
        "limit": limit,
    }
    
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    rows = resp.json()
    
    df = pd.DataFrame(rows, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = pd.to_numeric(df[col])
    
    print(f"✓ 获取数据: {symbol} {timeframe}, {len(df)} 根K线 ({df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]})")
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def print_result(result, params):
    """打印回测结果"""
    print("\n" + "="*50)
    print("  汪汪汪·V3稳健趋势  — 回测结果")
    print("="*50)
    
    r = result.to_dict()
    ret = r["total_return"] * 100
    dd = r["max_drawdown"] * 100
    
    print(f"\n  📈 收益")
    print(f"     总收益:     {ret:+.2f}%")
    print(f"     Sharpe:    {r['sharpe_ratio']:.3f}")
    print(f"     最大回撤:  {dd:.2f}%")
    
    print(f"\n  📊 交易统计")
    print(f"     总交易:    {r['total_trades']} 笔")
    print(f"     胜率:      {r['win_rate']*100:.1f}%")
    print(f"     盈亏比:    {r['profit_factor']:.3f}")
    print(f"     平均盈:    {r['avg_win']:.2f}")
    print(f"     平均亏:    {r['avg_loss']:.2f}")
    
    print(f"\n  ⚠️ 风险")
    print(f"     爆炸次数:  {r['blowup_count']}")
    print(f"     最大连赢: {r['max_consecutive_wins']}")
    print(f"     最大连亏: {r['max_consecutive_losses']}")
    
    print(f"\n  ⚙️ 策略参数")
    print(f"     杠杆:      {params.base_leverage}x (max {params.max_leverage}x)")
    print(f"     入场阈值:  {params.entry_threshold}")
    print(f"     ATR止损:   {params.sl_atr_mult}x")
    print(f"     盈亏比:    {params.tp_rr_ratio}:1")
    print(f"     滚仓:     {'✓' if params.rolling_enabled else '✗'} (最多{params.rolling_max_times}次)")
    print(f"     移动止损:  {'✓' if params.trailing_enabled else '✗'}")
    
    # 质量评级
    print("\n  🎯 质量评级")
    score = 0
    if r["sharpe_ratio"] >= 0.5: score += 1
    if r["sharpe_ratio"] >= 1.0: score += 1
    if dd < 25: score += 1
    if dd < 20: score += 1
    if r["blowup_count"] == 0: score += 1
    if r["profit_factor"] > 1.2: score += 1
    if r["total_trades"] >= 50: score += 1
    
    stars = "★" * score + "☆" * (7 - score)
    print(f"     综合评分:  {stars} ({score}/7)")
    
    if r["sharpe_ratio"] < 0.4:
        print(f"\n  ⚠️  警告: Sharpe ({r['sharpe_ratio']:.3f}) < 0.4，策略偏弱")
    if dd > 35:
        print(f"\n  ⚠️  警告: 最大回撤 ({dd:.1f}%) > 35%，风险偏高")
    if r["blowup_count"] > 0:
        print(f"\n  🚨 危险: 发生 {r['blowup_count']} 次爆仓，不建议实盘")


def main():
    ap = argparse.ArgumentParser(description="汪汪汪·V3策略回测")
    ap.add_argument("--params", default=str(SCRIPT_DIR.parent / "config" / "v3_default.json"),
                   help="策略参数JSON文件")
    ap.add_argument("--data", help="本地CSV文件（可选，默认从Binance拉取）")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--timeframe", default="15m")
    ap.add_argument("--days", type=int, default=148, help="数据天数（默认148天）")
    ap.add_argument("--capital", type=float, default=10000.0, help="初始资金")
    ap.add_argument("--output", help="结果保存路径")
    args = ap.parse_args()
    
    # 加载参数
    params = V3StrategyParams.from_json(args.params)
    print(f"✓ 参数加载: {args.params}")
    print(f"  策略: V3稳健趋势 (杠杆 {params.base_leverage}x)")
    
    # 加载数据
    if args.data:
        df = pd.read_csv(args.data)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        print(f"✓ 数据加载: {args.data} ({len(df)} 根K线)")
    else:
        df = fetch_data(args.symbol, args.timeframe, args.days)
    
    # 回测
    print(f"\n开始回测... (数据: {len(df)} 根K线)")
    result = run_backtest(df, params, initial_capital=args.capital)
    
    # 打印结果
    print_result(result, params)
    
    # 保存
    if args.output:
        out = {
            "params": params.to_dict(),
            "backtest_result": result.to_dict(),
            "meta": {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "bars": len(df),
                "initial_capital": args.capital,
            }
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 结果已保存: {args.output}")


if __name__ == "__main__":
    main()
