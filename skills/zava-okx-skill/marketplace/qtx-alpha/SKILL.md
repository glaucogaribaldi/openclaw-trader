---
name: qtx-alpha
title: QTX 量化信号引擎 — 多因子扫描与回测
description: |
  机构级加密衍生品 Alpha 信号引擎。基于编译态多因子模型实时扫描永续合约市场，
  自动输出带完整风控参数的可执行信号。内置仓位管理、敞口控制与离线回测框架，
  通过 OKX CLI 完成全链路交易闭环。
allowed-tools: Bash(okx *) Bash(node *) Bash(python3 *) Bash(mkdir *)
---

# QTX Alpha Engine

> Institutional-grade quantitative signal engine for crypto perpetual swaps.

机构级加密货币永续合约量化信号引擎。引擎将**多维市场微观结构分析**、**动态因子评分**与**实时风险预算管理**整合为端到端的交易信号管线。核心评分模型、因子权重及风控算法经编译期混淆封装，信号逻辑不可逆向。

### 核心能力

| 能力 | 说明 |
|------|------|
| 全市场实时扫描 | 毫秒级处理全量 SWAP 标的行情快照，多维度筛选与评分 |
| 自适应风控 | 基于账户权益动态计算仓位规模、保证金分配与退出价位 |
| 信号即执行 | 输出包含完整下单参数的 JSON 信号，可直接映射为 OKX CLI 指令 |
| 离线回测 | 支持历史行情回放、多参数网格搜索与交互式 HTML 报告 |
| 跨平台部署 | 基于 Node.js 运行，支持 macOS / Linux / Windows |

### 系统架构

```
                    ┌─────────────────────────┐
  OKX Market Data   │     QTX Alpha Engine     │   OKX Execution
  ───────────────►  │  ┌───────────────────┐   │  ──────────────►
   Tickers (JSON)   │  │ Factor Scoring    │   │   swap place
   Candles (JSON)   │  │ Risk Budgeting    │   │   swap leverage
                    │  │ Position Sizing   │   │   algo orders
                    │  └───────────────────┘   │
                    └─────────────────────────┘
                              │
                        Signals (JSON)
                     inst / px / score
                     t1 / t2 / sz / lev
```

- **信号管线**：引擎接收原始行情 → 因子计算 → 评分排序 → 风险预算分配 → 输出可执行信号
- **执行隔离**：引擎不持有任何凭证，不发起任何网络请求，所有交易指令通过 OKX CLI 外部执行
- **状态无关**：每次扫描独立运算，不依赖本地状态文件，可在任意环境无缝迁移

---

## 环境准备

### 1. OKX CLI

```bash
npm install -g @okx_ai/okx-trade-cli
okx setup   # 按引导完成 API Key 配置
```

### 2. 引擎初始化

引擎以 Node.js 模块形式交付（需 Node.js 18+），无需额外安装依赖：

```bash
QTX="node ${CLAUDE_SKILL_DIR}/bin/qtx.js"
```

后续所有命令中 `$QTX` 即为引擎可执行路径。

### 3. 配置文件

引擎配置位于 `${CLAUDE_SKILL_DIR}/config/engine.json`，参数说明如下：

**扫描参数（`scan` 段）**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `pc` | 最低信号强度阈值 | 0.15 |
| `px` | 最高信号强度上限 | 1.50 |
| `vl` | 最低流动性门槛（USDT） | 20,000,000 |
| `va` | 最低日均流动性门槛 | 1,000,000 |
| `mp` | 最大并发持仓数 | 3 |
| `ex` | 排除标的列表 | BTC, ETH, USDC |

**执行参数（`exec` 段）**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `tp` | 主退出目标系数 | 0.30 |
| `sl` | 保护性退出系数 | 0.50 |
| `th` | 持仓超时（小时） | 72 |
| `ch` | 冷却期（小时） | 24 |
| `ru` | 单笔最大敞口（USDT） | 5.0 |
| `lv` | 杠杆倍数 | 3 |
| `tr` | 组合总敞口上限（USDT） | 30.0 |
| `mm` | 保证金使用率上限 | 50% |
| `ic` | 回测初始资金（USDT） | 10,000 |

> 参数键名经过混淆处理，调整时请严格参照上表，错误值可能导致风控失效或信号质量劣化。

---

## 交易流程

### Phase 1 — 信号扫描

获取全量 SWAP 市场快照，送入引擎实时评分：

```bash
okx market tickers SWAP --json | $QTX scan --config "${CLAUDE_SKILL_DIR}/config/engine.json"
```

**输出结构**（JSON）：

```json
{
  "n": 3,
  "signals": [
    { "inst": "...", "px": ..., "score": ..., "t1": ..., "t2": ..., "sz": ..., "cost": ..., "exp": ..., "lev": ... }
  ]
}
```

| 字段 | 含义 | 用途 |
|------|------|------|
| `inst` | 合约标的 ID | 下单 `--instId` |
| `px` | 参考价格 | 信息展示 |
| `score` | 信号强度评分 | 越高置信度越强，用于优先级排序 |
| `liq` | 24h 流动性（$M） | 流动性过低的标的应谨慎 |
| `t1` | 目标价位 1 | 下单 `--tpTriggerPx` |
| `t2` | 目标价位 2 | 下单 `--slTriggerPx` |
| `sz` | 建仓数量 | 下单 `--sz` |
| `cost` | 所需保证金 (USDT) | 余额校验 |
| `exp` | 单笔最大敞口 (USDT) | 风控参考 |
| `lev` | 杠杆倍数 | 下单 `--lever` |

> 当 `"n": 0` 时表示无有效信号，**严禁强制开仓**。

### Phase 2 — 建仓执行

对每个信号 **严格按序** 执行：

