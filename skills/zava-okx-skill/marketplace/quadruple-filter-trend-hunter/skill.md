---

name: 四重滤网趋势猎手

description: 通过周线、日线、4小时、1小时四层EMA30过滤器筛选强趋势币种，在15分钟图等待突破信号入场，金字塔加仓跟随趋势，数学模型严格锁定每笔风险在总资金2%以内。只做多，最大持仓2笔，最大风险敞口4%。

---

> **策略简介**
>
> 本策略是一套纯趋势跟随交易系统，通过周线、日线、4小时、1小时四个时间框架的 EMA30 过滤器，
> 层层筛选出多头趋势最强、方向最清晰的币种，再在 15 分钟图等待价格突破均线+ATR 的入场信号。
> 进场后采用金字塔加仓结构，随趋势发展逐步放大仓位，每次加仓均通过数学模型严格锁定本金风险，
> 无论加仓多少次，单笔交易最大亏损始终控制在账户总资金的 2% 以内。
> 策略的核心哲学：**宁可多次小额止损，绝不错过一次大级别趋势。**

---

## 基本信息

| 项目 | 内容 |
|------|------|
| 策略版本 | V1.0 |
| 策略类型 | 趋势跟随 + 金字塔加仓 |
| 交易方向 | 只做多 |
| 交易品种 | USDT 永续合约 |
| 杠杆倍数 | 20 倍逐仓 |
| 最大持仓数 | 2 笔（不同币种） |
| 最大单笔风险 | 账户总资金 2% |
| 最大总风险敞口 | 账户总资金 4% |
| 主循环频率 | 每 15 分钟 |
| 适用行情 | 趋势明确的单边上涨行情 |

---

## 交易标的（固定，按优先级从高到低）

| 优先级 | 合约 |
|--------|------|
| 1 | BTC-USDT-SWAP |
| 2 | ETH-USDT-SWAP |
| 3 | XRP-USDT-SWAP |
| 4 | BNB-USDT-SWAP |
| 5 | SOL-USDT-SWAP |
| 6 | TRX-USDT-SWAP |
| 7 | DOGE-USDT-SWAP |
| 8 | HYPE-USDT-SWAP |
| 9 | ADA-USDT-SWAP |
| 10 | BCH-USDT-SWAP |

---

## 初始化（首次启动时执行一次，仅执行一次）

1. 调用 account_get_balance，读取当前账户总权益（eq 字段），
   将此值设为 account_total_capital。
   此后 account_total_capital 仅通过策略内部盈亏计算更新，
   永远不再用 API 返回值覆盖。
   ⚠️ 若账户发生外部充值或提现，需手动重启策略重新初始化。

2. 调用 account_set_position_mode，将账户设置为单向持仓模式。
   若因已有持仓导致设置失败，记录警告，策略继续运行，
   但后续每次入场前必须验证持仓模式。

3. 将 active_trades 初始化为空列表。
   将 weekly_pass / daily_pass / h4_pass / h1_pass 初始化为空列表。

---

## 全局状态（持久化保存，每次执行读取，结束时写回）

```
account_total_capital    账户资金基准（USDT），初始化后只由策略内部加减更新

weekly_pass              通过周线 EMA 过滤的币种列表
daily_pass               通过周线 + 日线 EMA 过滤的币种列表
h4_pass                  通过周线 + 日线 + 4小时 EMA 过滤的币种列表
h1_pass                  通过全部四层高周期过滤的币种列表（15分钟入场候选池）

last_weekly_update       上次执行周线过滤的时间戳
last_daily_update        上次执行日线过滤的时间戳
last_h4_update           上次执行4小时过滤的时间戳
last_h1_update           上次执行1小时过滤的时间戳

active_trades            当前持仓列表（最多2笔），每笔记录以下字段：
  instId                 合约ID
  add_count              已加仓次数（0 / 1 / 2 / 3）
  C                      当前总仓位张数
  avg_entry              加权平均入场价（USDT）
  ctVal                  合约面值（入场时获取，后续复用）
  minSz                  最小交易单位（入场时获取，后续复用）
  E0                     初次入场时的15分钟EMA30
  E1                     第一次加仓时的15分钟EMA30（加仓后写入）
  E2                     第二次加仓时的15分钟EMA30（加仓后写入）
  X0                     初次入场价差（R0 - S0）
  X1                     第一次加仓价差（R1 - S1，加仓后写入）
  X2                     第二次加仓价差（R2 - S2，加仓后写入）
  S                      当前强制止损价
  stop_algo_id           当前挂在交易所服务器的止损条件单ID
  h1_pass_entry_time     该币种进入h1_pass的时间戳（防逻辑反转用）
```

