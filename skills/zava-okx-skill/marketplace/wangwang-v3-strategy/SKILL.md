---
name: wangwang-v3-strategy
description: 汪汪汪·V3稳健趋势策略。自动化执行 ADX动量趋势追踪（入场阈值0.28、ADX大等于25双确认、18x杠杆、2.5x ATR止损加移动止损、滚仓复利）。当用户提到「V3策略」「汪汪汪策略」「趋势追踪策略」「ADX策略」「加密货币量化」「合约策略回测」时触发。提供回测、参数调整、策略解释、实盘信号等能力。
---

# 汪汪汪·V3稳健趋势策略

## 核心概念

V3策略是汪汪汪的核心交易系统：**少交易、抓趋势、稳复利**。

### 信号逻辑

```
入场信号 = 0.7×趋势信号 + 0.2×动量信号 + 0.1×波动率信号
          趋势信号 = EMA(40%) + Supertrend(30%) + DI方向(30%)

入场条件：
  composite > 0.28 → 做多（ADX>25时全额信号，ADX<25时信号削弱70%）
  composite < -0.28 → 做空
```

### 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 基础杠杆 | 15x | 可上调至18x |
| ATR止损 | 2.5x | 止损距离 |
| 盈亏比 | 4:1 | 止盈/止损比 |
| 移动止损 | 浮盈5.5%激活 | ATR 2.0x追踪 |
| 滚仓复利 | 浮盈10%触发 | 50%加仓，最多3次 |

### 历史回测（BTCUSDT 15m，148天）

| 指标 | 结果 |
|------|------|
| 总收益 | **+25.47%** |
| Sharpe | **0.622** |
| 最大回撤 | 24.52% |
| 胜率 | 21.58% |
| 盈亏比 | 1.151 |
| 交易次数 | 760笔 |
| 爆仓次数 | **0** |

## 使用方式

### 回测
```python
from strategy import V3StrategyParams, run_backtest
import pandas as pd

params = V3StrategyParams.from_json("config/v3_default.json")
df = pd.read_csv("data.csv")  # 需要 [timestamp, open, high, low, close, volume]

result = run_backtest(df, params, initial_capital=10000)
print(result.to_dict())
```

### 命令行回测
```bash
python scripts/run_backtest.py --symbol BTCUSDT --timeframe 15m --days 148
```

### 修改策略参数
编辑 `config/v3_default.json`，推荐调节范围：

- `entry_threshold`: 0.20~0.40（越小越敏感，交易越多）
- `trend_strength_min`: 20~30（ADX阈值，越高越保守）
- `trailing_activation_pct`: 0.04~0.08（移动止损激活点）
- `rolling_trigger_pct`: 0.08~0.15（滚仓触发点）

### 参数调整建议

| 场景 | 建议调整 |
|------|---------|
| 牛市 | 降低 `trend_strength_min` 至 20，增加交易机会 |
| 熊市 | 提高 `trend_strength_min` 至 30，减少假信号 |
| 高波动 | 提高 `sl_atr_mult` 至 3.0，放宽止损 |
| 低波动 | 降低 `entry_threshold` 至 0.22，更快反应 |
| 保守 | 设置 `rolling_enabled: false`，禁用滚仓 |

## 策略原理

详见 `references/strategy_guide.md`