**Step 1 — 余额校验**

```bash
okx account balance USDT --json
```

确认可用余额 > 信号 `cost` 字段。多信号并行时需覆盖所有 `cost` 之和。

**Step 2 — 杠杆设置**

```bash
okx swap leverage --instId <inst> --lever <lev> --mgnMode cross
```

> 必须在下单 **之前** 完成，否则可能以错误杠杆成交。

**Step 3 — 开仓下单**

```bash
okx swap place --instId <inst> --side sell --ordType market \
  --sz <sz> --tdMode cross \
  --tpTriggerPx <t1> --tpOrdPx -1 \
  --slTriggerPx <t2> --slOrdPx -1
```

| 参数 | 说明 |
|------|------|
| `--side sell` | 引擎信号方向 |
| `--tpTriggerPx <t1>` | 触达 t1 时市价平仓（主退出） |
| `--slTriggerPx <t2>` | 触达 t2 时市价平仓（保护性退出） |
| `--tdMode cross` | 全仓保证金 |

**Step 4 — 成交确认**

```bash
okx swap orders --instId <inst> --json
```

确认 `state: filled`。部分成交 → 30s 后复查；2 分钟未成交 → 撤单重新评估。

### Phase 3 — 持仓监控

```bash
# 全量持仓
okx swap positions --json

# 指定标的
okx swap positions --instId <inst> --json
```

关键监控指标：
- `upl` — 未实现盈亏
- `mgnRatio` — 保证金率（低于 15% 应考虑减仓或追加保证金）
- `liqPx` — 强平价格

### Phase 4 — 人工干预

**强制平仓：**

```bash
okx swap close --instId <inst> --mgnMode cross
```

**管理委托单：**

```bash
# 查看当前止盈止损委托
okx swap algo orders --instId <inst> --ordType conditional --json

# 撤销指定委托
okx swap algo cancel --instId <inst> --algoId <id>
```

---

## 风险控制体系

引擎内部强制执行多层风控约束。执行层也应独立验证：

| 层级 | 规则 | 说明 |
|------|------|------|
| 仓位层 | 最大并发数 | 受配置 `mp` 参数硬性限制 |
| 仓位层 | 单笔敞口上限 | 信号 `exp` 字段（USDT） |
| 组合层 | 总敞口上限 | 受配置 `tr` 参数限制 |
| 组合层 | 保证金使用率 | 不超过账户权益的 `mm` 配置百分比 |
| 时间层 | 持仓超时 | 超过 `th` 小时后引擎建议平仓 |
| 时间层 | 冷却期 | 同一标的退出后 `ch` 小时内禁止重新开仓 |

**建仓前检查清单：**
1. 账户余额 ≥ 信号 `cost`
2. 当前持仓数 < 最大并发限制
3. 标的杠杆已正确设置
4. 无相同标的的活跃持仓

---

## 策略验证 (回测与参数优化)

### 数据准备

下载目标品种 1H K 线（约 12.5 天历史）：

```bash
okx market tickers SWAP --json > /tmp/tickers.json

python3 -c "
import sys, json
tickers = json.load(open('/tmp/tickers.json'))
exclude = {'BTC-USDT-SWAP','ETH-USDT-SWAP','USDC-USDT-SWAP'}
valid = [t for t in tickers if t['instId'] not in exclude]
valid.sort(key=lambda t: -float(t.get('volCcy24h','0')))
for t in valid[:50]:
    print(t['instId'])
" > /tmp/universe.txt

mkdir -p data
while IFS= read -r inst; do
  okx market candles "\$inst" --bar 1H --limit 300 --json > "data/\${inst}_1H.json"
  sleep 0.5
done < /tmp/universe.txt
```

### 单配置回测

```bash
$QTX backtest --config "${CLAUDE_SKILL_DIR}/config/engine.json" --data-dir data/ --format markdown
```

输出格式：`markdown`（终端友好）| `json`（程序化接入）| `html`（可视化报告）

### 参数网格搜索

```bash
$QTX sweep --config "${CLAUDE_SKILL_DIR}/config/engine.json" \
  --data-dir data/ --output report.html --format html
```

引擎在内部参数空间上进行全组合回测，按风险调整后收益排序，输出交互式 HTML 报告：
- 每组参数的收益率、夏普比率、最大回撤、胜率、盈亏比
- S/A/B/C/D 五档综合评级
- 支持列排序，快速定位最优参数组合

自定义网格可通过 `--sweep-config sweep.json` 传入，格式规范请咨询引擎维护者。

---

## 模拟交易 (Paper Trading)

正式上线前 **必须** 在 OKX 模拟盘完成充分验证：

```bash
# 信号扫描（模拟盘与实盘共享行情数据）
okx market tickers SWAP --json | $QTX scan --config "${CLAUDE_SKILL_DIR}/config/engine.json"

# 模拟盘建仓
okx --demo swap leverage --instId <inst> --lever <lev> --mgnMode cross
okx --demo swap place --instId <inst> --side sell --ordType market \
  --sz <sz> --tdMode cross \
  --tpTriggerPx <t1> --tpOrdPx -1 \
  --slTriggerPx <t2> --slOrdPx -1

# 模拟盘监控
okx --demo swap positions --json

# 模拟盘平仓
okx --demo swap close --instId <inst> --mgnMode cross
```

---

## 免责声明

本引擎仅提供量化信号与风控参数计算，不构成投资建议。加密货币衍生品交易具有高风险，可能导致本金全部损失。使用者应自行评估风险承受能力，并对所有交易决策负全部责任。引擎维护者不对任何交易损失承担责任。

---

*QTX Alpha Engine v0.1.0 — Multi-factor scoring | Built-in risk management | Backtesting & parameter optimization*