---

## 技术指标计算说明

优先使用工具包内置技术指标功能直接获取 EMA(30) 和 ATR(30)。
若需手动计算，按以下方法执行：

**EMA30 计算**
```
取该时间框架最近 60 根 K 线收盘价
种子值 = 前 30 根收盘价的简单算术平均值
乘数 k = 2 ÷ 31 ≈ 0.0645
EMA[i] = 收盘价[i] × k + EMA[i-1] × (1 - k)，从第31根迭代至最新根
当前EMA30 = 最后一根迭代结果
上一根EMA30 = 倒数第二根迭代结果
```

**ATR30 计算**
```
取最近 31 根 K 线
TR[i] = max(
  最高价[i] - 最低价[i],
  |最高价[i] - 收盘价[i-1]|,
  |最低价[i] - 收盘价[i-1]|
)
ATR30 = 最近 30 根 TR 的简单算术平均值
```

**所有时间框架通用过滤条件（两条必须同时满足）**
```
条件一：当前K线收盘价 > 当前EMA30
条件二：当前EMA30 > 上一根EMA30
任意一条不满足，该币种本轮淘汰。
```

**合约参数获取**
```
入场时调用 market_get_tickers 获取对应合约的 ctVal（合约面值）和 minSz（最小交易单位）。
入场后保存至 active_trades，后续加仓直接复用，不重复调用。
```

---

## LAYER W · 周线过滤（每天执行一次）

对全部 10 个固定币种逐一执行：
- 调用 market_get_candles(instId, bar=1W, limit=60)
- 计算周线EMA30（当前值与上一根值）
- 判断是否通过通用过滤条件

更新 weekly_pass = 本次通过的币种列表
记录日志：【周线过滤】通过列表、淘汰列表及每个淘汰的具体原因

---

## LAYER D · 日线过滤（每天执行一次，紧接 LAYER W 之后）

仅对 weekly_pass 中的币种执行：
- 调用 market_get_candles(instId, bar=1D, limit=60)
- 计算日线EMA30
- 判断是否通过通用过滤条件

更新 daily_pass = 本次通过的币种列表
记录日志：【日线过滤】通过列表、淘汰列表及原因

---

## LAYER H4 · 4小时过滤（每4小时执行一次）

仅对 daily_pass 中的币种执行：
- 调用 market_get_candles(instId, bar=4H, limit=60)
- 计算4小时EMA30
- 判断是否通过通用过滤条件

更新 h4_pass = 本次通过的币种列表
记录日志：【4小时过滤】通过列表、淘汰列表及原因

---

## LAYER H1 · 1小时过滤（每1小时执行一次）

仅对 h4_pass 中的币种执行：
- 调用 market_get_candles(instId, bar=1H, limit=60)
- 计算1小时EMA30
- 判断是否通过通用过滤条件

对本轮新进入 h1_pass 的币种（上轮不在列表、本轮通过的）：
- 记录 h1_pass_entry_time = 当前时间戳

对本轮从 h1_pass 移除的币种：
- 若该币种当前在 active_trades 中有持仓，持仓不受影响，继续按策略管理至离场。

更新 h1_pass = 本次通过的币种列表
记录日志：【1小时过滤】通过列表、淘汰列表及原因

---

## 15分钟交易主循环（每15分钟执行一次）

每根15分钟K线收盘后触发。
严格按 T1 → T2 → T3 → T4 顺序执行，不得跳步。

---

### T1 · 强制止损监控（最高优先级，每轮必须首先执行）

对 active_trades 中每笔持仓执行以下检查：

调用 market_get_ticker(instId) 获取最新成交价 P_now

若 P_now <= S（当前强制止损价）：

```
调用 swap_place_order(
  instId  = instId,
  side    = sell,
  ordType = market,
  sz      = C,
  posSide = long,
  tag     = "agentTradeKit"
)

调用条件单撤销工具，撤销交易所服务器上的止损单（stop_algo_id）

realized_pnl = (P_now - avg_entry) × C × ctVal
account_total_capital = account_total_capital + realized_pnl

从 active_trades 移除该笔记录
```

记录日志：【强制止损触发】instId、触发价 P_now、止损价 S、盈亏 realized_pnl、更新后 account_total_capital

⚠️ 该合约不从本轮 T4 排除。本根15分钟K线收盘若仍满足入场条件，T4 允许重新入场。

---

### T2 · 趋势离场监控（每根15分钟K线收盘后判断）

对 active_trades 中每笔持仓执行：

```
调用 market_get_candles(instId, bar=15m, limit=60)
计算当根收盘时的 EMA30（E_now）和 ATR30（ATR_now）

趋势离场线 = E_now - ATR_now
```

若当根15分钟K线收盘价 < 趋势离场线：

```
exit_price = 当根15分钟K线收盘价

调用 swap_place_order(
  instId  = instId,
  side    = sell,
  ordType = market,
  sz      = C,
  posSide = long,
  tag     = "agentTradeKit"
)

调用条件单撤销工具，撤销止损单（stop_algo_id）

realized_pnl = (exit_price - avg_entry) × C × ctVal
account_total_capital = account_total_capital + realized_pnl

从 active_trades 移除该笔记录
```

记录日志：【趋势离场】instId、离场价 exit_price、趋势离场线、盈亏 realized_pnl、更新后 account_total_capital

---

### T3 · 加仓判断（仅对 add_count < 3 的持仓执行）

对 active_trades 中每笔 add_count < 3 的持仓执行：

```
调用 market_get_candles(instId, bar=15m, limit=60)
计算当根收盘时的 EMA30（E_new）和 ATR30（ATR_new）
```

**第一次加仓（仅当 add_count = 0 时执行）**

触发条件：E_new - E0 >= X0 / 2

```
R1 = 当根15分钟K线收盘价
E1 = E_new
S1 = E1 - ATR_new
X1 = R1 - S1

profit_at_S1 = C × ctVal × (S1 - avg_entry)
A1_usdt = profit_at_S1 + account_total_capital × 2%

若 A1_usdt <= 0：跳过，记录【第一次加仓跳过】浮亏已超出风险预算

calculated_sz = floor(A1_usdt ÷ (X1 × ctVal))
若 calculated_sz < minSz：跳过，记录【第一次加仓跳过】计算张数不足最小交易单位

【保证金检查】
调用 account_get_max_size(instId, tdMode=isolated, lever=20)
add1_sz = min(calculated_sz, max_available_sz)
若 add1_sz < minSz：跳过，记录【第一次加仓跳过】可用保证金不足

调用 swap_set_leverage(instId, lever=20, mgnMode=isolated)
调用 swap_place_order(instId, side=buy, ordType=market, sz=add1_sz, posSide=long, tag="agentTradeKit")
撤旧止损单，挂新止损单至 S1（sz = C + add1_sz）

新 avg_entry = (avg_entry × C + R1 × add1_sz) ÷ (C + add1_sz)
更新：add_count=1, C+=add1_sz, S=S1, X1=X1, E1=E1, avg_entry=新值
```

**第二次加仓（仅当 add_count = 1 时执行）**

触发条件：E_new - E1 >= X1 / 2

```
R2 = 当根15分钟K线收盘价
E2 = E_new
S2 = E2 - ATR_new
X2 = R2 - S2

profit_at_S2 = C × ctVal × (S2 - avg_entry)
A2_usdt = profit_at_S2 + account_total_capital × 2%

若 A2_usdt <= 0：跳过
calculated_sz = floor(A2_usdt ÷ (X2 × ctVal))
若 calculated_sz < minSz：跳过

【保证金检查】
add2_sz = min(calculated_sz, max_available_sz)
若 add2_sz < minSz：跳过

调用 swap_place_order(instId, side=buy, ordType=market, sz=add2_sz, posSide=long, tag="agentTradeKit")
撤旧止损单，挂新止损单至 S2（sz = C + add2_sz）

新 avg_entry = (avg_entry × C + R2 × add2_sz) ÷ (C + add2_sz)
更新：add_count=2, C+=add2_sz, S=S2, X2=X2, E2=E2, avg_entry=新值
```

**第三次加仓（仅当 add_count = 2 时执行）**

触发条件：E_new - E2 >= X2 / 2

⚠️ 第三次加仓只使用纯浮盈，不补充2%资金

```
R3 = 当根15分钟K线收盘价
E3 = E_new
S3 = E3 - ATR_new
X3 = R3 - S3

profit_at_S3 = C × ctVal × (S3 - avg_entry)
A3_usdt = profit_at_S3（只用纯浮盈）

若 A3_usdt <= 0：跳过，记录【第三次加仓跳过】无浮盈可用
calculated_sz = floor(A3_usdt ÷ (X3 × ctVal))
若 calculated_sz < minSz：跳过

【保证金检查】
add3_sz = min(calculated_sz, max_available_sz)
若 add3_sz < minSz：跳过

调用 swap_place_order(instId, side=buy, ordType=market, sz=add3_sz, posSide=long, tag="agentTradeKit")
撤旧止损单，挂新止损单至 S3（sz = C + add3_sz）

新 avg_entry = (avg_entry × C + R3 × add3_sz) ÷ (C + add3_sz)
更新：add_count=3, C+=add3_sz, S=S3, avg_entry=新值
```

---

### T4 · 入场信号检测

```
若 len(active_trades) >= 2：跳过 T4，本轮执行结束。
若 h1_pass 为空：记录【T4跳过】当前无通过四层过滤的候选币种，结束。

slots = 2 - len(active_trades)

扫描列表：从 h1_pass 中按优先级顺序
（BTC→ETH→XRP→BNB→SOL→TRX→DOGE→HYPE→ADA→BCH）
排除当前已在 active_trades 中的币种，顺序取前 slots 个币种
```

对扫描列表中每个币种执行：

```
【防逻辑反转检查】
若（当前时间 - h1_pass_entry_time）< 15 分钟：
  记录【防逻辑反转】instId 刚进入候选池，等待下一根K线，跳过

调用 market_get_candles(instId, bar=15m, limit=60)
计算当根收盘时的 EMA30（E_15m）和 ATR30（ATR_15m）

入场条件：当根15分钟K线收盘价 >= E_15m + ATR_15m
若不满足：记录【无入场信号】，跳过

若满足：
  R0 = 当根15分钟K线收盘价
  E0 = E_15m
  S0 = E_15m - ATR_15m
  X0 = R0 - S0

  调用 market_get_tickers 获取 ctVal 和 minSz
  A0_usdt = account_total_capital × 2%
  calculated_sz = floor(A0_usdt ÷ (X0 × ctVal))
  若 calculated_sz < minSz：跳过

  【保证金检查】
  调用 account_get_max_size(instId, tdMode=isolated, lever=20)
  entry_sz = min(calculated_sz, max_available_sz)
  若 entry_sz < minSz：跳过

  【持仓模式验证】
  验证账户为单向持仓模式，若非单向立即恢复。

  调用 swap_set_leverage(instId, lever=20, mgnMode=isolated)
  调用 swap_place_order(instId, side=buy, ordType=market, sz=entry_sz, posSide=long, tag="agentTradeKit")
  
  挂止损条件单至交易所服务器（
    instId=instId, side=sell, ordType=conditional,
    slTriggerPx=S0, slOrdPx=market, sz=entry_sz, posSide=long, tag="agentTradeKit"
  ）
  保存返回的 algo_id 为 stop_algo_id

  加入 active_trades（instId, add_count=0, C=entry_sz, avg_entry=R0,
    ctVal, minSz, E0, X0, S=S0, stop_algo_id, h1_pass_entry_time）
```

记录日志：【入场执行】instId、入场价 R0、止损价 S0、价差 X0、ATR、计划张数、实际张数、通过过滤层级

---

## 风控总规则

| 规则 | 内容 |
|------|------|
| 方向 | 只做多，严禁开空单，严禁对冲持仓 |
| 持仓模式 | 全程单向持仓，禁止切换为双向 |
| 品种 | USDT 永续合约，逐仓模式，20 倍杠杆 |
| 最大持仓 | 2 笔不同币种，总风险敞口 ≤ 4% |
| 同一币种 | 同时只允许 1 笔交易，持仓期间只加仓不新开 |
| 强制止损 | 条件单挂在交易所服务器，价格触碰即触发市价平仓，不等K线收盘 |
| T1双重保障 | 每15分钟主动检查价格，作为交易所条件单的兜底 |
| 趋势离场 | 当根15分钟K线收盘低于（EMA30 - ATR30）时当轮市价全平 |
| 资金基准 | 启动初始化一次，此后只通过策略内部盈亏加减更新，不从API覆盖 |
| 重入场 | 强制止损后同根K线若仍满足条件，允许当轮T4重新入场 |
| 标识 | 所有下单必须携带 tag="agentTradeKit" |

---

## 每轮执行顺序总检查表

**每天额外执行（早于当天所有其他步骤）：**
- [ ] LAYER W · 更新 weekly_pass（全部10个币种的周线EMA）
- [ ] LAYER D · 更新 daily_pass（weekly_pass 的日线EMA，紧接W之后）

**每4小时额外执行：**
- [ ] LAYER H4 · 更新 h4_pass（daily_pass 的4小时EMA）

**每1小时额外执行：**
- [ ] LAYER H1 · 更新 h1_pass（h4_pass 的1小时EMA）

**每15分钟执行：**
- [ ] T1 · 强制止损监控（最高优先级，必须首先执行）
- [ ] T2 · 趋势离场监控
- [ ] T3 · 加仓判断（仅对 add_count < 3 的持仓）
- [ ] T4 · 入场信号检测（仅当持仓 < 2 时执行）

---

## 输出格式要求

每次发生开仓、加仓、趋势离场、强制止损事件时，在终端以以下表格格式输出完整记录：

```
╔══════════════════╦══════════════════════════════════════════╗
║ 事件类型         ║ 开仓 / 第N次加仓 / 趋势离场 / 强制止损  ║
║ 时间             ║ YYYY-MM-DD HH:MM                         ║
║ 币种             ║ BTC-USDT-SWAP                            ║
║ 操作价格         ║ 83,250 USDT                              ║
║ 操作张数         ║ 3 张                                     ║
║ 当前止损价       ║ 81,900 USDT                              ║
║ 加权平均入场价   ║ 82,100 USDT                              ║
║ 当前总仓位       ║ 5 张                                     ║
║ 出场方式         ║ 趋势离场 / 强制止损 / 持仓中             ║
║ 本笔累计盈亏     ║ +125.30 USDT                             ║
║ 账户资金基准     ║ 1,125.30 USDT                            ║
╚══════════════════╩══════════════════════════════════════════╝
```

---


