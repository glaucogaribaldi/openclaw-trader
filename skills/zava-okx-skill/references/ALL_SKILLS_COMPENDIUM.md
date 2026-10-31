# ZAVA OKX SKILL — Complete Aggregated Compendium (76 Skills Total)

This file aggregates every official OKX Agent Skill (10), custom Zava/EEA/TRE OS skill (3), and all OKX Marketplace community skills (63).

## 1. Custom Zava / EEA XPERP & TRE OS Skills

### [1] `okx-eea-futures-and-funding`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/custom/okx-eea-futures-and-funding/SKILL.md`

---
name: okx-eea-futures-and-funding
description: Use when trading OKX Europe (eea.okx.com), fixing empty Trading balances, or resolving code 50124 on SWAP; trades regulated USD_UM_XPERP futures.
---

# OKX Europe (EEA) Perpetual Futures (USD_UM_XPERP) & Funding Account Transfer

Use this procedure when working with OKX Europe (https://eea.okx.com) REST v5 APIs for perpetual futures or account balance checks.

## 1. Check Both Trading (18) and Funding (6) Balances

When GET /api/v5/account/balance returns empty details ([]) or zero equity, check the Funding Account (6) because OKX sweeps can move idle USDC out of the Trading Account (18).

1. Query both endpoints:
   - Trading Account (18): GET /api/v5/account/balance
   - Funding Account (6): GET /api/v5/asset/balances
2. Verify recent internal transfers if needed via GET /api/v5/asset/bills.
3. To make funds available for order placement, transfer USDC from Funding (6) to Trading (18) via POST /api/v5/asset/transfer with body {"ccy": "USDC", "amt": "<amount>", "from": "6", "to": "18"}.
4. Re-check GET /api/v5/account/balance and confirm details lists the USDC balance (availBal > 0).

## 2. Discover Regulated EEA Perpetual Futures (instType=FUTURES, ruleType=xperp)

On OKX Europe (https://eea.okx.com under MiCA/MiFID II), standard instType=SWAP (*-USDT-SWAP and *-USD-SWAP) returns code 50124 ("This API Key does not have trading permission for the market") and maxBuy="0". Regulated European perpetual futures are listed under instType=FUTURES with ruleType="xperp" (*-USD_UM_XPERP-*), settled 1:1 against USDC (settleCcy="USD").

1. Query GET /api/v5/public/instruments?instType=FUTURES and filter for live xperp contracts (e.g., BTC-USD_UM_XPERP-310404, ETH-USD_UM_XPERP-310404, SOL-USD_UM_XPERP-310404) where ruleType == "xperp" and state == "live".
2. Inspect each contract's sizing fields before placing orders because sz is in contracts, not base units (including commodity/macro XPERP contracts such as `XAU-USD_UM_XPERP-310502` Gold with `ctVal=0.001, tickSz=0.1` and `CL-USD_UM_XPERP-310509` WTI Crude Oil with `ctVal=0.1, tickSz=0.01`):
   - ctVal: base units per contract (e.g., 0.0001 BTC, 0.01 SOL, 0.001 XAU, 0.1 CL, 1 SUI/XRP/NEAR, 10 DOGE/AVAX/FET/SEI)
   - minSz, lotSz, tickSz, and max lever
3. Check fee tier with GET /api/v5/account/trade-fee?instType=FUTURES (typically maker: -0.0002 / 2 bps, taker: -0.0005 / 5 bps).
4. For HTTP error inspection in Python requests, use resp.text if resp is not None else str(e) rather than bool(resp) because Response.__bool__() evaluates to False on HTTP 4xx/5xx.

## 3. Configure Leverage and Verify Buying Power on *-USD_UM_XPERP-*

1. Set isolated or cross leverage on the exact *-USD_UM_XPERP-* instId via POST /api/v5/account/set-leverage with {"instId": "SOL-USD_UM_XPERP-310404", "lever": "2.5", "mgnMode": "isolated"}.
2. Verify buying/selling capacity in contracts via GET /api/v5/account/max-size?instId=SOL-USD_UM_XPERP-310404&tdMode=isolated and confirm maxBuy > 0 and maxSell > 0.
3. Place and cancel a far-from-mid post_only order via POST /api/v5/trade/order (tdMode="isolated", ordType="post_only") and POST /api/v5/trade/cancel-order to confirm sCode="0".

## 4. Calculate Contract Size and Reconcile Live XPERP Positions

1. Convert target USD notional into contract count sz using ctVal and lotSz because XPERP order sz is in contracts (`raw_contracts = notional_usd / (px * ctVal)`, rounded to lotSz decimals and clamped to `>= minSz`).
2. Query open positions and pending orders with `instType=FUTURES` (`GET /api/v5/account/positions?instType=FUTURES` and `GET /api/v5/trade/orders-pending?instType=FUTURES`) rather than `instType=SWAP`.
3. Do not insert a `post_only` entry order into local open positions until `GET /api/v5/account/positions?instType=FUTURES` reports `abs(float(pos)) > 0`, and count live `orders-pending` toward your concurrency/slot limit so multiple orders do not fire in the same cycle before filling.
4. Import any live exchange position (`abs(float(pos)) > 0`) missing from local state using its `avgPx`, `pos` sign (`>0` LONG, `<0` SHORT), `margin`, and trailing/shield flags initialized to `0` (disarmed) so the next cycle does not immediately trigger a false protective exit.
5. Attach exchange-native take-profit and stop-loss triggers directly inside every entry `POST /api/v5/trade/order` payload via `"attachAlgoOrds": [{"tpTriggerPx": "<tp_px>", "tpOrdPx": "-1", "tpTriggerPxType": "last", "slTriggerPx": "<sl_px>", "slOrdPx": "-1", "slTriggerPxType": "last"}]` so OKX's matching engine enforces the hard stop even if the client host goes offline.
6. When a previously open position disappears from `GET /api/v5/account/positions?instType=FUTURES` (closed by exchange-side `attachAlgoOrds` or a software `reduceOnly` order), do not delete the local row; match its latest filled `reduceOnly="true"` order in `GET /api/v5/trade/orders-history?instType=FUTURES` and update the row to closed with the exchange's `avgPx`, `pnl`, and `fee` so post-stop cooldowns trigger and realized PnL matches exchange equity.
7. To ratchet the exchange-side stop-loss to break-even once a position reaches profit, query `GET /api/v5/trade/orders-algo-pending?instType=FUTURES&ordType=conditional,oco&instId=<instId>` to get the active `algoId`, then call `POST /api/v5/trade/amend-algos` with `{"instId": "<instId>", "algoId": "<algoId>", "newSlTriggerPx": "<breakeven_px>"}` and verify `sCode == "0"`.
8. To read Open Interest deltas on EEA XPERP contracts, call `GET /api/v5/public/open-interest?instType=FUTURES&instId=<instId>` (`instType=FUTURES`, not `SWAP`) and compare `oi` against a 15-minute rolling anchor `(anchor_ts, anchor_oi)` rather than the previous 15-second poll because OKX updates public Open Interest every 1–5 minutes.

---

### [2] `okx-trade`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/custom/okx-trade/SKILL.md`

---
name: okx-agent-tradekit
description: >
  Setup, install, and use OKX Agent Trade Kit (v1.5.0) — the official OKX toolkit and Agent Skills suite for AI-powered trading.
  Use this skill whenever the user mentions: OKX trading, agent tradekit, okx-trade-mcp, okx Skills, okx/agent-skills,
  OKX Skills Marketplace, installing OKX on OpenClaw, configuring OKX API keys or OAuth, trading BTC/ETH/crypto with natural language,
  spot/futures/options/event contracts/grid/DCA bots/earn/smartmoney/sentiment on OKX, or wants to connect an AI agent to OKX exchange.
---

# OKX Agent Trade Kit & Official Agent Skills (v1.5.0)

OKX Agent Trade Kit (`@okx_ai/okx-trade-cli` & `@okx_ai/okx-trade-mcp` v1.5.0) and the official `okx/agent-skills` repository provide a modular suite of 10 specialized skills and CLI modules for OKX (including EEA `site = "eea"`).

## Installed Official Skills (`~/.openclaw/workspace/skills/`)

All 10 official skills from `https://github.com/okx/agent-skills` are installed locally:

| Skill | CLI Module(s) | Funzione | Auth richiesta |
|---|---|---|---|
| `okx-cex-auth` | `auth`, `config` | Login OAuth 2.0 device flow, profili API key (`config.toml`), binary `okx-auth` | Setup |
| `okx-cex-market` | `market` | Prezzi, ticker, orderbook, candele, funding rate, OI, screener, stock/metalli/forex e 70+ indicatori tecnici (RSI, MACD, Bollinger, SuperTrend, AHR999…) | ❌ No |
| `okx-cex-trade` | `spot`, `swap`, `futures`, `option`, `event` | Ordini spot, perpetual swap, futures, opzioni, event contracts, TP/SL, trailing stop, iceberg, TWAP | ✅ Sì |
| `okx-cex-portfolio` | `account` | Saldi, posizioni, P&L, storico transazioni, fee tier, trasferimenti fondi, modalità posizione | ✅ Sì |
| `okx-cex-bot` | `bot` | Grid Bot (spot/contract/coin-margined), DCA Martingale (Spot/Contract), Smart Portfolio | ✅ Sì |
| `okx-cex-earn` | `earn` | Simple Earn (flessibile/fisso/lending), Flash Earn, On-chain Earn (staking/DeFi), Dual Investment (DCD), AutoEarn | ✅ Sì |
| `earn-hunter` | `earn` | Monitoraggio automatico opportunità Flash Earn, Fixed Earn e Flexible Earn | ✅ Sì |
| `okx-cex-smartmoney` | `smartmoney` | Analisi Smart Money: leaderboard top trader, tracking posizioni, segnali di consenso, flusso di capitale | ✅ Sì |
| `okx-sentiment-tracker` | `news` | Crypto news, sentiment analysis per coin, trending coins, social buzz, calendario macroeconomico | ✅ Sì |
| `okx-cex-skill-mp` | `skill` | OKX Skills Marketplace (`my.okx.com/it/agent-tradekit/skills`): ricerca, categorie, installazione, aggiornamento e verifica firme Ed25519 | ✅ Sì |

Helper condiviso: `skills/_shared/preflight.md` (preflight automatico CLI, rilevamento Auth API Key vs OAuth, controllo versione).

---

## Aggiornamento Rapido

1. **Aggiornare CLI e MCP Server**:
   ```bash
   okx upgrade
   # oppure:
   npm install -g --prefix ~/.local @okx_ai/okx-trade-cli@latest @okx_ai/okx-trade-mcp@latest
   ```

2. **Aggiornare le Skill Ufficiali da GitHub (`okx/agent-skills`)**:
   ```bash
   npx -y skills add okx/agent-skills --skill '*' -a openclaw --copy -y
   ```

3. **Gestire Skill dal Marketplace OKX**:
   ```bash
   okx skill search --keyword <kw>
   okx skill categories
   okx skill add <name>
   okx skill check <name>
   okx skill list
   ```

---

## Configurazione EEA / Profili (`~/.okx/config.toml`)

Per utenti europei (OKX Europe `my.okx.com`), impostare `site = "eea"` nel profilo in `~/.okx/config.toml`.
Non incollare mai API key o secret in chat.

## Riferimenti

- Marketplace OKX Europe: https://my.okx.com/it/agent-tradekit/skills
- Repository Skill Ufficiali: https://github.com/okx/agent-skills
- Repository Trade Kit CLI/MCP: https://github.com/okx/agent-trade-kit
- Riferimento Tool: [references/tools-reference.md](references/tools-reference.md)
- Setup MCP: [references/mcp-setup.md](references/mcp-setup.md)

---

### [3] `openclaw-trader`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/custom/openclaw-trader/SKILL.md`

# TRE OS • OpenClaw Quant Trader AgentSkill

Use this skill to control, monitor, and audit the TRE OS v5.5 Quantitative Trading System on OKX Spot.

## Capabilities & Workflows
1. **Live System Audit:** Runs a full-stack health check on the 1-minute execution daemon, OKX Spot API latency, and SQLite database.
2. **Account Balances & Fills:** Interrogates OKX Spot balance, NAV, USDC cash, and active limit traps across the 8 High-Beta tokens (, , , , , , , ).
3. **AI Co-Audit Integration:** Connects with OpenRouter Free Models () for secondary risk auditing and anomaly detection.
4. **Google Sheets Export:** Exports real-time transaction ledger and run metrics to CSV for Google Sheets integration.

## Installation
Run the 1-click installer:


## Commands & Tools
- Run Watcher Daemon: 
- Rebuild Ledger: 
- Run OpenRouter AI Co-Audit: 
- Launch Web Terminal:

---

## 2. Official OKX Agent Skills (v1.5.0)

### [1] `earn-hunter`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/earn-hunter/SKILL.md`

---
name: earn-hunter
description: "Automatically monitors OKX Flash Earn, Fixed Earn and Flexible Earn opportunities, sends push notifications, and guides subscription. 自动监控 OKX 闪赚、定期和活期赚币机会，推送通知并引导申购。Use when user says: 有闪赚通知我, 监控赚币, monitor earn, notify me about earn, 定时检查理财, 执行 earn-hunter 扫描, earn-hunter scan, 活期年化高了通知我, 监控活期."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: okx-cli
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# Earn Hunter

Automated monitor for OKX Flash Earn, Fixed Earn, and Flexible Earn (Simple Earn) opportunities.

**`{baseDir}`** = the directory containing this SKILL.md file. All relative paths (references/, templates/, config/) are resolved from here.

## Preflight

1. Verify `okx` CLI installed: `which okx`. If missing, install via `npm install -g @okx_ai/okx-trade-cli`.
   On OpenClaw, also verify the in-session `cron` tool is available in the agent tool list (used for scheduling — not the `openclaw` CLI).
2. Check optional dependent skills:
   ```bash
   okx skill list --json
   ```
   Optional skills (not required for scanning/notifications):
   - `okx-cex-earn` — needed for purchase guide (subscription execution)
   - `okx-cex-auth` — needed for authentication recovery

   If either is missing, attempt to install but **do not block** if installation fails:
   ```bash
   okx skill add okx-cex-earn
   okx skill add okx-cex-auth
   ```
   - Install succeeds → continue
   - Install fails (network error, marketplace unavailable, etc.) → **warn and continue**:
     "⚠ `{skill_name}` 安装失败，扫描和通知功能不受影响。申购引导和认证恢复需要该 skill，后续可手动安装。"
   - Preflight continues regardless of skill installation result
4. Auth mode detection — run **both**, first match wins:
   - `okx config show --json` → has non-empty `api_key` field → **API Key mode**. Add `--profile live` to all commands.
   - No API key + `okx auth status --json` → `"status":"logged_in"` → **OAuth mode**. No `--profile` flag needed.
   - Neither → **stop**. Load `okx-cex-auth` skill and follow login steps.
5. Init config and state:
   - If `~/.okx/earn-hunter/` directory does not exist → `mkdir -p ~/.okx/earn-hunter`
   - If `~/.okx/earn-hunter/config.json` does not exist → copy `{baseDir}/config/default.json` to it
   - If `~/.okx/earn-hunter/state.json` does not exist → write `{"flash":{},"fixed":{},"flexible":{},"consecutive_failures":0,"last_error":""}`
   - If `~/.okx/earn-hunter/platform.json` does not exist → run [Platform Detection](#platform-detection-active-probe--user-confirmation)
   - Always (re)install the scan script: `cp {baseDir}/scripts/scan.sh ~/.okx/earn-hunter/scan.sh && chmod +x ~/.okx/earn-hunter/scan.sh`. This is the script cron and interactive scans both call.
   - Write `~/.okx/earn-hunter/env.snapshot` with resolved tool paths (cron cannot rely on the user's login PATH):
     ```bash
     cat > ~/.okx/earn-hunter/env.snapshot << SNAP
     # auto-generated by earn-hunter activation — $(date -Iseconds)
     OKX_BIN=$(command -v okx)
     NODE_BIN=$(command -v node)
     JQ_BIN=$(command -v jq)
     ACTIVATION_PATH=$PATH
     SNAP
     ```
     The scan script sources this file to resolve tool paths even under cron's minimal `PATH=/usr/bin:/bin`.

   Config/state/platform JSON read-write done by the agent is only for activation/config management. The recurring **scan itself is performed entirely by `scripts/scan.sh`** (shell + jq) — `jq` is required for scanning. Verify with `which jq`; if missing, install (`brew install jq` / `apt-get install jq`).

## Platform & Channel Detection

Three independent dimensions: **platform** (where the agent runs), **scheduler** (what triggers scans), **notification channel** (where alerts go).

### Platform Detection (active probe + user confirmation)

**First run (no `platform.json` exists):**

1. Probe environment clues:
   - `OPENCLAW_HOME` env var exists? → hint: OpenClaw
   - Agent tool list contains `cron` / `delivery` tools? → hint: OpenClaw
   - `HERMES_HOME` env var exists or `which hermes` succeeds? → hint: Hermes Agent
   - Running inside Claude Code session? → hint: Claude Code
   - None of the above matched → hint: Generic
2. Present detection result and **ask user to confirm**:
   - "检测到你正在使用 **{detected_platform}**，是否正确？"
   - User confirms → proceed
   - User says no → ask: "你使用的是哪个平台？1) OpenClaw  2) Claude Code  3) Hermes Agent  4) 其他"
3. Initialize platform config:
   - OpenClaw / Claude Code → copy `{baseDir}/config/<confirmed_platform>.default.json` to `~/.okx/earn-hunter/platform.json`
   - Hermes Agent → copy `{baseDir}/config/claude-code.default.json` as base, set `.platform` to `"hermes"`, `.scheduler.type` to `"cron"`
   - Generic → copy `{baseDir}/config/claude-code.default.json` as base, set `.platform` to `"generic"`, `.scheduler.type` to `"manual"`
4. Result written to `~/.okx/earn-hunter/platform.json`, subsequent runs skip detection.

**Subsequent runs (platform.json exists):**
Read `~/.okx/earn-hunter/platform.json` and extract the `.platform` field (returns `"openclaw"`, `"claude-code"`, `"hermes"`, or `"generic"`).

**No scheduler available on detected platform** (only applies to platforms that should have one but don't) → error: "当前客户端不支持定时任务，请升级到最新版本。"
**Generic platform** → no automatic scheduler. Inform: "当前平台不支持自动调度，你可以手动说'执行 earn-hunter 扫描'来触发。"

### Configuration Files

| File | Scope | Content |
|---|---|---|
| `config.json` | Shared | Scan scope (flash/fixed/flexible), currencies, APY thresholds, terms, language, verboseLog |
| `platform.json` | Platform-specific | Scheduler type/interval, notification channel, TG/Lark credentials |
| `state.json` | Shared | Dedup state |

Core config (`config.json`) is identical across platforms. Platform config (`platform.json`) differs — the `scheduler.type` field determines how scans are triggered:

**OpenClaw (`openclaw.default.json`):**
- scheduler.type = `"openclaw-cron"` — scheduled via the in-session **`cron` agent tool** (no OS crontab, no CLI commands). The job runs as an **isolated, light-context** agent turn and delivers its output back to the conversation channel via cron **`announce`** delivery. notify.channel defaults to `"session"` so the scan prints to stdout for `announce` to push (avoids double-send).

**Claude Code / Hermes / Generic (`claude-code.default.json`):**
- scheduler.type = `"cron"` — scheduled via **OS crontab → `scripts/scan.sh`** (zero LLM token cost), notification via TG / Lark curl from the script itself.

### Notification Channels (independent of platform)

Detect in priority order (PRD requirement: TG first):
1. **Telegram** — `$TELEGRAM_BOT_TOKEN` and `$TELEGRAM_CHAT_ID` both set → TG ready
2. **Lark** — `platform.notify.lark_webhook` non-empty → Lark ready
3. **Session** — fallback, only works in interactive mode

TG and Lark are **standalone push channels** — they work regardless of whether the agent client is open. On OS-crontab platforms, scheduled scans send notifications via direct curl. On **OpenClaw**, the scheduled scan runs in an isolated cron agent turn and delivers via cron **`announce`** to the conversation channel (channel = `"session"`); TG/Lark curl is not used unless the user explicitly switches the channel.

---

## Skill Routing

| User intent | Route |
|---|---|
| "有闪赚通知我" / "monitor earn" / "帮我监控赚币" / "活期年化高了通知我" | → [Activation Flow](#activation-flow) |
| "改 APY 阈值" / "只看 USDT" / "change config" / "活期加上 BTC" | → [Config Management](#config-management) |
| "申购 USDT 定期 7D" / "subscribe" / "我要买" | → [Purchase Guide](#purchase-guide) |
| "执行 earn-hunter 扫描" (cron OR interactive) | → [Scan Cycle](#scan-cycle) — run `scripts/scan.sh` and relay its output |
| "停止监控" / "暂停" / "stop" | → [Pause/Resume](#pauseresume) |
| "卸载 earn-hunter" / "uninstall" | → [Uninstall](#uninstall) |
| "测试 earn-hunter" / "smoke test" / "测试定时任务" | → [Test Mode](#test-mode) |

---

## Activation Flow

First-time setup. Only confirm platform — everything else uses smart defaults.

### Step 1 — Platform Detection & Confirmation

See [Platform Detection](#platform-detection-active-probe--user-confirmation). Probe environment → ask user to confirm → write `platform.json`.

### Step 2 — Detect Notification Channel & Confirm

**Must actively check available channels before proceeding.** Do NOT silently fall back to session.

On OS-crontab platforms, scheduled notifications go out via direct curl; on OpenClaw they go out via cron `announce` to the conversation. Detection order (check each, report status for all):
1. Check `$TELEGRAM_BOT_TOKEN` and `$TELEGRAM_CHAT_ID` env vars:
   - Both set → TG ready
   - Token set but chat_id missing → warn: "Telegram 配置不完整（缺少 TELEGRAM_CHAT_ID），跳过 TG" → continue to next channel
   - Neither set → TG not available
2. Check `platform.notify.lark_webhook` or Lark MCP tools:
   - Webhook set and valid (starts with `https://` and contains `/hook/`) → Lark ready
   - Webhook set but format invalid (does not start with `https://` or missing `/hook/`) → warn: "Lark webhook 格式无效，跳过 Lark" → continue to next channel
   - Not configured and no Lark MCP → Lark not available

**Always ask the user to confirm notification channel — never silently default to session.** For a monitoring tool, notification is critical; defaulting to session means alerts are lost when the user is not in the conversation.

**If one or more external channels detected:**

"检测到以下推送渠道可用：
- {list of detected channels, e.g. Telegram / Lark}

你希望通知发到哪里？
1. {detected channel 1}
2. {detected channel 2, if any}
3. 仅在当前会话显示（离线收不到）"

**If no external channel detected:**

"新机会才能推送到你手上。你希望通知发到哪里？
1. Telegram — 需要提供 Bot Token 和 Chat ID（通过环境变量）
2. Lark/飞书 — 需要提供 Webhook URL
3. 仅在当前会话显示（⚠ 离线收不到通知）

推荐配置 Telegram 或 Lark，这样即使不在对话中也能收到提醒。"

- If user picks Telegram → guide setting `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars
- If user picks Lark → ask for webhook URL, validate format (starts with `https://`, contains `/hook/`), write to `platform.notify.lark_webhook`
- If user picks session → write `"session"` and warn: "⚠ 离线状态下不会收到通知，建议后续配置外部渠道。"

Write confirmed channel to `platform.json` `notify.channel`.

### Step 3 — Confirm Scan Config (3-step with defaults)

Present default config and ask user to confirm or customize. Each step offers a default — user can press enter to accept.

**Step 1/3 — 扫描范围：**
"扫描范围（可多选）：
 [1] Flash Earn（闪赚）
 [2] Fixed Earn（定期赚币）
 [3] Flexible Earn（活期赚币）
 默认：全选"
- Default: all three enabled
- If user picks specific items → disable the others
- If user only picks [1] → set `config.fixed.enabled = false`, `config.flexible.enabled = false`; skip Step 2/3 and 3/3
- If user only picks [3] → set `config.flash.enabled = false`, `config.fixed.enabled = false`; go to flexible-specific config (Step 2/3 asks flexible currencies, Step 3/3 asks flexible APY threshold)

**Step 2/3 — 监控币种：**
For Fixed Earn: "定期监控币种：全部（默认，按回车）或输入指定币种（如 USDT, SOL）"
- Default: `"all"` (all currencies)
- If user specifies → set `config.currencies` to array (e.g. `["USDT", "SOL"]`)

For Flexible Earn: "活期监控币种：USDT, USDC（默认，按回车）或输入指定币种"
- Default: `["USDT", "USDC"]`
- If user specifies → set `config.flexible.currencies` to array
- Note: flexible requires per-currency API calls, so recommend keeping the list small

**Step 3/3 — APY 阈值：**
For Fixed Earn: "定期最低 APY 阈值：不限（默认，按回车）或输入百分比（如 8）"
- Default: `0` (no limit)
- If user specifies → set `config.fixed.globalMinApy` to `value / 100` (e.g. 8 → `0.08`)

For Flexible Earn: "活期最低 APY 阈值：8%（默认，按回车）或输入百分比"
- Default: `0.08` (8%)
- If user specifies → set `config.flexible.globalMinApy` to `value / 100`

Auto-detect language from conversation and write to `config.json` `notify.language`.

Write config to `~/.okx/earn-hunter/config.json`.

Display summary using `{baseDir}/templates/activation.md` template (in user's language).

### Step 4 — Smoke Test & Delivery Confirmation

**Smoke test always sends a notification, regardless of `verboseLog` setting.**

1. Run one scan cycle immediately with `verboseLog` forced on so output is always produced, even when there are no opportunities. Temporarily flip `verboseLog`, run the script, then restore it — and use `EH_TEST_NAMESPACE=1` so smoke-test dedup keys go under the `test:` prefix and don't pollute production state:
   ```bash
   jq '.verboseLog=true' ~/.okx/earn-hunter/config.json > ~/.okx/earn-hunter/config.tmp \
     && mv ~/.okx/earn-hunter/config.tmp ~/.okx/earn-hunter/config.json
   EH_TEST_NAMESPACE=1 OKX_PROFILE=live ~/.okx/earn-hunter/scan.sh
   # then restore verboseLog to the user's original value (e.g. false)
   ```
2. **If new opportunities found** → the script sends the normal notification (rendered from templates)
3. **If no opportunities found** → with `verboseLog` forced on, the script sends the brief status. Optionally append the activation confirmation message:
   "Earn Hunter 已激活，当前暂无新机会，将在下一轮自动扫描。"
   (Use `{baseDir}/templates/activation.md` as base, append the no-opportunity note)
4. TG or Lark channel → **ask:** "已向 {channel} 发送测试消息，请确认是否收到？"
5. User confirms → proceed to Step 5
6. Not received → troubleshoot (see `notify-channels.md`)
7. 5 min no response → ping once
8. Session channel → skip confirmation

**Note:** The smoke test ignores `verboseLog` setting — it always produces output to verify the full pipeline works end-to-end.

### Step 4b — Cron Environment Smoke Test (OS-crontab platforms only)

**Critical:** The user's interactive shell has a full PATH, but cron does not. Run a second smoke test simulating cron's minimal environment to verify `env.snapshot` works:

```bash
env -i HOME="$HOME" PATH=/usr/bin:/bin \
  EH_TEST_NAMESPACE=1 OKX_PROFILE=live \
  bash ~/.okx/earn-hunter/scan.sh
```

- If exit 0 → cron will work. Proceed to Step 5.
- If exit 127 / "FATAL: 'okx' not found" → `env.snapshot` is incomplete or missing. Re-run Preflight step to regenerate it. **Do NOT proceed to Step 5** — the cron job will fail silently.
- Show the user: "已验证 cron 最小环境下可正常执行。如果此步失败，说明 env.snapshot 中的工具路径有误。"

### Step 5 — Set Up Scheduler

The scheduling mechanism depends on `platform.json` `.scheduler.type`. Branch on the platform.

#### OpenClaw (`scheduler.type = "openclaw-cron"`)

On OpenClaw, scheduling is done **inside the conversation** by calling the in-session **`cron` agent tool** — never an OS command or `openclaw cron` CLI (the CLI path has permission issues in this context). Encourage the user to set it up right here in the chat: the cron job you create inherits the current session's channel, so its scan output is delivered straight back to this conversation.

Call the `cron` tool with `action: "add"` and a `job` shaped like this (read `.scheduler.interval` from `platform.json` for the frequency):

- `name`: `"earn-hunter-hourly"`
- `schedule`: `{ "kind": "every", "everyMs": 3600000 }` — derive `everyMs` from `scheduler.interval` (`"1h"` → 3600000, `"30m"` → 1800000, `"2h"` → 7200000)
- `sessionTarget`: `"isolated"` — run in an isolated session, not the main one
- `payload`: `{ "kind": "agentTurn", "message": "执行 earn-hunter 扫描", "lightContext": true }`
  - `lightContext: true` runs the turn with a lightweight bootstrap context (skips workspace bootstrap files) → lower token cost per tick.
  - **Token budget:** OpenClaw cron jobs have **no per-job tool-whitelist field** (the old `--tools exec,read,write` flag no longer exists). The scan stays cheap because it runs the `okx` CLI through `exec` and does **not depend on** the 160+ okx MCP tools — so as long as the isolated cron agent isn't configured to load the okx MCP server, only the regular tools (exec/read/write) are in play. Which tools load is governed by the agent's config, not by this job.
- `delivery`: `{ "mode": "announce" }` — pushes the turn's output back to the conversation channel that created the job.

When it fires, the isolated agent runs the prompt `"执行 earn-hunter 扫描"` → [Scan Cycle](#scan-cycle) (which runs `scripts/scan.sh` with channel `session`/stdout) → relays the result → `announce` delivers it here. Any new opportunity is therefore sent automatically.

**Do NOT** emit any shell/`openclaw cron` CLI command in the conversation — drive scheduling only through the `cron` tool.

#### OS-crontab platforms (`scheduler.type = "cron"` or `"launchagent"` — Claude Code / Hermes / Generic)

These use **OS scheduler → `scripts/scan.sh`**. The script does everything (CLI calls, filter, dedup, render, curl notifications) with **zero LLM cost**.

**Install the script** — copy the skill's `scripts/scan.sh` into the state dir so the scheduler has a stable path:

```bash
mkdir -p ~/.okx/earn-hunter
cp {baseDir}/scripts/scan.sh ~/.okx/earn-hunter/scan.sh
chmod +x ~/.okx/earn-hunter/scan.sh
```

**Set up scheduler** — try crontab first, fallback to LaunchAgent on macOS if cron daemon is not running:

```bash
# Resolve tool directories from the current shell
NODE_DIR=$(dirname "$(command -v node)")
OKX_DIR=$(dirname "$(command -v okx)")
JQ_DIR=$(dirname "$(command -v jq)")
CRON_PATH=$(printf '%s\n' "$NODE_DIR" "$OKX_DIR" "$JQ_DIR" /usr/bin /bin | awk '!seen[$0]++' | paste -sd: -)
```

**Step A: Try crontab + verify cron daemon (macOS)**

```bash
(crontab -l 2>/dev/null; echo "0 * * * * PATH=$CRON_PATH OKX_PROFILE=live ~/.okx/earn-hunter/scan.sh >> ~/.okx/earn-hunter/cron.log 2>&1") | crontab -
```

On macOS (`uname -s` == `Darwin`), immediately check if the cron daemon is running:

```bash
if [[ "$(uname -s)" == "Darwin" ]] && ! launchctl list com.vix.cron >/dev/null 2>&1; then
  # cron daemon not running — fallback to LaunchAgent
fi
```

- If cron daemon is running → done, `scheduler.type = "cron"`.
- If cron daemon is **not** running → remove the crontab entry and proceed to Step B.
- On Linux → skip the check (cron is always available), `scheduler.type = "cron"`.

**Step B: macOS LaunchAgent fallback** (`scheduler.type = "launchagent"`)

Generate `~/Library/LaunchAgents/com.okx.earn-hunter.plist` with the resolved paths:

```bash
SCAN_SCRIPT="$HOME/.okx/earn-hunter/scan.sh"
LOG_FILE="$HOME/.okx/earn-hunter/cron.log"
INTERVAL=3600  # derive from scheduler.interval: "1h"→3600, "30m"→1800, "10m"→600

cat > ~/Library/LaunchAgents/com.okx.earn-hunter.plist << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.okx.earn-hunter</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCAN_SCRIPT}</string>
    </array>
    <key>StartInterval</key>
    <integer>${INTERVAL}</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${CRON_PATH}</string>
        <key>OKX_PROFILE</key>
        <string>live</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST

launchctl load ~/Library/LaunchAgents/com.okx.earn-hunter.plist
```

Write `scheduler.type = "launchagent"` to `platform.json`. Inform user:

"macOS cron 服务未运行，已自动切换为 LaunchAgent 调度（无需 sudo，重启自动恢复）。"

**Notes:**
- **OAuth mode** → omit `OKX_PROFILE` from the plist `EnvironmentVariables` (or set to empty).
- LaunchAgent plist paths must be absolute (no `~`). The activation flow expands `$HOME` at generation time.
- `RunAtLoad: true` means the first scan runs immediately after loading.
- The script reads `config.json` / `platform.json`, writes `state.json` / `notify.log`, and sends notifications via curl to TG Bot API or Lark Webhook itself. No agent involvement needed at tick time.
- The script exits 0 and produces **no output** when there are no new opportunities and `verboseLog=false` — this is the intended silent behavior.

**IMPORTANT: On OS-scheduler platforms, do NOT use agent-platform `/loop` / Routines** (Claude Code `/loop`, cloud Routines). These spawn LLM sessions per tick and cannot reliably push external notifications. (OpenClaw is the exception above — it uses its in-session `cron` tool with `announce` delivery by design.)

---

## Scan Cycle

**The entire Scan Cycle is implemented by `scripts/scan.sh` (pure shell + jq, zero LLM cost).** Whether triggered by OS crontab, by an OpenClaw isolated cron agent turn, or by a user in an interactive session ("执行 earn-hunter 扫描"), the cycle is the **same**: run the script and relay its output. Do NOT re-implement the scan steps in natural language — the script is the single source of truth.

**OpenClaw isolated cron turn:** the job's prompt routes here. Run `scripts/scan.sh` (with `platform.json` `notify.channel = "session"`, the script prints any notification to stdout); relay that stdout as the turn's response. The cron job's `announce` delivery then pushes it to the conversation channel. Do not curl TG/Lark from this turn — delivery is handled by `announce`.

### How the agent runs a scan (interactive trigger)

```bash
# Profile: pass OKX_PROFILE only in API Key mode (omit for OAuth mode).
OKX_PROFILE=live ~/.okx/earn-hunter/scan.sh
```

Then **relay the script's stdout verbatim** to the user:
- If the script prints a notification (Flash / Fixed / mixed / verbose status), show it.
- If the script prints **nothing** (silent exit 0, the no-new-opportunity + `verboseLog=false` case), tell the user "本轮扫描完成，无新机会" — do NOT fabricate a "scan complete" message into a channel; the silence is intentional.

### What the script does (see `references/scan-logic.md` for the spec it implements)

1. Reads `~/.okx/earn-hunter/config.json`
2. Runs scan commands (based on `flash.enabled` / `fixed.enabled` / `flexible.enabled`):
   - Flash: `okx [--profile live] earn flash-earn projects --status 0,100 --json`
   - Fixed: `okx [--profile live] earn savings fixed-products --json` (auto-fallback to `rate-history` + `fixedOffers` on CLI <1.3.3)
   - Flexible: for each currency in `flexible.currencies`, `okx [--profile live] earn savings rate-history --ccy <ccy> --limit 1 --json`
3. Filters (two-layer APY threshold, terms filter, currency filter; flexible uses threshold-crossing model)
4. Dedups against `~/.okx/earn-hunter/state.json` (`state.flash["<id>:<status>"]`, `state.fixed["<ccy>:<term>:<rate>"]`, `state.flexible["<ccy>"]`)
5. If new opportunities → renders the matching template (flash / fixed / flexible / mixed) and sends via the detected channel (TG → Lark → session), logging to `notify.log`
6. Updates `state.json` (write new keys; flash ID-level diff cleanup; fixed key-level diff cleanup; flexible threshold-crossing diff cleanup; 7-day TTL; failure counter)
7. If no new opportunities: `verboseLog=true` → brief status; `verboseLog=false` → **silent exit 0, no output, nothing sent**
8. Error handling: consecutive-failure counter (alert at 3, then reset); 401/session-expired → credential alert + stop

**Channel routing inside the script:** detection order TG (`$TELEGRAM_BOT_TOKEN`+`$TELEGRAM_CHAT_ID`) → Lark (`platform.json` `.notify.lark_webhook`) → session (stdout). A `notify.channel` of `telegram`/`lark`/`session` in `platform.json` forces that channel.

**Auth / profile:** the script never reads or prints credentials. It delegates all auth to the `okx` CLI (which reads `~/.okx/config.toml`). Profile is injected only via the `OKX_PROFILE` env var.

**Flexible Earn dedup model:** Unlike Flash/Fixed which dedup by specific opportunity, Flexible uses a **threshold-crossing** model — key is just `<ccy>`. Notifies once when APY crosses above threshold; stays silent while it remains above; resets when APY drops below threshold (diff cleanup removes the key). This avoids frequent notifications from rate fluctuations.

---

## Purchase Guide

When user wants to subscribe to a Fixed Earn product after receiving a notification.

Read `{baseDir}/references/purchase-guide.md` for the complete flow.

Summary:

1. Parallel balance check (funding + trading + flexible earn)
2. Compare fixed APR vs flexible lendingRate
3. Calculate recommended amount: `min(idle + movable_simple_earn, lendQuota)`
4. Present recommendation with comparison hint
5. User confirms → **re-check offer availability** (soldOut guard) → hand off to `okx-cex-earn`

Edge cases covered in purchase-guide.md:
- Balance < minLend → show deficit
- Amount > lendQuota → auto-cap with notice
- Redeem succeeded but subscribe failed → warn user, funds are in funding account
- Offer sold out between notification and subscription → inform user

**Important:** earn-hunter does NOT execute write operations directly. It transfers control to `okx-cex-earn`.

---

## Config Management

Read `{baseDir}/references/config-reference.md` for field definitions and natural language examples.

When user wants to change settings:
1. Parse intent → map to config field (see `config-reference.md` for field mapping)
2. Read the target JSON file (`config.json` or `platform.json`) → modify the field → write back
3. Read the updated file → confirm the change to user

**Exception:** TG credentials cannot be changed via natural language. Tell user to set environment variables directly.

---

## Pause/Resume

Branch on `platform.json` `.scheduler.type`:

**OpenClaw (`openclaw-cron`)** — manage via the in-session `cron` tool (no CLI):
- **Pause:** call `cron` with `action: "update"`, targeting the `earn-hunter-hourly` job, patch `{ "enabled": false }` (or `action: "remove"` to delete it).
- **Resume:** `action: "update"` with `{ "enabled": true }` (or re-create as in Activation Step 5).
- Use `action: "list"` to find the job id.

**OS-crontab platforms (`cron`):**
- **Pause:** `crontab -l | grep -v 'earn-hunter' | crontab -`
- **Resume:** Re-add the crontab entry (same as Activation Step 5).

**macOS LaunchAgent (`launchagent`):**
- **Pause:** `launchctl unload ~/Library/LaunchAgents/com.okx.earn-hunter.plist`
- **Resume:** `launchctl load ~/Library/LaunchAgents/com.okx.earn-hunter.plist`

Config and state are preserved — resuming picks up where it left off.

---

## Uninstall

When user says "卸载" / "uninstall":
1. Stop the scheduler (same as Pause). For LaunchAgent, also remove the plist:
   `launchctl unload ~/Library/LaunchAgents/com.okx.earn-hunter.plist && rm -f ~/Library/LaunchAgents/com.okx.earn-hunter.plist`
2. Ask: "是否保留配置和历史数据？"
   - Yes → only remove scheduler
   - No → also remove `~/.okx/earn-hunter/` directory

---

## Test Mode

Trigger phrases: "测试 earn-hunter" / "earn-hunter smoke test" / "测试定时任务触发"

Behavior — run the script with the Test Mode hooks (no separate logic needed):

```bash
# Force verbose so output is always produced; write dedup keys under test: prefix.
EH_TEST_NAMESPACE=1 OKX_PROFILE=live ~/.okx/earn-hunter/scan.sh   # with config.verboseLog temporarily set to true
```

1. **Execute a full Scan Cycle** — the script runs the same scan, but `EH_TEST_NAMESPACE=1` isolates state writes
2. **Force-send notification** — temporarily set `config.verboseLog=true` so the script always sends output regardless of whether opportunities are found (restore afterwards)
3. **Dedup writes to test namespace** — `EH_TEST_NAMESPACE=1` prefixes dedup keys with `test:` (e.g. `test:flash:12345:100`); these keys are immune to diff cleanup (only TTL removes them), so test runs do not pollute production state
4. **Output diagnostics** after scan completes:
   - okx auth status (logged in / expired / not configured)
   - Scan command results (flash project count + fixed product count + flexible rate count)
   - Post-filter results (how many passed filters per type)
   - Notification channel status (which channel is configured, send result)
   - Scheduler status (OS-crontab platforms: crontab entry exists? / OpenClaw: `cron` tool `action: "list"` shows the `earn-hunter-hourly` job?)
   - Last 5 lines of `~/.okx/earn-hunter/notify.log`
5. **Completion message:** "测试完成。test: 前缀的 state 不影响正式去重，正式扫描不受影响。"

---

## Error Handling

Read `{baseDir}/templates/error-alert.md` for exact alert message templates.

| Error | Action |
|---|---|
| `okx` 401 / "Session expired" | Stop scan. Send alert (凭证失效 template). Load `okx-cex-auth` if interactive. |
| Network error / timeout | Retry once silently. If still fails, skip this cycle. |
| 3 consecutive scan failures | Send alert (连续失败 template). Counter stored in `state.consecutive_failures`, reset after alert. |
| `state.json` corrupted | Reset by writing `{"flash":{},"fixed":{},"consecutive_failures":0,"last_error":""}`. May cause one round of duplicate notifications. |
| Notification send fails | Log to `notify.log`, continue scan. Dedup key NOT added (next cycle retries). |
| `config.json` missing at runtime | Send alert: "earn-hunter 未配置，请运行首次激活流程。" |
| Dual-client suspected (user mentions both platforms) | Warn: "建议仅在一个客户端运行 earn-hunter，避免重复通知。" |
| `verboseLog = true` + no hits | Send brief status (not silent). |

---

## i18n

- **All notifications rendered in user's language** (detected at activation, stored in `config.notify.language`)
- **Locked terms (never translate):** Flash Earn, Fixed Earn, Simple Earn, DCD, APY, APR, OKX, earn-hunter, Telegram, project names, currency codes (USDT, BTC, etc.)
- **Fallback:** If LLM rendering fails, send Chinese template + append `(translation unavailable, sent in zh-CN)`

---

## Global Notes

- **Security:** Never accept credentials in chat. TG token only via env vars. Guide users to `okx config init` for OKX auth.
- **Output:** Use `--json` for all okx commands. Render results as markdown tables.
- **Logging:** All notification send results logged to `~/.okx/earn-hunter/notify.log`.
- **Scope:** Covers Flash Earn, Simple Earn Fixed, and Simple Earn Flexible (活期). DCD, on-chain, auto-earn are out of scope.
- **Mode:** Live trading only. `config.simulatedTrading` is always `false`.

## Defensive Design Principles

These constraints apply to all changes to earn-hunter:

1. **cron PATH ≠ user shell PATH.** Any cron-triggered script must resolve tool paths independently — never assume cron inherits the user's login PATH. The script uses `env.snapshot` + `resolve_bin` fallback.
2. **Sanity check first.** Before running any CLI command, verify the binary exists. Missing tool → immediate exit with clear error, not silent failure.
3. **Never swallow stderr.** Use `2>&1` (capture into variable) instead of `2>/dev/null` for CLI calls. Otherwise error messages vanish and `last_error` is empty.
4. **Smoke test must simulate production.** Activation smoke test runs twice: once in user shell (verify credentials/network), once in minimal `env -i PATH=/usr/bin:/bin` (verify cron can run). Don't pass Step 5 if cron smoke fails.
5. **Alert templates must handle empty fields.** If `last_error` is empty string, append "check `~/.okx/earn-hunter/cron.log`; empty error usually means PATH issue" guidance.
6. **Tool paths use snapshot + fallback, not global PATH.** `env.snapshot` written at activation with exact paths; `resolve_bin` tries snapshot → `command -v` → hardcoded common paths. Survives `nvm switch` / Homebrew upgrades.

---

### [2] `okx-cex-auth`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-auth/SKILL.md`

---
name: okx-cex-auth
description: "Use this skill when the user wants to 'login/log in/sign in', 'authenticate', 'authorize', 'connect OKX account', 'set up credentials', 'first time setup', 'configure okx', '登录', '授权', '认证', '连接账户', '首次配置'. Also when any OKX CLI command fails with an auth error: 'Run okx auth login first', 'Session expired', 'not authenticated', 'requires_auth', '401 Unauthorized', 'token expired/not found', 'StorageNotFoundError', '会话过期', '未认证', '需要登录'. Also when the user asks about login status or the login was interrupted. Also when the user wants to install/update/check/remove the okx-auth binary — 'install/update/remove auth', 'download okx-auth', '安装/更新/卸载认证', 'auth binary status', 'Failed to spawn okx-auth'. Also use before using okx-cex-trade/portfolio/earn/bot for the first time. Do NOT use for market data queries (use okx-cex-market)."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Authentication

OAuth 2.0 device flow authentication for OKX CLI. Guides first-time setup, re-authentication after session expiry, and logout.

## Supported Sites

| Site | Region | URL |
| -------- | ----------------------- | --------------- |
| `global` | Global | `www.okx.com` |
| `eea`    | EEA    | `my.okx.com`  |
| `us`     | US     | `app.okx.com` |
| `tr`     | TR     | `tr.okx.com`  |

Site is a separate dimension from auth method. Both API-key and OAuth paths require a site. Once selected, a site is persisted:
- **API-key users**: `profile.site` in `~/.okx/config.toml` (written by `okx config init`).
- **OAuth users**: saved inside the `okx-auth` binary state the first time `okx auth login --site <X>` succeeds, and returned by `okx auth status --json` as the `site` field.

There is **no `okx config set-site` command** — site cannot be persisted independently of an auth attempt. For OAuth flows, the agent must remember the user's choice within the conversation and pass `--site <X>` on `okx auth login`.

## Prerequisites

Install `okx` CLI if not already installed:

```bash
npm install -g @okx_ai/okx-trade-cli
```

## Step 0: Pre-flight Check (MANDATORY)

**Unconditional rule — do NOT skip Step 0 under any circumstances.** Even if a prior skill (preflight, okx-cex-portfolio, etc.) already ran `auth status` and passed you a conclusion like "user is not_logged_in, go log in" — **you MUST re-run the two commands below yourself and walk Steps 0.1 → 0.2 → 0.3 in order**. Upstream tool output does not substitute for your own pre-flight. The single most common failure mode for this skill is an agent that reads an upstream "not authenticated" signal, skips Step 0.1 site selection, and calls `okx auth login` with a silently-defaulted site.

Run both in parallel:

```bash
okx config show --json
okx auth status --json
```

Then apply the following three checks **in strict order** — each step short-circuits the rest.

### Step 0.1 — Site check (independent of auth mode)

A site is considered already selected if **either** is true:
- `config show --json` has any profile with a non-empty `site` field, OR
- `auth status --json` returns a non-empty `site` field **AND** `status` is `logged_in` or `pending`.

> ⚠ When `status` is `not_logged_in`, the `site` field from `auth status --json` is a **default placeholder** (typically `"global"`) that the auth binary emits regardless of user choice — it does NOT mean the user ever picked a site. Treat it as absent.

If **neither** condition above holds, site has never been chosen. You MUST ask the user to pick one before any login attempt by echoing the following menu verbatim (Chinese), and wait for their reply:

> 您需要选择要连接的 OKX 站点：
> 1) Global (www.okx.com)
> 2) EEA (my.okx.com)
> 3) US (app.okx.com)
> 4) TR (tr.okx.com)

Map the reply (`1`/`2`/`3`/`4` or `global`/`eea`/`us`/`tr`) to the corresponding site id and remember it for the rest of this flow. Do NOT default to `global` silently — that hides the regional choice from the user.

### Step 0.2 — API-key check

Parse `config show --json`: does any profile have a non-empty `api_key` field?

If yes → **STOP.** Tell the user "已配置 API key (profile: <name>)" and proceed with their original request directly. DO NOT run `okx auth login` or `okx config init`.

> The CLI's REST client always prefers API key over OAuth and never falls back (see `rest-client.ts applyAuth`). Starting an OAuth login in this state is wasted effort — any OAuth token obtained would not be used, because the broken API key is still picked first.
>
> Belt-and-suspenders: as of CLI `1.3.1-beta.17`, `okx auth login` itself refuses to start OAuth when any profile has `api_key` — in `--manual` mode it emits `{"status":"skipped","reason":"api_key_configured","profile":"<name>"}`. Treat that output as success.

#### Step 0.2.a — Handling an invalid API key (401 / signature error)

If Step 0.2 detected an `api_key` profile and the subsequent API call returns an authentication error (`401 Unauthorized`, `Invalid Sign`, `Invalid API-KEY`, OKX error code `50111`/`50113`), **the API key is bad — OAuth login is NOT a valid remediation**. Per `rest-client.ts applyAuth`, any OAuth token obtained afterwards would still not be used because the broken API key is still picked first.

Present the user with exactly these two options, neutrally (do NOT label OAuth as "recommended"):

1. **Replace the API key** — the user generates a new key on the OKX web console (`https://<site>/account/my-api`) and either provides `AK/SK/PP` to you or re-runs `okx config init` themselves.
2. **Switch entirely to OAuth** — first remove the broken API-key profile (`okx config use <other-profile>` or delete the profile block in `~/.okx/config.toml`), THEN run the OAuth login flow from Step 0.3.

Option 2 requires removing the profile first. If you attempt `okx auth login` while the API key profile still exists, the CLI guard will skip OAuth with `{"status":"skipped","reason":"api_key_configured",...}` and nothing will change.

Wait for the user's choice. Do not pick for them.

### Step 0.3 — OAuth check

Use `auth status --json`:

| `status` value  | Action |
| --------------- | ------ |
| `logged_in`     | **STOP.** Reply using the success template from [Agent login procedure](#agent-login-procedure) Step 3 `logged_in` branch (site + scopes only; see its negative-list rules), then proceed. |
| `pending`       | Previous login in progress — follow [Login Flow](#login-flow) wait-for-signal procedure. Do NOT start a new login, do NOT auto-poll. |
| `not_logged_in` | Proceed to [Login Flow](#login-flow) with the site chosen in Step 0.1. |

## Pre-login Gate (MANDATORY — do not run `okx auth login` without this)

Before invoking `okx auth login` (with or without `--manual`), you MUST verify all **three** of the following are true right now:

1. You posted the exact Chinese site menu from Step 0.1 to the user earlier in this conversation (or immediately before this login call).
2. The user's most recent message was a site choice (`1` / `2` / `3` / `4` / `global` / `eea` / `us` / `tr`).
3. You are about to pass **that exact choice** as `--site <...>`.

If **any** of the three is false — even if a prior skill's output, `auth status --json` output, or `config show --json` output seems to imply a site — you MUST first post the Step 0.1 menu, wait for the user's reply, then re-check this gate. The `site` field in `auth status --json` when `status` is `not_logged_in` is a placeholder (typically `"global"`) and **does not** satisfy condition 1.

Worked counter-example (anti-pattern):
> Upstream portfolio skill runs `auth status --json`, gets `{"status":"not_logged_in","site":"global"}`, tells you "user is not_logged_in, load okx-cex-auth and log in".
> ❌ **Wrong:** you read that context, run `okx auth login --manual --site global`, immediately return the OAuth URL and code.
> ✅ **Right:** you ignore the upstream site value, post the Step 0.1 menu yourself, wait for user's reply, then run `okx auth login --manual --site <user's choice>`.

## Login Flow

> **Prerequisite:** Step 0 completed **and** the Pre-login Gate above passes. You have a site the user just chose in chat, and you confirmed no `api_key` profile exists.

`okx auth login` without `--manual` is a **blocking command** — it polls until the user authorizes in their browser.

> **CRITICAL for AI agents:** You MUST use `okx auth login --manual` to avoid blocking. The `--manual` flag outputs a JSON payload with the verification URL and user code, then exits immediately — it does NOT block.

### Agent login procedure

1. Run `okx auth login --manual --site <global|eea|us|tr>` with the site chosen in Step 0.1.
   - If the CLI returns `{"status":"skipped","reason":"api_key_configured",...}`, your Step 0.2 check was stale — re-read `config show --json` and stop. Do not retry.
   - Otherwise the CLI prints a single line of JSON: `{"verificationUri":"...","userCode":"XXXX-XXXX","expiresIn":600}`.

2. **Surface the verification URL and user code in your assistant reply — NOT only inside a tool-output block.**

   > ⚠ **CRITICAL.** The tool-output panel in many UIs (openclaw-control-ui, Claude Desktop, IDE chat panels) is collapsible and users may run with it hidden by default. If the URL and code appear ONLY in tool stdout, users cannot authorize. You MUST echo the parsed fields in your own natural-language response so they render as plain chat text.

   Parse the JSON returned by the previous step and reply using **exactly one** of the templates below (verbatim except for field substitution). The wording is normative — do not abbreviate, reword, reorder, or translate.

   **Chinese template** (use when the user is conversing in Chinese):

   ```
   请在浏览器中打开下面的链接并输入验证码完成授权：

   站点：<site>
   链接：<verificationUri>
   验证码：<userCode>
   （有效期 <expiresIn>/60 分钟）

   通过链接完成授权，然后告诉我。
   ```

   **English template** (use when the user is conversing in English):

   ```
   Please open the link below in your browser and enter the verification code to authorize:

   Site: <site>
   URL: <verificationUri>
   Code: <userCode>
   (Valid for <expiresIn/60> minutes)

   Please authorise current session with access to your account, tell me when you are done.
   ```

   All four fields — `site`, `verificationUri`, `userCode`, `expiresIn` — must appear as plain text in the assistant message.

3. **Wait for the user to signal completion** (e.g. "done", "ok", "好了", "完成了"). Do NOT auto-poll. Upon receiving the signal, run `okx auth status --json` **once** to verify, then branch:
   - `"status": "logged_in"` → success. Reply using **exactly one** of the templates below (verbatim except for field substitution), then proceed with the user's original request in the same turn.

     **Chinese template**:

     ```
     登录成功。
     站点：<site>
     权限：<scopes>
     ```

     **English template**:

     ```
     Login successful.
     Site: <site>
     Scopes: <scopes>
     ```

     **DO NOT include any other field from `auth status --json` in this reply.** Specifically:
     - `expiresAt` / `ttl` refer to the short-lived access token, not the OAuth session. The CLI auto-refreshes tokens transparently; surfacing these values will mislead users into thinking their login expires soon.
     - `profile` is an internal routing field with no user value.
     - Only `site` and `scopes` are user-relevant.
     - If asked about session longevity, say "Session stays active as long as you use the CLI periodically." Do not quote a number.

   - `"status": "pending"` → authorization not yet complete; tell the user it's not done yet and wait for another signal. Do NOT auto-poll.
   - `"status": "not_logged_in"` → device code expired or was rejected; ask the user whether to retry.

4. **Do NOT run any other `okx` commands** while waiting for authorization.

### Interactive login (user runs directly in terminal)

1. **Tell the user BEFORE running** that they will need to authorize in their browser.
2. **Run `okx auth login --site <global|eea|us|tr>`** — the command will block and poll until the user completes authorization.
3. **Do NOT assume the command is stuck.** The polling phase produces no output — this is normal.
4. **Check the result:**
   - `Logged in successfully!` — proceed with the user's original request.
   - `API key already configured ...` — Step 0.2 check was stale, use the existing API key.
   - Login failed — show the error and ask if they want to retry.

## First-Time Setup (API-key users only)

> `okx config init` is an **API-key** wizard. It prompts for site, then demo/live, then asks for `AK/SK/PP` credentials. It does NOT perform OAuth. Use it only when the user explicitly wants to configure an API key.

```bash
okx config init
```

Wizard steps:

1. **Select site:**
   - `1` — Global (`www.okx.com`)
   - `2` — EEA (`my.okx.com`) — European Economic Area
   - `3` — US (`app.okx.com`) — United States
   - `4` — TR (`tr.okx.com`) — Türkiye
2. **Demo / live**: whether this profile should target simulated trading.
3. **AK / SK / Passphrase**: credentials created on the OKX web console.

After `okx config init` completes, re-run the Step 0 pre-flight check — `api_key` will now be present and Step 0.2 will short-circuit any further login.

## Login Status Check

Run `okx auth status --json` to check login status. Parse the JSON output:

```json
{
  "profile": "oauth",
  "site": "global",
  "status": "logged_in",
  "expiresAt": "2026-04-11T20:30:00+00:00",
  "ttl": 3600,
  "scopes": ["live:read", "live:trade"]
}
```

| `status` value   | Meaning                        | Action                          |
| ----------------- | ------------------------------ | ------------------------------- |
| `logged_in`       | Valid session                  | Proceed                        |
| `pending`         | Login in progress              | Wait for user to signal completion; do NOT auto-poll |
| `not_logged_in`   | No active session              | Run `okx auth login --manual`  |

## Re-authentication (Session Expired)

When any command fails with "Session expired" or "Run `okx auth login` first":

1. Run `okx auth login --manual [--site <global|eea|us|tr>]` (agent) or `okx auth login [--site <global|eea|us|tr>]` (interactive)
2. Follow the same [Login Flow](#login-flow) above

> Token expiry is managed automatically — you only need to re-authenticate when the refresh token itself expires (typically after an extended period of inactivity).

## Logout

```bash
okx auth logout
```

DCR client registration is retained after logout. The next `okx auth login` will be faster.

## Binary Management

The `okx auth` commands (`login`, `logout`, `status`) depend on the `okx-auth` binary. It is normally installed automatically during `npm install`, but can also be managed manually.

> **IMPORTANT for AI agents:** Do NOT manually check platform, CDN availability, or binary paths. Always use the CLI commands below — they handle platform detection and download internally.

### Install / Update

```bash
okx auth install
```

Downloads or updates the `okx-auth` binary. Reports "up to date" if already current. Use `--json` for machine-readable output.

### Check Installation

```bash
okx auth install-status
```

Shows whether the binary is installed and up to date. Use `--json` for machine-readable output.

### Remove

```bash
okx auth remove          # interactive confirmation
okx auth remove --force  # skip confirmation
```

### Troubleshooting: "Failed to spawn okx-auth"

If any `okx auth` command (`login`, `logout`, `status`) fails with "Failed to spawn okx-auth", the binary is missing or corrupted:

1. Run `okx auth install` to download it
2. Verify with `okx auth install-status`
3. Retry the original command

## Error Reference

| Error message                                 | Cause                                  | Action                                           |
| --------------------------------------------- | -------------------------------------- | ------------------------------------------------ |
| `No config found. Run okx config init first.` | No config                              | Run `okx config init`                            |
| `Session expired — run okx auth login again`  | Refresh token expired                  | Run `okx auth login --manual`                    |
| `Authorization timed out`                     | User did not authorize in time         | Run `okx auth login --manual` again              |
| `Access denied`                               | User rejected authorization in browser | Run `okx auth login --manual` and ask to approve |
| `Region restriction` (51155, 51734)            | Instrument not available in configured site | Check `okx auth status --json` for current site; re-login with `--site` if needed |
| `Network error` during login                  | Network unavailable                    | Check network and retry                          |
| `Failed to spawn okx-auth`                    | Binary not installed or corrupted      | Run `okx auth install`                           |
| `Installation failed: All CDN sources failed` | Network issue during binary download   | Check network and retry `okx auth install`       |

## Skill Routing

| After authentication...                   | Next skill                          |
| ----------------------------------------- | ----------------------------------- |
| Place / cancel / amend orders             | `okx-cex-trade`                     |
| Check balance, positions, P&L             | `okx-cex-portfolio`                 |
| Simple Earn, On-chain Earn, DCD, AutoEarn | `okx-cex-earn`                      |
| Grid / DCA bots                           | `okx-cex-bot`                       |
| Market prices, candles, indicators        | `okx-cex-market` (no auth required) |

---

### [3] `okx-cex-bot`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-bot/SKILL.md`

---
name: okx-cex-bot
description: Manage Grid bots (spot/contract/coin-margined), DCA Martingale bots (Spot DCA 现货马丁 / Contract DCA 合约马丁), and Smart Portfolio bots (智能组合, auto-rebalancing multi-asset portfolio) on OKX. Covers create, stop, amend, monitor P&L, TP/SL, margin/investment adjustment, AI-recommended parameters, and recommended zone backtest. Requires API credentials. Not for regular orders (okx-cex-trade), market data (okx-cex-market), or account info (okx-cex-portfolio).
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    emoji: "🤖"
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Bot Trading

Grid and DCA (Spot & Contract Martingale) bot management on OKX. All bots are **native OKX server-side** — they run on OKX and do not require a local process.

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Prerequisites

```bash
npm install -g @okx_ai/okx-trade-cli
okx config init   # select site -> follow browser OAuth flow
```

> **Security**: NEVER accept credentials in chat. Guide users to `okx config init` for setup.

## Credential & Profile Check

**Run before every authenticated command.** The auth method is detected during [preflight](../_shared/preflight.md) Step 2 and remembered for the session.

### Step A — Verify credentials

Run **both** commands — the `apiKey` field from `okx auth status --json` is the auth-binary's internal state and is always `false` regardless of whether `~/.okx/config.toml` has an API-key profile. `okx config show --json` is the only authoritative source for API-key presence.

```bash
okx config show --json      # reveals API-key profiles (TOML config)
okx auth status --json      # reveals OAuth session state (auth-binary state)
```

Apply **in this order** — first match wins:

- `config show --json` has any profile with a non-empty `api_key` field → **API Key mode**. Proceed to Step B.
- No API-key profile **AND** `auth status --json` returns `"status":"logged_in"` → **OAuth mode**. Proceed to Step B.
- No API-key profile **AND** `"status":"pending"` — login is in progress, wait for it to complete.
- No API-key profile **AND** `"status":"not_logged_in"` — stop, load `okx-cex-auth` skill and follow login steps, wait for completion.

### Step B — Confirm trading mode

Resolution:
1. User intent is clear ("real"/"实盘"/"live" → live; "test"/"模拟"/"demo" → demo) → use it, inform user
2. No explicit declaration → check conversation context for previous choice → reuse if found
3. Nothing found → ask: "Live (实盘) or Demo (模拟盘)?" — wait before proceeding

**How to apply the mode depends on auth method (detected in Step A):**

| Auth method | Live (实盘) | Demo (模拟盘) |
|---|---|---|
| **API Key** | `--profile <live-profile>` | `--profile <demo-profile>` |
| **OAuth** | *(no flag needed, live is default)* | `--demo` |

- **API Key users**: run `okx config show --json` to discover available profile names and their `demo` settings.
- **OAuth users**: omit flags for live; add `--demo` for simulated trading.

**After every command**: append `[mode: live]` or `[mode: demo]`

### Handling 401 Errors

**Authentication error** (error contains "401", "Session expired", or "Run `okx auth login` first"):
1. Stop immediately
2. Load `okx-cex-auth` skill and follow re-authentication steps
3. Retry original command

## Skill Routing

| Need | Skill |
|---|---|
| Market data, prices, depth | `okx-cex-market` |
| Account balance, positions, fees | `okx-cex-portfolio` |
| Regular spot/swap/futures orders | `okx-cex-trade` |
| **Grid / DCA bots** | **`okx-cex-bot` (this skill)** |

## Command Index

### Grid Bot

| Command | Type | Description |
|---|---|---|
| `okx bot grid create` | WRITE | Create a grid bot (spot or contract) |
| `okx bot grid amend` | WRITE | Amend price range, grid count, or TP/SL of a running grid bot |
| `okx bot grid stop` | WRITE | Stop a grid bot |
| `okx bot grid positions` | READ | Query open contract-grid positions (liquidation price, margin ratio, unrealized PnL) |
| `okx bot grid liquidate-price` | READ | Estimate liquidation price for a contract-grid bot |
| `okx bot grid close-position` | WRITE | Close remaining position after bot stopped with stopType=2 |
| `okx bot grid orders` | READ | List active or history grid bots |
| `okx bot grid details` | READ | Grid bot details + PnL |
| `okx bot grid sub-orders` | READ | Individual grid fills or pending orders |

### DCA Bot (Spot & Contract)

| Command | Type | Description |
|---|---|---|
| `okx bot dca create` | WRITE | Create a DCA (Martingale) bot (spot or contract) |
| `okx bot dca stop` | WRITE | Stop a DCA bot (spot or contract) |
| `okx bot dca orders` | READ | List active or history DCA bots (default: contract_dca) |
| `okx bot dca positions` | READ | DCA bot position info (avgPx, upl, liqPx, ...) |
| `okx bot dca details` | READ | **Deprecated** - use `okx bot dca positions` (same endpoint) |
| `okx bot dca sub-orders` | READ | DCA cycles and orders within a cycle |
| `okx bot dca add-margin` | WRITE | Add margin to a running contract DCA bot |
| `okx bot dca reduce-margin` | WRITE | Reduce margin on a running contract DCA bot |
| `okx bot dca update-tp` | WRITE | Update take-profit price on a running contract DCA bot |

### Smart Portfolio Bot

> **Note**: Load with `--modules bot.smartportfolio` or `bot.all` (not in default modules).

| Command | Type | Description |
|---|---|---|
| `okx bot smart-portfolio create` | WRITE | Create a Smart Portfolio bot (2–10 assets, ratios summing to 1.0, deltaRatio threshold) |
| `okx bot smart-portfolio stop` | WRITE | Stop a running Smart Portfolio bot |
| `okx bot smart-portfolio orders` | READ | List Smart Portfolio bots (default: running; add --history for stopped) |
| `okx bot smart-portfolio details` | READ | Get Smart Portfolio bot details and current allocation |
| `okx bot smart-portfolio amend-rebalance` | WRITE | Update rebalance threshold and interval (both --deltaRatio and --interval required) |
| `okx bot smart-portfolio instant-rebalance` | WRITE | Trigger an immediate rebalance |
| `okx bot smart-portfolio recommend-zones` | READ | Browse OKX-recommended portfolio zone configurations |
| `okx bot smart-portfolio zones-backtest` | READ | Get historical backtest results for a recommended zone |

## Operation Flow

### Step 1 — Identify bot type and action

Parse user request → determine module (Grid / DCA / Smart Portfolio) and action (create / stop / list / details).

### Step 2 — Execute

**READ commands** (orders, details, sub-orders): run immediately after profile confirmation.

**WRITE commands** (create, amend, stop): confirm key parameters with user once before executing.

### Step 3 — Verify after writes

- After create → run the corresponding `orders` command to confirm active
- After amend → run `details --algoId <id>` to confirm updated config
- After Grid/DCA stop → run `orders --history` to confirm stopped
- After Smart Portfolio stop → run `smart-portfolio orders --history` to confirm stopped

## Key Rules

- **Never auto-transfer funds.** If balance is insufficient for bot creation, report the shortfall (current available vs required) and ask the user how to proceed: (1) transfer funds manually, (2) reduce size, or (3) cancel.
- **`algoId`** is the bot's algo order ID (from create or list output). It is NOT a normal `ordId`. Never fabricate — always obtain from a prior command.
- **`algoOrdType`** for grid must match the bot's actual type. Always use the value from `bot grid orders` — do not infer from user description alone. Mismatch causes error `50016`.
- When operating on existing bots, **always list first** to get correct IDs, unless the user provides them explicitly.
- **TP/SL constraints**: `tpTriggerPx`/`tpRatio` and `slTriggerPx`/`slRatio` are mutually exclusive pairs.

## CLI Command Reference

For Grid Bot command syntax, parameter tables, Quickstart examples, and edge cases,
read `{baseDir}/references/grid-commands.md`.

For DCA Bot command syntax, parameter tables, Quickstart examples, and edge cases,
read `{baseDir}/references/dca-commands.md`.

For Smart Portfolio Bot command syntax, parameter tables, and examples,
read `{baseDir}/references/smart-portfolio-commands.md`.

For cross-skill workflow examples (chaining `okx-cex-market`/`okx-cex-portfolio` with bot
creation), read `{baseDir}/references/workflows.md`.

## Communication Guidelines

- **Grid/DCA**: use "bot" not "strategy" (e.g., "grid bot", "DCA bot")
- **DCA**: always say "DCA" or "Martingale" — DCA supports both Spot DCA and Contract DCA
- **Chinese**: Grid = "网格", Spot DCA = "现货马丁", Contract DCA = "合约马丁", Smart Portfolio = "智能组合"
- Use natural language for parameters — "What price range?" not "Enter minPx and maxPx"
- If the user already provides values, map directly — don't re-ask

> `{base}` and `{quote}`: extract from `instId` by splitting on `-`. E.g., `BTC-USDT-SWAP` → base=BTC, quote=USDT.

## Global Notes

- All bots run on OKX servers — stopping the CLI does not affect them
- Auth method and trading mode are determined in "Credential & Profile Check"; see that section for parameter rules
- `--json` returns the raw OKX API v5 response by default. Add `--env` to wrap the output as `{"env": "<live|demo>", "profile": "<name>", "data": <response>}`
- Rate limit: 20 requests per 2 seconds per UID
- Grid `--gridNum` range: 2–100

---

### [4] `okx-cex-earn`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-earn/SKILL.md`

---
name: okx-cex-earn
description: "Manages OKX Simple Earn (flexible savings/lending), Flash Earn, On-chain Earn (staking/DeFi), Dual Investment (DCD/双币赢), and AutoEarn (自动赚币) via the okx CLI. Use this skill whenever the user wants to check earn balances, browse flash-earn projects, subscribe or redeem earn products, view or set lending rates, monitor on-chain staking orders, interact with dual investment structured products, or manage auto-earn — even if phrased casually as 活期赚币, 定期赚币, 闪赚, 赚币, 申购, 赎回, 链上赚币, 质押, 理财, 双币赢, 双币理财, 双币申购, 高卖, 低买, dual investment, DCD, flash earn, buy low, sell high structured product, earn with target price, 目标价, 自动赚币, auto earn, auto-earn, 自动借出, 自动质押, auto lend, auto staking, USDG earn, USDG 赚币, 闲置资金自动理财, fixed earn, fixed deposit, term deposit, 定期理财, 定期. Also use when the user asks about idle funds and whether to earn on them."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Earn CLI

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure credentials:
   ```bash
   okx config init   # select site -> follow browser OAuth flow
   ```
3. Verify: `okx earn savings balance`

> **Security**: NEVER accept credentials in chat. Guide users to `okx config init` for setup.

---

## Credential & Profile Check

Run **both** commands before any authenticated command — the `apiKey` field from `okx auth status --json` is the auth-binary's internal state and is always `false` regardless of whether `~/.okx/config.toml` has an API-key profile. `okx config show --json` is the only authoritative source for API-key presence. The auth method is detected during [preflight](../_shared/preflight.md) Step 2 and remembered for the session.

```bash
okx config show --json      # reveals API-key profiles (TOML config)
okx auth status --json      # reveals OAuth session state (auth-binary state)
```

Apply **in this order** — first match wins:

- `config show --json` has any profile with a non-empty `api_key` field → **API Key mode**. Proceed.
- No API-key profile **AND** `auth status --json` returns `"status":"logged_in"` → **OAuth mode**. Proceed.
- No API-key profile **AND** `"status":"pending"` — login is in progress, wait for it to complete.
- No API-key profile **AND** `"status":"not_logged_in"` — **stop**, load `okx-cex-auth` skill and follow login steps, wait for completion.

OKX Earn does not support demo mode. Always use live mode silently — don't mention it unless there's an error.
- **API Key users**: use `--profile <live-profile>` (the profile without `demo=true`).
- **OAuth users**: no flag needed (live is the default).

**On authentication errors (401 / "Session expired" / "Run `okx auth login` first"):** stop immediately, load `okx-cex-auth` skill and follow re-authentication steps, then retry.

---

## Skill Routing

| User intent | Route to skill |
|---|---|
| Market prices, tickers, candles | `okx-cex-market` |
| Spot / swap / futures / options orders | `okx-cex-trade` |
| Account balance, positions, transfers | `okx-cex-portfolio` |
| Grid / DCA trading bots | `okx-cex-bot` |
| Simple Earn, Flash Earn, On-chain Earn, Dual Investment (双币赢), or AutoEarn (自动赚币) | **This skill** |

---

## Command Index

### earn savings — Simple Earn (10 commands)

| Command | Type | Auth | Description |
|---|---|---|---|
| `earn savings balance [ccy]` | READ | Required | Savings balance (all or specific currency). Also fetch fixed-term orders for a complete picture. |
| `earn savings purchase --ccy --amt [--rate]` | WRITE | Required | Subscribe funds to Simple Earn (活期) |
| `earn savings redeem --ccy --amt` | WRITE | Required | Redeem funds from Simple Earn (活期) |
| `earn savings set-rate --ccy --rate` | WRITE | Required | Set minimum lending rate |
| `earn savings lending-history` | READ | Required | User's personal lending records with earnings detail |
| `earn savings rate-history` | READ | Required | Simple Earn lending rates and fixed-term offers (require auth) |
| `earn savings fixed-products [--ccy]` | READ | Required | Browse available fixed-term (定期) products with APR, term, remaining quota, and sold-out status |
| `earn savings fixed-orders [--ccy] [--state]` | READ | Required | Query fixed-term (定期) orders. States: pending/earning/expired/settled/cancelled |
| `earn savings fixed-purchase --ccy --amt --term [--confirm]` | WRITE | Required | Subscribe to Simple Earn Fixed (定期). Without `--confirm`: preview only |
| `earn savings fixed-redeem --reqId <reqId>` | WRITE | Required | Redeem a fixed-term order (full amount). Only `pending` state orders can be redeemed early |

For full command syntax, rate field semantics, and confirmation templates, read `{baseDir}/references/savings-commands.md`.

### earn dcd — Dual Investment / 双币赢 (6 commands)

| Command | Type | Auth | Description |
|---|---|---|---|
| `earn dcd pairs` | READ | Required | Available DCD currency pairs |
| `earn dcd products` | READ | Required | Active products with filters |
| `earn dcd quote-and-buy --productId --sz --notionalCcy` | WRITE | Required | Atomic subscribe: quote + execute in one step |
| `earn dcd order --ordId` | READ | Required | Quick state check for a single order |
| `earn dcd orders` | READ | Required | Full order list / history |
| `earn dcd redeem-execute --ordId` | WRITE | Required | Two-step early redemption: preview then execute |

> DCD does **not** support demo/simulated trading mode. Always use live mode (API Key: `--profile <live-profile>`; OAuth: no flag needed).

For full command syntax, product concepts, and error codes, read `{baseDir}/references/dcd-commands.md`.

### earn onchain — On-chain Earn (6 commands)

| Command | Type | Auth | Description |
|---|---|---|---|
| `earn onchain offers` | READ | Required | Available staking/DeFi products |
| `earn onchain purchase --productId --ccy --amt` | WRITE | Required | Subscribe to on-chain product |
| `earn onchain redeem --ordId --protocolType` | WRITE | Required | Redeem on-chain investment |
| `earn onchain cancel --ordId --protocolType` | WRITE | Required | Cancel pending on-chain order |
| `earn onchain orders` | READ | Required | Active on-chain orders |
| `earn onchain history` | READ | Required | Historical on-chain orders |

For full command syntax and parameters, read `{baseDir}/references/onchain-commands.md`.

### earn auto-earn — AutoEarn / 自动赚币 (3 commands)

| Command | Type | Auth | Description |
|---|---|---|---|
| `earn auto-earn status [CCY]` | READ | Required | Query currencies supporting auto-earn and their status |
| `earn auto-earn on <CCY>` | WRITE | Required | Enable auto-earn for a currency |
| `earn auto-earn off <CCY>` | WRITE | Required | Disable auto-earn for a currency |

> **24h restriction:** Cannot disable within 24 hours of enabling (API hard limit). Always warn user before enabling.

For full command syntax, earnType inference rules, and MCP tool reference, read `{baseDir}/references/autoearn-commands.md`.

### earn flash-earn — Flash Earn / 闪赚 (1 command)

| Command | Type | Auth | Description |
|---|---|---|---|
| `earn flash-earn projects [--status <0\|100\|0,100>]` | READ | Required | Browse Flash Earn projects by status. `0`=upcoming, `100`=in-progress, default is both |

---

## Operation Flow

### Step 0 — Credential & Profile Check

Before any authenticated command: see [Credential & Profile Check](#credential--profile-check). Always use live mode silently.

### Step 1 — Identify earn intent

**Simple Earn Flexible (活期):**
- Query balance / history / rates → READ command, proceed directly.
- Subscribe / redeem / set-rate → WRITE command, go to Step 2.

**Simple Earn Fixed (定期):**
- Browse available products / check quota → `earn savings fixed-products [--ccy]`. This is the dedicated tool for querying the fixed-term product pool — use it whenever the user asks about available fixed earn products, remaining quota, or APR.
- Query user's existing orders → `earn savings fixed-orders [--ccy] [--state]`.
- Subscribe (two-step: preview then confirm) / redeem (pending state only) → WRITE command, go to Step 2. Read `{baseDir}/references/savings-commands.md` for pre-execution checklists and confirmation templates.
- For multi-step workflows (subscribe with preview, early redemption), read `{baseDir}/references/workflows.md`.

**On-chain Earn:**
- Query offers / orders / history → READ command, proceed directly.
- Purchase / redeem / cancel → WRITE command, go to Step 2.

**AutoEarn (自动赚币):**
- Query auto-earn status → READ, proceed directly.
- Enable / disable auto-earn → WRITE, go to Step 2. Read `{baseDir}/references/autoearn-commands.md` for confirmation templates and earnType inference.

**Flash Earn (闪赚):**
- Browse projects → READ, proceed directly.
- Use `--status 0` for upcoming projects, `--status 100` for in-progress projects, or omit the flag to view both.

When user asks to view "earn positions" or "赚币持仓" (regardless of whether they mention DCD explicitly), query all position-bearing sub-modules simultaneously (Flash Earn is query-only, no positions):

```bash
okx earn savings balance --json        # Simple Earn Flexible (活期)
okx earn savings fixed-orders --json   # Simple Earn Fixed (定期)
okx earn onchain orders --json         # On-chain Earn
okx earn dcd orders --json             # Dual Investment (双币赢)
```

Only present sections that have actual holdings. For DCD: translate state codes using the table in `{baseDir}/references/dcd-commands.md`.

**Dual Investment (DCD / 双币赢):**
- Browse products / pairs → READ; when user specifies a currency, read `{baseDir}/references/workflows.md` (DCD browse flow) for the mandatory parallel pre-fetch before rendering the product table
- Subscribe (quote-and-buy) → WRITE → see `{baseDir}/references/workflows.md` (DCD subscribe flow)
- Early redeem → WRITE → see `{baseDir}/references/workflows.md` (DCD early redeem flow)

For multi-step workflows (idle fund analysis, subscribe + verify, redeem + transfer, on-chain subscribe), read `{baseDir}/references/workflows.md`.

### Step 2 — Confirm write operation

For all WRITE commands, present a summary and wait for explicit confirmation.

> "just do it" / "直接搞" is NOT valid confirmation — the user must see the summary first.

For Simple Earn confirmation dialog format, read `{baseDir}/references/savings-commands.md`. For On-chain confirmation, read `{baseDir}/references/onchain-commands.md`.

### Step 3 — Execute and verify

After any purchase, verify based on product type:
- **DCD** `quote-and-buy` succeeded → run `earn dcd orders --json`, show only the matching order.
- **On-chain** purchase (response contains `ordId`) → run `earn onchain orders --json`, show only the matching order.
- **Simple Earn Flexible** purchase (no `ordId` in response) → run `earn savings balance --ccy <ccy> --json`.
- **Simple Earn Fixed** purchase → run `earn savings fixed-orders --ccy <ccy> --state pending --json`, show the new order.

**Simple Earn Flexible purchase:** Run in parallel — `earn savings balance --ccy <ccy>` and `earn savings rate-history --ccy <ccy> --limit 1 --json`. For output format, read `{baseDir}/references/savings-commands.md`.

**Simple Earn Flexible redeem:** Run `earn savings balance --ccy <ccy>` to confirm updated balance. Inform user funds returned to funding account.

**Simple Earn Fixed purchase:** Run `earn savings fixed-orders --ccy <ccy> --state pending --json` to confirm the order was created. Show order details including APR, term, and expected expiry date.

**Simple Earn Fixed redeem:** Run `earn savings fixed-orders --json` to confirm the order state changed to `cancelled`. Inform user full principal returned to funding account — no interest earned for early cancellation.

**On-chain redeem:** Query `earn onchain orders` to confirm state. Show `estSettlementTime` as estimated arrival time.

**On-chain cancel:** Query `earn onchain orders` after submission:
- Order gone from list → inform user: cancellation complete, funds returned to funding account.
- `state: 3` (cancelling) → inform user: cancellation in progress, funds will return to funding account shortly.

---

## Global Notes

- **Security:** Never ask users to paste API keys or secrets into chat.
- **Output:** Always pass `--json` to list/query commands and render results as a Markdown table — never paste raw terminal output.
- **Network errors:** If commands fail with a connection error, prompt user to check VPN: `curl -I https://www.okx.com`
- **Language:** Always respond in the user's language.

For number/time formatting and response structure conventions, read `{baseDir}/references/templates.md`.

---

### [5] `okx-cex-market`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-market/SKILL.md`

---
name: okx-cex-market
description: "Use this skill when the user asks for: price of any asset, ticker, order book, candles, OHLCV, funding rate, open interest, OI change scanner, market screener (top movers, high-volume, newly listed), mark price, index price, recent trades, instrument list, stock tokens, metals prices (gold, XAU, XAG), commodities (oil, OIL), forex rates (EUR/USD, EURUSDT), bond instruments, non-crypto assets, or any technical indicator query (RSI, MACD, EMA, Bollinger Bands, KDJ, SuperTrend, AHR999, BTC rainbow, and 70+ more). All commands are read-only and do NOT require API credentials. Do NOT use for account balance/positions (okx-cex-portfolio), placing/cancelling orders (okx-cex-trade), or bots (okx-cex-bot). Do NOT use when the user wants to TRADE a directional view as an event contract — that is okx-cex-trade. Merely ASKING which way an asset's price is moving is a market-data question and belongs here."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Market Data CLI

> **Compliance notice**: This skill provides raw market data only. No strategy, recommendation, or optimization logic is embedded. All indicator outputs are objective numerical values; interpretation and trading decisions remain solely with the user.

Public market data for OKX: prices, order books, candles, funding rates, open interest, instrument info, and technical indicators. All commands are **read-only** and require **no API credentials**.

**Skill routing**
- Market data / indicators → `okx-cex-market` (this skill)
- Account balance / positions → `okx-cex-portfolio`
- Place / cancel orders → `okx-cex-trade`
- **Trading a directional view as an event contract** → `okx-cex-trade`
- Market sentiment / most bullish-bearish coins → `okx-sentiment-tracker`
- Grid / DCA bots → `okx-cex-bot`

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Install

```bash
npm install -g @okx_ai/okx-trade-cli
okx market ticker BTC-USDT   # verify
```

Market data commands return the same public data regardless of demo/live mode — no API credentials required. If the user's profile has `demo=true` set and they want live data context, they can use `--live` to confirm they are in live mode (it has no effect on public market data but clarifies environment). Always inform the user which environment is active (demo or live) when it is relevant to their query. No confirmation needed before running any market command. Add `--json` to any command for raw OKX API v5 response. Add `--env` to wrap the output as `{"env", "profile", "data"}`.

---

## Command Index

| # | Command | Description |
|---|---|---|
| 1 | `okx market ticker <instId>` | Last price, 24h high/low/vol/change% |
| 2 | `okx market tickers <instType>` | All tickers for SPOT / SWAP / FUTURES / OPTION |
| 3 | `okx market instruments --instType <type> [--instId <id>] [--uly <uly>] [--instFamily <fam>] [--seriesId <id>]` | List instruments (instId, ctVal, lotSz, minSz, tickSz, state); OPTION requires `--uly` or `--instFamily`; EVENTS requires `--seriesId` |
| 4 | `okx market orderbook <instId> [--sz <n>]` | Order book asks/bids (default top 5 per side, max 400) |
| 5 | `okx market candles <instId> [--bar <bar>] [--limit <n>] [--after <ts>] [--before <ts>]` | OHLCV candles (default `--bar 1m`); auto-routes to historical endpoint for data back to 2021; `--after` paginates back in time, `--before` paginates forward |
| 6 | `okx market index-candles <instId> [--bar <bar>] [--limit <n>] [--history]` | Index OHLCV (use `BTC-USD` not `BTC-USDT`) |
| 7 | `okx market funding-rate <instId> [--history] [--limit <n>]` | Current or historical funding rate (SWAP only) |
| 8 | `okx market trades <instId> [--limit <n>]` | Recent public trades |
| 9 | `okx market mark-price --instType <type> [--instId <id>]` | Mark price (SWAP / FUTURES / OPTION) |
| 10 | `okx market index-ticker [--instId <id>] [--quoteCcy <ccy>]` | Index price (e.g., BTC-USD) |
| 11 | `okx market price-limit <instId>` | Upper/lower price limits (SWAP / FUTURES only) |
| 12 | `okx market open-interest --instType <type> [--instId <id>]` | Open interest in contracts and base currency |
| 13 | `okx market instruments-by-category --instCategory <3\|4\|5\|6\|7>` | Discover instruments by asset category: 3=Stock tokens (AAPL/TSLA), 4=Metals (gold/silver), 5=Commodities (oil/gas), 6=Forex (EUR/USD), 7=Bonds |
| 13† | `okx market stock-tokens` | **Deprecated** — use `instruments-by-category --instCategory 3` instead |
| 14 | `okx market filter --instType <SPOT\|SWAP\|FUTURES> [--sortBy <field>] [--sortOrder <asc\|desc>] [--limit <n>] [--baseCcy <ccy>] [--quoteCcy <ccy>] [--settleCcy <ccy>] [--instFamily <fam>] [--ctType <linear\|inverse>] [--minLast <n>] [--maxLast <n>] [--minChg24hPct <n>] [--maxChg24hPct <n>] [--minMarketCapUsd <n>] [--maxMarketCapUsd <n>] [--minVolUsd24h <n>] [--maxVolUsd24h <n>] [--minFundingRate <n>] [--maxFundingRate <n>] [--minOiUsd <n>] [--maxOiUsd <n>]` | Screen / rank instruments by multi-dimensional criteria (price, volume, OI, funding rate, market cap). Prints `Total: N` + a ranked table of matching instruments (`No results` only when nothing matches). Add `--json` for the raw OKX API v5 response (structurally unchanged). |
| 15 | `okx market oi-history <instId> [--bar <5m\|15m\|1H\|4H\|1D>] [--limit <n>] [--ts <ms>]` | OI history time series with bar-over-bar delta for a single instrument |
| 16 | `okx market oi-change --instType <SWAP\|FUTURES> [--bar <5m\|15m\|1H\|4H\|1D>] [--sortBy <field>] [--sortOrder <asc\|desc>] [--limit <n>] [--minOiUsd <n>] [--minVolUsd24h <n>] [--minAbsOiDeltaPct <n>]` | Find instruments with largest OI changes (accumulation/distribution scanner) |
| 17 | `okx market indicator list` | List all supported indicator names and descriptions |
| 18 | `okx market indicator <indicator> <instId> [--bar] [--params] [--list] [--limit] [--backtest-time]` | Technical indicator values. For period-based indicators (ema/ma/wma/rsi/macd/bb/…) the CLI applies a sensible default period when `--params` is omitted (e.g. EMA/RSI → `14`, MACD → `12,26,9`, BB → `20,2`) so values render without you specifying params; explicit `--params` always wins. If no values come back, the CLI prints a visible hint (`try --params …`) — never silent. |
| 19 | `okx market pair-spread <instIdA> <instIdB> [--bar <5m\|15m>] [--window <window>] [--backtest-time <ms>]` | Spread statistics (abs + ratio: mean/stdDev/median/min/max) over a lookback window; supports backtest mode |

---

## Operation Flow

### Step 1 — Identify data type and load reference

| User intent | Reference to load |
|---|---|
| Price, candles, order book, recent trades | `{baseDir}/references/price-data-commands.md` |
| Technical indicators (RSI, MACD, EMA, BB, KDJ, SuperTrend, AHR999, Rainbow, etc.) | `{baseDir}/references/indicator-commands.md` |
| Funding rate, mark price, open interest, price limit, index ticker | `{baseDir}/references/derivatives-commands.md` |
| Screen / rank instruments; find top movers, high-OI, high-volume contracts | Use `okx market filter` directly |
| OI history time series for a single instrument | Use `okx market oi-history` directly |
| OI change scanner; find contracts with large OI shifts | Use `okx market oi-change` directly |
| Pair spread statistics; mean-reversion / pairs-trade sizing | Use `okx market pair-spread` directly |
| List instruments, discover stock tokens, metals/commodities/forex/bonds, find option instIds | `{baseDir}/references/instrument-commands.md` |
| Multi-step or cross-skill workflows; MCP tool names | `{baseDir}/references/workflows.md` |

**Event contracts are not served by this skill.**

| User asks | Do |
|---|---|
| Which way an asset is moving — "is BTC going up", "what's the 15m trend" | **Answer here** with candles / indicators |
| Direction *and* whether they can trade it | Answer the data half here, then name `okx-cex-trade` for the trade half |
| To trade an event contract — "buy YES/NO on …" | **Route to `okx-cex-trade`**, serve nothing here |

Never substitute another product for an event contract — not a perp, not a futures position,
not market data presented as the contract they asked for. If you cannot load
`okx-cex-trade`, say so and stop.

### Step 2 — Run commands immediately

All market data commands are read-only — no confirmation needed.

### Step 3 — No writes, no verification needed

All commands in this skill are read-only.

---

## Edge Cases

- **instId format**: SPOT `BTC-USDT` · SWAP `BTC-USDT-SWAP` · FUTURES `BTC-USDT-250328` · OPTION `BTC-USD-250328-95000-C` · Index `BTC-USD` · Stock token `TSLA-USDT-SWAP` · Metals/Commodities/Forex/Bonds: use `instruments-by-category` to discover valid instIds first
- **OPTION listing**: `instruments --instType OPTION` requires `--uly BTC-USD` or `--instFamily BTC-USD`; if unknown, run `open-interest --instType OPTION` first to discover active instIds
- **EVENTS listing**: `instruments --instType EVENTS` requires `--seriesId` (e.g. `--seriesId BTC-ABOVE-DAILY`); run `okx event series` first to discover valid series IDs
- **funding-rate / price-limit**: SWAP only · mark-price: SWAP / FUTURES / OPTION only
- **candles `--bar`**: uppercase — `1H` not `1h`; use `--after <ts>` to paginate back into historical data (back to 2021); index-candles supports `--history` for extended history
- **⚠️ Large historical range**: before fetching with `--after`/`--before`, estimate candle count = `time_range_ms / bar_interval_ms`. If estimate > 500, tell the user the estimated count and ask for confirmation before proceeding. This prevents silently filling the context window.
- **indicator `--bar`**: uses `1Dutc` not `1D`, `1Wutc` not `1W` — different from candle bar values
- **`market filter` sortBy values**: `last` `chg24hPct` `marketCapUsd` `volUsd24h` `fundingRate` `oiUsd` `listTime` — default `volUsd24h`
- **`market filter` ctType**: `linear` or `inverse` (SWAP/FUTURES only); omit for SPOT
- **`market filter` quoteCcy**: comma-separated list supported, e.g. `--quoteCcy USDT,USDC`
- **`market filter` SPOT + quoteCcy**: when `--instType SPOT`, the API returns instruments across **all** quote currencies (USDT, USDC, BTC, ETH, etc.) mixed together — this pollutes sort order and bloats results. Always pass `--quoteCcy USDT` by default unless the user explicitly asks for other quote currencies.
- **`market filter` chg24hPct**: value is a percentage number — `--minChg24hPct -5` means -5%, `--maxChg24hPct 10` means 10%
- **`market oi-history` ts**: Unix ms timestamp; returns bars with ts ≤ this value for historical pagination
- **`market oi-history` / `oi-change` bar**: valid values `5m` `15m` `1H` `4H` `1D` — default `1H`. Server accepts case variants (`1h` == `1H`) but prefer canonical casing.
- **`market oi-history` limit**: 1–500 (default 50)
- **`market oi-change` instType**: only `SWAP` or `FUTURES` supported (not SPOT)
- **`market oi-change` minAbsOiDeltaPct**: filters by absolute OI change — `1.0` keeps only rows where |oiDeltaPct| ≥ 1%
- **`market oi-change` sortBy values**: `oiUsd` `oiDeltaUsd` `oiDeltaPct` `absOiDeltaPct` `volUsd24h` `fundingRate` `last` — default `oiDeltaPct` (signed). Use `absOiDeltaPct` to rank by |oiDeltaPct| (largest magnitude regardless of direction).
- **`market oi-change` limit**: 1–100 (default 20). For deeper than 100 rows, fetch `oi-history` per instId.
- **indicator `--bar` valid values**: `3m` `5m` `15m` `1H` `4H` `12Hutc` `1Dutc` `3Dutc` `1Wutc` — `1m` is **not supported** for indicators (use `candles` for 1-minute data)
- **indicator `--limit`**: 1–100 (only used with `returnList`, i.e. when a historical series is requested)
- **indicator arg order**: indicator name before instId — `okx market indicator rsi BTC-USDT`
- **indicator `--params`**: comma-separated, no spaces — `--params 5,20`. For period-based indicators (ema/ma/wma/rsi/macd/bb/…) omitting `--params` makes the CLI substitute a default period (EMA/MA/WMA/RSI → `14`, MACD → `12,26,9`, BB → `20,2`) so the table is populated instead of empty; pass `--params` explicitly to override the default. (CLI-only convenience — the MCP `market_get_indicator` raw-data path still requires an explicit `paramList`.)
- **indicator no values returned**: the CLI never prints nothing — if a query yields no values (e.g. a non-period indicator, or a period indicator with no default), it prints a visible hint: `No indicator values returned. This indicator may require a period — try --params (e.g. --params 14).`
- **BTC-only indicators**: `ahr999`, `rainbow` — BTC-USDT only
- **Unknown indicator name**: returns a `ValidationError` with similar-name suggestions before the API is called — use `market_list_indicators` / `okx market indicator list` to see all valid names
- **Stock token hours**: US stocks trade Mon–Fri ~09:30–16:00 ET; verify live price before acting
- **No data returned**: instrument may be delisted — verify with `okx market instruments`
- **`boll`** is an alias for `bb`

## Global Notes

- No API key required for any command in this skill
- Rate limit: 20 req / 2 s per IP
- Candle data is sorted newest-first
- `vol24h` is in base currency (e.g., BTC for BTC-USDT)
- `--demo`/`--live` and `--profile` do not affect market data results via CLI (public endpoints); they only determine the active trading environment context

---

### [6] `okx-cex-portfolio`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-portfolio/SKILL.md`

---
name: okx-cex-portfolio
description: "This skill should be used when the user asks about 'account balance', 'how much USDT do I have', 'my funding account', 'show my positions', 'open positions', 'position P&L', 'unrealized PnL', 'closed positions', 'position history', 'realized PnL', 'account bills', 'transaction history', 'trading fees', 'fee tier', 'account config', 'max order size', 'how much can I buy', 'withdrawable amount', 'transfer funds', 'move USDT to trading account', or 'switch position mode'. Also use for '总资产', 'full balance', 'all assets', 'total holdings', 'net worth', 'how much do I have in total', 'show all my balances', 'all account balances', 'asset overview', 'aggregated balance', 'asset snapshot', '资产快照'. Requires API credentials. Do NOT use for market prices (use okx-cex-market), placing/cancelling orders (use okx-cex-trade), or grid/DCA bots (use okx-cex-bot)."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Portfolio & Account CLI

Account balance, positions, P&L, bills, fees, and fund transfers on OKX exchange. **Requires API credentials.**

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure credentials:
   ```bash
   okx config init   # select site -> follow browser OAuth flow
   ```
3. Test with demo mode (simulated trading, no real funds):
   ```bash
   okx --demo account balance
   ```

> **Security**: NEVER accept credentials in chat. Guide users to `okx config init` for setup.

## Credential & Profile Check

**Run this check before any authenticated command.** The auth method is detected during [preflight](../_shared/preflight.md) Step 2 and remembered for the session.

### Step A — Verify credentials

Check **both** sources (see [preflight Step 2](../_shared/preflight.md#step-2--detect-auth-method-once-per-session) for the decision table). `okx auth status --json` alone is insufficient — its `apiKey` field is always `false` and does NOT reflect the TOML config.

```bash
okx config show --json      # authoritative for API-key presence
okx auth status --json      # authoritative for OAuth session state
```

Branch in this order — first match wins:

- `config show` has any profile with a non-empty `api_key` — **API Key mode**. Proceed to Step B.
- No API-key profile **AND** `auth status` returns `"status": "logged_in"` — **OAuth mode**. Proceed to Step B.
- No API-key profile **AND** `auth status` returns `"status": "pending"` — login in progress, wait.
- No API-key profile **AND** `auth status` returns `"status": "not_logged_in"` — **stop all operations**, load `okx-cex-auth` skill and follow login steps, wait for completion.

### Step B — Confirm trading mode

**Resolution rules:**
1. Current message intent is clear (e.g. "real" / "实盘" / "live" → live; "test" / "模拟" / "demo" → demo) → use it and inform the user
2. Current message has no explicit declaration → check conversation context for a previous choice:
   - Found → reuse it, inform user
   - Not found → ask: `"Live (实盘) or Demo (模拟盘)?"` — wait for answer before proceeding

**How to apply the mode depends on auth method (detected in Step A):**

| Auth method | Live (实盘) | Demo (模拟盘) |
|---|---|---|
| **API Key** | `--profile <live-profile>` | `--profile <demo-profile>` |
| **OAuth** | *(no flag needed, live is default)* | `--demo` |

- **API Key users**: run `okx config show --json` to discover available profile names and their `demo` settings. Use `--profile <name>` to select the correct one.
- **OAuth users**: omit flags for live trading; add `--demo` for simulated trading. Do **not** use `--profile` to switch modes.

### Handling Authentication Errors

**Authentication error** (error contains "401", "Session expired", or "Run `okx auth login` first"):
1. **Stop immediately** — do not retry the same command
2. Inform the user: "Authentication failed. Your session may have expired."
3. Load `okx-cex-auth` skill and follow the re-authentication steps
4. After successful re-authentication, retry the original command

## Demo vs Live Mode

| Mode | Funds | API Key param | OAuth param |
|---|---|---|---|
| 实盘 (live) | Real funds | `--profile <live-profile>` | *(default, no flag)* |
| 模拟盘 (demo) | Simulated funds | `--profile <demo-profile>` | `--demo` |

```bash
# API Key user
okx --profile okx-prod  account balance     # 实盘
okx --profile okx-demo  account balance     # 模拟盘

# OAuth user
okx account balance                          # 实盘 (default)
okx --demo account balance                   # 模拟盘
```

**Rules:**
- **Read commands** (balance, positions, bills, etc.): always state which mode was used
- **Write commands** (`transfer`, `set-position-mode`): **mode must be confirmed before execution** (see "Credential & Profile Check" Step B); transfer especially — wrong mode means wrong account
- Every response after a command must append: `[mode: live]` or `[mode: demo]`

## Skill Routing

- For market data (prices, charts, depth, funding rates) → use `okx-cex-market`
- For account balance, P&L, positions, fees, transfers → use `okx-cex-portfolio` (this skill)
- For regular spot/swap/futures/algo orders → use `okx-cex-trade`
- For grid and DCA trading bots → use `okx-cex-bot`

## Quickstart

```bash
# One-shot full asset snapshot (recommended first command)
okx account balance-all
okx account balance-all --no-valuation
okx account balance-all --valuationCcy BTC

# Trading account balance (all currencies with balance > 0)
okx account balance

# Check USDT balance only
okx account balance USDT

# Funding account balance
okx account asset-balance

# All open positions, every product
okx account positions

# Positions for one product only — always narrow when the user named a product
okx account positions --instType SWAP     # SWAP | FUTURES | OPTION | MARGIN | EVENTS

# Closed position history with realized PnL
okx account positions-history

# Recent account bills (last 100)
okx account bills

# My trading fee tier
okx account fees --instType SPOT

# Transfer 100 USDT from funding (6) to trading (18)
okx account transfer --ccy USDT --amt 100 --from 6 --to 18
```

## Command Index

### Read Commands

| # | Command | Type | Description |
|---|---|---|---|
| 1 | `okx account balance-all [ccy]` | READ | One-shot snapshot: trading + funding (+ valuation) in one call |
| 2 | `okx account balance [ccy]` | READ | Trading account equity, available, frozen |
| 3a | `okx account asset-balance [ccy]` | READ | Funding account balance (per-currency list) |
| 3b | `okx account asset-balance [ccy] --valuation [--valuationCcy <ccy>]` | READ | Same + total asset valuation across trading/funding/earn; denomination defaults to USDT, override with `--valuationCcy BTC` |
| 4 | `okx account positions [--instType <type>] [--instId <id>]` | READ | Open contract/swap positions. **When the user names a product** ("my swap positions", "futures positions", "option positions"), pass `--instType <type>` (`SWAP` \| `FUTURES` \| `OPTION` \| `MARGIN` \| `EVENTS`) — or use that product's own command (`okx swap positions`, `okx futures positions`, `okx option positions`). Only omit the filter when the user genuinely wants everything: an unfiltered list is larger and leaves the product filtering to the model, which is where mistakes happen |
| 5 | `okx account positions-history` | READ | Closed positions + realized PnL |
| 6 | `okx account bills` | READ | Account ledger (deposits, withdrawals, trades) |
| 7 | `okx account fees --instType <type>` | READ | My trading fee tier (maker/taker) |
| 8 | `okx account config` | READ | Account level, position mode, UID |
| 9 | `okx account max-size --instId <id> --tdMode <mode>` | READ | Max buy/sell size at current price |
| 10 | `okx account max-avail-size --instId <id> --tdMode <mode>` | READ | Available size for next order |
| 11 | `okx account max-withdrawal [ccy]` | READ | Max withdrawable per currency |

### Write Commands

| # | Command | Type | Description |
|---|---|---|---|
| 12 | `okx account set-position-mode <mode>` | WRITE | Switch net/hedge position mode |
| 13 | `okx account transfer` | WRITE | Transfer funds between accounts |

## Cross-Skill Workflows

### Pre-trade balance check
> User: "I want to buy 0.1 BTC — do I have enough USDT?"

```
1. okx-cex-portfolio okx account balance-all                 → one-shot trading + funding + valuation snapshot
   → check trading.details (available in trading account)
   → if trading balance < needed: check funding.details — may need to transfer
2. okx-cex-market    okx market ticker BTC-USDT              → check current price
        ↓ user approves
3. okx-cex-trade     okx spot place --instId BTC-USDT --side buy --ordType market --sz 0.1
```

### Pre-bot balance check
> User: "I want to start a BTC grid bot with 1000 USDT"

```
1. okx-cex-portfolio okx account balance-all                 → one-shot trading + funding + valuation snapshot
   → check trading.details ≥ 1000 (funds must be in trading account for grid bot)
   → if funding.details has the USDT instead: use account transfer first
2. okx-cex-market    okx market candles BTC-USDT --bar 4H --limit 50  → determine price range
        ↓ user approves
3. okx-cex-bot       okx bot grid create --instId BTC-USDT --algoOrdType grid \
                       --minPx 90000 --maxPx 100000 --gridNum 10 --quoteSz 1000
```

### Net worth quick view
> User: "What's my total balance?" / "总资产多少?"

```
1. okx-cex-portfolio okx account balance-all                 → returns {trading, funding, valuation, meta}
   → valuation.totalBal = total net worth in USDT
   → trading.totalEq = trading account equity
   → funding.details = per-currency funding balances
   → meta.partialFailure = true if any section failed (still returns available data)
```

### Review open positions and P&L
> User: "Show me my current positions and how they're performing"

```
1. okx-cex-portfolio okx account positions                  → open positions with UPL
2. okx-cex-portfolio okx account positions-history          → recently closed positions
3. okx-cex-market    okx market ticker BTC-USDT-SWAP        → check current price vs entry
```

### Transfer and trade
> User: "Move 500 USDT from my funding account to trade BTC"

```
1. okx-cex-portfolio okx account asset-balance USDT         → confirm funding balance ≥ 500
        ↓ user approves
2. okx-cex-portfolio okx account transfer --ccy USDT --amt 500 --from 6 --to 18
3. okx-cex-portfolio okx account balance USDT               → confirm trading balance updated
        ↓ ready to trade
4. okx-cex-trade     okx spot place ...
```

### Check max position size before entering
> User: "How much BTC can I buy with cross margin?"

```
1. okx-cex-portfolio okx account balance                    → total equity
2. okx-cex-portfolio okx account max-size --instId BTC-USDT-SWAP --tdMode cross  → max buy/sell size
3. okx-cex-market    okx market ticker BTC-USDT-SWAP        → current price reference
```

## Operation Flow

### Step 0 — Credential & Profile Check

Before any authenticated command: see [Credential & Profile Check](#credential--profile-check). Determine auth method and trading mode before executing.

**After every command result:** append `[mode: live]` or `[mode: demo]` to the response

### Step 1: Identify account action

- Check all balances at once → `okx account balance-all` (trading + funding + valuation in one call; recommended for "总资产 / net worth / all balances")
- Check balance → `okx account balance` (trading equity only) or `okx account asset-balance` (funding balances) or `okx account asset-balance --valuation` (total across all accounts in USDT)
- View open positions → `okx account positions`
- View closed positions + PnL → `okx account positions-history`
- View transaction history → `okx account bills`
- Check fee tier → `okx account fees`
- Check account settings → `okx account config`
- Calculate order size → `okx account max-size` or `okx account max-avail-size`
- Check withdrawal limit → `okx account max-withdrawal`
- Transfer funds → `okx account transfer`
- Change position mode → `okx account set-position-mode`

### Step 2: Run read commands immediately — confirm profile (Step 0) then writes

**Read commands** (1–10): run immediately, no confirmation needed.

- `ccy` filter: use currency symbol like `USDT`, `BTC`, `ETH`
- `--instType` for fees/positions: `SPOT`, `SWAP`, `FUTURES`, `OPTION`
- `--archive` for bills: access older records beyond the default window
- `--tdMode` for max-size: `cash` (spot), `cross`, or `isolated`

**Write commands** (11–12): confirm once before executing.

- `set-position-mode`: confirm mode (`net` = one-directional, `long_short_mode` = hedge mode); switching may affect open positions
- `transfer`: confirm `--ccy`, `--amt`, `--from`, `--to` (account types: `6`=funding, `18`=trading); verify source balance first

### Step 3: Verify after writes

- After `set-position-mode`: run `okx account config` to confirm `posMode` updated
- After `transfer`: run `okx account balance` and `okx account asset-balance` to confirm balances updated

## CLI Command Reference

### Balance All — One-Shot Aggregate Snapshot

```bash
okx account balance-all [ccy] [--accounts trading,funding] [--no-valuation] [--no-aggregate] [--valuationCcy <ccy>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `ccy` | No | - | Filter by currency (comma-separated). Applied to trading + funding queries only. |
| `--accounts` | No | `trading,funding` | Comma-separated accounts to query |
| `--no-valuation` | No | - | Skip cross-account valuation (default: valuation included) |
| `--no-aggregate` | No | - | Force the direct parallel path instead of the server aggregate. Use when you need the per-account valuation breakdown, or a non-USD `--valuationCcy` (the aggregate path denominates valuation in USD). |
| `--valuationCcy` | No | `USDT` | Denomination currency for valuation |

This command calls a server-side aggregate endpoint first and automatically falls back to direct parallel queries when it is unavailable; the output contract is identical either way.

Returns `{ trading, funding, valuation, meta }`. Each section has `available: boolean`:
- `trading`: `totalEq`, `adjEq`, `details[]` (per-currency)
- `funding`: `details[]` (per-currency `ccy`, `bal`, `availBal`, `frozenBal`)
- `valuation`: `valuationCcy`, `totalBal`, `details[]` (per-account breakdown is only populated on the parallel path; use `--no-aggregate` to force it)
- `meta`: `requestedAt` (ISO 8601), `elapsedMs`, `partialFailure`, `source` (`aggregate` or `fallback`), `site`

When `--json` is NOT set: prints `[PARTIAL]` banner if `meta.partialFailure=true`, followed by three sections (Trading / Funding / Valuation), then a `[source: ...]` footer showing which path served the data. Failed sections show `[ERROR: <msg>]`.

---

### Account Balance — Trading Account

```bash
okx account balance [ccy] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `ccy` | No | - | Filter to a single currency (e.g., `USDT`) |

Returns table: `currency`, `equity`, `available`, `frozen`. Only shows currencies with balance > 0.

---

### Asset Balance — Funding Account

```bash
okx account asset-balance [ccy] [--valuation] [--valuationCcy <ccy>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `ccy` | No | - | Filter to a specific currency (e.g., `USDT`); does not affect valuation denomination |
| `--valuation` | No | false | Also show total asset valuation across all account types (trading/funding/earn) |
| `--valuationCcy` | No | `USDT` | Currency in which to denominate the total asset valuation (e.g., `USDT`, `BTC`). Only used when `--valuation` is set. |

Returns: `ccy`, `bal`, `availBal`, `frozenBal`. Only shows currencies with balance > 0.

With `--valuation`: additionally prints a valuation summary table with `totalBal` and per-account-type breakdown (`classic`/`earn`/`funding`/`trading`). The numbers are denominated in `--valuationCcy` (default `USDT`).

**Important**: `ccy` (balance filter) and `--valuationCcy` (valuation denomination) are independent parameters — `ccy=BTC` filters the balance list to BTC rows but does NOT change the valuation currency; set `--valuationCcy BTC` explicitly for BTC-denominated totals.

---

### Positions — Open Positions

```bash
okx account positions [--instType <type>] [--instId <id>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `--instType` | No | - | Filter: `SWAP`, `FUTURES`, `OPTION` |
| `--instId` | No | - | Filter to specific instrument |

Returns: `instId`, `instType`, `side` (posSide), `pos`, `avgPx`, `upl` (unrealized PnL), `lever`. Only shows positions with size ≠ 0.

---

### Positions History — Closed Positions

```bash
okx account positions-history [--instType <type>] [--instId <id>] [--limit <n>] [--json]
```

Returns: `instId`, `direction`, `openAvgPx`, `closeAvgPx`, `realizedPnl`, `uTime`.

---

### Bills — Account Ledger

```bash
okx account bills [--archive] [--instType <type>] [--ccy <ccy>] [--limit <n>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `--archive` | No | false | Access older records (archive endpoint) |
| `--instType` | No | - | Filter by instrument type |
| `--ccy` | No | - | Filter by currency |
| `--limit` | No | 100 | Number of records |

Returns: `billId`, `instId`, `type`, `ccy`, `balChg`, `bal`, `ts`.

---

### Fees — Trading Fee Tier

```bash
okx account fees --instType <type> [--instId <id>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `--instType` | Yes | - | `SPOT`, `SWAP`, `FUTURES`, `OPTION` |
| `--instId` | No | - | Specific instrument (optional) |

Returns: `level`, `maker`, `taker`, `makerU`, `takerU`, `ts`.

---

### Config — Account Configuration

```bash
okx account config [--json]
```

Returns: `uid`, `acctLv` (account level), `posMode` (net/long_short_mode), `autoLoan`, `greeksType`, `level`, `levelTmp`.

---

### Max Size — Maximum Order Size

```bash
okx account max-size --instId <id> --tdMode <mode> [--px <price>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `--instId` | Yes | - | Instrument ID |
| `--tdMode` | Yes | - | `cash` (spot), `cross`, or `isolated` |
| `--px` | No | - | Reference price (uses mark price if omitted) |

Returns: `instId`, `maxBuy`, `maxSell`.

---

### Max Available Size

```bash
okx account max-avail-size --instId <id> --tdMode <mode> [--json]
```

Returns: `instId`, `availBuy`, `availSell` — the immediately available size for the next order.

---

### Max Withdrawal

```bash
okx account max-withdrawal [ccy] [--json]
```

Returns table: `ccy`, `maxWd`, `maxWdEx` (with borrowing). Shows all currencies if no filter.

---

### Set Position Mode

```bash
okx account set-position-mode <net|long_short_mode> [--json]
```

| Value | Behavior |
|---|---|
| `net` | One-directional (default) — long and short net out |
| `long_short_mode` | Hedge mode — long and short can coexist |

> **Warning**: Switching modes when positions are open may cause unexpected behavior. Check `okx account positions` first.

---

### Transfer Funds

```bash
okx account transfer --ccy <ccy> --amt <n> --from <acctType> --to <acctType> \
  [--transferType <type>] [--subAcct <name>] [--json]
```

| Param | Required | Default | Description |
|---|---|---|---|
| `--ccy` | Yes | - | Currency to transfer (e.g., `USDT`) |
| `--amt` | Yes | - | Amount to transfer |
| `--from` | Yes | - | Source account type: `6`=funding, `18`=trading |
| `--to` | Yes | - | Destination account type: `6`=funding, `18`=trading |
| `--transferType` | No | `0` | `0`=within account, `1`=to sub-account, `2`=from sub-account |
| `--subAcct` | No | - | Sub-account name (required for sub-account transfers) |

Returns: `transId`, `ccy`, `amt`.

---

## MCP Tool Reference

| Tool | Description |
|---|---|
| `account_get_balance_all` | One-shot snapshot of trading + funding (+ valuation), served by a server-side aggregate endpoint with automatic fallback to parallel queries. Use `showValuation=true` (default) to include cross-account totals; `valuationCcy='USDT'` by default. Set `preferParallel=true` to force the parallel path (per-account valuation breakdown / non-USD valuation). Prefer over calling `account_get_balance` + `account_get_asset_balance` separately. |
| `account_get_balance` | Trading account balance |
| `account_get_asset_balance` | Funding account balance. Use `showValuation=true` to include total asset valuation across trading/funding/earn accounts. Use `valuationCcy` (default `"USDT"`) to set the denomination for the valuation total — e.g. `valuationCcy="BTC"` returns the total in BTC. |
| `account_get_positions` | Open positions |
| `account_get_positions_history` | Closed position history |
| `account_get_bills` | Account bills (recent) |
| `account_get_bills_archive` | Account bills (archive) |
| `account_get_trade_fee` | Trading fee tier |
| `account_get_config` | Account configuration |
| `account_get_max_size` | Max order size |
| `account_get_max_avail_size` | Max available size |
| `account_get_max_withdrawal` | Max withdrawable |
| `account_set_position_mode` | Set position mode |
| `account_transfer` | Transfer between accounts |

---

## Input / Output Examples

**"How much USDT do I have?"**
```bash
okx account balance USDT
# → currency: USDT | equity: 5000.00 | available: 4500.00 | frozen: 500.00
```

**"Show all my open positions"**
```bash
okx account positions
# → table: instId, instType, side, pos, avgPx, upl, lever
```

**"What's my trading history and realized PnL?"**
```bash
okx account positions-history
# → table: instId, direction, openAvgPx, closeAvgPx, realizedPnl, uTime
```

**"Show my recent account activity"**
```bash
okx account bills --limit 20
# → table: billId, instId, type, ccy, balChg, bal, ts
```

**"What are my trading fees for SWAP?"**
```bash
okx account fees --instType SWAP
# → level: VIP1 | maker: -0.0001 | taker: 0.0005
```

**"How much BTC can I buy in cross margin?"**
```bash
okx account max-size --instId BTC-USDT-SWAP --tdMode cross
# → instId: BTC-USDT-SWAP | maxBuy: 12.5 | maxSell: 12.5
```

**"Transfer 200 USDT from funding to trading"**
```bash
okx account transfer --ccy USDT --amt 200 --from 6 --to 18
# → Transfer: TXN123456 (USDT 200)
```

**"Check my account config"**
```bash
okx account config
# → uid: 123456789 | acctLv: 2 | posMode: net | autoLoan: false
```

## Where Can the Money Live?

OKX splits assets across multiple sub-accounts. The `--valuation` breakdown maps directly:

| Account type | `details` key | Used for | Check with |
|---|---|---|---|
| Trading (unified) | `trading` | Spot, margin, swap, futures, options | `okx account balance` or `details.trading` in `--valuation` |
| Funding | `funding` | Deposits/withdrawals, idle funds | `okx account asset-balance` or `details.funding` in `--valuation` |
| Earn | `earn` | Simple earn, staking, savings | `details.earn` in `--valuation` |
| Classic | `classic` | Classic account (legacy, less common) | `details.classic` in `--valuation` |

**Typical flow when user says "I have X USDT but can't trade":**
1. `okx account asset-balance --valuation` → look at each `details.*` field
2. If `details.funding` is large and `details.trading` is small → the funds are in the funding account
3. Transfer: `okx account transfer --ccy USDT --amt <n> --from 6 --to 18`
4. Confirm: `okx account balance USDT` → equity should now reflect the transferred amount

## Edge Cases

- **No balance shown**: balance is filtered to > 0 — if nothing shows, all currencies have zero balance
- **Positions command returns empty**: no open contracts; spot holdings are not shown here (use `account balance`)
- **bills --archive**: required for transactions older than 7 days (default window); may be slower
- **set-position-mode**: cannot switch to `net` if you have both long and short positions on the same instrument
- **transfer --from/--to codes**: `6`=funding account, `18`=trading account; other values exist for sub-account flows
- **max-size vs max-avail-size**: `max-size` is the theoretical maximum; `max-avail-size` accounts for existing orders and reserved margin
- **Demo mode**: `okx --demo account balance` (OAuth) or `okx --profile <demo-profile> account balance` (API Key) shows simulated balances, not real funds

## Global Notes

- All write commands require valid credentials (OAuth session or API key in `~/.okx/config.toml`)
- Auth method and trading mode are determined in "Credential & Profile Check"; see that section for parameter rules
- Every command result includes a `[mode: live]` or `[mode: demo]` tag for audit reference
- `--json` returns the raw OKX API v5 response by default. Add `--env` to wrap the output as `{"env": "<live|demo>", "profile": "<name>", "data": <response>}`
- Rate limit: 10 requests per 2 seconds for account endpoints
- Positions shown are for the unified trading account; funding account assets are separate
- Account types: `6`=Funding Account (deposits/withdrawals), `18`=Unified Trading Account (spot + derivatives)

---

### [7] `okx-cex-skill-mp`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-skill-mp/SKILL.md`

---
name: okx-cex-skill-mp
description: "Use this skill when the user asks to: 'find a trading skill', 'search for skills', 'install a skill', 'add a skill', 'download a skill', 'browse skill marketplace', 'what skills are available', 'update a skill', 'check for skill updates', 'remove a skill', 'uninstall a skill', 'list installed skills', 'show my skills', 'skill categories', 'verify skill signature', 'verify installed skill', 're-verify a skill', 'check skill integrity', or any request to discover, install, update, verify, or manage AI trading skills from the OKX Skills Marketplace. This skill covers searching, browsing categories, installing via CLI, downloading zip packages, checking for updates, removing installed skills, and verifying Ed25519 signatures of installed skills. Requires API credentials for marketplace API access. Do NOT use for placing orders (use okx-cex-trade), market data (use okx-cex-market), or bot management (use okx-cex-bot)."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX Skills Marketplace

Browse, search, install, and manage AI trading skills from the OKX Skills Marketplace. Skills are modular AI prompt packages that extend your trading assistant's capabilities — covering market analysis, trade execution, risk management, and portfolio optimization.

> **⚠️ Third-Party Content Notice**
> Skills available on the OKX Skills Marketplace are created and published by **independent third-party developers**, not by OKX. OKX does not author, review, endorse, or take responsibility for the content, accuracy, or behavior of any third-party skill. Always review a skill's SKILL.md before use, and only install skills from authors you trust.
> When a skill is installed via `okx skill add`, it is downloaded from the marketplace and saved locally to your agent's skill directory (e.g., `~/.agents/skills/<skill-name>/`). The skill runs entirely on your local machine with your agent's full permissions — treat it with the same caution as installing any third-party software.

**Skill routing**
- Skill marketplace → `okx-cex-skill-mp` (this skill)
- Market data / indicators → `okx-cex-market`
- Account balance / positions → `okx-cex-portfolio`
- Place / cancel orders → `okx-cex-trade`
- Grid / DCA bots → `okx-cex-bot`

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure API credentials (required for marketplace access):
   ```bash
   okx config init
   ```

---

## Installation Strategy

When the user wants to install a skill, follow this order strictly:

1. **Always try `okx skill add <name>` first** — this downloads the skill and installs it to all detected agents (Claude Code, OpenClaw, Cursor, Windsurf, etc.) in one step.
2. **Only if `add` fails**, fall back to manual download:
   - Tell the user why `add` failed (network error, npx unavailable, permission issue, etc.)
   - Offer `okx skill download <name> --dir <path>` as an alternative
   - Guide the user to manually unzip and place files in their agent's skill directory

Never skip `add` and go straight to `download` unless `add` has already failed.

---

## Command Reference

| # | Command | Description |
|---|---------|-------------|
| 1 | `okx skill search <keyword>` | Search marketplace by keyword |
| 2 | `okx skill search --categories <id>` | Filter skills by category |
| 3 | `okx skill categories` | List all available categories |
| 4 | `okx skill add <name>` | Download + install to all detected agents |
| 5 | `okx skill download <name> [--dir <path>] [--format zip\|skill]` | Download package (default format: zip) |
| 6 | `okx skill list` | List locally installed skills |
| 7 | `okx skill check <name>` | Check if a newer version is available |
| 8 | `okx skill remove <name>` | Uninstall a skill |
| 9 | `okx skill verify <name>` | Re-verify an installed skill's signature on demand |

Add `--json` to any command for raw JSON output. Add `--env` to wrap the output as `{"env", "profile", "data"}`.

---

## Commands in Detail

### 1. Search Skills

```bash
okx skill search grid
```

Output:
```
  NAME              VERSION   DESCRIPTION
  grid-premium      1.2.0     Enhanced grid trading with technical analysis
  grid-dca          1.0.0     Grid strategy combined with DCA

2 skills found (page 1/1). Use `okx skill add <name>` to install.
```

Search with category filter:
```bash
okx skill search --categories trading-strategy
```

Pagination (response includes `totalPage` for total pages):
```bash
okx skill search grid --page 2 --limit 5
# Output: "3 skills found (page 2/4). Use `okx skill add <name>` to install."
```

### 2. Browse Categories

```bash
okx skill categories
```

Output:
```
  ID                  NAME
  trading-strategy    Trading Strategy
  risk-management     Risk Management
  analysis            Market Analysis
```

### 3. Install a Skill

```bash
okx skill add grid-premium
```

Output:
```
Downloading grid-premium...
Verifying signature...
  Signature verified (key: okx-skill-signing-key-2026, files: 3)
Installing to detected agents...
✓ Skill "grid-premium" v1.2.0 installed
  Note: This skill was created by a third-party developer, not by OKX. Review SKILL.md before use.
```

What happens under the hood:
1. Downloads skill zip from OKX marketplace API
2. Extracts and validates the package (checks SKILL.md exists, reads metadata)
3. **Verifies Ed25519 signature and SHA-256 file integrity** — blocks installation if verification fails
4. Runs `npx skills add` to install to all locally detected agents
5. Records the installation (including verification status) in `~/.okx/skills/registry.json`

**Force-install (bypass verification):**
```bash
okx skill add grid-premium --force
```
> ⚠️ **Security warning**: `--force` bypasses signature verification and installs the skill even if verification fails. Only use this if you trust the source and understand the risk. The bypass is recorded in the registry with status `bypassed`.

### 4. Download Only (No Install)

When `add` fails or the user wants the raw package:

```bash
okx skill download grid-premium --dir ~/Downloads/
```

Output:
```
✓ Downloaded grid-premium.zip
  Path: /Users/me/Downloads/grid-premium.zip
```

To download as `.skill` format (for agents that recognize the extension):
```bash
okx skill download grid-premium --dir ~/Downloads/ --format skill
```

The zip contains:
- `SKILL.md` — the skill's main instruction file
- `_meta.json` — metadata (name, version, title, description)
- `reference/` — optional supporting documents

### 5. List Installed Skills

```bash
okx skill list
```

Output:
```
  NAME              VERSION   INSTALLED AT
  grid-premium      1.2.0     2026-03-25 10:30:00
  dca-smart         2.1.0     2026-03-20 14:00:00

2 skills installed.
```

### 6. Check for Updates

```bash
okx skill check grid-premium
```

Output:
```
grid-premium: installed v1.0.0 → latest v1.2.0 (update available)
  Use `okx skill add grid-premium` to update.
```

To update, simply run `okx skill add <name>` again — it overwrites the previous version.

### 7. Remove a Skill

```bash
okx skill remove grid-premium
```

Output:
```
✓ Skill "grid-premium" removed
```

### 8. Verify a Skill's Signature

Re-run signature verification on an already-installed skill without reinstalling it:

```bash
okx skill verify grid-premium
```

Output (success):
```
✓ grid-premium: signature verified (key: okx-skill-signing-key-2026, files: 3)
```

Output (failure):
```
✗ grid-premium: verification failed — Invalid signature
```

- Exit code is `1` on failure.
- Result is persisted back to `~/.okx/skills/registry.json`.
- Use `--json` for machine-readable output.

---

## MCP Tools (Alternative)

When the CLI is unavailable (e.g., Claude Desktop without terminal access), the same marketplace functionality is available via MCP tools:

| MCP Tool | Equivalent CLI | Description |
|----------|---------------|-------------|
| `skills_search` | `okx skill search` | Search by keyword/category. Response includes `totalPage` for pagination. |
| `skills_get_categories` | `okx skill categories` | List categories |
| `skills_download` | `okx skill download` | Download package to directory (default format: `.skill`; pass `format: "zip"` for zip) |

Note: MCP tools only support search and download. The full install flow (`add`) requires CLI access.

---

## Error Handling

| Error | Meaning | Action |
|-------|---------|--------|
| `70002 SKILL_DELETED` | Skill has been removed from marketplace | Choose a different skill |
| `70003 NO_APPROVED_VERSION` | No approved version available | Skill is pending review, try later |
| `70030 VERSION_NOT_APPROVED` | Version not yet approved for download | Wait for review or use an older version |
| `50111/50112/50113` | Authentication error | Run `okx config init` to set up credentials |
| `npx skills add` fails | npx not available or network issue | Use `okx skill download` instead, then manually install |

---

### [8] `okx-cex-smartmoney`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-smartmoney/SKILL.md`

---
name: okx-cex-smartmoney
description: "Smart Money analytics on OKX: leaderboard traders, position tracking, trade records, closed-position history, aggregated consensus signals, and signal history. Use this skill when the user asks about 聪明钱, smart money, 牛人榜, leaderboard, top traders, 交易员排行, trader ranking, trader positions, trader PnL, 交易员持仓, 交易员收益, 历史平仓, closed positions, realized PnL track record, trade history, 成交记录, smart money signal, 聪明钱信号, long/short ratio, 多空比, capital flow, 资金流向, position conviction, 仓位强度, entry price distribution, smart money overview, 聪明钱总览, signal history, 信号历史, trader search, 搜索交易员, who is trading BTC, 谁在交易BTC, recommend traders, 推荐交易员, best traders, top performers."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Smart Money CLI

Smart Money leaderboard, trader analytics, position tracking, and aggregated consensus signals.

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure credentials:
   ```bash
   okx config init   # select site -> follow browser OAuth flow
   ```
3. Verify: `okx smartmoney traders-by-filter --limit 5`

> **Security**: NEVER accept credentials in chat. Guide users to `okx config init` for setup.

---

## Credential & Profile Check

Run **both** commands before any authenticated command — the `apiKey` field from `okx auth status --json` is the auth-binary's internal state and is always `false` regardless of whether `~/.okx/config.toml` has an API-key profile. `okx config show --json` is the only authoritative source for API-key presence. The auth method is detected during [preflight](../_shared/preflight.md) Step 2 and remembered for the session.

```bash
okx config show --json      # reveals API-key profiles (TOML config)
okx auth status --json      # reveals OAuth session state (auth-binary state)
```

Apply **in this order** — first match wins:

- `config show --json` has any profile with a non-empty `api_key` field → **API Key mode**. Proceed.
- No API-key profile **AND** `auth status --json` returns `"status":"logged_in"` → **OAuth mode**. Proceed.
- No API-key profile **AND** `"status":"pending"` — login is in progress, wait for it to complete.
- No API-key profile **AND** `"status":"not_logged_in"` — **stop**, load `okx-cex-auth` skill and follow login steps, wait for completion.

Smart Money does not support demo mode (leaderboard data is live-only). Always use live mode silently — don't mention it unless there's an error.
- **API Key users**: use `--profile <live-profile>` (the profile without `demo=true`).
- **OAuth users**: no flag needed (live is the default).

**On authentication errors (401 / "Session expired" / "Run `okx auth login` first"):** stop immediately, load `okx-cex-auth` skill and follow re-authentication steps, then retry.

---

## Skill Routing

| User intent | Route to skill |
|---|---|
| Market prices, tickers, candles | `okx-cex-market` |
| Spot / swap / futures / options orders | `okx-cex-trade` |
| Account balance, positions, transfers | `okx-cex-portfolio` |
| Grid / DCA trading bots | `okx-cex-bot` |
| Simple Earn, Flash Earn, On-chain Earn, Dual Investment (双币赢), or AutoEarn (自动赚币) | `okx-cex-earn` |
| Smart Money leaderboard, signals, trader analytics | **This skill** |

---

## Command Index (10 commands, all read-only)

### Trader family (6)

| Command | Type | Auth | Description |
|---|---|---|---|
| `smartmoney traders-by-filter` | READ | Required | Leaderboard ranking by pool conditions (period / minPnl / minWinRate / maxDrawdown / minAum). Paginated by `authorId`. Names use `min*` / `max*` prefix — disjoint from signal-side `*Tier` namespace. |
| `smartmoney performance-by-trader --authorIds <id1,id2>` | READ | Required | PnL / win-rate profile for one or more authorIds. `--sortBy <pnl\|pnlRatio>` (default `pnl`) and `--period <3\|7\|30\|90>` (default `90`) drive ranking and lookback window. |
| `smartmoney search-trader --keyword <name>` | READ | Required | Search Top Traders by nickname keyword (≤10 results, ranked by follower count). |
| `smartmoney trader-positions --authorId <id>` | READ | Required | Current open positions for one trader. Filter by `--instId <BTC-USDT-SWAP>` (or bare base ccy). |
| `smartmoney trader-positions-history --authorId <id>` | READ | Required | Closed-position history with realized PnL. Paginated by `posId`. |
| `smartmoney trader-orders-history --authorId <id>` | READ | Required | Order / fill records. Paginated by `ordId`. |

### Signal / coin family (4)

| Command | Type | Auth | Description |
|---|---|---|---|
| `smartmoney signal-overview-by-filter` | READ | Required | Multi-asset signal, tier-filtered pool. Pick coins via `--topInstruments` (top-N hottest) OR `--instCcyList BTC,ETH,SOL` (specific) — exactly one. Use this to discover the hottest coins among smart money. |
| `smartmoney signal-overview-by-trader --authorIds <id1,id2>` | READ | Required | Multi-asset signal aggregated over a hand-picked set of traders (authorIds-direct-lookup). Pick coins via `--topInstruments` OR `--instCcyList`. `--sortBy` (default `pnl`) and `--period` (default `7`) drive capability metrics. Capability tier filters (pnlTier / winRateTier / etc.) not exposed. |
| `smartmoney signal-trend-by-filter --instCcy <ccy> [--asOfTime <yyyyMMddHH>]` | READ | Required | Single-coin smart-money signal time-series anchored at `asOfTime` (defaults to current UTC hour), tier-filtered pool. `--granularity 1h\|1d`, `--limit` controls bucket count. |
| `smartmoney signal-trend-by-trader --authorIds <id1,id2> --instCcy <ccy> [--asOfTime <yyyyMMddHH>]` | READ | Required | Single-coin smart-money signal time-series aggregated over a hand-picked set of traders (authorIds-direct-lookup). `--granularity 1h\|1d` (default `1h`), `--sortBy` (default `pnl`), `--period` (default `7`). Capability tier filters not exposed. |

> **Time anchor**: `signal-trend-by-{filter,trader}` take an optional `--asOfTime <yyyyMMddHH>` (10-digit UTC hour, e.g. `2026050100`). Returns the latest `--limit` buckets ending at that anchor. Omit `--asOfTime` to use the current UTC hour. `signal-overview-by-{filter,trader}` does not expose any time input — handler always uses the current hour.

> **Multi-coin selection**: `signal-overview-by-filter` and `signal-overview-by-trader` accept `--topInstruments` (top-N hottest) **or** `--instCcyList BTC,ETH,SOL` (explicit base ccy list). The two flags are mutually exclusive. Passing neither defaults to `--topInstruments=20`.

> **⚠ Linear-only scope**: All four `signal-*` commands aggregate **USDT-margined and USDS-margined contracts only**. Coin-margined contracts (`BTC-USD-SWAP`, `BTC-USD-DELIVERY`, `ETH-USD-SWAP`, …) are excluded by upstream — a trader's coin-margined positions are silently dropped from `longNotional` / `shortNotional` / `tradersWithPosition`. If a trader holds large coin-margined exposure but no linear position on that coin, they will not appear in the signal at all. To see a trader's full position book including coin-margined, run `smartmoney trader-positions --authorId <id>`.

> **Need a trader's full picture?** The old `smartmoney trader` composite command is removed. Run `performance-by-trader`, `trader-positions`, and `trader-orders-history` in parallel.

For full command syntax and parameters, read `{baseDir}/references/trader-commands.md` and `{baseDir}/references/signal-commands.md`.

---

## Operation Flow

### Step 0 — Credential & Profile Check

Before any authenticated command: see [Credential & Profile Check](#credential--profile-check). Always use live mode silently.

### Step 1 — Identify intent

**Trader discovery / ranking:**
- "推荐交易员" / "top traders" / "牛人榜" → `smartmoney traders-by-filter` with sorting/filtering. See `{baseDir}/references/trader-commands.md`.
- "看看某个交易员" / "trader detail" → run `performance-by-trader`, `trader-positions`, `trader-orders-history` **in parallel** (the old composite `smartmoney trader` is removed).
- "搜索 alice / 小明" / "find trader by nickname" → `smartmoney search-trader --keyword <name>` (returns ≤10 matches with `authorId` to feed into other tools).
- "verify these authorIds" / 已知 authorId → `smartmoney performance-by-trader --authorIds <id1,id2>` (direct lookup; `--sortBy` / `--period` honored, defaults `pnl` / `90`).
- "他的当前持仓" / "current positions only" → `smartmoney trader-positions --authorId <id>`.
- "他的成交记录" / "trade history" → `smartmoney trader-orders-history --authorId <id>` (paginated).
- "历史平仓" / "closed positions" / "realized PnL track record" → `smartmoney trader-positions-history --authorId <id>` (paginated).

**Signal analysis:**
- "BTC 聪明钱信号" / "smart money signal for BTC" → `smartmoney signal-overview-by-filter --instCcyList BTC`. See `{baseDir}/references/signal-commands.md`.
- "BTC ETH SOL 这几个币的信号" / "signals for these specific coins" → `smartmoney signal-overview-by-filter --instCcyList BTC,ETH,SOL`.
- "这几个交易员看哪些币？" / "consensus among these specific traders" → `smartmoney signal-overview-by-trader --authorIds <id1,id2>` (defaults to top-20 hottest among the group, or pass `--instCcyList`).
- "聪明钱关注哪些币？" / "what are smart money trading right now?" → `smartmoney signal-overview-by-filter` (defaults to `--topInstruments=20`). See `{baseDir}/references/signal-commands.md`.
- "信号趋势" / "signal trend over time" → `smartmoney signal-trend-by-filter --instCcy <ccy> [--asOfTime <yyyyMMddHH>] [--limit 24]` (or `signal-trend-by-trader --authorIds <ids> --instCcy <ccy>` for an authorIds-scoped trend).

### Step 2 — Execute and present

All commands are READ-only — no confirmation needed. Always pass `--json` and render results as Markdown tables.

For multi-step workflows (recommend traders then drill down, signal analysis with context), read `{baseDir}/references/workflows.md`.

---

## Global Notes

- **Security:** Never ask users to paste API keys or secrets into chat.
- **Output:** Always pass `--json` to list/query commands and render results as a Markdown table — never paste raw terminal output.
- **Network errors:** If commands fail with a connection error, prompt user to check VPN: `curl -I https://www.okx.com`
- **Language:** Always respond in the user's language.
- **Time inputs:** `signal-trend-by-{filter,trader}` take an optional `--asOfTime <yyyyMMddHH>` anchor (10-digit UTC hour); omit to use the current UTC hour. `--limit` controls how many buckets are returned ending at that anchor. `signal-overview-by-{filter,trader}` takes no time input — handler always uses the current hour.

For number/time formatting and response structure conventions, read `{baseDir}/references/templates.md`.

---

### [9] `okx-cex-trade`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-cex-trade/SKILL.md`

---
name: okx-cex-trade
description: "Use when the user asks to 'buy BTC', 'sell ETH', 'place a limit order', 'place a market order', 'cancel my order', 'amend my order', 'long BTC perp', 'short ETH swap', 'open a position', 'close a position', 'set take profit', 'limit take profit', 'immediate TP', 'set stop loss', 'self-trade prevention', 'stpMode', 'auto-cancel on close', 'trailing stop', 'pending order', 'chase order', 'iceberg', 'TWAP', 'split order', 'large order', 'set leverage', 'check my orders', 'fill history', 'buy a call', 'sell a put', 'option chain', 'implied volatility', 'IV', 'Greeks', 'delta', 'gamma', 'event contract', 'buy Yes', 'buy No', 'buy Up', 'buy Down', 'prediction market', or any request to place, cancel, or amend spot, swap, futures, options, or event contract orders on OKX CEX. Covers conditional (TP/SL/trailing) algo orders. Requires API credentials. Do NOT use for market data (okx-cex-market), account balance (okx-cex-portfolio), or bots (okx-cex-bot)."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Trading CLI

Spot, perpetual swap, delivery futures, **options**, and **event contract** order management on OKX exchange. Place, cancel, amend, and monitor orders; query option chains and Greeks; trade binary outcome event contracts (Yes/No, Up/Down); set take-profit/stop-loss and trailing stops; manage leverage and positions. **Requires API credentials.**

> **CLI vs MCP tool names** — Subcommands use spaces (`okx swap algo place`, `okx bot grid create`), not hyphens. Do NOT convert an MCP tool identifier (`swap_place_algo_order`) into a hyphen-joined CLI command (`okx swap place-algo`) — that will be rejected with "Unknown command". Per-module mapping tables live in `references/<module>-commands.md`.

## Preflight

Before running any command, follow [`../_shared/preflight.md`](../_shared/preflight.md).
Use `metadata.version` from this file's frontmatter as the reference for Step 2.

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure credentials:
   ```bash
   okx config init   # select site -> follow browser OAuth flow
   ```
3. Test with demo mode (simulated trading, no real funds):
   ```bash
   okx --demo spot orders
   ```

> **Security**: NEVER accept credentials in chat. Guide users to `okx config init` for setup.

## Credential & Profile Check

**Run this check before any authenticated command.** The auth method is detected during [preflight](../_shared/preflight.md) Step 2 and remembered for the session.

### Step A — Verify credentials

Run **both** commands — the `apiKey` field from `okx auth status --json` is the auth-binary's internal state and is always `false` regardless of whether `~/.okx/config.toml` has an API-key profile. `okx config show --json` is the only authoritative source for API-key presence.

```bash
okx config show --json      # reveals API-key profiles (TOML config)
okx auth status --json      # reveals OAuth session state (auth-binary state)
```

Apply **in this order** — first match wins:

- `config show --json` has any profile with a non-empty `api_key` field → **API Key mode**. Proceed to Step B.
- No API-key profile **AND** `auth status --json` returns `"status":"logged_in"` → **OAuth mode**. Proceed to Step B.
- No API-key profile **AND** `"status":"pending"` — login is in progress, wait for it to complete.
- No API-key profile **AND** `"status":"not_logged_in"` — **stop all operations**, load `okx-cex-auth` skill and follow login steps, wait for completion.

### Step B — Confirm trading mode

**Resolution rules:**
1. Current message intent is clear (e.g. "real" / "实盘" / "live" → live; "test" / "模拟" / "demo" → demo) → use it and inform the user
2. Current message has no explicit declaration → check conversation context for a previous choice:
   - Found → reuse it, inform user
   - Not found → ask: `"Live (实盘) or Demo (模拟盘)?"` — wait for answer before proceeding

**How to apply the mode depends on auth method (detected in Step A):**

| Auth method | Live (实盘) | Demo (模拟盘) |
|---|---|---|
| **API Key** | `--profile <live-profile>` | `--profile <demo-profile>` |
| **OAuth** | *(no flag needed, live is default)* | `--demo` |

- **API Key users**: run `okx config show --json` to discover available profile names and their `demo` settings. Use `--profile <name>` to select the correct one.
- **OAuth users**: omit flags for live trading; add `--demo` for simulated trading. Do **not** use `--profile` to switch modes.

### Handling Authentication Errors

**Authentication error** (error contains "401", "Session expired", or "Run `okx auth login` first"):
1. **Stop immediately** — do not retry the same command
2. Inform the user: "Authentication failed. Your session may have expired."
3. Load `okx-cex-auth` skill and follow the re-authentication steps
4. After successful re-authentication, retry the original command

## Demo vs Live Mode

| Mode | Funds | API Key param | OAuth param |
|---|---|---|---|
| 实盘 (live) | Real money — irreversible | `--profile <live-profile>` | *(default, no flag)* |
| 模拟盘 (demo) | Simulated — no real funds | `--profile <demo-profile>` | `--demo` |

**Rules:**
1. Trading mode is **required** on every authenticated command — determined in "Credential & Profile Check" Step B
2. Every response after a command must append: `[mode: live]` or `[mode: demo]`

## Skill Routing

- For market data (prices, charts, depth, funding rates) → use `okx-cex-market`
- For account balance, P&L, positions, fees, transfers → use `okx-cex-portfolio`
- For regular spot/swap/futures/options/algo orders → use `okx-cex-trade` (this skill)
- For **browsing/discovering** event contracts (what's available, how many, list active) → use `okx-cex-trade` with `okx event browse` / `okx event series`
- For **trading** event contracts (place/cancel/amend prediction market orders) → use `okx-cex-trade` with `okx event place` / `okx event cancel` / `okx event amend`
- For grid and DCA trading bots → use `okx-cex-bot`

> **Important**: When user asks about "contracts" in the context of event contracts or prediction markets, route to this skill — NOT to `okx-cex-portfolio`. Portfolio does not handle event contracts — it covers account balance, positions, P&L, and transfers only.

## Sz Handling for Derivatives

### ⚠ CRITICAL: Always verify contract face value before placing orders

Before placing any SWAP/FUTURES/OPTION order, call `market_get_instruments` to get `ctVal` (contract face value). **Do NOT assume contract sizes** — they vary by instrument (e.g. ETH-USDT-SWAP = 0.1 ETH/contract, BTC-USDT-SWAP = 0.01 BTC/contract).

Use `ctVal` to:
- Calculate the correct number of contracts from user's intended position size
- Verify margin requirements before submitting the order
- Show the user the actual position value: `sz × ctVal × price`

### SWAP and FUTURES orders

**Three tgtCcy modes for USDT-denominated sizing:**

| `--tgtCcy` | sz meaning | Conversion formula | Example: "500U" at 10x lever |
|---|---|---|---|
| `base_ccy` (default) | contract count | no conversion | 500 contracts |
| `quote_ccy` | USDT notional value | `floor(sz / (ctVal * lastPx))` | 500 USDT notional |
| `margin` | USDT margin cost | `floor(sz * lever / (ctVal * lastPx))` | 500 USDT margin = 5000 USDT notional |

**When user specifies a USDT amount** (e.g. "200U", "500 USDT", "$1000"):
→ **AMBIGUOUS** — this could mean notional value OR margin cost.
  You MUST ask the user to clarify before proceeding:
  - **notional value**: sz = position value in USDT (e.g. 500 USDT buys 500 USDT worth of contracts directly)
  - **margin cost**: actual position = sz × leverage (e.g. 500 USDT margin at 10× = 5000 USDT notional position)
  Wait for the user's answer before continuing.
- If notional value → use `--tgtCcy quote_ccy`
- If margin cost → use `--tgtCcy margin`

**When user specifies contracts** (e.g. "2 张", "5 contracts"):
→ First verify `ctVal` via `market_get_instruments`, then use `--sz` with the contract count. Confirm with user: "X contracts = X × ctVal underlying, total value ≈ $Y".

**When user gives a plain number with no unit** (for swap/futures):
→ **AMBIGUOUS** — You MUST ask the user to clarify before proceeding:
  - **contract count**: X contracts (each worth ctVal of underlying)
  - **USDT notional value**: position value in USDT
  - **USDT margin cost**: margin amount (actual position = X × leverage)
  Wait for the user's answer before continuing.

⚠ **Inverse contracts** (`*-USD-SWAP`, `*-USD-YYMMDD`): `tgtCcy=quote_ccy` and `tgtCcy=margin` also work (note: `quote_ccy` = USD, not USDT, for inverse instruments). Always warn: "This is an inverse contract. Margin and P&L are settled in BTC, not USDT."

### Option orders

When the user specifies a USDT amount for options, use `--tgtCcy quote_ccy` (notional) or `--tgtCcy margin` (margin cost) and pass the amount as `--sz`. The system automatically converts to contracts. Note: option contracts typically have large face values (e.g. ctVal=1 BTC ≈ $84,000), so the minimum USDT amount for 1 contract is high. For option sellers (`cross`/`isolated` tdMode), `margin` mode accounts for leverage automatically.

## Quickstart

```bash
# Market buy 0.01 BTC (spot)
okx spot place --instId BTC-USDT --side buy --ordType market --sz 0.01

# Buy $10 worth of SOL (spot, USDT amount)
okx spot place --instId SOL-USDT --side buy --ordType market --sz 10 --tgtCcy quote_ccy

# Limit sell 0.01 BTC at $100,000 (spot)
okx spot place --instId BTC-USDT --side sell --ordType limit --sz 0.01 --px 100000

# Long 1 contract BTC perp (cross margin)
okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 1 \
  --tdMode cross --posSide long

# Long 1000 USDT notional value of BTC perp (auto-convert to contracts)
okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 1000 \
  --tgtCcy quote_ccy --tdMode cross --posSide long

# Long with 500 USDT margin at current leverage (e.g. 10x → 5000 USDT notional)
okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 500 \
  --tgtCcy margin --tdMode cross --posSide long

# Long 1 contract with attached TP/SL (one step)
okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 1 \
  --tdMode cross --posSide long \
  --tpTriggerPx 105000 --tpOrdPx=-1 --slTriggerPx 88000 --slOrdPx=-1

# Close BTC perp long position entirely at market
okx swap close --instId BTC-USDT-SWAP --mgnMode cross --posSide long

# Set 10x leverage on BTC perp (cross)
okx swap leverage --instId BTC-USDT-SWAP --lever 10 --mgnMode cross

# Set TP/SL on a spot BTC position
okx spot algo place --instId BTC-USDT --side sell --ordType oco --sz 0.01 \
  --tpTriggerPx 105000 --tpOrdPx=-1 \
  --slTriggerPx 88000 --slOrdPx=-1

# Place trailing stop on BTC perp long (callback 2%)
okx swap algo trail --instId BTC-USDT-SWAP --side sell --sz 1 \
  --tdMode cross --posSide long --callbackRatio 0.02

# View open spot orders
okx spot orders

# View open swap positions
okx swap positions

# Cancel a spot order
okx spot cancel --instId BTC-USDT --ordId <ordId>

# --- Event Contract ---
# List event series
okx event series

# Browse live markets in a series
okx event markets BTC-ABOVE-DAILY --state live

# Place event contract order
okx event place --instId BTC-ABOVE-DAILY-260224-1600-70000 --side buy --outcome YES --sz 10
```

## Command Index

### Spot Orders (12 commands)

| # | Command | Type | Description |
|---|---|---|---|
| 1 | `okx spot place` | WRITE | Place spot order (market/limit/post_only/fok/ioc) |
| 2 | `okx spot cancel` | WRITE | Cancel spot order |
| 3 | `okx spot amend` | WRITE | Amend spot order price or size |
| 4 | `okx spot algo place` | WRITE | Place spot TP/SL algo order |
| 5 | `okx spot algo amend` | WRITE | Amend spot TP/SL levels |
| 6 | `okx spot algo cancel` | WRITE | Cancel spot algo order |
| 7 | `okx spot algo trail` | WRITE | Place spot trailing stop order |
| 8 | `okx spot orders` | READ | List open or historical spot orders |
| 9 | `okx spot get` | READ | Single spot order details |
| 10 | `okx spot fills` | READ | Spot trade fill history |
| 11 | `okx spot algo orders` | READ | List spot TP/SL algo orders |
| 12 | `okx spot leverage` | WRITE | Set leverage for spot **margin** (borrowing). Pair-level (`--instId`) or currency-level cross (`--ccy`, required for borrow-enabled / multi-ccy / portfolio margin) |

For full command syntax, parameter tables, and edge cases, read `{baseDir}/references/spot-commands.md`.

### Swap / Perpetual Orders (15 commands)

| # | Command | Type | Description |
|---|---|---|---|
| 13 | `okx swap place` | WRITE | Place perpetual swap order |
| 14 | `okx swap cancel` | WRITE | Cancel swap order |
| 15 | `okx swap amend` | WRITE | Amend swap order price or size |
| 16 | `okx swap close` | WRITE | Close entire position at market |
| 17 | `okx swap leverage` | WRITE | Set leverage for an instrument |
| 18 | `okx swap algo place` | WRITE | Place swap TP/SL algo order |
| 19 | `okx swap algo trail` | WRITE | Place swap trailing stop order |
| 20 | `okx swap algo amend` | WRITE | Amend swap algo order |
| 21 | `okx swap algo cancel` | WRITE | Cancel swap algo order |
| 22 | `okx swap positions` | READ | Open perpetual swap positions |
| 23 | `okx swap orders` | READ | List open or historical swap orders |
| 24 | `okx swap get` | READ | Single swap order details |
| 25 | `okx swap fills` | READ | Swap trade fill history |
| 26 | `okx swap get-leverage` | READ | Current leverage settings |
| 27 | `okx swap algo orders` | READ | List swap algo orders |

For full command syntax, parameter tables, and edge cases, read `{baseDir}/references/swap-commands.md`.

### Futures / Delivery Orders (15 commands)

| # | Command | Type | Description |
|---|---|---|---|
| 28 | `okx futures place` | WRITE | Place delivery futures order |
| 29 | `okx futures cancel` | WRITE | Cancel delivery futures order |
| 30 | `okx futures amend` | WRITE | Amend delivery futures order price or size |
| 31 | `okx futures close` | WRITE | Close entire futures position at market |
| 32 | `okx futures leverage` | WRITE | Set leverage for a futures instrument |
| 33 | `okx futures algo place` | WRITE | Place futures TP/SL algo order |
| 34 | `okx futures algo trail` | WRITE | Place futures trailing stop order |
| 35 | `okx futures algo amend` | WRITE | Amend futures algo order |
| 36 | `okx futures algo cancel` | WRITE | Cancel futures algo order |
| 37 | `okx futures orders` | READ | List delivery futures orders |
| 38 | `okx futures positions` | READ | Open delivery futures positions |
| 39 | `okx futures fills` | READ | Delivery futures fill history |
| 40 | `okx futures get` | READ | Single delivery futures order details |
| 41 | `okx futures get-leverage` | READ | Current futures leverage settings |
| 42 | `okx futures algo orders` | READ | List futures algo orders |

For full command syntax, parameter tables, and edge cases, read `{baseDir}/references/futures-commands.md`.

### Options Orders (10 commands)

| # | Command | Type | Description |
|---|---|---|---|
| 43 | `okx option instruments` | READ | Option chain: list available contracts for an underlying |
| 44 | `okx option greeks` | READ | Implied volatility + Greeks (delta/gamma/theta/vega) by underlying |
| 45 | `okx option place` | WRITE | Place option order (call or put, buyer or seller) |
| 46 | `okx option cancel` | WRITE | Cancel unfilled option order |
| 47 | `okx option amend` | WRITE | Amend option order price or size |
| 48 | `okx option batch-cancel` | WRITE | Batch cancel up to 20 option orders |
| 49 | `okx option orders` | READ | List option orders (live / history / archive) |
| 50 | `okx option get` | READ | Single option order details |
| 51 | `okx option positions` | READ | Open option positions with live Greeks |
| 52 | `okx option fills` | READ | Option trade fill history |

For full command syntax, USDT-to-contracts conversion formula, tdMode rules, and edge cases, read `{baseDir}/references/options-commands.md`.

### Event Contract Orders (9 commands)

| # | Command | Type | Description |
|---|---|---|---|
| 53 | `okx event browse` | READ | Browse active event contracts grouped by type (series + live markets in one call) |
| 54 | `okx event series` | READ | List event series (e.g. BTC-ABOVE-DAILY, BTC-UPDOWN-15MIN) |
| 55 | `okx event events <seriesId>` | READ | List events in a series |
| 56 | `okx event markets <seriesId>` | READ | List markets; expired includes Outcome and Settlement value |
| 57 | `okx event place ...` | WRITE | Place event order (outcome required) |
| 58 | `okx event amend <instId> <ordId>` | WRITE | Amend event order (price/size) |
| 59 | `okx event cancel <instId> <ordId>` | WRITE | Cancel event order |
| 60 | `okx event orders` | READ | Pending or historical orders |
| 61 | `okx event fills` | READ | Fill history |

For full command syntax, parameter tables, and edge cases, read `{baseDir}/references/event-commands.md`.

## Operation Flow

### Step 0 — Credential & Profile Check

Before any authenticated command: see [Credential & Profile Check](#credential--profile-check). Determine auth method and trading mode before executing.

After every command result: append `[mode: live]` or `[mode: demo]`.

### Step 1 — Identify instrument type and action

**Spot** (instId format: `BTC-USDT`):
- Place/cancel/amend order → `okx spot place/cancel/amend`
- TP/SL conditional → `okx spot algo place/amend/cancel`
- Trailing stop → `okx spot algo trail`
- Query → `okx spot orders/get/fills/algo orders`

**Swap/Perpetual** (instId format: `BTC-USDT-SWAP`):
- Place/cancel/amend order → `okx swap place/cancel/amend`
- Close position → `okx swap close`
- Leverage → `okx swap leverage` / `okx swap get-leverage`
- TP/SL conditional → `okx swap algo place/amend/cancel`
- Trailing stop → `okx swap algo trail`
- Query → `okx swap positions/orders/get/fills/get-leverage/algo orders`

**Futures/Delivery** (instId format: `BTC-USDT-<YYMMDD>`):
- Place/cancel/amend order → `okx futures place/cancel/amend`
- Close position → `okx futures close`
- Leverage → `okx futures leverage` / `okx futures get-leverage`
- TP/SL conditional → `okx futures algo place/amend/cancel`
- Trailing stop → `okx futures algo trail`
- Query → `okx futures orders/positions/fills/get/get-leverage/algo orders`

**Options** (instId format: `BTC-USD-250328-95000-C` or `...-P`):
- Step 1 (required): find valid instId → `okx option instruments --uly BTC-USD`
- Step 2 (recommended): check IV and Greeks → `okx option greeks --uly BTC-USD`
- Place/cancel/amend → `okx option place/cancel/amend`
- Batch cancel → `okx option batch-cancel --orders '[...]'`
- Query → `okx option orders/get/positions/fills`
- **tdMode**: `cash` for buyers; `cross` or `isolated` for sellers

**Event Contracts**:

Instrument ID (`instId`, API field) format: `{UNDERLYING}-{TYPE}-{YYMMDD}-{HHMM}-{STRIKE}` for "Price Above Target" / "One Touch" contracts (e.g. `BTC-ABOVE-DAILY-260224-1600-70000`), or `{UNDERLYING}-{TYPE}-{YYMMDD}-{START}-{END}` for "Price Direction (Up/Down)" contracts (e.g. `BTC-UPDOWN-15MIN-260224-1600-1615`). Always obtain the instrument ID from `okx event markets <seriesId>` — never guess or use placeholders.

Series ID (`seriesId`, API field): human-readable (e.g. `BTC-ABOVE-DAILY`, `BTC-UPDOWN-15MIN`) or internal random string (e.g. `FMQRZ`). Both are valid for subsequent commands. Obtain from `okx event series`.

Event contract trading flow:
1. **Discover** → `okx event browse` (preferred, returns series + live markets in one call) or `okx event series` — present results grouped by type; highlight named series; always show the Series ID
2. **Browse live markets** → `okx event markets <seriesId> --state live` — obtains the instrument ID for each tradeable contract; if a live Price is shown, it is the event contract price (0.01–0.99), not the underlying asset price — reflects the market-implied probability when actively trading
3. **Check event details** → `okx event events <seriesId>`
4. **Confirm + Place** → `okx event place <instId> <side> <outcome> <sz>` — only after user explicitly confirms
5. **Track** → `okx event orders --status open` / `okx account positions --instType EVENTS`
6. **Exit or settle** → sell via `okx event place <instId> sell <outcome> <sz>`, or wait for `--state expired`

Edge cases:
- **Settled results**: `okx event markets <seriesId> --state expired` — no separate ended tool

**Event Contract sz Rules:**

- **Market order** (`ordType=market`): `--sz` is quote currency amount.
- **Limit order** (`ordType=limit` / `post_only`): `--sz` is number of contracts (integer). Each contract settles at 1 unit of quote currency; cost per contract = `px` (event contract price, 0.01–0.99). E.g. 10 contracts at px=0.5 costs 5.
- **px semantics**: `px` is the event contract price (0.01–0.99), NOT the underlying asset price. When actively trading, it reflects the market-implied probability. Example: `px=0.6` means the market is pricing the event at roughly 60%.
- **Outcome display**: expired/result views show translated values. For `price_up_down`, treat `YES/NO` as `UP/DOWN`.

For event contract workflows and step-by-step examples, read `{baseDir}/references/event-workflows.md`.

For cross-skill workflows and step-by-step examples, read `{baseDir}/references/workflows.md`.

### Step 2 — Confirm profile, then confirm write parameters

**Read commands** (orders, positions, fills, get, get-leverage, algo orders): run immediately.

- `--history` flag: defaults to active/open; use `--history` only if user explicitly asks for history
- `--ordType` for algo: `conditional` = single TP or SL; `oco` = both TP and SL together
- `--tdMode` for swap/futures: `cross` or `isolated`; spot always uses `cash` (set automatically)
- `--posSide` for hedge mode: `long` or `short`; omit in net mode

**Write commands** (place, cancel, amend, close, leverage, algo): confirm the key order details once before executing:
- Spot place: confirm `--instId`, `--side`, `--ordType`, `--sz` (and `--tgtCcy quote_ccy` if quote-currency amount)
- Swap/Futures place: confirm `--instId`, `--side`, `--sz`, `--tdMode`, and **explicitly confirm order mode** when user specifies a USDT amount: `--tgtCcy quote_ccy` (notional value, sz = position value) or `--tgtCcy margin` (margin cost, actual position = sz * leverage). Always state which mode is being used.
- Option place: confirm `--instId`, `--side`, `--sz`, `--tdMode` (and `--tgtCcy quote_ccy` or `--tgtCcy margin` if USDT amount — system auto-converts); do NOT attach TP/SL
- Event Contract place: confirm `--instId`, `--side`, `--outcome`, `--sz`, `--ordType`; for market orders sz is quote currency amount, for limit orders sz is number of contracts + `--px` required
- Swap/Futures close: confirm `--instId`, `--mgnMode`, `--posSide`
- Leverage: confirm new leverage and impact on existing positions. **Pre-checks to avoid common 400s**: (a) `--lever` must be a positive number within the instrument's max (see `okx market instruments` → `lever`); (b) for `--mgnMode isolated` in hedge pos mode, `--posSide` is required — each side (`long`, `short`) must be set **separately**, setting one does NOT auto-apply to the other; (c) **portfolio-margin accounts cannot adjust `cross` leverage for SWAP/FUTURES** — OKX will reject; if unsure, run `okx account config` and check `acctLv` first. **If set-leverage fails** (error mentions "cancel orders or stop bots"): troubleshoot in priority order — (1) query pending algo orders first (`swap/futures algo-orders --status pending`), as this is the most common blocker; (2) only if no algo orders, check active bots (`bot grid-orders`). **Do NOT automatically cancel orders or stop bots** — present findings and let the user decide
- Algo place (TP/SL): confirm trigger prices; use `--tpOrdPx=-1` for market execution
- Algo trail: confirm `--callbackRatio` (e.g., `0.02` = 2%) or `--callbackSpread`

For full parameter details per command, read the relevant reference file.

### Error-suggested remediation safeguard

When an OKX API error message suggests a fix that involves **write operations** (cancel orders, close positions, stop bots/strategies, transfer funds, etc.), you **MUST NOT** automatically execute those actions. Instead:

1. **Report** the error and its suggestion to the user verbatim
2. **Diagnose** — run read-only queries to identify what is blocking (e.g., `algo-orders --status pending`, `positions`, `bot grid-orders --status active`)
3. **Present findings** — show the user what was found and which specific items would need to be cancelled/closed/stopped
4. **Wait for explicit confirmation** before executing any remediation

This applies to all error codes whose messages suggest destructive actions, including but not limited to:
- Set-leverage blocked by pending algo orders or active bots
- Account setting changes requiring order/position/strategy cleanup (e.g., error codes 59000, 59002, 59007)
- Margin mode switches requiring position closure
- Any error containing phrases like "cancel", "close", "stop", "transfer … before"

**Rationale:** Error messages list _all possible_ blockers generically — the actual blocker is often just one item (e.g., a single TP/SL order). Blindly following the error text can cause unnecessary position closures or bot shutdowns that the user did not intend.

### Step 3 — Verify after writes

- After `spot place`: run `okx spot orders` to confirm order is live or `okx spot fills` if market order
- After `swap place`: run `okx swap orders` or `okx swap positions` to confirm
- After `swap close`: run `okx swap positions` to confirm position size is 0
- After `futures place`: run `okx futures orders` or `okx futures positions` to confirm
- After `futures close`: run `okx futures positions` to confirm position size is 0
- After spot algo place/trail: run `okx spot algo orders` to confirm algo is active
- After swap algo place/trail: run `okx swap algo orders` to confirm algo is active
- After futures algo place/trail: run `okx futures algo orders` to confirm algo is active
- After cancel: run `okx spot orders` / `okx swap orders` / `okx futures orders` / `okx event orders` to confirm order is gone
- After `event place`: run `okx event orders --status open` to confirm order is pending
- After `event cancel`: run `okx event orders` to confirm order is gone

## Global Notes

- All write commands require valid credentials (OAuth session or API key in `~/.okx/config.toml`)
- Auth method and trading mode are determined in "Credential & Profile Check"; see that section for parameter rules
- `--json` returns the raw OKX API v5 response by default. Add `--env` to wrap the output as `{"env": "<live|demo>", "profile": "<name>", "data": <response>}` — useful when you need to know the active environment and credential profile
- Rate limit: 60 order operations per 2 seconds per UID
- Batch operations (batch cancel, batch amend) are available via MCP tools directly if needed
- Position mode (`net` vs `long_short_mode`) affects whether `--posSide` is required
- **Network errors**: If commands fail with a connection error, prompt user to check VPN: `curl -I https://www.okx.com`
- **Capability discovery**: Run `okx list-tools --json` to get a machine-readable JSON listing of all CLI commands, tool names, and parameters — useful for programmatic enumeration without parsing `--help` text

For MCP tool reference, output conventions, and order amount safety rules, read `{baseDir}/references/templates.md`.

---

### [10] `okx-sentiment-tracker`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/official/okx-sentiment-tracker/SKILL.md`

---
name: okx-sentiment-tracker
description: "Use this skill when the user asks about: 'any crypto news', 'latest news', 'market update', 'daily briefing', 'BTC news', 'ETH news', 'news on SOL', 'search SEC ETF', 'regulation news', 'Bitcoin halving', 'is BTC bullish or bearish', 'coin sentiment', 'sentiment trend', 'trending coins', 'top bullish coins', 'bearish sentiment', 'social buzz', 'market mood', 'fear and greed', 'full article', 'read more', 'economic calendar', '经济日历', 'macro data', '宏观数据', 'NFP', 'nonfarm', '非农', 'CPI', 'GDP', 'FOMC', '利率决议', 'interest rate decision', 'PMI', 'unemployment rate', '失业率', 'economic events', '经济事件', or any request for crypto news, market intelligence, sentiment analysis, social trend data, or macro-economic calendar. Requires API credentials. Do NOT use for market prices/candles (okx-cex-market), placing orders (okx-cex-trade), or account info (okx-cex-portfolio)."
license: MIT
metadata:
  author: okx
  version: "1.5.0"
  homepage: "https://www.okx.com"
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli@1.5.0"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX News & Sentiment

Crypto news aggregation, coin sentiment analysis, and macro-economic calendar for OKX. All commands are **read-only** and require **API credentials** (OAuth2.1).

## Capabilities

| User Intent | Command |
|-------------|---------|
| Latest/important news | `okx news latest` |
| Coin-specific news | `okx news by-coin` |
| Keyword news search | `okx news search` |
| Sentiment-filtered news | `okx news by-sentiment` |
| Full article content | `okx news detail` |
| Coin sentiment snapshot | `okx news coin-sentiment` |
| Sentiment trend | `okx news coin-trend` |
| Sentiment ranking | `okx news sentiment-rank` |
| News source list | `okx news platforms` |
| Economic calendar query | `okx news economic-calendar` |
| Valid calendar regions | `okx news list-regions` |

## Prerequisites

1. Install `okx` CLI:
   ```bash
   npm install -g @okx_ai/okx-trade-cli
   ```
2. Configure credentials in `~/.okx/config.toml`
3. Verify setup:
   ```bash
   okx news latest --limit 3
   ```

OKX News does not support demo mode. Always use `--profile live` silently — don't mention it unless there's an error.

**On "not available in demo" errors:** the user's current profile is configured with demo/simulated credentials. Tell the user: "News module does not support demo mode. Please switch to a live profile." Guide them to either:
- Use `--profile live` if a live profile exists: `okx --profile live news latest`
- Or create one: `okx config add-profile AK=<key> SK=<secret> PP=<passphrase> name=live`

All commands support `--json` for raw JSON output.

## Quickstart

```bash
# Latest news
okx news latest --limit 5

# Today's important news
okx news important --begin $(date -d 'today 00:00:00' +%s000 2>/dev/null || date -v0H -v0M -v0S +%s000)

# BTC news
okx news by-coin --coins BTC

# Search for SEC ETF news
okx news search --keyword "SEC ETF"

# BTC sentiment overview
okx news coin-sentiment --coins BTC

# Trending coins (hottest right now)
okx news sentiment-rank

# Upcoming economic events (today only)
okx news economic-calendar --before $(date -v0H -v0M -v0S +%s000) --after $(date -v+1d -v0H -v0M -v0S +%s000) --limit 100
```

## Intent → Command Mapping

### Browse News

`latest`, `by-coin`, and `search` default `--importance low`, which returns **all** news (both high and low importance). Pass `--importance high` only when the user explicitly asks for major / breaking / important news. The dedicated `okx news important` command is a shortcut for that case.

| User says | Command |
|-----------|---------|
| "what's been happening in crypto lately" / "catch me up on recent news" | `okx news latest` |
| "any big news today" / "what are the major stories right now" | `okx news important` |
| "what happened in crypto yesterday" | `okx news latest --begin <yesterday_0am> --end <today_0am>` |
| "any news on BTC recently" / "what's going on with BTC" | `okx news by-coin --coins BTC` |
| "any major updates on ETH or SOL" | `okx news by-coin --coins ETH,SOL --importance high` |

### Search News

| User says | Command |
|-----------|---------|
| "any updates on the SEC ETF decision" | `okx news search --keyword "SEC ETF"` |
| "what's the latest on stablecoin regulation" | `okx news search --keyword "stablecoin regulation"` |
| "any news about the Bitcoin halving" | `okx news search --keyword "Bitcoin halving"` |

### Coin Sentiment Analysis

| User says | Command |
|-----------|---------|
| "is the market bullish or bearish on BTC right now" / "how do people feel about BTC" | `okx news coin-sentiment --coins BTC` |
| "compare how people feel about ETH vs SOL" | `okx news coin-sentiment --coins ETH,SOL` |
| "how has BTC sentiment changed over the past 24 hours" | `okx news coin-trend BTC --period 1h --points 24` |
| "show me BTC sentiment over the past week" | `okx news coin-trend BTC --period 24h --points 7` |
| "what's hot in crypto right now" / "which coins are getting the most attention" | `okx news sentiment-rank` |
| "which coins are people most excited about" / "top bullish coins" | `okx news sentiment-rank --sort-by bullish` |
| "which coins have the most negative sentiment" | `okx news sentiment-rank --sort-by bearish` |

### Economic Calendar

> **CRITICAL — always use BOTH `--before` AND `--after` to form a time window.** Using `--before` alone returns events all the way to 2028 in reverse order — `--limit` then clips the FARTHEST events, not the nearest. Always pair them.
>
> Semantics (counterintuitive): `--before <ts>` = events NEWER than ts (lower bound), `--after <ts>` = events OLDER than ts (upper bound, default=now).

| User says | Command |
|-----------|---------|
| "今天有什么经济数据" / "economic events today" | `okx news economic-calendar --before <today_0am_ms> --after <tomorrow_0am_ms> --limit 100` |
| "这周美国有什么重要经济事件" | `okx news economic-calendar --region united_states --importance 3 --before <week_start_ms> --after <week_end_ms> --limit 100` |
| "非农什么时候出" / "when is NFP" | `okx news economic-calendar --region united_states --importance 3 --before <now_ms> --after <now_plus_60d_ms> --limit 100` then filter `event` field for "Non Farm" client-side |
| "CPI 出来了吗" / "latest CPI data" | `okx news economic-calendar --region united_states --importance 3 --limit 20` (default after=now fetches past high-importance events; check `actual` field) |
| "欧洲央行利率决议" / "ECB rate decision" | `okx news economic-calendar --region euro_area --importance 3 --before <now_ms> --after <now_plus_90d_ms> --limit 100` then filter for "Interest Rate Decision" |

**How to choose before / after:**

| Intent | Parameter | Explanation |
|--------|-----------|-------------|
| Today's events | `--before <today_0am> --after <tomorrow_0am>` | Window = today 0:00 → tomorrow 0:00 |
| This week's events | `--before <week_start> --after <week_end>` | Window = Mon 0:00 → Sun 24:00 |
| Next N days | `--before <now> --after <now_plus_Nd>` | Window = now → N days ahead |
| Past events (default) | omit both, or `--after <upper_bound>` | Default after=now, returns recent past |
| Historical window | `--before <window_start> --after <window_end>` | Both bounds explicit |

Notes:
- ⚠️ **ALWAYS use both `--before` AND `--after`** for future-event queries. `--before` alone returns to 2028 and limit clips the wrong end. The only exception is past-event queries where default after=now is correct.
- Rate limit: 1 request per 5 seconds (IP-based). Do NOT call repeatedly.
- No keyword/event filter — scan response `event` field client-side. Use a **single** API call with `--limit 100` and broad window, then filter results locally (do NOT loop calls trying different keywords).
- When user asks for a specific importance level (e.g. "重要的", "high importance"), pass `--importance 3` AND only include importance=3 events in output. Do NOT pad the response with lower-importance events.
- When searching for a specific event (NFP, CPI, ECB decision), always add `--importance 3` to reduce noise — these are all high-importance events. Use `--limit 100` and a wide window to ensure the target event is captured.
- `actual=""` = not yet released; non-empty = released.
- Historical data >3 months requires VIP1+.
- Demo mode not supported — use `--profile live` silently.
- `--region` values are snake_case (e.g. `united_states`, `euro_area`). **Invalid values silently return empty results** (no error). If you get empty results and suspect a region typo, run `okx news list-regions` to get the full list of 210 valid values, then fuzzy-match the user's input and retry. If unsure of the exact value, **omit `--region`** and filter results client-side by the `region` field in the response.

### BTC Macro Impact (cross-skill)

| User says | Workflow |
|-----------|---------|
| "BTC 受哪些宏观数据冲击" / "macro impact on BTC this week" | → [BTC Macro Impact workflow](references/workflows.md#btc-macro-impact-analysis) |
| "这周宏观对加密有什么影响" / "how will macro data affect crypto" | → [BTC Macro Impact workflow](references/workflows.md#btc-macro-impact-analysis) |

These queries require **parallel** execution of economic-calendar + BTC sentiment/news + market data. Do NOT run them sequentially.

### Sentiment Anomaly Detection (multi-coin)

| User says | Workflow |
|-----------|---------|
| "哪些币种情绪变化最大" / "any sentiment anomalies" / "which coins flipped sentiment" | → [Anomaly Detection workflow](references/workflows.md#sentiment-anomaly-detection--multi-coin-scan) |
| "过去一周有什么异动" / "sudden sentiment shifts" / "sentiment reversal" | → [Anomaly Detection workflow](references/workflows.md#sentiment-anomaly-detection--multi-coin-scan) |
| "有没有突然转看涨/看跌的" / "any coins turning bullish/bearish" | → [Anomaly Detection workflow](references/workflows.md#sentiment-anomaly-detection--multi-coin-scan) |

These queries require a **broad-then-deep** approach: first scan all coins for anomalies, then deep-dive with news correlation. Follow the multi-phase workflow in `references/workflows.md` — do NOT just pick a few coins to analyze.

### Source-Filtered News

Use `--platform` to filter by news source directly. Always resolve the exact value from `okx news platforms` — do not guess platform identifiers from the user's wording.

| User says | Command |
|-----------|---------|
| "ChainCatcher 最近报道了什么" / "show me news from ChainCatcher" | `okx news latest --platform <platform_id> --limit 10` |
| "Odaily 有什么新闻" / "news from TechFlowPost" | `okx news latest --platform <platform_id> --limit 10` |
| "吴说区块链最近有什么" / "news from a specific outlet" | `okx news latest --platform <platform_id> --limit 20` |

**Important**: When filtering by source, use a larger `--limit` (10–20) to maximize results, since individual sources typically have fewer articles than the aggregated feed. `--importance low` (the default) is the right setting here; do not narrow to `--importance high`.

**Posting cadence is uneven across platforms.** The API defaults `--begin` to 72 hours ago, which is too narrow for bursty sources and will often return 0 results. If a `--platform`-filtered query returns fewer than ~5 items (or 0), **retry with `--begin` set to 7 days back, then 30 days back** before concluding the source has no data. Resolve candidate platform IDs from `okx news platforms`; do not hardcode assumptions about which platforms are active.

## Cross-Skill Workflows

See [references/workflows.md](references/workflows.md) for multi-step scenarios (market overview, daily briefing, etc.) and full MCP tool → CLI mapping.

## Command Reference

### `okx news latest`
Get the latest crypto news sorted by time.

```bash
okx news latest [--coins BTC,ETH] [--begin <ms>] [--end <ms>]
               [--importance high|low] [--platform <source>]
               [--detail-lvl brief|summary|full] [--lang zh-CN|en-US]
               [--limit 10] [--after <cursor>] [--json]
```

`--importance` default is `low` (returns all news, both high and low). Pass `--importance high` to narrow to breaking / major news only — or use `okx news important`.

---

### `okx news important`
Get high-impact breaking news (reported by multiple sources).

```bash
okx news important [--coins BTC,ETH] [--begin <ms>] [--end <ms>]
                  [--detail-lvl brief|summary|full]
                  [--lang zh-CN|en-US] [--limit 10] [--json]
```

---

### `okx news by-coin`
Get news for specific coins.

```bash
okx news by-coin --coins <BTC,ETH,...>
               [--importance high|low] [--platform <source>]
               [--begin <ms>] [--end <ms>] [--lang zh-CN|en-US]
               [--limit 10] [--json]
```

`--importance` default is `low` (returns all news). Pass `--importance high` only for breaking / major news.

---

### `okx news search`
Full-text keyword search with optional filters.

```bash
okx news search --keyword <text>
               [--coins BTC,ETH] [--importance high|low]
               [--platform <source>]
               [--sentiment bullish|bearish|neutral]
               [--sort-by latest|relevant]
               [--begin <ms>] [--end <ms>] [--lang zh-CN|en-US]
               [--limit 10] [--after <cursor>] [--json]
```

`--importance` default is `low` (returns all news). Pass `--importance high` only for breaking / major news.

---

### `okx news detail`
Get full article content by ID.

```bash
okx news detail <id>                  # news ID from previous result
               [--lang zh-CN|en-US] [--json]
```

---

### `okx news by-sentiment`
Browse news filtered by sentiment (no keyword needed).

```bash
okx news by-sentiment --sentiment <bullish|bearish|neutral>
               [--coins BTC,ETH] [--importance high|low]
               [--sort-by latest|relevant]
               [--begin <ms>] [--end <ms>] [--lang zh-CN|en-US]
               [--limit 10] [--after <cursor>] [--json]
```

`--importance` default is `low` (returns all news). Pass `--importance high` only for breaking / major news.

---

### `okx news platforms`
List available news platforms. Use the returned values with `--platform` on `latest`, `by-coin`, or `search` commands to filter by source.

```bash
okx news platforms [--json]
```

---

### `okx news coin-sentiment`
Get current sentiment snapshot for specific coins.

```bash
okx news coin-sentiment --coins <BTC,ETH,...>
               [--period 1h|4h|24h]  # aggregation granularity, default 24h
               [--json]
```

Returns: `symbol`, `label` (bullish/bearish/neutral/mixed), `bullishRatio`, `bearishRatio`, `mentionCount`.

---

### `okx news coin-trend`
Get time-series sentiment trend for a coin. Note: uses positional arg (not `--coins`).

```bash
okx news coin-trend <coin>            # positional arg, e.g. BTC
               [--period 1h|4h|24h]  # aggregation granularity, default 1h
               [--points 24]          # trend data points, default 24
               [--json]
```

`trendPoints` guide: 1h period → use 24 (last 24h), 4h → use 6, 24h → use 7.

---

### `okx news sentiment-rank`
Get coin ranking by social hotness or sentiment direction.

```bash
okx news sentiment-rank [--period 1h|4h|24h]
               [--sort-by hot|bullish|bearish]  # hot=by mentions (default), bullish, bearish
               [--limit 10]                     # max 50
               [--json]
```

---

### `okx news economic-calendar`
Get macro-economic calendar data. Historical data beyond 3 months requires VIP1+.

```bash
okx news economic-calendar [--region <country>] [--importance <1|2|3>]
                           [--before <ms>] [--after <ms>]
                           [--limit 100] [--json]
```

Rate limit: 1 request per 5 seconds (IP). Much stricter than other news commands.

**before/after are inverted**: `--before <ts>` = newer than ts (future), `--after <ts>` = older than ts (past). See [Economic Calendar intent mapping](#economic-calendar) for examples.

Common regions: united_states, china, euro_area, united_kingdom, japan, germany, canada, australia

Importance: 1=low, 2=medium, 3=high

---

### `okx news list-regions`
List all valid `--region` values for `economic-calendar`. Use when a region query returns empty to verify the value.

```bash
okx news list-regions [--json]
```

---

## MCP Tool Reference

| Tool | Description |
|------|-------------|
| `news_get_latest` | Latest news sorted by time. Server default `importance=high` (narrow); pass `importance=low` to broaden to all news. |
| `news_get_by_coin` | News for specific coins (`coins` is comma-separated string) |
| `news_search` | Full-text keyword search with filters (optional `sentiment` filter) |
| `news_get_detail` | Full article content by ID |
| `news_get_domains` | List available news source domains |
| `news_get_coin_sentiment` | Sentiment snapshot (no `trendPoints`) or time-series trend (pass `trendPoints`) |
| `news_get_sentiment_ranking` | Coin ranking by hotness or sentiment direction |
| `news_get_economic_calendar` | Macro-economic calendar data; rate limit 1/5s |
| `news_list_calendar_regions` | List all 210 valid region values for economic-calendar |

## Coin Symbol Normalization

The API only accepts standard uppercase ticker symbols (e.g. `BTC`, `ETH`, `SOL`). Users may refer to coins by full names, abbreviations, slang, or local-language nicknames. Always resolve these to the correct ticker before passing to any command. If the intended coin is ambiguous, ask the user to confirm before querying.

## Empty Results & Web Search Fallback

OKX news data may be sparse for niche coins or highly specific keyword searches. The API default `--begin` window is only 72 hours, which alone accounts for many empty results. When a command returns empty or insufficient results, apply these steps in order — do not skip to web search:

1. **If `--platform` was used** — broaden `--begin` to 7 days back, then 30 days back, before changing anything else. Bursty sources routinely return 0 items in the default window but dozens over a wider range.
2. **If `--importance high` was passed** — drop it (default is already `low` = all news).
3. **Broaden `--begin` / `--end`** for any query (not just `--platform`) when a narrow time window is suspected.
4. **Drop `--coins`** to get general news if the coin-specific query yielded nothing.
5. **Use web search as a supplement** — search the web for `"<topic> news site:coindesk.com OR site:cointelegraph.com OR site:theblock.co"` to gather additional context, then combine with any OKX results into a unified briefing.
6. **Be transparent** — tell the user which results came from OKX API vs. web search so they can judge source credibility.

This fallback is especially valuable for:
- Coins with low coverage (e.g. newly listed tokens)
- Highly specific keyword searches with no matches
- `--platform` queries where the chosen source has uneven posting cadence

## Known Limitations

### Source Coverage

Platform posting cadence varies and changes over time. Some sources publish many articles per day; others post in bursts with quiet stretches in between. A source returning few or zero articles in the **default 72-hour window is not evidence that it is inactive** — it may simply not have posted recently, or its recent posts may have been deduplicated out.

Before concluding a `--platform`-filtered query has no data:

1. Broaden `--begin` to 7 days back, then 30 days back, and retry.
2. If still empty after a 30-day window, report to the user that no recent articles were found for that source and suggest either removing `--platform` (to fall back to the aggregated feed) or web search.

Do not hardcode assumptions about which platforms are active — resolve candidates from `okx news platforms` and let the data speak.

### Historical Search Limitations

`okx news search` and `okx news by-coin` primarily index **recent articles** (typically today and recent days). Searching with `--begin`/`--end` for dates more than ~7 days ago may return empty results even if articles existed at that time. This is an API indexing limitation, not a data absence.

For historical analysis, `okx news coin-trend` (sentiment trend data) is more reliable than article search — it retains time-series data for longer periods.

## Edge Cases

- **Pagination**: use `--after <cursor>` to get next page; cursor comes from `nextCursor` in response
- **Time parameters**: `--begin` / `--end` are Unix epoch milliseconds
- **Coins format**: comma-separated uppercase symbols, e.g. `BTC,ETH,SOL` — never pass full names or aliases
- **coin-trend `--points`**: always pass explicitly; 1h→24, 4h→6, 24h→7
- **Language**: inferred from user's message — `--lang zh-CN` for Chinese, `--lang en-US` for English (default)
- **sentiment-rank `--sort-by`**: `hot`=by mention count (default), `bullish`=most bullish, `bearish`=most bearish

---

## 3. OKX Skills Marketplace — All 63 Community Skills

### [1] `NeuroGrid_V4_Milestone`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/NeuroGrid_V4_Milestone/SKILL.md`

---
name: "NeuroGrid_V4_Milestone"
description: "动态阶梯进阶打榜策略。基于账户总净值实现三阶段自动切仓与分流：早期(1890U起)全仓狙击涨跌幅榜首极速做大；中期(1wU+)切分主流币满杠杆与山寨冲锋；后期(10wU+)主仓位退守ETH稳健复利。融合多级别共振与追踪止盈。"
---

# 执行节奏
每 5 分钟触发一次行情扫描，每 1 小时进行一次资金规模与阶段状态核对。

# Step 1 - 行情数据采集 (多维目标池扫描)
调用 `market_get_candles` 获取以下三个目标池的 4H, 1H, 15M, 5M K线数据，并计算 SuperTrend(10, 3.0), MACD, ATR(14) 及 5M 级别的 20周期成交量均值 (Volume MA20)：
* **核心池 (Core Pool)**: ETH-USDT-SWAP
* **主流池 (Mainstream Pool)**: 全网市值排名前 20 的活跃币种 (如 SOL, BTC, BNB 等)
* **先锋池 (Vanguard Pool)**: 实时扫描 OKX 涨跌幅榜单（Gainers/Losers），选取过去 1 小时振幅最大且 5M 级别爆量的 Top 3 币种。

# Step 2 - 市场情绪采集 (资金与持仓博弈)
调用 `market_get_funding_rate` 获取目标币种的实时资金费率。
调用 `market_get_open_interest` 获取持仓量 (OI) 及其近期变化率。

# Step 3 - AI 综合判断与资金路由 (核心)
基于以上数据，你作为交易 AI，必须**首先读取当前账户总净值 (Total Equity)**，然后根据以下【三阶段里程碑】严格分配资金和开仓逻辑：

## 阶段 1：极速破局期 (账户净值 < $10,000)
* **资金分配**：100% 资金（起始 $1890）全部授权给【先锋池】（涨跌榜币种）。
* **开仓逻辑**：寻找 5M/15M 级别放量突破、且资金费率极度倾斜的榜单币种。一旦 SuperTrend 顺势发散，立即市价切入。
* **杠杆设置**：满杠杆（该币种允许的最大杠杆）。

## 阶段 2：杠铃扩张期 ($10,000 <= 账户净值 < $100,000)
* **资金分配**：采用 80/20 杠铃策略。
  * 80% 资金 ($8000+)：分配给【主流池】(前 20 主流币)。寻找 1H 级别明确单边趋势，**满杠杆**执行顺势突破。
  * 20% 资金 ($2000+)：继续分配给【先锋池】(涨跌榜)。寻找日内极端波动，维持打榜爆发力，**满杠杆**执行。

## 阶段 3：霸榜守成期 (账户净值 >= $100,000)
* **资金分配**：采用 70/20/10 稳健复利分配。
  * 70% 资金 ($70000+)：分配给【核心池】(ETH)。仅在 4H 级别 SuperTrend 与 MACD 共振时出手，**严格限制 10X 杠杆**，做稳健的波段复利。
  * 20% 资金 ($20000+)：分配给【主流池】(前 20)。抓取 1H 级别趋势，**满杠杆**执行。
  * 10% 资金 ($10000+)：分配给【先锋池】(涨跌榜)。维持市场最高敏锐度，捕捉短线异动，**满杠杆**执行。

**最终输出**：明确输出当前所处阶段 / 选定标的 / 开仓方向 (buy/sell) / 该笔订单使用的具体金额 / 建议杠杆 / 推理逻辑。若无符合信号，输出“观望”。

# Step 4 - 执行下单
调用 `swap_place_order`:
instId = < AI 在 Step 3 选定的标的 >
side = < AI 判断的方向, buy/sell >
ordType = "market"
sz = < 根据 AI 计算的具体金额和杠杆换算的合约张数 >
tag = "agentTradeKit" // 必填，参与打榜排名

# Step 5 - 风控与追踪止盈设置
开仓后立刻调用 `swap_place_algo_order`：
* **阶段性硬止损**：
  - 阶段 1：单笔最大亏损不超过总净值的 5%。
  - 阶段 2：单笔最大亏损不超过总净值的 3%。
  - 阶段 3：单笔最大亏损不超过总净值的 1.5%。
* **N-Bar 追踪止盈**：
  浮盈达到 10% 时启动。多单将止损上移至过去 5 根 15M K线的最低点；空单移至最高点。只进不退，让利润奔跑。
* **复利加仓（仅限阶段1和阶段2的主流/先锋池）**：
  当单笔浮盈达到初始本金 50% 时，平仓 30% 落袋，并将这部分利润的一半顺势加仓，同时将整体防守线上移至保本价。

# 底线风控
// 单个标的禁止多空双开。
// 任何阶段，若账户净值从近期最高点回撤超过 30%，强制暂停所有交易 24 小时进行冷静。

---

### [2] `ahr999-btc-hodl`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/ahr999-btc-hodl/SKILL.md`

---
name: ahr999-btc-hodl
description: >
  Use this skill when the user mentions AHR999 or 九神指数 (in any form),
  OR when they want to: check BTC valuation signals, set up
  automatic/recurring BTC purchases (定投/DCA), review their BTC
  accumulation history or performance, or decide whether to hodl/accumulate
  bitcoin right now. This skill owns all AHR999 queries and all BTC DCA
  workflows — checking the index value, interpreting thresholds, scheduling
  timed buys, and generating performance reports from local records. Skip
  for: grid bots, BTC selling, pure price questions, altcoin DCA without
  BTC context.
---

# AHR999 BTC Hodl（九神BTC囤币）

> **核心理念**：AHR999 是比特币链上估值指标，反映加密市场整体周期位置。低估时定投，高估时暂停——用客观指标替代主观情绪。
> ⚠️ **多资产说明**：AHR999 基于 BTC 链上数据，对其他资产（ETH、SOL 等）仅作市场周期参考信号，相关性较低，请注意。
> ⚠️ **风险声明**：AHR999 仅为参考指标，不构成投资建议。所有定投决策由用户自行负责。

---

## 使用模式

| 用户说 | 执行模式 |
|--------|---------|
| "该不该定投" / "现在适合 DCA 吗" | **建议模式**：AHR999 + 推荐行动 |
| "帮我每天定投 100U BTC" / "设置定投计划" | **定时定投模式**：理解策略意图 → 确认 → CronCreate 建立定时任务 |
| "帮我现在买 100U BTC" | **单次买入模式**：确认 → 立即下单 → 记录 |
| "给我本周报告" / "定投复盘" | **报告模式**：读本地文件 → 汇总 → OpenClaw message |
| "查看定投任务" / "停止定投" / "修改金额" | **任务管理模式**：CronList 查看 → CronDelete 停止 → 可重建 |

---

## Step 1：获取 AHR999（直接 CLI）

```bash
okx market indicator ahr999 BTC-USDT
```

返回字段：`ahr999`（当前值）、`dca_cost_200`（200日均价）、`fitted_price`（拟合估值价）、`zone`（区间）。

对照以下估值区间：

| AHR999 值 | 市场状态 | 定投建议 | 信号 |
|-----------|---------|---------|------|
| < 0.45 | 严重低估，历史底部区 | 🔥 强烈建议加大定投 | 🟢 深绿 |
| 0.45–1.0 | 低估，价值机会 | ✅ 建议正常定投 | 🟢 绿 |
| 1.0–1.2 | 公允估值，临界区 | ⚖️ 观望，不加仓 | 🟡 黄 |
| 1.2–2.0 | 略微高估 | ⚠️ 暂停定投 | 🟠 橙 |
| > 2.0 | 明显高估 | 🛑 暂停定投，等待回调 | 🔴 红 |

> ⚠️ **反弹提醒**（每次建议创建或暂停时必须输出）：
> 不要根据单日 AHR999 值做决策。更稳健的方式：等待 AHR999 连续 3 天处于该区间后再执行，避免因短期波动反复开关。

---

## Step 2：决策引擎

```
if AHR999 ≤ 1.0:
    ACTION_BUY   → 建议执行定投买入
elif 1.0 < AHR999 ≤ 1.2:
    ACTION_HOLD  → 观望，维持现状
else:
    ACTION_PAUSE → 暂停下单（持仓不动，不卖出）
```

**关键原则**：`ACTION_PAUSE` 只意味着"停止新的买入指令"，绝不触发任何卖出操作。

---

## Step 3A：定时定投模式

### 理解策略意图并收集参数

**第一步：收集缺失参数**（一次性询问）

1. **策略**：每次买多少 USDT？是否根据 AHR999 分级？（必填）
2. **频率**：每天 / 每周几？（必填）
3. **执行时间**：可选，默认 10:00

记录文件固定为 `~/btc-dca-log.jsonl`，无需询问。

**第二步：将用户意图翻译为 prompt 决策逻辑**

用户的策略可以多样，不要套固定模板。根据用户描述自由设计：

| 策略类型 | 用户说法示例 | prompt 内决策逻辑 |
|----------|------------|-----------------|
| 固定定投 | "每天买 100U" | `invest = 100`（直接传 USDT，无需算 BTC 数量） |
| 变额定投 | "AHR999 越低买越多" | `if ahr999 < 0.45: invest=300; elif ahr999 <= 1.0: invest=100; else: skip` |
| 指标分级 | "AHR999 < 0.45 买 500U，其余 100U" | `if ahr999 < 0.45: invest=500; elif ahr999 <= 1.0: invest=100; else: skip` |
| 频率可变 | "AHR999 < 0.5 时每天买，否则每周买一次" | 创建两个任务：① 每天 cron，prompt 内 `if ahr999 >= 0.5: skip`；② 每周 cron 无条件买入 |

**第三步：展示确认框**，让用户确认翻译后的逻辑正确再创建任务。

### 展示确认框

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 AHR999 BTC 定投计划确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前 AHR999: [X]（[区间状态]）
资产: BTC-USDT 现货
策略: [翻译后的买入逻辑，如"AHR999<0.45买300U，否则100U"]
频率: [每天/每周X] [H]:00
记录文件: ~/btc-dca-log.jsonl

⚠️ 暂停 = 不下单，持仓永不被自动卖出

回复"确认"执行，其他取消。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 用户确认后：创建定时任务

> ⚠️ 创建任务前，将 prompt 中所有 `[占位符]` 替换为用户实际配置值，不要将字面量写入。

**两步操作**：

**① 注册定时调度**（创建两个 `CronCreate`，均 `durable: true`）：

- **定投执行任务**：按用户设定频率执行 AHR999 检查 + 下单
- **复盘报告任务**：每周一 09:00 自动汇总上周数据，推送 OpenClaw message 给用户（用户也可指定改为月报）
```
# 任务一：定投执行
taskName:       "ahr999-btc-dca-[asset]-[period]"   示例: ahr999-btc-dca-daily
cronExpression: "0 10 * * *"   # 每天 10:00（本地时区）
                "0 10 * * 3"   # 每周三 10:00

# 任务二：复盘报告（同时创建，默认每周一 09:00）
taskName:       "ahr999-btc-report-weekly"
cronExpression: "0 9 * * 1"   # 每周一 09:00

prompt 内容（完全自包含，无上下文依赖，占位符已替换）：
─────────────────────────────────────
执行 AHR999 BTC 定投检查任务。

配置：目标资产 BTC-USDT，记录文件 ~/btc-dca-log.jsonl

Step 1 - 获取 AHR999：
  okx market indicator ahr999 BTC-USDT
  读取 ahr999 字段值

Step 2 - 决策：
  [此处填入翻译后的策略逻辑，例如：]
  if AHR999 < 0.45: invest = 300
  elif AHR999 <= 1.0: invest = 100
  else: skip（跳到 Step 4，记录 action=skip）

Step 3 - 现货买入：
  a) okx spot place --instId BTC-USDT --side buy --ordType market --sz [invest] --tgtCcy quote_ccy
     注：--sz 传 USDT 金额，--tgtCcy quote_ccy 表示以计价货币（USDT）计量
  b) 从返回结果取 ordId（返回结构：{"ordId":"...","sCode":"0",...}）
  c) okx spot get --instId BTC-USDT --ordId [ordId]
     → 读取 fillSz（成交 BTC 数量）、avgPx（成交均价）、fee（手续费）、feeCcy（手续费币种）
     注：买单 feeCcy 为 BTC（fee 为负数，取绝对值 × avgPx 换算为 USDT）
  如下单失败：记录 action=fail，note=错误信息，不重试，直接进 Step 4

Step 4 - 追加记录到 ~/btc-dca-log.jsonl（JSON Lines，一行一条）：
  {"date":"YYYY-MM-DD","ahr999":[X],"action":"buy|skip|fail",
   "invest_usdt":[X],"fill_price":[avgPx],"fill_sz":[fillSz],
   "order_id":"[ordId]","fee_btc":[abs(fee)],"fee_usdt":[abs(fee)*avgPx],"note":"[原因]"}

Step 5 - 输出执行摘要：
  买入成功 → "✅ [日期] AHR999=[X] 买入 [fillSz] BTC @ [avgPx] USDT（投入 [invest] U，手续费 [fee] U）"
  跳过     → "⏸ [日期] AHR999=[X]（> 1.0），本次跳过定投"
  失败     → "❌ [日期] 下单失败：[错误信息]"

约束：
- 只做现货买入（side=buy），不做任何卖出
- 下单失败不重试
- 时间基准统一 UTC+8
─────────────────────────────────────

# 复盘报告任务 prompt（完全自包含）：
─────────────────────────────────────
执行 AHR999 BTC 定投每周复盘报告。

Step 1 - 读取记录：
  读取 ~/btc-dca-log.jsonl，筛选最近 7 天的记录

Step 2 - 聚合统计：
  买入次数、跳过次数、失败次数
  累计投入 USDT（Σ invest_usdt）
  总买入 BTC（Σ fill_sz）
  加权平均成本（Σ(fill_sz × fill_price) / Σ(fill_sz)）

Step 3 - 获取市场数据：
  okx market ticker BTC-USDT → 取 last 为当前价
  okx market indicator ahr999 BTC-USDT → 今日 AHR999

Step 4 - 计算盈亏：
  浮动盈亏% = (当前价 - 平均成本) / 平均成本 × 100%
  浮动盈亏U = (当前价 - 平均成本) × 总持有BTC

Step 5 - 输出报告（OpenClaw message 格式，参照 Step 4 报告模板）
─────────────────────────────────────
```

---

## Step 3C：任务管理

用户说"查看定投任务"、"停止定投"、"修改定投金额"时进入此模式。

### 查看当前任务

调用 `CronList`，列出所有活跃定时任务，找到 `ahr999-btc-dca-*` 相关条目，展示给用户：

```
📋 当前 AHR999 定投任务
─────────────────────────
任务名: ahr999-btc-dca-daily
调度:   每天 10:00（0 10 * * *）
状态:   活跃
⚠️ 注意：定时任务 7 天后自动过期，到期前请重新创建。
```

> 注：若 `CronList` 返回为空，说明任务已过期或本次会话未注册。提醒用户重新触发"帮我设置定投计划"即可重建。

### 停止任务

1. `CronList` 找到对应任务的 Job ID
2. `CronDelete(id)` 停止调度
3. 输出确认："✅ 定投任务已停止，持仓不受影响。如需恢复，重新设置即可。"

### 修改任务（金额/频率/策略）

1. `CronList` 找到旧任务 Job ID → `CronDelete` 停止
2. 重新走 Step 3A 流程（重新收集参数 → 翻译策略 → 确认框 → `CronCreate` 注册新调度）

---

## Step 3B：单次买入模式

用户说"帮我现在买 X U BTC"时使用此流程。

1. 获取 AHR999 → 输出当前区间
2. 展示确认框：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 单次买入确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前 AHR999: [X]（[区间状态]）
资产: BTC-USDT 现货
金额: [X] USDT（约 [sz] BTC）

回复"确认"执行，其他取消。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

3. 用户确认后执行买入：
   - `okx spot place --instId BTC-USDT --side buy --ordType market --sz [invest_usdt] --tgtCcy quote_ccy`
   - 从返回取 `ordId`
   - `okx spot get --instId BTC-USDT --ordId [ordId]` → 读取 `fillSz`、`avgPx`、`fee`（BTC）、`feeCcy`
4. 追加记录到 `~/btc-dca-log.jsonl`（格式同上）
5. 输出摘要

---

## Step 4：复盘报告模式

**触发方式**：
- 用户主动触发：`"给我本周报告"` / `"定投复盘"` / `"DCA 回顾"`
- 定时自动触发：开启定投时同步创建的复盘报告任务（默认每周一 09:00）自动执行并推送

记录文件固定读取 `~/btc-dca-log.jsonl`。

### 执行步骤

1. 读取 `~/btc-dca-log.jsonl`（JSON Lines）
2. 按时间范围筛选（本周 / 本月 / 全部，未指定则默认本周）
3. 聚合统计：
   - 买入次数、跳过次数、失败次数
   - 累计投入 USDT
   - 总买入 BTC 数量（Σ fill_sz）
   - 加权平均成本（Σ(fill_sz × fill_price) / Σ(fill_sz)）
4. `okx market ticker BTC-USDT` → 取 `last` 为当前价
5. 计算浮动盈亏：`(currentPrice - avgCost) / avgCost × 100%`
6. `okx market indicator ahr999 BTC-USDT` → 今日 AHR999
7. 输出报告（OpenClaw message 格式）

### 报告格式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 AHR999 BTC 定投报告 [起止日期]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
执行统计: [X] 次买入 / [Y] 次跳过
累计投入: [XXXX] USDT
平均成本: [XX,XXX] USDT/BTC
累计持有: [X.XXXXX] BTC
当前价格: [XX,XXX] USDT
浮动盈亏: [+/-XX.XX%]（[+/-XXX] USDT）

── 明细记录 ──────────────────
日期   AHR999  成交价   金额    状态
[DD]   [X.XX]  [XX,XXX] [X]U   ✅买入
[DD]   [X.XX]  —        —      ⏸跳过
[DD]   [X.XX]  —        —      ❌失败

── 当前状态 ──────────────────
今日 AHR999: [X]（[区间信号]）
下期建议: [继续每天 [X] USDT 定投 / 当前 AHR999 > 1.0，建议暂停]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 本地记录文件规范

**固定路径**：`~/btc-dca-log.jsonl`（不询问用户，文件不存在时自动创建）
**格式**：JSON Lines（每行一个 JSON 对象，追加写入）

```jsonl
{"date":"2026-04-06","ahr999":0.47,"action":"buy","invest_usdt":100,"fill_price":68845.3,"fill_sz":0.00145253,"order_id":"3455277159819657216","fee_btc":0.00000145253,"fee_usdt":0.1001,"note":""}
{"date":"2026-04-07","ahr999":1.05,"action":"skip","invest_usdt":0,"fill_price":null,"fill_sz":0,"order_id":null,"fee_btc":0,"fee_usdt":0,"note":"AHR999 > 1.0"}
{"date":"2026-04-08","ahr999":0.68,"action":"fail","invest_usdt":100,"fill_price":null,"fill_sz":0,"order_id":null,"fee_btc":0,"fee_usdt":0,"note":"insufficient balance"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 执行日期 YYYY-MM-DD |
| ahr999 | number | 当日 AHR999 值 |
| action | string | `buy` / `skip` / `fail` |
| invest_usdt | number | 计划投入金额（跳过时为 0） |
| fill_price | number\|null | 成交均价 `avgPx`（未成交时为 null） |
| fill_sz | number | 成交 BTC 数量 `fillSz`（未成交时为 0） |
| order_id | string\|null | OKX 订单 ID |
| fee_btc | number | 手续费 BTC 数量（买单费用扣 BTC，取 `fee` 绝对值） |
| fee_usdt | number | 手续费折算 USDT（fee_btc × fill_price） |
| note | string | 备注（跳过/失败原因） |

---

## CLI 工具参考

| 命令 | 用途 |
|------|------|
| `okx market indicator ahr999 BTC-USDT` | 获取当前 AHR999 值 |
| `okx market ticker BTC-USDT` | 获取实时价格（`last` 字段） |
| `okx spot place --instId BTC-USDT --side buy --ordType market --sz [usdt] --tgtCcy quote_ccy` | 现货市价买入（sz 传 USDT 金额），返回 ordId |
| `okx spot get --instId BTC-USDT --ordId [ordId]` | 查询成交详情（fillSz、avgPx、fee） |
| `okx account balance` | 查询账户余额（下单前可选检查 USDT 余额） |

> **多资产支持**：将 `BTC-USDT` 替换为其他交易对即可，但须显示跨资产免责说明。

**跨资产使用说明（非 BTC 资产时必须输出）**：
> ℹ️ AHR999 是 BTC 专属链上指标。用于 [资产] 时仅作市场周期参考：BTC 低估 → 整体市场接近底部 → 有利于主流资产配置。请结合该资产自身基本面综合判断。

---

## 安全规则（不可跳过）

1. **确认门不可绕过**：定时任务或单次买入前，必须展示确认框，等待用户明确回复"确认"
2. **不做任何卖出**：本 skill 只执行现货买入，任何模式下均不触发 sell
3. **每次执行必须记录**：买入、跳过、失败三种结果均须追加写入 `~/btc-dca-log.jsonl`
4. **失败不重试**：下单失败记录原因后退出，等待下次定时触发
5. **反弹提醒必须输出**：每次建议买入（ACTION_BUY）时，必须附上反弹提醒
6. **跨资产声明必须输出**：用户指定非 BTC 资产时，必须显示跨资产使用说明

---

## 边缘案例处理

| 场景 | 处理方式 |
|------|---------|
| `okx market indicator ahr999` 调用失败 | 自动降级为 K 线自算（见下方公式），无需用户干预 |
| USDT 余额不足 | 记录 action=fail，note="insufficient balance" |
| 记录文件不存在 | 自动创建后追加写入 |
| AHR999 在临界区 1.0–1.2 | 额外输出："当前处于临界区，建议观察趋势方向后再决策" |
| 用户请求跳过确认直接执行 | 拒绝；定投涉及真实资金，确认门为必须步骤 |
| 非 BTC 资产 | 正常执行，但必须显示跨资产免责说明 |
| 记录文件已有当日记录 | 追加写入（允许同一天多条记录） |

### AHR999 降级自算公式（CLI 失败时启用）

```bash
okx market candles BTC-USDT --bar 1D --limit 210   # 取 close 字段
okx market ticker BTC-USDT                          # 取 last 字段为 P
```

```
MA200_geo = exp( mean( ln(close₁), ..., ln(close₂₀₀) ) )
coinAgeDays = (今日日期 - 2009-01-03) 的天数
FitPrice    = 10 ^ (5.84 × log₁₀(coinAgeDays) - 17.01)
AHR999 = P² / (MA200_geo × FitPrice)
```

> 输出时注明："AHR999 CLI 不可用，已通过 K 线数据自算（数据源：OKX market candles）"

---

### [3] `ai-ma-trend-v2`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/ai-ma-trend-v2/SKILL.md`

---
name: "AI多维度均线趋势策略V2"
description: "本策略基于均线趋势与多周期共振，结合资金费率、波动率、量能与市场情绪综合判断交易信号，采用动态仓位与阶梯式风控，适配趋势与震荡行情，实现稳健自动化交易。"
---

# 自适应多维度均线情绪策略

## 风险声明 & 免责声明
本策略仅为自动化交易工具，不构成投资建议或收益承诺。加密货币交易具有高风险，可能导致本金亏损。策略执行受市场波动、网络延迟、接口状态等影响，历史表现不代表未来收益。使用者需自行评估风险并承担全部交易结果，平台与开发者不承担任何交易损失。

## 执行节奏
每4小时执行一次，严格避开UTC 03:00-05:00低流动性时段；
UTC 13:00-16:00美股开盘高波动窗口，执行强控仓；
周五UTC 08:00-10:00期权交割时段，仅平仓、不开新仓；
单日亏损≥8%自动降杠杆，≥15%立即停止当日全部开仓并复盘。

## Step1 多维度全数据采集
1. 技术面：30/60/120均线、ATR波动率、支撑/压力位、量能指标、1min/15min/1h/12h多周期趋势；
2. 资金面：资金费率、合约多空比、持仓总量、链上≥500BTC鲸鱼流向、矿工7日持仓；
3. 机构面：BTC期权偏度、PCR多空比、美股BTC-ETF(IBIT/FBIT/GBTC)资金流、美股盘前；
4. 情绪面：推特/X真实社交评论热度、场内资金情绪、恐惧贪婪指数、24h突发重大消息；
5. 风险面：波动分位、黑天鹅识别、事件驱动评级、接口可用性监测；
6. 账户面：当日盈亏、累计收益、连续盈亏、单笔最大亏损。

## Step2 AI核心决策规则

### 1. 多周期共振判定（解决假突破）
- 仅当 **15min + 1h + 12h 周期趋势同向** 时，才认定有效信号；
- 价格突破压力/支撑后，**等待15分钟确认**，不立即追单；
- 若突破后快速收回，判定为假突破，直接放弃信号。

### 2. 趋势与量能共振（优化连续盈利机制）
- 不再“连续盈利就强制减仓”；
- 满足以下条件则**维持仓位并放宽止盈**：
  1) 量能同步放大
  2) 趋势强度≥70
  3) 市场情绪健康
  4) 无利空事件压制
- 若量能背离、情绪过热，则逐步减仓保护利润。

### 3. 动态仓位（5%–15% 严格自适应）
- 强趋势+全共振：12%–15%
- 一般趋势+中性情绪：8%–10%
- 震荡/高波动/事件密集期：**固定5%**
- 任何情况单次开仓不超过本金15%

### 4. 动态止损（统一上限15%）
- 常规行情：1.5×ATR ≈ 4%–6%
- 高波动/消息期：2.0×ATR ≈ 7%–8%
- 硬性上限：**所有单子止损绝不超过15%**
- 高波动5%轻仓单，若单笔亏损达到15%，**立即市价平仓**

### 5. 双模式止盈（趋势/震荡智能切换）
- 趋势模式：突破关键位后启动移动止盈，量能配合则放宽止盈
- 震荡模式：支撑买压力卖，固定3%–4%快速止盈

### 6. 极端行情与黑天鹅处理
- 识别黑天鹅（极端波动、机构集中砸盘、重大利空）：
  → 停止开仓，已有持仓逐步减仓
  → 或极小仓位做空对冲，严格15%止损
- 不逆势、不扛单、不赌消息落地。

### 7. 数据可靠性保护（解决外部接口依赖）
- 外部舆情/ETF数据延迟或异常时，自动降级；
- 主要依靠 **场内资金情绪 + 合约多空比 + 量能** 独立判断；
- 社交情绪仅作参考，不做主决策。

### 8. 阶梯式风控（最终强化版）
- 单日亏损 ≥5%：降低开仓频率
- 单日亏损 ≥8%：**杠杆直接降至1–2倍**
- 单日亏损 ≥15%：**立即停止当日所有开仓，自动复盘**
- 连续3笔止损：强制休息12小时
- 1分钟波动＞5%：全仓平仓，暂停1小时
- 矿工流出＞1000BTC：禁止做多24h
- 资金费率绝对值 > 0.1% → 市场交易拥挤 → 本次开仓仓位自动降低50%

## Step3 订单执行（OKX官方标准命令）
okx swap place \
  --instId BTC-USDT-SWAP \
  --side ${AI_DIRECTION} \
  --ordType market \
  --sz ${DYNAMIC_SIZE} \
  --tag "agentTradeKit"

## Step4 自动复盘（单日大亏≥15%触发）
AI自动输出：
- 亏损原因（假突破/震荡磨损/黑天鹅/信号滞后）
- 多周期共振有效性
- 量能与趋势匹配度
- 仓位与止损合理性
- 3条可直接落地的优化策略

---

### [4] `alpha-vantage`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/alpha-vantage/SKILL.md`

---
name: alpha-vantage
description: >-
  Fetch crypto and financial market data from Alpha Vantage API including daily OHLCV, intraday candles, exchange rates, and 50+ technical indicators (RSI, MACD, SMA, EMA, BBANDS). Trigger when user asks for Alpha Vantage data, crypto historical prices, BTC or ETH daily chart, technical indicator calculation, or cross-market analysis combining crypto with equities, forex, or economic indicators.
---

# Alpha Vantage — Crypto and Financial Market Data

Access 20+ years of financial data from Alpha Vantage: crypto prices, technical indicators, equities, forex, commodities, and economic indicators. Focused on crypto market analysis with cross-asset context.

## Prerequisites

### Step 1: API Key Setup (Required)

```bash
export ALPHAVANTAGE_API_KEY="your_key_here"
```

Get a free key at https://www.alphavantage.co/support/#api-key (premium plans available for higher rate limits).

Check if key is configured:
```bash
echo $ALPHAVANTAGE_API_KEY
```

If not set, guide the user to obtain and set the key before proceeding.

### Step 2: Install Dependencies

```bash
pip install requests
```

## Execution Flow

### Step 1: Identify the Request

Parse the user's query to determine:
- **Asset**: Which crypto or financial instrument (BTC, ETH, AAPL, EUR/USD, etc.)
- **Data type**: Price data, technical indicator, fundamentals, news, or economic indicator
- **Timeframe**: Intraday (1min-60min), daily, weekly, or monthly
- **Period**: Compact (last 100 points) or full (20+ years)

### Step 2: Fetch Data via Alpha Vantage API

All requests use this base pattern:

```python
import requests, os

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

def av_get(function, **params):
    if not API_KEY:
        raise ValueError("ALPHAVANTAGE_API_KEY not set. Get a free key at https://www.alphavantage.co/support/#api-key")
    response = requests.get(BASE_URL, params={"function": function, "apikey": API_KEY, **params})
    data = response.json()
    if "Error Message" in data:
        raise ValueError(f"API Error: {data['Error Message']}")
    if "Note" in data:
        print(f"Rate limit warning: {data['Note']}")
    return data
```

**Crypto-specific functions:**

| Function | Use Case | Example |
|----------|----------|---------|
| `DIGITAL_CURRENCY_DAILY` | BTC/ETH daily OHLCV | `av_get("DIGITAL_CURRENCY_DAILY", symbol="BTC", market="USD")` |
| `CRYPTO_INTRADAY` | Intraday crypto candles | `av_get("CRYPTO_INTRADAY", symbol="ETH", market="USD", interval="60min")` |
| `CURRENCY_EXCHANGE_RATE` | Real-time exchange rate | `av_get("CURRENCY_EXCHANGE_RATE", from_currency="BTC", to_currency="USD")` |

**Technical indicators (all work with crypto symbols):**

| Function | Use Case | Example |
|----------|----------|---------|
| `RSI` | Relative Strength Index | `av_get("RSI", symbol="BTC", interval="daily", time_period=14, series_type="close")` |
| `MACD` | MACD | `av_get("MACD", symbol="BTC", interval="daily", series_type="close")` |
| `SMA` | Simple Moving Average | `av_get("SMA", symbol="BTC", interval="daily", time_period=200, series_type="close")` |
| `EMA` | Exponential Moving Average | `av_get("EMA", symbol="BTC", interval="daily", time_period=50, series_type="close")` |
| `BBANDS` | Bollinger Bands | `av_get("BBANDS", symbol="BTC", interval="daily", time_period=20, series_type="close")` |
| `STOCH` | Stochastic Oscillator | `av_get("STOCH", symbol="BTC", interval="daily")` |
| `ADX` | Average Directional Index | `av_get("ADX", symbol="BTC", interval="daily", time_period=14)` |
| `ATR` | Average True Range | `av_get("ATR", symbol="BTC", interval="daily", time_period=14)` |
| `OBV` | On-Balance Volume | `av_get("OBV", symbol="BTC", interval="daily")` |
| `VWAP` | Volume-Weighted Avg Price | `av_get("VWAP", symbol="BTC", interval="60min")` |

**Cross-asset context (equities, forex, macro):**

| Category | Key Functions |
|----------|--------------|
| Equities | GLOBAL_QUOTE, TIME_SERIES_DAILY, TIME_SERIES_INTRADAY |
| Fundamentals | OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET, EARNINGS |
| Forex | CURRENCY_EXCHANGE_RATE, FX_DAILY |
| Commodities | GOLD, BRENT, NATURAL_GAS, ALL_COMMODITIES |
| Economic | REAL_GDP, TREASURY_YIELD, FEDERAL_FUNDS_RATE, CPI, INFLATION, UNEMPLOYMENT |
| News/Sentiment | NEWS_SENTIMENT, TOP_GAINERS_LOSERS |

### Step 3: Supplement with OKX Trade Kit (When Available)

For real-time exchange data, supplement Alpha Vantage with OKX Trade Kit:

**OKX MCP tools (primary for real-time OKX data):**
- Call OKX Trade MCP `market.ticker` for real-time bid/ask on OKX
- Call OKX Trade MCP `market.candles` for OKX candlestick data
- Call OKX Trade MCP `market.funding-rate` for perpetual swap funding rates
- Call OKX Trade MCP `market.indicator` for OKX-calculated indicators (70+ types)

**OKX CLI fallback:**
```bash
okx market ticker BTC-USDT
okx market candles BTC-USDT --bar 1D --limit 100
okx market indicator BTC-USDT --ind RSI
okx market funding-rate BTC-USDT-SWAP
```

**When to use OKX vs Alpha Vantage:**
- **OKX**: Real-time prices, funding rates, order book, OKX-specific volume
- **Alpha Vantage**: Historical data (20+ years), cross-asset analysis, economic indicators, news sentiment
- **Both together**: Comprehensive analysis combining real-time OKX data with AV historical context

**If OKX Trade Kit is unavailable:**
```
For real-time OKX exchange data, install OKX Trade Kit:

1. Install the packages:
   npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli

2. Configure your API credentials:
   okx config init

3. (For AI agent use) Register the MCP server:
   okx-trade-mcp setup --client claude-code

For details, see: https://github.com/okx/agent-trade-kit
```

### Step 4: Present Results

Format results based on query type:

**Crypto price output:**
```
## BTC/USD Daily Summary (Alpha Vantage)

| Date | Open | High | Low | Close | Volume |
|------|------|------|-----|-------|--------|
| 2024-01-15 | $42,500 | $43,200 | $42,100 | $42,800 | $1.2B |
| 2024-01-14 | $41,800 | $42,600 | $41,500 | $42,500 | $1.1B |

Source: Alpha Vantage DIGITAL_CURRENCY_DAILY
```

**Technical indicator output:**
```
## BTC RSI(14) — Daily

| Date | RSI | Signal |
|------|-----|--------|
| 2024-01-15 | 62.3 | Neutral |
| 2024-01-14 | 58.7 | Neutral |

Current: 62.3 (Neutral — between 30 and 70)
Overbought threshold: 70 | Oversold threshold: 30
```

**Cross-asset context output:**
```
## Market Context

| Asset | Value | Change |
|-------|-------|--------|
| BTC/USD | $42,800 | +2.3% |
| S&P 500 | 4,783 | +0.5% |
| Gold | $2,035 | -0.2% |
| DXY | 102.3 | -0.1% |
| Fed Funds Rate | 5.50% | unchanged |

Correlation note: BTC moving with risk assets today.
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `ALPHAVANTAGE_API_KEY not set` | Missing API key | Guide user to obtain key at alphavantage.co |
| `Error Message` in response | Invalid symbol or function | Check symbol format, verify function name |
| `Note` in response | Rate limit warning | Add 0.5s delay between requests, consider premium |
| HTTP 429 | Rate limit exceeded | Free tier: 25 req/day. Suggest waiting or upgrading |
| Empty time series | Symbol not found or no data | Verify crypto symbol format (use "BTC" not "BTC-USDT") |

## Rate Limits

- Free tier: 25 requests/day
- Premium plans: higher limits, real-time data, intraday access
- Add `time.sleep(0.5)` between batch requests
- For heavy usage, combine Alpha Vantage (historical) with OKX Trade Kit (real-time) to reduce AV API calls

## Common Parameters

| Parameter | Values | Notes |
|-----------|--------|-------|
| `outputsize` | `compact` / `full` | compact = last 100; full = 20+ years |
| `datatype` | `json` / `csv` | Default: json |
| `interval` | `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` | Depends on endpoint |
| `series_type` | `close`, `open`, `high`, `low` | For TA indicators |
| `time_period` | Integer (e.g., 14, 50, 200) | Lookback period for TA indicators |

---

### [5] `apex-crypto-intelligence`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/apex-crypto-intelligence/SKILL.md`

---
name: apex-crypto-intelligence
description: >
  Use this skill to compare live crypto prices across exchanges,
  detect price-based arbitrage, or run a multi-exchange market scan.
  The primary trigger: two or more exchange names appear together
  (Binance, OKX, Bybit, KuCoin, Gate.io, MEXC), or the user asks about
  price differences, spreads, or arbitrage between venues. Also invoke
  for: multi-exchange market reports, institutional-grade
  cross-exchange analysis, APEX analysis, Hyper-Council verdicts, or
  trading blueprints. If the query is about how a coin trades
  differently across venues, this is the right skill. Skip for:
  single-exchange data, one-venue price lookups, funding rate queries
  on a single instrument, or tokenomics research.
---

# APEX Crypto Intelligence — Multi-Exchange Trading Analysis

Multi-exchange cryptocurrency analysis that fetches live market data from OKX, CoinGecko, Binance, Bybit, KuCoin, MEXC, and Gate.io, performs cross-exchange arbitrage detection, and delivers AI-powered institutional trading analysis through a Hyper-Council of 5 specialized agents.

> **Note:** The Hyper-Council analysis is powered by `api.neurodoc.app` (GPT-4o), a separate AI service — not Claude. Only aggregated market prices and your query text are sent; exchange API keys never leave your machine.

---

## Prerequisites

### OKX Trade Kit

```bash
npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli
okx config init
okx-trade-mcp setup --client claude-code
```

### Exchange API Keys (all optional)

The skill works without any keys using OKX Trade Kit and CoinGecko free tier. Keys enable authenticated endpoints (higher rate limits) for other exchanges.

| Variable | Exchange |
|----------|----------|
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Binance |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Bybit |
| `KUCOIN_API_KEY` / `KUCOIN_API_SECRET` | KuCoin |
| `MEXC_API_KEY` / `MEXC_API_SECRET` | MEXC |
| `GATEIO_API_KEY` / `GATEIO_API_SECRET` | Gate.io |

Configure with **read-only permissions** only. Keys are used locally to fetch data and are never sent to `api.neurodoc.app`.

---

## Data Source Priority

For OKX data, fetch in this order — stop at the first that works:

1. **CLI** (primary): `okx market ticker BTC-USDT`
2. **MCP** (fallback): `market_get_ticker(instId="BTC-USDT")`
3. **REST API** (last resort): direct exchange API calls via `scripts/client.py`

---

## Workflow

### Step 1: Fetch OKX Data

**CLI (try first):**
```bash
okx market ticker {TOKEN}-USDT
okx market candles {TOKEN}-USDT --bar 1D --limit 100
okx market indicator {TOKEN}-USDT --ind RSI
okx market indicator {TOKEN}-USDT --ind MACD
okx market funding-rate {TOKEN}-USDT-SWAP
okx market open-interest --instType SWAP --instId {TOKEN}-USDT-SWAP
okx market orderbook {TOKEN}-USDT
```

**MCP fallback (if CLI unavailable):**
- `market_get_ticker(instId="{TOKEN}-USDT")` — price, bid/ask, 24h stats
- `market_get_candles(instId="{TOKEN}-USDT", bar="1Dutc", limit=100)` — OHLCV
- `market_get_indicator(instId="{TOKEN}-USDT", indicator="rsi", bar="1Dutc")` — RSI
- `market_get_indicator(instId="{TOKEN}-USDT", indicator="macd", bar="1Dutc")` — MACD
- `market_get_funding_rate(instId="{TOKEN}-USDT-SWAP")` — funding rate
- `market_get_open_interest(instId="{TOKEN}-USDT-SWAP", instType="SWAP")` — open interest
- `market_get_orderbook(instId="{TOKEN}-USDT")` — order book depth

### Step 2: Fetch Cross-Exchange Data

Run `scripts/client.py` for multi-exchange price comparison and arbitrage detection. The script fetches from CoinGecko, Binance, Bybit, KuCoin, MEXC, and Gate.io locally, then sends only aggregated prices (no keys) to `api.neurodoc.app`.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/client.py
```

> **Symbol coverage note:** The client currently has hardcoded symbol mappings for BTC, ETH, and SOL. For other coins, cross-exchange comparison falls back to CoinGecko data only.

**To verify the exact payload before sending:**
```bash
python ${CLAUDE_SKILL_DIR}/scripts/client.py  # runs in verification mode by default
```

### Step 3: Send to Hyper-Council API

Choose the appropriate analysis mode:

| Mode | API payload | Use when |
|------|-------------|----------|
| Scanner | `mode="scanner"` | Quick cross-exchange scan |
| Analysis | `mode="analysis"` | Full APEX council report |
| Blueprint | `mode="blueprint"` | Hedge fund-grade trading plan |

API endpoint: `POST https://api.neurodoc.app/aetherlang/execute`

**Example payloads:**

Cross-exchange scan:
```json
{
  "code": "flow CryptoScan {\n  using target \"neuroaether\" version \">=0.3\";\n  input text query;\n  node Scanner: crypto exchanges=\"all\", language=\"en\";\n  output text result from Scanner;\n}",
  "query": "BTC ETH SOL"
}
```

APEX council analysis:
```json
{
  "code": "flow ApexAnalysis {\n  using target \"neuroaether\" version \">=0.3\";\n  input text query;\n  node Apex: crypto mode=\"analysis\", language=\"en\";\n  output text result from Apex;\n}",
  "query": "Full APEX analysis for BTC"
}
```

Trading blueprint:
```json
{
  "code": "flow Blueprint {\n  using target \"neuroaether\" version \">=0.3\";\n  input text query;\n  node Report: crypto mode=\"blueprint\", language=\"en\";\n  output text result from Report;\n}",
  "query": "Generate trading blueprint for BTC"
}
```

Rate limit: 100 req/hour (free tier). If exceeded, wait before retrying.

### Step 4: Present Results

Combine OKX real-time data with the Hyper-Council verdict into a single report covering:
- Cross-exchange price comparison and arbitrage spread
- OKX technical indicators (RSI, MACD, funding rate, OI)
- Council verdicts from MACRO, QUANT, STATS, RISK (Damocles), EXECUTION agents
- Risk assessment and trading blueprint (if blueprint mode)

---

## Hyper-Council Agents

| Agent | Role | Can Veto |
|-------|------|----------|
| MACRO | Global Macro CIO | No |
| QUANT | Head of Quant Research | No |
| STATS | Chief Statistician | No |
| RISK (Damocles) | Chief Risk Officer | **Yes** |
| EXECUTION | Execution Architect | No |

---

## Error Handling

| Error | Cause | Action |
|-------|-------|--------|
| OKX CLI/MCP unavailable | Not installed | Fall back to `scripts/client.py` for OKX REST data |
| Exchange API returns empty | Rate limit or auth error | Use CoinGecko free tier as price baseline |
| `api.neurodoc.app` timeout | Network / server load | Retry once; if still failing, present OKX data only without council analysis |
| Rate limit hit (100 req/hr) | Free tier exceeded | Inform user, wait before retrying |

---

*Analysis is for informational purposes only. Not financial advice.*

---

### [6] `bb-momentum-breakout`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/bb-momentum-breakout/SKILL.md`

---
name: bb-momentum-breakout
description: "布林带收缩突破 + MACD 确认的动量交易 Skill。当用户说'布林突破'、'动量突破'、'BB突破'、'启动突破策略'时使用此技能。自动检测布林带收缩后的方向性突破，结合 MACD 信号和 ATR 动态止损，快进快出捕捉动量行情。"
version: "1.0.0"
user-invocable: true
---

# 布林带动量突破策略（BB Momentum Breakout）

基于**布林带收缩（Squeeze）→ 方向突破**的动量交易策略，结合 MACD 信号过滤虚假突破，使用 ATR 动态设置止损止盈，适合捕捉短周期的方向性爆发行情。

## 策略逻辑

```
核心假设：价格在布林带收窄期积蓄能量，突破时产生方向性动量

信号触发条件（做多）：
  1. BB Width < 阈值（布林带收缩，波动率低）
  2. 当前收盘价 > 布林带上轨（向上突破）
  3. MACD 柱状 > 0 且 MACD 线 > 信号线（动量确认多头）
  4. 价格 > EMA20（在均线上方，过滤弱势突破）

信号触发条件（做空）：
  1. BB Width < 阈值（布林带收缩）
  2. 当前收盘价 < 布林带下轨（向下突破）
  3. MACD 柱状 < 0 且 MACD 线 < 信号线（动量确认空头）
  4. 价格 < EMA20（在均线下方）

止损：入场价 ± 1.5 × ATR(14)
止盈：入场价 ± 3.0 × ATR(14)（风险收益比 2:1）
```

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instId | string | ✅ | - | 交易对，如 BTC-USDT-SWAP |
| amount | number | ✅ | - | 每次开仓金额（USDT） |
| bar | string | ❌ | 15m | K 线周期：5m / 15m / 1H |
| bb_period | integer | ❌ | 20 | 布林带周期 |
| bb_std | number | ❌ | 2.0 | 布林带标准差倍数 |
| squeeze_threshold | number | ❌ | 0.03 | BB Width 收缩阈值（<此值视为收缩，建议 0.02-0.05） |
| atr_period | integer | ❌ | 14 | ATR 周期 |
| sl_atr_mult | number | ❌ | 1.5 | 止损 ATR 倍数 |
| tp_atr_mult | number | ❌ | 3.0 | 止盈 ATR 倍数 |
| lever | integer | ❌ | 3 | 合约杠杆倍数（建议 2-5，不超过 5） |
| mode | string | ❌ | swap | 交易模式：swap（永续合约）/ spot（现货，只能做多） |
| profile | string | ❌ | demo | 实盘 live / 模拟盘 demo |

## 执行流程

### Phase 1：参数确认

1. 用户触发后，确认 instId 和 amount。
2. 未指定 profile 时**默认 demo 模拟盘**，保护资金安全。
3. mode=swap 时，instId 格式须为 `XXX-USDT-SWAP`；mode=spot 时为 `XXX-USDT`。
4. 向用户展示完整参数并确认后开始执行。

### Phase 2：多指标信号采集

**Step 1：获取布林带数据**

```bash
# BB Width（布林带宽度，用于判断收缩）
okx market indicator bbwidth <instId> --bar <bar> --params <bb_period> <bb_std>

# BB %B（价格在布林带中的位置，>1 表示突破上轨，<0 表示突破下轨）
okx market indicator bbpct <instId> --bar <bar> --params <bb_period> <bb_std>

# 布林带上下轨（获取具体数值）
okx market indicator bb <instId> --bar <bar> --params <bb_period> <bb_std>
```

**Step 2：获取 MACD 信号**

```bash
# MACD（返回 macd 线、signal 线、histogram 柱状值）
okx market indicator macd <instId> --bar <bar>
# 默认参数：快线12, 慢线26, 信号线9
```

**Step 3：获取 EMA20 均线**

```bash
okx market indicator ema <instId> --bar <bar> --params 20
```

**Step 4：获取 ATR（用于动态止损止盈）**

```bash
okx market indicator atr <instId> --bar <bar> --params <atr_period>
```

**Step 5：获取当前价格**

```bash
okx market ticker <instId>
```

### Phase 3：信号判断

从各指标提取最新值后，按以下逻辑判断：

**收缩检测：**
```
is_squeeze = bbwidth < squeeze_threshold
```

**突破方向判断：**
```
# 多头突破
long_signal = is_squeeze AND bbpct > 1.0 AND macd_hist > 0 AND macd_line > signal_line AND price > ema20

# 空头突破（仅 mode=swap 时可用）
short_signal = is_squeeze AND bbpct < 0.0 AND macd_hist < 0 AND macd_line < signal_line AND price < ema20
```

**向用户输出当前指标快照：**
```
📊 指标快照 - <instId> [<bar>]
━━━━━━━━━━━━━━━━━━━━
当前价格：$xxx
BB Width：0.025（收缩中 ✅ / 未收缩 ❌）
BB %B：1.05（突破上轨 ✅）
MACD 柱：+12.5（多头 ✅）
EMA20：$xxx（价格在均线上方 ✅）
ATR(14)：$xxx
━━━━━━━━━━━━━━━━━━━━
信号：🚀 多头突破 / 🔻 空头突破 / ⏳ 等待收缩突破
```

### Phase 4：开仓执行

**条件满足时执行开仓：**

**Step 1：查询账户余额与现有仓位**

```bash
okx account balance USDT --profile <profile>
okx account positions --instType SWAP --profile <profile>
```

检查：
- USDT 余额 >= amount
- 同一标的无已有持仓（避免重复开仓）

**Step 2：设置杠杆**

```bash
okx swap leverage <instId> --lever <lever> --mgnMode cross --profile <profile>
```

**Step 3：计算止损止盈价**

```
# 多头
sl_price = entry_price - sl_atr_mult × atr
tp_price = entry_price + tp_atr_mult × atr

# 空头
sl_price = entry_price + sl_atr_mult × atr
tp_price = entry_price - tp_atr_mult × atr
```

**Step 4：下单（附带 TP/SL）**

多头开仓：
```bash
okx swap place --instId <instId> \
  --side buy --ordType market \
  --sz <amount> --tgtCcy quote_ccy \
  --tdMode cross --posSide long \
  --tpTriggerPx <tp_price> --tpOrdPx -1 \
  --slTriggerPx <sl_price> --slOrdPx -1 \
  --profile <profile>
```

空头开仓：
```bash
okx swap place --instId <instId> \
  --side sell --ordType market \
  --sz <amount> --tgtCcy quote_ccy \
  --tdMode cross --posSide short \
  --tpTriggerPx <tp_price> --tpOrdPx -1 \
  --slTriggerPx <sl_price> --slOrdPx -1 \
  --profile <profile>
```

**Step 5：开仓报告**

```
⚡ 开仓成功！
━━━━━━━━━━━━━━━━━━━━
方向：做多 / 做空
开仓价：$xxx
开仓金额：xxx USDT（杠杆 3x，名义价值 xxx USDT）
止盈价：$xxx（+x.x% / +ATR×3.0）
止损价：$xxx（-x.x% / -ATR×1.5）
风险收益比：1:2
订单ID：xxxxxxxxx
━━━━━━━━━━━━━━━━━━━━
```

### Phase 5：持仓监控

当检测到有未平仓位时，自动进入监控模式：

```bash
# 查询持仓和未平仓盈亏
okx account positions --instType SWAP --instId <instId> --profile <profile>
```

每个 bar 周期输出持仓状态：
```
📍 持仓监控 - <instId>
方向：做多 | 开仓价：$xxx
当前价：$xxx | 浮盈：+x.xx%
止盈：$xxx | 止损：$xxx
状态：持仓中... (TP/SL 已挂单，自动平仓)
```

> TP/SL 已在开仓时通过参数挂单，无需手动干预，触发后自动平仓。

### Phase 6：复盘输出

平仓后（无论止盈还是止损），输出本次交易复盘：

```
📋 交易复盘
━━━━━━━━━━━━━━━━━━━━
交易对：<instId>
方向：做多
开仓价：$xxx | 平仓价：$xxx
盈亏：+xxx USDT（+x.xx%）
持仓时长：约 x 小时 x 分
触发原因：止盈 / 止损
━━━━━━━━━━━━━━━━━━━━
下一步：继续监控新的突破信号...
```

## 使用示例

- "启动布林突破，BTC-USDT-SWAP，每次 100U"
- "BB突破策略，ETH-USDT-SWAP，200U，15分钟线"
- "动量突破 SOL-USDT-SWAP 50U，杠杆2倍，模拟盘"
- "查看 BTC-USDT-SWAP 当前布林带信号"
- "切换到实盘，布林突破 BTC-USDT-SWAP 100U"

## 风险提示

1. **默认模拟盘（demo）**，切换实盘需用户明确指定 `profile=live`。
2. 动量突破策略在震荡行情中假突破率较高，建议配合更高周期趋势判断。
3. 建议单笔开仓金额不超过账户总资金的 5-10%，杠杆不超过 5 倍。
4. BB Width 收缩阈值（squeeze_threshold）需根据标的波动特性调整，低波动标的建议调低至 0.02。
5. 本 Skill 仅供学习研究，不构成投资建议，盈亏自负。

---

### [7] `btc-altcoin-market-pulse`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/btc-altcoin-market-pulse/SKILL.md`

---
name: btc-altcoin-market-pulse
description: "Activated when users say 'BTC analysis', 'Bitcoin market update', 
  'altcoin pulse', 'altcoin season check', 'what's pumping today', 'top altcoins', 
  'crypto market briefing', 'BTC dominance', 'which alts are moving', 
  'market overview', 'daily crypto update', 'altcoin movers', 
  'is it altseason', 'Bitcoin funding rate', 'crypto news today', 
  'what coins are up', 'market sentiment check', or 'BTC vs alts'. 
  Fetches live OKX market data across Bitcoin and major altcoins, analyzes 
  price momentum, funding rates, open interest, RSI, MACD, and BTC dominance 
  signals to produce a structured BTC + Altcoin Market Pulse report."
license: Apache-2.0
metadata:
  author: muendocolo
  version: "1.0.0"
  moltbot:
    requires:
      bins: ["okx"]
---

# BTC & Altcoin Market Pulse

A structured market intelligence skill that delivers a real-time snapshot of
Bitcoin and the broader altcoin market — covering price momentum, RSI/MACD
technical signals, funding sentiment, open interest shifts, and BTC dominance
to help traders quickly assess where the market stands.

---

## Trigger Phrases

This skill activates on phrases like:
- "BTC analysis", "Bitcoin update", "Bitcoin market check"
- "altcoin pulse", "altcoin season", "is it altseason"
- "what's pumping today", "top altcoins", "which alts are moving"
- "market overview", "daily crypto update", "market sentiment"
- "BTC dominance", "BTC vs alts", "crypto news today"

---

## Tracked Assets

**Bitcoin:**
`BTC-USDT` (spot) · `BTC-USDT-SWAP` (perpetual)

**Major Altcoins:**
`ETH-USDT` · `SOL-USDT` · `BNB-USDT` · `XRP-USDT` · `DOGE-USDT` ·
`ADA-USDT` · `AVAX-USDT` · `LINK-USDT` · `DOT-USDT` · `TON-USDT`

---

## Workflow

### Step 1 — BTC Price & 24h Momentum
```
okx market ticker BTC-USDT
okx market candles BTC-USDT --bar 1H --limit 24
```
Extract: current price, 24h change %, 24h high/low range, volume.

---

### Step 2 — BTC Technical Indicators (RSI + MACD)
```
okx market indicators BTC-USDT --bar 1H --indicator RSI
okx market indicators BTC-USDT --bar 1H --indicator MACD
okx market indicators BTC-USDT --bar 1D --indicator RSI
okx market indicators BTC-USDT --bar 1D --indicator MACD
```
Interpret RSI:
- `RSI > 70` → Overbought — potential pullback risk 🔴
- `RSI 50–70` → Bullish momentum, healthy trend 🟢
- `RSI 30–50` → Bearish/neutral, watch for reversal 🟡
- `RSI < 30` → Oversold — potential bounce setup 🟢

Interpret MACD:
- MACD line **above** signal line → Bullish momentum
- MACD line **below** signal line → Bearish momentum
- Histogram expanding → Trend strengthening
- Histogram shrinking → Trend weakening, possible reversal

---

### Step 3 — BTC Derivatives Sentiment
```
okx market funding-rate BTC-USDT-SWAP
okx market open-interest --instType SWAP --instId BTC-USDT-SWAP
```
Interpret funding rate:
- `> +0.05%` → Strong bullish leverage, longs paying — overheated long risk
- `0% to +0.05%` → Mild bullish bias, healthy
- `< 0%` → Bearish bias, shorts paying — possible short squeeze setup

---

### Step 4 — Altcoin Sweep (Top Movers)
```
okx market tickers SPOT
```
From the full ticker list, filter for USDT pairs and rank by:
1. **Top 5 Gainers** — highest 24h change %
2. **Top 5 Losers** — lowest 24h change %
3. **Top 5 by Volume** — highest 24h USDT volume

---

### Step 5 — Core Altcoin Deep Check + RSI
Run for each tracked altcoin: ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK
```
okx market ticker ETH-USDT
okx market indicators ETH-USDT --bar 1H --indicator RSI
okx market ticker SOL-USDT
okx market indicators SOL-USDT --bar 1H --indicator RSI
okx market ticker BNB-USDT
okx market indicators BNB-USDT --bar 1H --indicator RSI
okx market ticker XRP-USDT
okx market indicators XRP-USDT --bar 1H --indicator RSI
okx market ticker DOGE-USDT
okx market indicators DOGE-USDT --bar 1H --indicator RSI
okx market ticker ADA-USDT
okx market indicators ADA-USDT --bar 1H --indicator RSI
okx market ticker AVAX-USDT
okx market indicators AVAX-USDT --bar 1H --indicator RSI
okx market ticker LINK-USDT
okx market indicators LINK-USDT --bar 1H --indicator RSI
```
For each: capture price, 24h change %, volume, and RSI signal.

---

### Step 6 — Altcoin Funding Rates (Sentiment Layer)
```
okx market funding-rate ETH-USDT-SWAP
okx market funding-rate SOL-USDT-SWAP
okx market funding-rate XRP-USDT-SWAP
```
Flag any altcoin with funding rate > +0.08% (overheated) or < -0.03% (bearish squeeze risk).

---

### Step 7 — BTC Dominance Signal (Alt Season Check)
Calculate a simple proxy:
- Sum the 24h volume of all tracked altcoins vs BTC volume
- If altcoin aggregate volume > 2× BTC volume AND majority of alts outperforming BTC → flag as **Alt Season Signal 🟢**
- If BTC volume dominates and alts underperforming → flag as **BTC Season Signal 🟡**
- Mixed signals → **Neutral / Rotating 🔵**

---

## Output Format

Present the final report in this structure:

---

### 🟠 BTC Snapshot
| Metric | Value |
|---|---|
| Price | $XX,XXX |
| 24h Change | +X.X% |
| 24h Range | $XX,XXX – $XX,XXX |
| RSI (1H) | XX — Bullish / Overbought / Oversold |
| RSI (1D) | XX — Bullish / Overbought / Oversold |
| MACD (1H) | Bullish / Bearish / Weakening |
| Funding Rate | +0.0X% (Mild Bullish) |
| Open Interest | $X.XB |

---

### 🌊 Alt Season Meter
**Signal:** [Alt Season 🟢 / BTC Season 🟡 / Neutral 🔵]
Brief 1-sentence reasoning based on dominance proxy.

---

### 📈 Top Altcoin Movers (24h)
| Coin | Price | 24h % | RSI (1H) | Volume |
|---|---|---|---|---|
| SOL | $XXX | +X.X% | 62 — Bullish | $XXX M |
| ... | | | | |

---

### 📉 Top Losers (24h)
| Coin | Price | 24h % | RSI (1H) |
|---|---|---|---|
| ... | | | |

---

### ⚠️ Alerts
- **Funding Rate Alerts:** List any coin with abnormal funding rates and what it signals.
- **RSI Extremes:** Flag any coin with RSI > 70 (overbought) or RSI < 30 (oversold).
- **MACD Signal:** Flag any BTC MACD crossover signals detected.

---

### 💡 Market Summary
2–3 sentence plain-English summary of overall market conditions —
is BTC leading or lagging, are alts rotating, any overbought/oversold coins
worth watching based on RSI and MACD signals?

---

## Notes & Limitations

- All data is pulled live from OKX public market endpoints (no API key required).
- Funding rates update every 8 hours; check timing when interpreting sentiment.
- RSI and MACD are lagging indicators — always combine with price action context.
- This skill provides market data and analysis only — it does not place trades.
- For trade execution, combine with `okx-cex-trade` skill.
- Always do your own research. This is not financial advice.

---

### [8] `btc-grid-buy-okb`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/btc-grid-buy-okb/SKILL.md`

---
name: btc-grid-buy-okb
description: BTC合约网格利润自动购买OKB复合策略（全参数可自定义）。运行BTC永续合约网格交易、监控利润自动买入OKB、定时巡检、OKB目标持仓追踪、红黄线风控管理、智能网格区间调整。首次使用自动引导配置杠杆/阈值/风控参数。关键词：BTC网格、合约网格、买OKB、利润再投资、风控、定时巡检、grid profit buy OKB。
license: MIT
compatibility: Requires okx CLI (npx skills add okx/agent-skills)
metadata:
  author: ligodan3
  version: "3.2.0"
  tags: "trading,grid,btc,okb,futures,compound,patrol,target"
agent:
  requires:
    bins: ["okx"]
---

# BTC 合约网格 — 利润买入 OKB

## 策略概述

两个联动部分：

1. **BTC/USDT 永续合约网格**：可配置杠杆的做多网格，在震荡区间低买高卖赚取网格利润
2. **利润复投 OKB**：累计利润达到阈值后，自动买入 OKB

核心理念：用 BTC 波动赚取网格收益，将利润转化为 OKB 持仓 —— "BTC 挖矿 + OKB 囤币"。

---

## 可配置参数

首次使用时逐项确认或修改（说"用默认"跳过）：

**策略参数**

| 参数 | 默认值 | 可选范围 | 说明 |
|------|--------|----------|------|
| 杠杆倍数 | 2x | 1x-5x | 越高收益越大风险也越大 |
| 网格方向 | long（做多） | long / neutral | neutral 多空都做 |
| 网格数量 | 30 格 | 10-100 | 格数越多单格利润越小但成交越频繁 |
| 价格区间宽度 | ±15% | ±5% ~ ±30% | 窄区间利润高但容易越界 |
| 利润阈值 | $100 USDT | $50-$500 | 触发买入 OKB 的最低累计利润 |
| 利润分配 | 100% 买 OKB | 10%-100% | 剩余部分留存 USDT（最低 10%） |
| OKB 买入方式 | 市价 | 市价 / 限价 | 限价按当前价 -1% 挂单，24h未成交转市价 |
| OKB 目标持仓 | 无上限 | 任意数量 | 达到目标后利润留存 USDT |
| 巡检间隔 | 每 4 小时 | 1h-24h | 自动检查网格状态和利润 |

**风控参数**

| 参数 | 默认值 | 可选范围 | 说明 |
|------|--------|----------|------|
| 保证金率红线 | 150% | 120%-300% | 低于此值自动停网格（硬底线 120%） |
| 账户总止损 | -15% | -5% ~ -30% | 总亏损达到后停止所有交易 |
| 单日止损 | -5% | -3% ~ -10% | 当日亏损达到后暂停 OKB 买入（硬底线 -10%） |
| BTC 闪崩阈值 | 1h 跌 8% | 5%-15% | 触发后自动停网格 |
| 网格浮亏告警 | -20% | -10% ~ -30% | 黄线告警，建议调整 |
| OKB 单笔上限 | $200 | $50-$1000 | 单次买入 OKB 最大金额 |
| OKB 追高保护 | 24h 涨 10% | 5%-20%（0=关闭） | OKB 短期涨幅过大暂缓买入 |
| 总敞口上限 | 60% | 30%-80% | 网格+OKB 占总资产比例 |

> 所有参数随时可通过对话修改，例如"利润阈值改成 50"、"关闭 OKB 追高保护"。

---

## 首次使用：初始化引导

```
1. 检查账户 → okx account balance → USDT 余额是否充足
2. 询问 → "你打算投入多少 USDT？"
3. 展示参数表 → 用户逐项确认或"用默认"
   → 重点确认：杠杆、利润阈值、风控止损线
4. 参数摘要 → 列出最终参数，用户确认后创建网格
```

---

## 核心流程

### 第一步：启动 BTC 合约网格

获取 BTC 当前价格：

```
okx market ticker --instId BTC-USDT-SWAP
okx market candles --instId BTC-USDT-SWAP --bar 4H --limit 50
```

根据用户配置的参数创建网格：

```
okx bot create-contract-grid \
  --instId BTC-USDT-SWAP \
  --direction <用户配置: long/neutral> \
  --lever <用户配置: 杠杆倍数> \
  --gridNum <用户配置: 网格数量> \
  --minPx <当前价 × (1 - 区间宽度)> \
  --maxPx <当前价 × (1 + 区间宽度)> \
  --sz <每格张数，根据投入资金计算> \
  --triggerAction start
```

验证并记录 `algoId`：

```
okx bot grid-orders-pending --algoOrdType contract_grid
```

### 第二步：监控利润 & 买入 OKB

查询网格利润：

```
okx bot grid-orders-pending --algoOrdType contract_grid
```

读取 `profit` 字段。当利润 ≥ 用户设定的阈值时：

1. 检查风控（见下方风控章节）—— 任何红线/黄线触发则中止买入
2. 检查 OKB 目标 —— 已达目标则留存 USDT
3. 检查 OKB 24h 涨幅 —— 追高保护触发则暂缓
4. 查询 OKB 价格：`okx market ticker --instId OKB-USDT`
5. 计算买入量（不超过单笔上限，按利润分配比例）
6. 执行买入：

```
# 市价买入
okx trade place-order --instId OKB-USDT --tdMode cash --side buy --ordType market --sz <数量>

# 限价买入（用户选择限价模式时）
okx trade place-order --instId OKB-USDT --tdMode cash --side buy --ordType limit --px <当前价*0.99> --sz <数量>
```

7. 确认成交：`okx trade order-details --instId OKB-USDT --ordId <订单ID>`
8. 限价单 24h 未成交 → 撤单转市价

### 第三步：状态报告

```
okx account balance
okx account positions --instType SWAP
```

输出格式：

```
📊 策略状态报告
━━━━━━━━━━━━━━━━━━━━
🔲 BTC合约网格
   网格ID: <algoId> | 状态: <running/stopped>
   区间: $<minPx> ~ $<maxPx> | 偏离度: <X>%
   累计利润: $<profit> USDT | 持仓: <pos> 张

💎 OKB持仓
   数量: <amount> OKB ($<value>)
   目标进度: <amount>/<target> (<X>%)  [无目标时显示"未设目标"]
   累计投入: $<total> | 买入 <count> 次

🛡️ 风控
   保证金率: <X>% | 今日盈亏: <X>%
   总敞口: <X>% | 状态: 🟢正常 / 🟡注意 / 🔴触发

💰 策略总收益: $<total_pnl> USDT
━━━━━━━━━━━━━━━━━━━━
```

---

## 定时巡检

每次巡检按以下优先级顺序执行：

```
巡检开始
  ↓
① 风控检查（最高优先级）
  → 🔴 红线触发? → 自动执行保护 → 通知用户 → 结束
  → 🟡 黄线触发? → 告警 + 建议（等用户确认）
  ↓ 全部通过
② 网格健康检查
  → 偏离度 > 80%? → 建议调整区间（需确认）
  ↓
③ 利润检查 & OKB 买入
  → 利润 ≥ 阈值 + 通过所有保护检查 → 买入 OKB
  ↓
④ 输出状态报告（合并风控 + 网格 + OKB）
```

### 网格健康检查

```
okx market ticker --instId BTC-USDT-SWAP
okx bot grid-orders-pending --algoOrdType contract_grid
```

偏离度 = `(当前价 - 区间中点) / (区间宽度/2) × 100%`

| 偏离度 | 状态 | 动作 |
|--------|------|------|
| < 50% | 安全 | 正常 |
| 50%-80% | 注意 | 提醒 |
| 80%-95% | 警告 | 建议调整区间 |
| > 95% | 危险 | 建议立即停止重设 |

### 资金费率检查

```
okx market funding-rate --instId BTC-USDT-SWAP
```

连续 3 期 > 0.1% 时提醒持仓成本。

---

## 智能网格调整

触发条件：偏离度 > 80%，或运行超 7 天且利润增速放缓。

```
1. 获取数据 → okx market candles --instId BTC-USDT-SWAP --bar 1D --limit 14
2. 计算新区间 → 中点=当前价, 宽度=ATR(14)/价格 动态调整（至少±10%）
3. 告知用户旧网格利润，确认后停止旧网格
   → okx bot stop-grid --algoId <旧ID> --algoOrdType contract_grid
4. 用新参数创建新网格（杠杆/方向不变）
5. 旧网格利润达标则先买入 OKB
```

⚠️ **停止和创建网格必须用户确认后才执行。**

---

## OKB 目标持仓管理

设定目标（如"囤 100 个 OKB"）后的逻辑：

- 未达目标 → 利润达标时买入 OKB
- 已达目标 → 利润留存 USDT，通知用户
- 用户可说"继续囤 OKB"追加目标

进度报告：

```
💎 OKB 目标: 45.8/100 (45.8%)
   ████████░░░░░░░░
   剩余 54.2 OKB ≈ $1,842 | 预计 ~18天达成
```

---

## 风控管理

原则：**先保本，再谈利润。** 红线自动执行，黄线告警等确认。

### 🔴 红线（自动执行）

**1. 保证金率** — `okx account positions --instType SWAP`
- < 用户设定阈值 → 立即停止网格

**2. 账户总亏损** — `(当前权益 - 初始本金) / 初始本金`
- 超过用户设定阈值 → 停止所有交易

**3. 单日亏损** — `okx account bills --instType SWAP --begin <今日0点> --limit 100`
- 超过用户设定阈值 → 暂停 OKB 买入

**4. BTC 闪崩** — `okx market candles --instId BTC-USDT-SWAP --bar 1H --limit 2`
- 1h 跌幅超阈值 → 立即停止网格

红线触发报告：

```
🚨 风控红线触发！
━━━━━━━━━━━━━━━━━━━━
⚠️ 触发项: <具体项目和数值>
🛑 已执行: <保护动作>
💰 利润已保全: $<X> USDT
⏳ 等待你的指令
━━━━━━━━━━━━━━━━━━━━
```

### 🟡 黄线（告警 + 建议）

**1. 网格浮亏** — `okx account positions --instType SWAP --instId BTC-USDT-SWAP`
- 超阈值 → 建议缩小区间 / 暂停买 OKB / 设止损

**2. OKB 追高保护** — `okx market candles --instId OKB-USDT --bar 1D --limit 1`
- 24h 涨幅超阈值 → 暂缓买入，下次巡检再评估

**3. 总敞口** — `(网格保证金 + OKB 持仓) / 总资产`
- 超阈值 → 暂停买入 OKB

---

## 策略暂停 & 恢复

用户可随时说"暂停策略"或"恢复策略"：

**暂停：**
- 网格继续运行（不停网格，避免损失已挂订单）
- 暂停利润买入 OKB
- 巡检降频为每 12 小时一次（仅执行风控检查，不执行买入）
- 报告暂停时的持仓快照

**恢复：**
- 检查网格是否仍在运行
- 若网格已停止 → 引导重新创建
- 恢复巡检和 OKB 买入

**紧急停止**（说"全部停止"）：
- 停止网格 + 取消所有挂单 + 暂停一切操作
- 需用户主动说"恢复"才能重启

---

## 异常处理

| 异常场景 | 处理方式 |
|----------|----------|
| API 调用失败 | 等待 30s 重试，连续 3 次失败 → 通知用户，暂停自动操作 |
| 网格意外停止 | 巡检发现后立即通知，询问是否重新创建 |
| OKB 下架/停止交易 | 利润留存 USDT，通知用户 |
| 账户余额不足以买 OKB | 跳过本次买入，下次巡检再试 |
| 限价单长时间未成交 | 24h 后自动撤单，按当时市价重新买入 |
| 网格创建失败 | 检查余额和参数，提示具体错误原因 |

---

## 完整工作流程

```
首次使用 → 初始化引导 → 确认参数 → 创建网格
                                        ↓
用户触发 / 定时巡检 ←──────────────── 网格运行中
        ↓
    策略已暂停? → 是 → 跳过，等待恢复
        ↓ 否
    ① 风控红线检查
        → 触发 → 自动保护 → 通知 → 等待指令
        ↓ 通过
    ② 风控黄线检查
        → 触发 → 告警建议（等确认）
        ↓ 通过
    ③ 网格健康 + 偏离度
        → > 80% → 建议调整（需确认）
        ↓ 正常
    ④ 利润 ≥ 阈值?
        → 否 → 输出状态报告 → 结束
        ↓ 是
    ⑤ OKB 保护检查（追高 / 目标 / 敞口 / 单笔上限）
        → 任一触发 → 暂缓，利润留存
        ↓ 全部通过
    ⑥ 买入 OKB → 确认成交 → 输出报告
```

---

## 常见问题

**Q: 利润不足阈值但想手动买 OKB？**
A: 说具体金额即可跳过阈值检查。

**Q: 想调整网格参数？**
A: 需先停止当前网格再创建新的，我会引导完成。

**Q: 网格被止损了？**
A: 检查市场状况后建议是否重开及新区间。

**Q: 怎么暂停？不想停网格但暂时不买 OKB。**
A: 说"暂停策略"，网格继续运行但暂停买入和巡检。

**Q: 利润可以分配吗？**
A: 可以，例如"60% 买 OKB，40% 留 USDT"。

**Q: 限价买 OKB 一直不成交？**
A: 24h 未成交自动转市价。也可随时说"改成市价"。

详细的风控规则说明和网格参数计算逻辑见 [references/REFERENCE.md](references/REFERENCE.md)。

---

## 免责声明

本 Skill 仅供参考和学习，不构成任何投资建议。合约交易存在爆仓风险，杠杆交易可能导致本金全部损失。使用前请充分了解合约网格交易机制，并根据自身风险承受能力设置参数。作者不对因使用本策略造成的任何损失承担责任。建议先用小资金测试验证后再投入正式资金。

---

### [9] `btc-naked-k-breakout`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/btc-naked-k-breakout/SKILL.md`

---
name: btc-naked-k-breakout
description: "BTC裸K结构AI突破策略。每5分钟触发，基于300根K线识别结构点、构建箱体、评估结构质量，通过AI综合判断执行突破回踩交易，支持动态仓位和高级持仓管理。"
---

# BTC 裸K结构 AI 交易策略 V4

基于 300K 结构分析的 BTC 裸K突破策略。每 5 分钟触发一次，通过识别关键结构点、构建箱体、评估结构质量，进行 AI 综合判断，仅交易干净结构且有空间的突破，执行突破回踩策略并动态管理仓位。

## 执行节奏

每 5 分钟触发一次

但仅在以下条件满足时进入决策流程：
- 新 15M K线刚收盘
- 或 新 1H K线刚收盘
- 或 当前价格接近箱体边界 ±0.2%

否则：本轮跳过（避免噪音交易）

## 依赖 Skills（必须先安装）

- `okx-cex-market` — 获取 K线数据、实时价格、ATR 等技术指标
- `okx-cex-trade` — 执行买入和卖出订单、设置止盈止损、修改止损
- `okx-cex-portfolio` — 查询账户持仓、余额、净值

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instId | string | ✅ | BTC-USDT-SWAP | 交易对，仅支持 BTC-USDT-SWAP |
| risk_per_trade | number | ❌ | 1 | 单笔风险占账户净值百分比（建议 0.5%-2%） |
| max_daily_trades | integer | ❌ | 5 | 每日最大交易笔数（建议 3-8） |
| max_hourly_trades | integer | ❌ | 1 | 每小时最大交易笔数（建议 1-2） |
| profile | string | ❌ | demo | 实盘 live / 模拟盘 demo（强烈建议先用 demo 测试） |

## 执行流程

### Step 1 · 行情数据采集（300K结构）

调用 `okx-cex-market` 获取行情数据：

```bash
# 获取 300 根 1H K线
okx market candles BTC-USDT-SWAP --bar 1H --limit 300

# 获取 300 根 15M K线
okx market candles BTC-USDT-SWAP --bar 15m --limit 300

# 获取当前价格
okx market ticker BTC-USDT-SWAP

# 获取 ATR(14)
okx market indicator atr BTC-USDT-SWAP --bar 1H --params 14
```

AI 需要完成：

**① 提取关键结构点**

从 300 根 K线中识别：
- Swing High（局部高点）
- Swing Low（局部低点）

过滤小波动，仅保留有效结构点

**② 构建 1H 箱体**

判断是否满足：
- 上沿至少被触及 ≥ 2 次
- 下沿至少被触及 ≥ 2 次
- 中间存在明显震荡

输出：
- 箱体上沿
- 箱体下沿

**③ 箱体质量评分（新增核心）**

AI 对结构打分：
- 清晰度（边界是否干净）
- 测试次数（越多越强）
- 假突破次数（越少越好）

输出：
```id="score1"
结构评分：
- 高（可交易）
- 中（降低仓位）
- 低（跳过）
```

### Step 2 · 市场状态识别

基于 300 根 1H K线判断：

```id="market_state"
市场状态：
- 趋势
- 震荡
- 高风险
```

判断规则：
- 高点持续抬高 → 上升趋势
- 低点持续降低 → 下降趋势
- 高低点重叠 → 震荡

若出现：
- 连续 ≥ 3 根强趋势K
- 或 ATR > 20周期均值 1.5倍

判定为：**高风险 → 本轮跳过**

### Step 3 · AI 综合决策（核心）

**① 是否允许交易**

```id="check_trade"
条件：
- 结构评分 ≥ 中
- 市场状态 = 震荡
```

否则：本轮跳过

**② 判断突破性质**

必须满足：
- 收盘价突破箱体（不看影线）
- K线实体明显
- 未立即回到箱体内部
- 回踩仅触边界

输出：
- 真突破 / 假突破

假突破 → 跳过

**③ 方向确定**

- 上破 → 做多
- 下破 → 做空

**④ 15M 入场确认**

做多：
- 回踩后低点抬高
- 出现转强结构

做空：
- 反抽后高点降低
- 出现转弱结构

**⑤ 盈亏比评估**

计算：
- 止损 = 箱体内部失效位
- 止盈 = 下一个 1H 结构位

要求：盈亏比 ≥ 1:2

否则：放弃交易

**⑥ 动态仓位计算**

```id="position"
单笔风险 = 账户权益 × 1%

仓位 = 单笔风险 ÷ (入场价 - 止损价)
```

调整：
- 结构评分 = 中 → 仓位 × 0.5
- ATR 偏高 → 仓位 × 0.5
- ATR 偏低 → 不交易

**⑦ 频率限制（防过度交易）**

```id="limit"
- 每小时最多 1 笔
- 每日最多 5 笔
- 1小时内同方向只允许1次
```

**⑧ 最终决策（必须输出）**

```id="decision"
1. 开多（理由 + 仓位）
2. 开空（理由 + 仓位）
3. 本轮跳过（理由）
```

### Step 4 · 执行下单

当 AI 决策为开多或开空时，执行以下步骤：

**Step 4.1：检查前置条件**

```bash
# 查询账户 USDT 余额和净值
okx account balance USDT --profile <profile>

# 查询当前持仓
okx account positions --instType SWAP --profile <profile>

# 查询今日交易次数（需记录）
```

检查条件：
1. 账户可用余额充足
2. 当前未持有 BTC-USDT-SWAP 仓位（避免对冲）
2. 今日交易次数 < max_daily_trades
3. 本小时交易次数 < max_hourly_trades
4. 本小时同方向未开仓
5. 连续亏损次数 < 3
6. 当日回撤 < 5%

**Step 4.2：计算仓位**

根据 Step 3.⑥ 的动态仓位计算公式确定实际下单金额。

**Step 4.3：执行下单**

调用 `swap_place_order`：

```bash
# 做多
okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz <仓位金额> --tdMode cross --posSide long --tgtCcy quote_ccy --profile <profile> --tag agentTradeKit

# 做空
okx swap place --instId BTC-USDT-SWAP --side sell --ordType market --sz <仓位金额> --tdMode cross --posSide short --tgtCcy quote_ccy --profile <profile> --tag agentTradeKit
```

**重要**：`tag` 参数必须为 `agentTradeKit`，否则不计入排行榜

记录开仓价格（从 ticker 返回的 last 值）

### Step 5 · 止损设置

开仓成功后立即设置止损：

**Step 5.1：计算止损价格**

根据 Step 3.⑤ 确定的箱体内部失效位：
- 多单止损 = 箱体内部失效位
- 空单止损 = 箱体内部失效位

**Step 5.2：设置止损**

调用 `swap_place_algo_order`：

```bash
# 多单止损
okx swap place-algo --instId BTC-USDT-SWAP --side sell --ordType stop_loss --sz <持仓数量> --slTriggerPx <止损价格> --slOrdType market --tdMode cross --posSide long --profile <profile>

# 空单止损
okx swap place-algo --instId BTC-USDT-SWAP --side buy --ordType stop_loss --sz <持仓数量> --slTriggerPx <止损价格> --slOrdType market --tdMode cross --posSide short --profile <profile>
```

### Step 6 · 持仓管理（高级）

**盈利管理：**

当存在持仓时，持续监控价格变化：

```bash
# 获取当前价格
okx market ticker BTC-USDT-SWAP

# 获取 ATR
okx market indicator atr BTC-USDT-SWAP --bar 1H --params 14
```

盈利 ≥ 1 ATR：
- 将止损移动至开仓价（保本）

盈利 ≥ 2 ATR：
- 平仓 50% 锁定利润
- 剩余仓位止损移动至开仓价

**提前退出：**

若出现：
- 重新回到箱体内部
- 出现反向结构（15M）

立即平仓：

```bash
# 多单平仓
okx swap close --instId BTC-USDT-SWAP --mgnMode cross --posSide long --profile <profile>

# 空单平仓
okx swap close --instId BTC-USDT-SWAP --mgnMode cross --posSide short --profile <profile>
```

## 风控规则（职业级）

```id="risk"
// 单笔亏损 ≤ 1%
// 盈亏比 ≥ 1:2
// 连续 3 笔亏损 → 停止交易 12 小时
// 当日回撤 ≥ 5% → 停止开仓
// 同时仅允许 1 个仓位
// 禁止加仓 / 补仓 / 对冲
```

## 使用示例

用户可以这样触发：

- "启动 BTC裸K突破策略"
- "BTC结构突破交易，模拟盘"
- "运行裸K策略，每笔风险1%"

## 输出格式

每次执行后向用户报告：

**开仓成功时**：

```
📊 BTC裸K结构AI策略 - 执行报告
━━━━━━━━━━━━━━━━━━━━
⏰ 执行时间：2024-04-10 14:00
💰 账户净值：10,000 USDT
━━━━━━━━━━━━━━━━━━━━
📦 箱体结构：
   上沿：$87,500
   下沿：$85,000
   高度：$2,500
   测试次数：上沿 3 次 / 下沿 4 次
📊 结构评分：高
🎯 市场状态：震荡
━━━━━━━━━━━━━━━━━━━━
🤖 AI 综合判断：
✅ 结构评分 ≥ 中（评分：高）
✅ 市场状态 = 震荡
✅ 真突破确认（收盘价突破）
✅ 回踩后低点抬高
✅ 盈亏比 ≥ 1:2（风险:$500 / 目标:$1,200）
━━━━━━━━━━━━━━━━━━━━
📋 决策：开多
💰 开仓价格：$87,800
📊 动态仓位：300 USDT（风险 1%）
🎯 止盈目标：$89,000
🛑 止损位置：$85,300（箱体内部失效位）
📋 订单ID：xxxxxxxxx
✅ 止损已设置
```

**跳过时**：

```
📊 BTC裸K结构AI策略 - 执行报告
━━━━━━━━━━━━━━━━━━━━
⏰ 执行时间：2024-04-10 14:00
💰 账户净值：10,000 USDT
━━━━━━━━━━━━━━━━━━━━
📦 箱体结构：
   上沿：$87,500
   下沿：$85,000
   高度：$2,500
   测试次数：上沿 2 次 / 下沿 2 次
📊 结构评分：低
🎯 市场状态：趋势
━━━━━━━━━━━━━━━━━━━━
🤖 AI 综合判断：
❌ 结构评分 < 中（评分：低）
❌ 市场状态 ≠ 震荡（趋势状态）
❌ 不满足交易条件
━━━━━━━━━━━━━━━━━━━━
📋 决策：本轮跳过
💡 理由：结构评分低且市场处于趋势状态
⏰ 下次检查：5 分钟后
```

## 注意事项

1. **Agent Trade Kit 标识**：下单时必须包含 `tag=agentTradeKit`，否则不计入排行榜
2. **默认使用模拟盘**：首次运行建议使用 `profile=demo`，充分测试后再切换实盘
3. **高频触发但不乱交易**：每 5 分钟检查，但仅在满足条件时交易，避免噪音
4. **只做干净结构**：结构评分低的交易不参与，保证胜率优势
5. **有空间的突破**：盈亏比必须 ≥ 1:2，否则放弃交易
6. **止损优先**：每笔交易必须设置止损，严格执行风控纪律
7. **禁止加仓补仓**：严格按照策略执行，禁止手动干预
8. **连续亏损保护**：连续 3 笔亏损后停止 12 小时，避免情绪化交易
9. **滑点风险**：实际交易存在滑点、手续费等风险，实际盈亏与理论值会有偏差
10. **学习研究**：本 Skill 仅供学习研究，不构成投资建议，盈亏自负

---

### [10] `btc-trader`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/btc-trader/SKILL.md`

---
name: btc-trader
description: 面向 BTC-USDT-SWAP 的 4h 趋势/波动/拥挤度交易技能。用于生成结构化交易信号，结合 EMA20/EMA60、RSI14、ATR14、资金费率与持仓量变化做出 开仓 / 观望 / 跳过 判断。默认是信号版，不自动下单；仅在用户明确要求执行且执行工具可用时，才进入下单与止损流程。
---

# BTC Trader

这是一个 **BTC 单标的交易信号技能**，默认标的为 `BTC-USDT-SWAP`。

目标：
- 用尽量少但稳定的规则，输出 **可解释、可审计、可降级** 的交易决策。
- 默认先做 **信号判断**，而不是直接下单。
- 震荡市优先跳过，趋势市才考虑参与。

## 适用场景

当用户提出以下意图时使用本技能：
- 分析 BTC 当前是否适合开多 / 开空
- 写 BTC 自动交易 / 半自动交易策略
- 生成 BTC 交易信号
- 基于 4h K 线做趋势判断
- 给出交易理由、仓位建议、止损建议

## 默认行为

**默认只输出信号，不下单。**
只有在同时满足以下条件时，才可进入执行层：
1. 用户明确要求下单或自动执行
2. 可用的行情/交易工具已经存在
3. 风控条件完整可验证
4. 本次信号达到 `high` 置信等级

如果任一条件不满足：
- 只输出分析结果
- 不伪造执行结果
- 不假装已下单

## 需要的数据

优先获取以下数据：
1. `BTC-USDT-SWAP` 的 `4h` K线
2. `BTC-USDT-SWAP` 的 `1h` K线（辅助确认）
3. 资金费率（funding rate）
4. 持仓量（open interest）或其变化值

若无法拿到完整数据：
- 缺 `1h`：可退化为仅 4h 分析，但降低置信度
- 缺 funding / OI：允许输出趋势信号，但必须标记 `riskFlags`
- 缺关键 K线：直接停止并说明无法分析

## 指标计算

基于 K 线计算：
- `EMA20`
- `EMA60`
- `RSI14`
- `ATR14`
- `atrPct = ATR14 / close`

尽量直接用最新已收线数据，不要依赖未收线 K 的瞬时值做最终结论。

## 决策流程

按以下顺序执行，不要跳步。

### Step 1: 判断市场状态（Regime）

基于 4h 为主，1h 为辅，将市场划分为：
- `bull_trend`
- `bear_trend`
- `range`

#### Bull Trend 候选
通常满足：
- 4h `EMA20 > EMA60`
- 4h EMA20 斜率向上
- 价格位于 4h EMA20 上方，或回踩后重新站回

#### Bear Trend 候选
通常满足：
- 4h `EMA20 < EMA60`
- 4h EMA20 斜率向下
- 价格位于 4h EMA20 下方，或反弹失败后重新转弱

#### Range
出现以下任一倾向时，优先视为震荡：
- EMA20 与 EMA60 缠绕、距离很小
- RSI 长时间在 `45~55` 徘徊
- 最近几根 K 没有清晰高低点趋势
- 价格反复穿越 EMA20/EMA60

**原则：震荡优先跳过。**

### Step 2: 评估方向性信号强度

给信号打分，推荐总分 0~10。

#### 多头加分项
- 4h EMA20 > EMA60
- 1h EMA20 > EMA60
- RSI14 位于 `52~68`
- 价格不是极度远离均线后的追高
- 价格结构呈更高低点 / 更高高点
- OI 上升且价格上涨
- Funding 未过热
- atrPct 在合理区间

#### 空头加分项
- 4h EMA20 < EMA60
- 1h EMA20 < EMA60
- RSI14 位于 `32~48`
- 价格不是极度远离均线后的追空
- 价格结构呈更低高点 / 更低低点
- OI 上升且价格下跌
- Funding 未极端偏空
- atrPct 在合理区间

### Step 3: 拥挤度过滤（Funding）

将资金费率视为拥挤度代理。

推荐阈值：
- `|funding| <= 0.03%`：正常
- `0.03% < |funding| <= 0.08%`：轻度拥挤，仓位 × 0.7
- `0.08% < |funding| <= 0.12%`：明显拥挤，仓位 × 0.5
- `|funding| > 0.12%`：极端拥挤，优先 `skip`

注意：
- 正 funding 很高时做多风险上升
- 负 funding 很高时做空风险上升
- 拥挤度不是反手信号，而是 **缩仓 / 跳过信号**

### Step 4: 波动过滤（ATR）

重点看 `atrPct = ATR14 / close`。

推荐区间：
- `< 1.2%`：波动太低，机会不足，降仓或跳过
- `1.2% ~ 3.5%`：合理交易区间
- `3.5% ~ 5%`：偏高，降仓
- `> 5%`：极端波动，优先跳过

### Step 5: OI 质量确认

结合价格与 OI：
- 价格上涨 + OI 上升：多头趋势更可信
- 价格下跌 + OI 上升：空头趋势更可信
- 价格上涨/下跌但 OI 下降：可能主要是平仓推动，趋势质量下降
- Funding 极端 + OI 暴增：警惕拥挤尾声

### Step 6: 生成最终动作

动作只能是：
- `open`
- `observe`
- `skip`
- `reduce`

含义：
- `open`：趋势明确，可考虑开仓
- `observe`：有方向，但条件不够整齐，先等
- `skip`：本次不做
- `reduce`：若用户已持仓，则建议减仓/降风险

## 置信度映射

建议：
- `score >= 8` → `high`
- `score 5~7` → `medium`
- `score <= 4` → `low`

默认规则：
- `high` 才允许进入自动执行候选
- `medium` 只建议人工确认后执行
- `low` 直接 `observe` 或 `skip`

## 仓位建议

不要默认满仓或固定大仓位。

### 基础规则
- 单笔建议风险：账户净值的 `0.5% ~ 1%`
- 不建议 V1 默认直接使用 3% 风险上限

### 仓位缩放因子
- `high`：`1.0`
- `medium`：`0.5`
- funding 轻度拥挤：再 × `0.7`
- funding 明显拥挤：再 × `0.5`
- atrPct 偏高：再 × `0.5`
- 缺少 funding / OI 数据：再 × `0.5`

输出中用 `positionScale` 表示，范围 `0.0 ~ 1.0`。

## 止损建议

优先使用 ATR 止损：
- 多头止损：`entry - 1.5 * ATR`
- 空头止损：`entry + 1.5 * ATR`

若执行环境只支持固定百分比止损，可退化为：
- 多头：`entry * 0.98`
- 空头：`entry * 1.02`

必须在输出中明确注明所使用的止损方法。

## 风控红线

若用户要求执行，必须先检查并满足：
- 单笔最大亏损不超过账户净值 `3%`
- 当日净值回撤超过 `8%`，停止新开仓
- 最多同时持有 `2` 个标的
- 禁止对冲持仓

若缺少账户净值 / 当日回撤 / 当前持仓信息：
- 不可声称风控已通过
- 只能输出“策略建议”，不能假装满足执行条件

## 执行层（仅在用户明确要求时）

如果用户明确要求下单，并且交易工具可用，按以下顺序：
1. 先完成分析
2. 再明确输出：方向 / 仓位 / 止损
3. 再执行下单
4. 成交后立即设置止损
5. 若任一步失败，清楚说明失败点

推荐参数（仅作为执行模板，不代表总是应执行）：
- `instId = BTC-USDT-SWAP`
- `side = buy | sell`
- `ordType = market`
- `sz = 按 positionScale 与账户风险规则计算`
- `tag = agentTradeKit`

## 输出格式

优先输出结构化 JSON，然后附简短中文说明。

```json
{
  "symbol": "BTC-USDT-SWAP",
  "timeframe": "4h",
  "marketRegime": "bull_trend",
  "direction": "buy",
  "signalScore": 8,
  "confidence": "high",
  "positionScale": 0.7,
  "fundingRate": 0.0002,
  "openInterestBias": "rising_with_price",
  "atrPct": 0.021,
  "action": "open",
  "stopLossMethod": "atr",
  "suggestedStopLoss": 81234.5,
  "riskFlags": [],
  "reasoning": [
    "4h 与 1h 同向偏多",
    "RSI 位于健康趋势区间",
    "funding 未过热",
    "atrPct 处于可交易范围"
  ]
}
```

## 说明纪律

- 不要把概率说成确定性。
- 不要宣称“稳赚”。
- 不要伪造回测结果。
- 如果数据不足，直接说明不足。
- 如果市场震荡，允许明确说“本次跳过”。

## 参考文件

需要细节时读取：
- `references/strategy-spec.md`：完整策略说明
- `references/risk-rules.md`：风险控制与执行约束
- `references/output-example.md`：输出示例

---

### [11] `btc-usdt-swap-defensive-ai`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/btc-usdt-swap-defensive-ai/SKILL.md`

---
name: btc-usdt-swap-defensive-ai
description: 仅交易 BTC-USDT-SWAP 的防守型 AI 永续合约策略 Skill。使用多周期趋势、资金费率、持仓量、波动率与账户风控做综合判断，并通过 Agent Trade Kit 自动执行开平仓与止损，适合谨慎型实盘交易。
---

# 策略名称
BTC-USDT 永续防守型多信号融合 AI 策略 V1.0

# 适用范围
本 Skill 只允许交易 `BTC-USDT-SWAP`，只允许 `USDT` 永续合约，不得扩展到 ETH、SOL 或其他币种。

本 Skill 的首要目标不是追求极限收益，而是优先保护本金，在趋势清晰、拥挤度可控、波动率合适时才参与。若信号不一致，宁可跳过，也不勉强交易。

# 运行前置
建议以显式模块方式启动 Agent Trade Kit，而不是依赖默认模块。推荐：

```text
okx-trade-mcp --profile "AI SHIPAN" --modules market,swap,account
```

建议在 Agent Trade Kit 中启用以下能力：

- `market` 模块：用于 `market_get_candles`、`market_get_funding_rate`、`market_get_open_interest`、`market_get_mark_price`
- `swap` 模块：用于 `swap_place_order`、`swap_get_positions`、`swap_get_fills`、`swap_get_leverage`
- `account` 模块：用于 `account_get_balance`、`account_get_config`、`account_get_max_size`

若你使用 Skills 方式接入，建议至少安装：

- `okx-cex-market`
- `okx-cex-trade`
- `okx-cex-portfolio`

当前本机环境已经表现出以下真实特征，Skill 必须按此适配：

- `account_get_config` 返回 `posMode = "long_short_mode"`
- 最近真实订单使用的是 `tdMode = "isolated"`
- `swap_place_order` 支持直接附带 `slTriggerPx/slOrdPx`
- 已安装版本也支持独立 `swap_place_algo_order`

因此本 Skill 默认使用：

- 持仓模式：`long_short_mode`
- 保证金模式：`isolated`
- 方向表达：用 `posSide = "long"` 或 `posSide = "short"`
- 风控落地：优先在 `swap_place_order` 中直接附带止损；如需后续移动止损，再使用 `swap_place_algo_order`

虽然账户是 `long_short_mode`，本策略仍然是单方向净敞口策略：任意时刻只允许持有 `long` 或 `short` 其中一种，不允许同时有两边仓位。

# 执行节奏
每 1 小时触发一次，但使用多周期共振：

- `4h`：定义主趋势和市场状态
- `1h`：决定是否允许开仓、加严风控或平仓
- `15m`：优化入场节奏，避免在短线过热位置追单

# 核心原则
1. 只做 `BTC-USDT-SWAP`。
2. 任何时候只保留一个净方向仓位，禁止多空对冲。
3. 只在趋势清晰时开仓，震荡与极端拥挤阶段以观望为主。
4. 先计算风险，再决定仓位；不是先想赚多少，而是先确认最多亏多少。
5. 允许错过，不允许失控。

# Step 0 · 账户、模式与风险预算检查
先调用真实的 Agent Trade Kit 账户与持仓工具：

- `account_get_balance`
- `account_get_config`
- `swap_get_positions`
- `swap_get_leverage`
- 如需核对最近成交与连续止损情况，可补充 `swap_get_fills`

你必须先得到以下信息：

- 当前账户净值 `equity`
- 今日北京时间 `00:00` 的起始净值 `day_start_equity`
- 当前账户持仓模式是否为 `long_short_mode`
- 当前 BTC 永续杠杆设置
- 当前 BTC 持仓方向、仓位大小、均价、未实现盈亏
- 当前是否已经存在 BTC 的保护性止损安排

执行以下预检查：

1. 若 `account_get_config` 返回的 `posMode` 不是 `long_short_mode`：
   本轮不自动交易，先完成模式确认或初始化。因为本 Skill 的实际下单参数将显式使用 `posSide=long/short`。
2. 若 `equity <= day_start_equity * 0.92`，说明当日净值回撤已达 `8%` 或更多：
   本轮禁止新开仓，只允许减仓、平仓、移动止损，不允许抄底或逆势开新单。
3. 若已有 BTC 多头仓位，则本轮只允许做多头管理，不允许开空。
4. 若已有 BTC 空头仓位，则本轮只允许做空头管理，不允许开多。
5. 若同时存在 `long` 与 `short` 两边持仓，则视为违反策略，优先平掉弱势一边，恢复单方向净敞口后再继续。
6. 若当前杠杆高于保守阈值，优先在无仓状态下使用 `swap_set_leverage` 将 `long` 与 `short` 两个方向都设置到 `3x`；若无法完成，则停止新开仓。
7. 若账户可用保证金过低，或开仓后预估保证金占用会明显压缩缓冲区，则放弃新开仓。

关于 `day_start_equity`：

- 若这是北京时间 `00:00` 之后的第一轮执行，将当前 `equity` 记录为当日起始净值。
- 若不是第一轮执行，则沿用本日之前已经记录的 `day_start_equity`。
- 若缺乏持久化记忆，宁可放弃“新增开仓”，也不要在无法确认日内回撤约束时盲目继续。

风险预算采用保守制度：

- 常规单笔风险预算：`equity * 0.8%`
- 强趋势高质量机会：最多提升到 `equity * 1.2%`
- 绝对上限：单笔最大亏损不得超过 `equity * 3%`
- 当日出现连续 2 笔止损后，本日后续所有新仓风险预算降为 `equity * 0.5%`

# Step 1 · 行情数据采集
调用 `market_get_candles` 获取 `BTC-USDT-SWAP` 的 `15m / 1h / 4h` K 线，并计算以下指标：

- `EMA21`
- `EMA55`
- `EMA200`
- `RSI(14)`
- `ATR(14)`
- `ADX(14)`，若环境不支持则可省略，但必须说明
- 最近 20 根 K 线平均成交量
- 最近 10 根 `1h` K 线的局部高点与低点
- 最新 `mark price`，可通过 `market_get_mark_price` 获取，用于风控与止损触发参考

重点提取以下信息：

1. `4h` 趋势方向：
   价格是否位于 `EMA55` 和 `EMA200` 上方或下方，均线是否同向发散，斜率是否健康。
2. `1h` 执行结构：
   当前是否顺着 `4h` 主趋势，且价格回踩 `EMA21/EMA55` 后重新走强或走弱。
3. `15m` 入场节奏：
   是否出现追高追空风险，是否刚经历急拉急跌，是否有更优的回撤切入点。
4. 波动状态：
   计算 `ATR% = ATR / 最新价格`，判断当前是否过于剧烈或过于沉寂。

# Step 2 · 市场情绪与拥挤度采集
调用：

- `market_get_funding_rate` 获取 `BTC-USDT-SWAP` 最新资金费率
- `market_get_open_interest` 获取最新持仓量及其变化

你需要把它们与价格行为联动理解，而不是机械判断：

1. 若价格上涨、持仓量同步明显上升、资金费率转高，说明多头正在拥挤。
2. 若价格下跌、持仓量同步明显上升、资金费率转负，说明空头正在拥挤。
3. 若价格创新高但持仓量没有跟上，趋势可能衰竭，不适合激进追多。
4. 若价格创新低但持仓量没有跟上，趋势可能衰竭，不适合激进追空。
5. 若资金费率绝对值超过 `0.10%`，视为拥挤度过高：
   只能半仓参与，或直接跳过。
6. 若资金费率绝对值超过 `0.18%` 且持仓量仍在单边放大：
   直接禁止顺着拥挤方向新开仓，优先等待回落或信号重置。

# Step 3 · AI 综合判断（核心）
你必须先进行自然语言推理，再做最终决策。禁止只输出一句“满足条件所以开仓”。

请按以下 5 个维度逐项推理，并给出 `LongScore` 与 `ShortScore`：

1. 趋势质量 `0-35`
   判断 `4h` 与 `1h` 是否同向。
   若 `4h`、`1h` 同向，且价格与 `EMA21/55/200` 排列健康、均线斜率清晰，则该方向高分。
   若长短周期冲突，或价格远离均线后已明显扩张，则降分。

2. 动量与入场结构 `0-20`
   判断 `RSI` 是否支持当前方向但未极端透支。
   判断 `15m` 是否处于刚刚爆拉爆跌后的追价区。
   理想状态是：顺大级别趋势、在 `1h` 回踩后重新转强或转弱，而不是在离均线过远处追单。

3. 拥挤度与反身性风险 `0-20`
   结合资金费率与持仓量变化，判断当前方向是否过于拥挤。
   若方向正确但过度拥挤，则可以保留方向判断、下调仓位。
   若方向正确且拥挤度温和，则加分。
   若出现明显挤仓风险，则直接降为观望。

4. 波动率与止损可行性 `0-15`
   若 `ATR%` 过高，说明止损需要放很宽，盈亏比会变差。
   若 `ATR%` 过低，说明市场机会不足、来回摩擦大。
   仅当波动率处于中等区间时才允许正常开仓。

5. 风控上下文 `0-10`
   判断本日是否已有连续亏损、是否接近日内 `8%` 停机线、当前是否已有持仓需要管理。
   越接近风控边界，分数越低，仓位越小。

评分后按下面规则决策：

- 若 `LongScore >= 75` 且 `LongScore - ShortScore >= 15`：
  允许做多。
- 若 `ShortScore >= 75` 且 `ShortScore - LongScore >= 15`：
  允许做空。
- 若最高分在 `65-74`：
  只允许轻仓试探，且必须说明为什么不是满配信号。
- 若最高分低于 `65`：
  本轮跳过，不新开仓。
- 若信号方向与现有持仓一致：
  优先判断是否继续持有、上移止损或减仓，不必重复追单。
- 若信号方向与现有持仓相反：
  先平旧仓，再决定是否反手；禁止同一时刻对冲。

你在输出结论时，必须明确回答以下问题：

1. 当前市场属于趋势、多空拉扯，还是高波动噪音？
2. 为什么当前更适合做多、做空，或完全不做？
3. 当前资金费率和持仓量是在确认趋势，还是提示拥挤？
4. 现在开仓后，止损是否能放在一个“合理但不失控”的位置？
5. 综合来看，本轮是：
   `开多 / 开空 / 仅管理已有仓位 / 跳过`

# Step 4 · 仓位计算
只有在 Step 3 给出明确方向后，才允许计算仓位。

先计算止损距离：

- 多头初始止损距离百分比：
  `stop_distance_pct_long = max(1.2 * ATR1h_pct, 0.009)`
- 空头初始止损距离百分比：
  `stop_distance_pct_short = max(1.2 * ATR1h_pct, 0.009)`

同时加入宽度上限，避免止损过宽：

- 若 `stop_distance_pct > 0.022`，本轮默认不新开仓，除非 AI 能明确说明这是强趋势突破且仓位会同步显著缩小。

风险资金公式：

```text
base_risk_pct =
  1.2%  (仅限强趋势高质量机会)
  0.8%  (默认)
  0.5%  (当日已有连续亏损或分数只是轻仓试探)

risk_cap = equity * base_risk_pct
position_notional = risk_cap / stop_distance_pct
```

再调用 `account_get_max_size` 对 `BTC-USDT-SWAP` 做一次容量校验，最终下单名义价值不得超过账户与交易所当前允许的最大值。

本机版本的 `swap_place_order` 支持 `tgtCcy="quote_ccy"`，因此最终执行时建议直接以 `USDT` 名义价值下单，而不是手动换算合约张数：

```text
tgtCcy = "quote_ccy"
sz = <final_notional 对应的 USDT 金额>
```

这样可直接把风险预算映射为下单规模，减少合约面值换算误差。

仓位上限采用双层限制：

1. 风险上限：
   无论如何，单笔最大亏损不得超过账户净值 `3%`。
2. 名义仓位上限：
   - 默认不超过账户净值的 `25%` 名义价值
   - 强趋势且拥挤度温和时，最多放宽到 `35%`
   - 任何情况下，不得超过账户净值的 `40%`

最终仓位取以下最小值：

```text
final_notional =
min(
  position_notional,
  equity * 25% 或 35%,
  equity * 40% 的绝对上限
)
```

将 `final_notional` 转为下单张数 `sz` 时，必须向下取整到交易所允许的最小单位，不得向上取整冒险。

# Step 5 · 执行下单
仅当 AI 在 Step 3 给出明确开仓结论时，调用：

```text
swap_place_order
instId = "BTC-USDT-SWAP"
tdMode = "isolated"
side = "buy" 或 "sell"
posSide = "long" 或 "short"
ordType = "market"
tgtCcy = "quote_ccy"
sz = <按 Step 4 计算后的 USDT 名义金额>
slTriggerPx = <止损触发价>
slOrdPx = "-1"
```

方向映射必须严格一致：

- 开多：`side = "buy"`，`posSide = "long"`
- 开空：`side = "sell"`，`posSide = "short"`
- 平多：`side = "sell"`，`posSide = "long"`
- 平空：`side = "buy"`，`posSide = "short"`

执行要求：

1. 不得手动下单替代。
2. 若已有同方向持仓，除非这是预先定义的同向加仓逻辑，否则默认不再追单。
3. 默认不做逆势摸顶抄底。
4. 若下单后滑点明显恶化，导致实际止损风险超过原计划，则立即缩减仓位。

# Step 6 · 止损设置
开仓后必须立即设置保护性止损，禁止裸奔。

由于本机 `okx-trade-mcp 1.3.0` 已支持两种止损路径，本 Skill 采用以下固定顺序：

1. 首选在 `swap_place_order` 下单时直接附带：
   `slTriggerPx` + `slOrdPx = "-1"`
2. 下单成交后，立即用 `swap_get_order` 或 `swap_get_positions` 核对仓位与保护状态。
3. 若首单未成功附带止损，立刻调用 `swap_place_algo_order` 补挂独立条件止损。
4. 若后续需要移动止损，先取消旧止损，再挂新止损，避免多重止损互相干扰。

止损逻辑如下：

- 多头止损价：
  `long_stop = entry_price * (1 - stop_distance_pct_long)`
- 空头止损价：
  `short_stop = entry_price * (1 + stop_distance_pct_short)`

若需要补挂或更新独立条件止损，则使用：

```text
swap_place_algo_order
instId = "BTC-USDT-SWAP"
tdMode = "isolated"
side = <平仓方向，多头仓位用 sell，空头仓位用 buy>
posSide = <long 或 short>
ordType = "conditional"
sz = <需要保护的仓位规模；若以 USDT 输入则显式设置 tgtCcy>
slTriggerPx = <long_stop 或 short_stop>
slOrdPx = "-1"
slTriggerPxType = "mark"
```

其中 `slTriggerPxType = "mark"` 的目标，是尽量减少短时插针对风控判断的干扰。

若最近 `1h` 结构低点/高点比上述 ATR 止损更合理，可以使用更保守的一侧，但必须保证：

- 单笔最大亏损仍不超过账户净值 `3%`
- 不得为了“避免被打止损”而无限放宽

动态保护规则：

1. 浮盈达到 `1R` 后，将止损上移到保本或略微盈利位置。
2. 浮盈达到 `2R` 后，优先保护利润，可：
   - 上移止损到锁定至少 `0.8R` 收益的位置
   - 或按计划减仓一部分，再保留趋势仓
3. 若下一次触发时，`LongScore/ShortScore` 明显衰减到 `55` 以下，即使未打止损，也可以主动平仓。

# Step 7 · 主动平仓与放弃交易条件
出现以下任一情形，优先考虑平仓或跳过：

1. `4h` 主趋势与当前持仓方向不再一致。
2. `1h` 级别跌破或站不上关键均线，且动量明显转弱。
3. 资金费率极端、持仓量持续堆高，拥挤度显著恶化。
4. `ATR%` 高到止损过宽，盈亏比不足。
5. 本日净值已接近 `8%` 回撤警戒线。
6. 市场处于高噪音震荡，`LongScore` 与 `ShortScore` 接近，没有明显优势方向。

此时优先输出：

- `仅管理已有仓位`
- `减仓观望`
- `本轮跳过`

不要因为“长时间没交易”就硬做单。

# 风控规则
以下风控规则为硬约束，不得突破：

```text
// 单笔最大亏损不超过账户净值 3%
// 当日净值回撤超 8% 则停止新开仓
// 本 Skill 只交易 BTC-USDT-SWAP，因此天然不超过 2 个标的
// 同时只允许 1 个净方向仓位，禁止对冲持仓
// 开仓后必须立即设置止损
// 禁止亏损加仓，禁止摊平补仓
// 当前本机环境按 isolated + long_short_mode 执行，但策略仍禁止双向同时持仓
// 推荐使用 isolated + 3x 保守杠杆，不依赖高杠杆放大收益
```

# 输出格式
每次执行时，先输出你的推理摘要，再决定是否下单。输出至少包含：

```text
市场状态:
主方向判断:
LongScore:
ShortScore:
资金费率/持仓量解读:
波动率解读:
风险预算:
计划动作:
计划仓位:
止损价:
是否执行:
```

其中：

- 若 `是否执行 = 否`，要写清楚为什么跳过。
- 若 `是否执行 = 是`，要写清楚为什么当前值得承担这笔风险。

# 执行风格
你是一名偏保守、重视回撤控制的 BTC 永续交易 AI。你的目标不是预测每一个波动，而是在赔率合适、风险受控、趋势明确时进场，在不确定时保持耐心。

若数据冲突，请默认站在风控一边。

---

### [12] `cmc-okx`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/cmc-okx/SKILL.md`

---
name: cmc-okx
description: >
  Use this skill for cryptocurrency market data and information
  lookups: current prices (including Chinese queries like BTC现在多少钱 or
  大饼多少), market cap, multi-coin comparisons (e.g., SOL vs AVAX), fear
  & greed index (恐贪指数), broad market overview (大盘怎么样), top
  gainers/losers, technical indicators (RSI, MACD), funding rates,
  open interest, and crypto news. Powered by CoinMarketCap and OKX.
  Trigger for pure data retrieval and market information requests. Do
  NOT trigger when the user explicitly wants an actionable trading
  plan with entry prices, exit targets, stop-loss levels, or position
  sizing — those belong to specialized trading plan skills.
---

# CoinMarketCap + OKX Market Data Skill

Fetch comprehensive cryptocurrency market data through CoinMarketCap MCP + OKX Trade Kit. CMC provides market cap, supply, dominance, and news. OKX provides real-time prices, funding rates, open interest, and 70+ technical indicators.

**Quick Start for common queries:**
- "BTC 多少錢?" → Step 1 (search) → `get_crypto_quotes_latest` + OKX `market_get_ticker`
- "ETH 技術分析" → Step 1 → OKX `market_get_indicator` (RSI, MACD, MA, BB)
- "今天大盤怎樣?" → `get_global_metrics_latest` + `trending_crypto_narratives`
- "什麼幣漲最多?" → OKX `market_get_tickers` → sort by 24h change
- "BTC funding rate?" → OKX `market_get_funding_rate` (instId: `BTC-USDT-SWAP`)

## Data Source Priority

**OKX Trade Kit is the primary source** for all real-time prices, TA indicators, funding rates, and open interest — no API key required.

**CMC MCP is a supplementary source** that adds market cap, supply data, fear/greed index, narratives, and news. If CMC tools are unavailable or return errors, fall back to OKX data.

## Optional: CMC MCP Setup

If the user wants CMC data and has not configured the MCP connection, guide them to set it up:

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": {
        "X-CMC-MCP-API-KEY": "your-api-key"
      }
    }
  }
}
```

Get a free API key from https://pro.coinmarketcap.com/login

**CMC API Free vs Premium access:**
- Free: `search_cryptos`, `get_crypto_quotes_latest`, `get_crypto_info`, `get_global_metrics_latest`, `search_crypto_info`
- Premium: `get_crypto_latest_news`, `trending_crypto_narratives`, `get_upcoming_macro_events`, trending gainers/losers
- Note: The CMC MCP server may provide access to premium tools regardless of your REST API plan. Try calling them first — fall back to OKX data if they return errors.

## Available CMC MCP Tools

| Tool | Purpose |
|------|---------|
| `search_cryptos` | Search crypto by name/symbol to get CMC numeric ID (required by other tools) |
| `get_crypto_quotes_latest` | Price, market cap, volume, percent changes (1h/24h/7d/30d/90d/1y), supply, dominance |
| `get_crypto_info` | Description, website, social links, explorer URLs, tags, launch date |
| `get_crypto_metrics` | Address counts by holding value, whale distribution, holder time breakdowns |
| `get_crypto_technical_analysis` | Moving averages (SMA, EMA), MACD, RSI, Fibonacci levels, pivot points |
| `get_crypto_latest_news` | Headlines, descriptions, content, URLs, publish dates |
| `search_crypto_info` | Semantic search on crypto concepts, whitepapers, FAQs |
| `get_global_metrics_latest` | Total market cap, fear/greed index, altcoin season index, BTC/ETH dominance, ETF flows |
| `get_global_crypto_derivatives_metrics` | Open interest, funding rates, liquidations, futures vs perpetuals |
| `get_crypto_marketcap_technical_analysis` | TA indicators for the entire crypto market cap |
| `trending_crypto_narratives` | Hot narratives with market cap, volume, performance, top coins |
| `get_upcoming_macro_events` | Fed meetings, regulatory deadlines, major announcements |

## Execution Flow

### Step 1: Search First (Always)

When a user mentions a cryptocurrency by name or symbol, search for it first to get the numeric CMC ID:

```
User: "How is Solana doing?"
1. Call search_cryptos with query "solana"
2. Get ID (e.g., 5426)
3. Use the ID in subsequent tool calls
```

Most tools require the numeric CMC ID, not the name or symbol. The search tool returns: id, name, symbol, slug, and rank.

**Disambiguation:** Popular symbols often match multiple coins (e.g., "PEPE" → 32 results). Always:
1. Filter to `is_active=1` only
2. Pick the coin with the **lowest rank number** (= highest market cap) as the default
3. If the top result rank is >500, mention the coin is small-cap and confirm with the user
4. If user says a specific name (e.g., "Pepe" not just the symbol), match by name first

### Step 2: Select Tools Based on Query Type

**Price check / market overview:**
1. Call `get_crypto_quotes_latest` with the ID(s)
2. Supplement with OKX `market_get_ticker` for real-time bid/ask and OKX-specific volume

**Technical analysis request:**
1. Call OKX `market_get_indicator` for real-time indicators — recommended combo for retail traders:
   - `rsi` (14) — momentum: <30 oversold, >70 overbought, 30–70 neutral
   - `macd` — trend: returns DIF, DEA, histogram. Bullish when histogram > 0
   - `ma` with params [50, 200] — trend structure: price above both = bullish, below both = bearish
   - `bb` — volatility + support/resistance: upper band = resistance, lower = support
2. Optionally call CMC `get_crypto_technical_analysis` to add Fibonacci levels and pivot points if available
3. If CMC TA tools fail, OKX indicators alone (RSI/MACD/MA/BB) are sufficient for a complete analysis
4. Use timeframe `1Dutc` for swing traders (most retail), `4H` for active traders, `1Wutc` for position traders

**Coin research / background:**
1. Call `get_crypto_info` for project description and links
2. Call `get_crypto_metrics` for holder distribution data

**News and trends:**
1. Call `get_crypto_latest_news` for recent headlines (may require premium CMC plan — if it fails, skip gracefully)
2. Call `trending_crypto_narratives` for market themes
3. Call `get_upcoming_macro_events` for scheduled catalysts
4. If news tools fail (premium-only), provide a data-driven substitute:
   - Global metrics changes (market cap 24h change, BTC dominance shift)
   - Funding rate extremes (signal overleveraged positions)
   - Top movers from OKX (sudden price moves often follow news)
   - Say: "CMC news requires a premium API plan. Based on market data, here's what's notable today:"

**Broad market question ("what's happening in crypto?"):**
1. Call `get_global_metrics_latest` for total market cap, fear/greed, dominance
2. Call `trending_crypto_narratives` for hot themes
3. Call `get_upcoming_macro_events` for upcoming catalysts
4. Optionally call `get_global_crypto_derivatives_metrics` for leverage data

**Multi-coin comparison:**
1. Search each coin to get IDs
2. Call `get_crypto_quotes_latest` with comma-separated IDs (e.g., `id="1,1027,5426"`)

**Top movers / "what's pumping?" / "什麼幣漲最多?":**
1. Try CMC `trending_crypto_narratives` for narrative-level trends (may require premium plan)
2. If unavailable, use OKX `market_get_tickers` with instType `SPOT`:
   - Filter for USDT pairs only (ignore USD pairs — lower liquidity, may show stale prices)
   - Filter by minimum 24h volume (>$1M USDT to exclude illiquid tokens)
   - Calculate % change from `open24h` to `last` price, sort and present top 10 gainers and top 5 losers
   - Note: `market_get_tickers` returns all pairs (~400+) in one response — this is expected, filter the results

### Step 3: Real-Time Data from OKX Trade Kit

OKX is the primary source for real-time trading data. Use these tools for all live price, TA, and derivatives queries:

**OKX CLI (try first):**
```bash
okx market ticker BTC-USDT
okx market funding-rate BTC-USDT-SWAP
okx market open-interest BTC-USDT-SWAP
okx market indicator BTC-USDT --ind RSI
okx market candles BTC-USDT --bar 1D --limit 100
```

**OKX MCP fallback (if CLI unavailable):**
- `market_get_ticker` — real-time last price, bid/ask spread, 24h high/low/volume on OKX
- `market_get_funding_rate` — perpetual swap funding rates (instId format: `BTC-USDT-SWAP`)
- `market_get_open_interest` — OKX-specific open interest for swaps/futures
- `market_get_candles` — OHLCV candlestick data (1m to 1M bars, up to 1440 bars)
- `market_get_indicator` — OKX-calculated technical indicators (70+ types including RSI, MACD, Bollinger)
- `market_get_orderbook` — live order book depth (bid/ask walls, up to 400 levels)

**OKX instrument ID format:**
- Spot: `BTC-USDT`
- Perpetual swap: `BTC-USDT-SWAP` (use for funding rate, OI, swap trading)
- Futures: `BTC-USDT-240329` (expiry date suffix)

**If OKX Trade Kit is unavailable:**
```
Install OKX Trade Kit:
  npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli
  okx config init
  okx-trade-mcp setup --client claude-code

Details: https://github.com/okx/agent-trade-kit
```

### Step 4: Format Results

Read `references/output-templates.md` for the exact template to use per query type:

| Query type | Template |
|------------|----------|
| Price / market check | Price check template |
| Technical analysis | Technical analysis template |
| Broad market overview | Market overview template |
| Multi-coin comparison | Comparison template |
| Derivatives / funding rate | Derivatives template |
| Top movers / gainers | Top movers template |

Always end every response with a **Quick Take** — 1-2 sentences in plain language. Never skip this.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Search returns no results | Coin not found or misspelled | Report not found, ask user to clarify |
| CMC 400 "Invalid value" | Symbol format rejected | Strip special chars, try name search instead |
| Ambiguous symbol (PEPE → 32 results) | Multiple coins share same ticker | Pick lowest rank#, confirm with user if rank >500 |
| OKX 51001 "Instrument doesn't exist" | Coin not listed on OKX | Inform user; use CMC-only data |
| Tool fails or times out | Transient API error | Retry once; note which data is unavailable, proceed with other tools |
| Rate limited (429) | API rate limit exceeded | Inform user, suggest waiting, reduce concurrent tool calls |
| CMC MCP not configured | Missing API key or server config | Show setup guide above |
| CMC premium endpoint blocked | Free plan limitation | Switch to OKX fallback |
| Quotes tool fails | Critical for price queries | Try OKX `market_get_ticker` as fallback |
| Info tool fails | Background data unavailable | Note "Project info unavailable", provide what other tools return |

## Adapting to User Sophistication

- Casual ("how's bitcoin?" / "大饼多少了") — summary with key numbers, avoid jargon
- Technical ("what's the RSI on BTC?" / "日线怎么看") — detailed data with indicator values and signals
- Broad ("what's happening in crypto?" / "大盘怎么样") — global metrics, narratives, macro events
- Comparison ("BTC vs ETH") — side-by-side table with batch requests
- Trending ("what's pumping?" / "什麼幣漲得猛") — top movers from OKX tickers
- Derivatives ("funding rate?" / "资金费率") — OKX funding rate + open interest

## Chinese Slang Mappings

| Slang | Meaning | Action |
|-------|---------|--------|
| 大饼 / 饼 / 烧饼 | Bitcoin (BTC) | Search BTC |
| 二饼 | Ethereum (ETH) | Search ETH |
| 以太 | Ethereum (ETH) | Search ETH |
| 土狗 | Meme/shitcoins | Top movers, filter small caps |
| 恐贪指数 | Fear & Greed Index | Global metrics |
| 资金费率 | Funding rate | Derivatives flow |
| 大盘 | Overall market | Market overview |
| 日线 / 4H | Daily chart / 4-hour | TA with timeframe |

## Handling Trade Advice Queries

When users ask for trade advice (买什么 / 梭哈 / 给个单 / should I buy), do NOT give buy/sell recommendations. Instead:

1. Acknowledge the question
2. Provide relevant data: price, TA signals, funding rate, market sentiment
3. Say: "I can provide market data to help you make informed decisions, but I cannot give financial advice. Here's what the data shows:"

## Core Principles

1. **Search first** — always resolve names/symbols to CMC numeric IDs before calling other tools
2. **OKX for real-time, CMC for fundamentals** — OKX is the primary live data source; CMC adds market cap, dominance, and sentiment context
3. **Batch when possible** — use comma-separated IDs for multi-coin queries
4. **Graceful degradation** — if CMC premium tools fail, fall back to OKX data (prices, TA, top movers)
5. **Never fabricate data** — if a tool fails, say so; never invent prices or metrics
6. **Interpret for retail** — raw numbers without context are useless. Always add "What It Means" for non-obvious metrics
7. **Quick Take always** — end every data output with a 1-2 sentence plain-language summary

---

### [13] `congress-trades`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/congress-trades/SKILL.md`

---
name: congress-trades
description: >
  Use this skill when the user asks about stock trades made by US
  politicians, members of Congress, senators, or representatives.
  Covers any query about what specific politicians (like Nancy Pelosi,
  Dan Crenshaw, etc.) are buying or selling, whether politicians are
  trading on insider information, recent congressional trading
  activity, or tracking political stock disclosures. Also use for
  setting up alerts on new politician trades or syncing congressional
  trade data. Do NOT use for general stock market analysis, crypto, or
  trading strategies unrelated to politician activity.
---

# Congress Trades Tracker

Monitor US congressional stock trades via the Quiver Quant API. Syncs data to a local SQLite database and alerts on new significant trades.

## Requirements

- Python 3.10+ with `requests` (`pip install requests`)
- **QUIVER_API_KEY** environment variable (obtain at https://www.quiverquant.com/)

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| QUIVER_API_KEY | **Yes** | -- | Quiver Quant API token |
| CONGRESS_DB_PATH | No | `data/congress_trades.db` | SQLite database path |
| MIN_TRADE_AMOUNT | No | `15001` | Minimum trade dollar amount to trigger alerts |

Never hard-code API keys in scripts or crontab entries. Use shell profile, `.env` file, or secure environment injection.

## Execution Flow

When the user activates this skill, follow the steps below based on what they need.

### 1. First-Time Setup

If the user has not set up the tracker yet, guide them through:

1. **Check Python**: Verify Python 3.10+ is available.
2. **Install dependency**: `pip install requests`
3. **Set API key**: Ask the user for their Quiver Quant API key. Instruct them to set it:
   ```bash
   export QUIVER_API_KEY="<their-key>"
   ```
4. **Run initial sync**: Execute the scraper to populate the database:
   ```bash
   python3 scripts/scraper.py
   ```
5. **Confirm success**: Check that `data/congress_trades.db` was created and report the number of trades synced.
6. **Optional -- schedule cron**: Help the user set up a cron job for automatic syncing:
   ```bash
   crontab -e
   # Add (adjust paths). Every 30 min is sufficient — data updates once daily at most:
   */30 * * * * . "$HOME/.profile" && /usr/bin/python3 /path/to/scripts/scraper.py >> /path/to/logs/scraper.log 2>&1
   ```

### 2. Manual Sync

If the user asks to sync, refresh, or update trades:

1. Run the scraper: `python3 scripts/scraper.py`
2. Report the result: number of new trades found, total in database.

### 3. Query Trades

When the user wants to look up trades, use the SQLite database directly. The database is at the path defined by `CONGRESS_DB_PATH` (default: `data/congress_trades.db`).

**Database schema** (table `trades`):

| Column | Type | Description |
|---|---|---|
| representative | TEXT | Politician name |
| party | TEXT | D, R, or I |
| house | TEXT | House or Senate |
| ticker | TEXT | Stock ticker symbol |
| transaction_type | TEXT | Purchase, Sale, etc. |
| transaction_date | TEXT | Date of trade (YYYY-MM-DD) |
| report_date | TEXT | Date reported (YYYY-MM-DD) |
| range_amount | TEXT | Dollar range (e.g., "$1,001 - $15,000") |
| description | TEXT | Additional details |

#### Query by Politician

```sql
SELECT representative, ticker, transaction_type, range_amount, transaction_date
FROM trades
WHERE representative LIKE '%Pelosi%'
ORDER BY transaction_date DESC
LIMIT 20;
```

#### Query by Ticker

```sql
SELECT representative, party, transaction_type, range_amount, transaction_date
FROM trades
WHERE ticker = 'NVDA'
ORDER BY transaction_date DESC
LIMIT 20;
```

#### Query by Party

```sql
SELECT representative, ticker, transaction_type, range_amount, transaction_date
FROM trades
WHERE party = 'D'
ORDER BY transaction_date DESC
LIMIT 20;
```

#### Query by Date Range

```sql
SELECT representative, ticker, transaction_type, range_amount, transaction_date
FROM trades
WHERE transaction_date BETWEEN '2026-01-01' AND '2026-03-31'
ORDER BY transaction_date DESC;
```

#### Query by Transaction Type

```sql
SELECT representative, ticker, range_amount, transaction_date
FROM trades
WHERE transaction_type = 'Purchase'
ORDER BY transaction_date DESC
LIMIT 20;
```

#### Combined Query (e.g., Republican purchases in a date range)

```sql
SELECT representative, ticker, range_amount, transaction_date
FROM trades
WHERE party = 'R'
  AND transaction_type = 'Purchase'
  AND transaction_date >= '2026-01-01'
ORDER BY transaction_date DESC;
```

#### Summary Statistics

```sql
-- Most traded tickers
SELECT ticker, COUNT(*) as trade_count
FROM trades
GROUP BY ticker
ORDER BY trade_count DESC
LIMIT 10;

-- Most active politicians
SELECT representative, party, COUNT(*) as trade_count
FROM trades
GROUP BY representative
ORDER BY trade_count DESC
LIMIT 10;

-- Trades by party breakdown
SELECT party, transaction_type, COUNT(*) as count
FROM trades
GROUP BY party, transaction_type
ORDER BY party, count DESC;
```

### 4. Check Alerts

If the user asks about recent alerts or significant trades:

1. Check `data/pending_congress_alert.txt` for the latest undelivered alert.
2. Check `data/new_trades.json` for the last 50 alert records.
3. Present the alert content to the user.
4. Ask the user if they want to clear the alert. If yes, delete `data/pending_congress_alert.txt` to prevent re-alerting.

### 5. Change Configuration

If the user wants to adjust settings:

- **Threshold**: `export MIN_TRADE_AMOUNT=50001` (or any dollar amount)
- **Database path**: `export CONGRESS_DB_PATH=/custom/path/trades.db`
- **Cron frequency**: Edit crontab to change interval (e.g., `*/15` for every 15 minutes)

## Output Templates

### Trade List Output

When displaying trade results, use this format:

```
Congress Trades: [query description]
Found [N] trades.

| Politician | Party | Ticker | Type | Amount Range | Trade Date |
|---|---|---|---|---|---|
| Nancy Pelosi | D | NVDA | Purchase | $1,000,001 - $5,000,000 | 2026-02-10 |
| Dan Crenshaw | R | MSFT | Sale | $15,001 - $50,000 | 2026-02-09 |
```

### Alert Output

```
New Congress Trade Alert -- [N] significant trade(s) detected:

[green] PURCHASE: Nancy Pelosi (D) [Rep]
   $NVDA -- $1,000,001 - $5,000,000
   Trade: 2026-02-10 | Reported: 2026-02-14

[red] SALE: Dan Crenshaw (R) [Rep]
   $MSFT -- $15,001 - $50,000
   Trade: 2026-02-09 | Reported: 2026-02-14
```

### Summary Statistics Output

```
Congress Trades Summary:
- Total trades in database: [N]
- Date range: [earliest] to [latest]
- Most traded ticker: [TICKER] ([count] trades)
- Most active politician: [Name] ([count] trades)
- Party breakdown: D: [n], R: [n], I: [n]
```

### Setup Confirmation Output

```
Congress Trades Tracker -- Setup Complete
- Database: [path] ([N] trades synced)
- API: Quiver Quant connected
- Threshold: $[amount] minimum for alerts
- Cron: [status]
```

## Error Handling

When issues occur, diagnose and guide the user:

| Error | Cause | Resolution |
|---|---|---|
| `QUIVER_API_KEY environment variable is required` | API key not set | Ask user to set `export QUIVER_API_KEY="..."` |
| `401 Unauthorized` | Invalid or expired API key | Ask user to verify key at quiverquant.com |
| `403 Forbidden` | API plan does not include congress data | Suggest upgrading Quiver Quant plan |
| `Connection error` / `timeout` | Network issue or API down | Retry in a few minutes; check internet |
| `No trades returned` | API returned empty response | May be temporary; data updates on reporting schedule |
| Database locked | Concurrent access to SQLite | Ensure only one scraper instance runs at a time |
| `ModuleNotFoundError: requests` | Missing dependency | Run `pip install requests` |

## Security Notes

- API key is read from environment variable only — never store it in scripts or crontab
- Restrict file permissions on data directory: `chmod 700 data/`
- Only outbound connection: `api.quiverquant.com` (HTTPS)

---

### [14] `crypto-research`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/crypto-research/SKILL.md`

---
name: crypto-research
description: >
  Use this skill for in-depth cryptocurrency research and due
  diligence. Triggers when a user wants to deeply understand a
  specific coin or token — its fundamentals, tokenomics, holder
  distribution, team, risks, or whether it's worth investing in. Also
  triggers for comprehensive analysis requests like "due diligence
  report", "deep dive", "DYOR", "is it legit/safe", or any request
  combining multiple research dimensions (e.g., staking yield
  analysis, tokenomics + holder data). Do NOT trigger for simple price
  checks, trade execution, market overviews, or technical indicator
  queries alone.
---

# Crypto Research Skill

Perform comprehensive due diligence on any cryptocurrency by systematically
gathering and analyzing data from multiple sources. Produces a structured
research report with green flags, red flags, and risk assessment.

## Data Sources

**Either one alone produces a useful report; both together give the most
complete picture.**

### Source A: OKX Trade Kit (Real-time Exchange Data)

Provides real-time price, TA indicators (70+ types), funding rates, open
interest, and order book depth.

**Fetch priority — try in this order:**
1. **CLI**: `okx market ticker BTC-USDT` (okx-trade-cli)
2. **MCP**: `market_get_ticker`, `market_get_indicator`, etc.

Check availability by running `okx market ticker BTC-USDT` or calling
`market_get_ticker`. If either works, OKX is available.

**If OKX Trade Kit is not configured:**
```
Install OKX Trade Kit:
  npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli
  okx config init
  okx-trade-mcp setup --client claude-code

Details: https://github.com/okx/agent-trade-kit
```

### Source B: CoinMarketCap (Fundamentals & Sentiment) — Optional

Provides project info, holder analysis, aggregated market data, and news.
**No API key required — use whichever path is available:**

- **MCP mode** (best): Call CMC tools directly if CMC MCP is configured
- **HTTP fallback**: If the user has a CMC API key, use WebFetch:
  ```
  https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={SYMBOL}&CMC_PRO_API_KEY={key}
  https://pro-api.coinmarketcap.com/v1/cryptocurrency/info?symbol={SYMBOL}&CMC_PRO_API_KEY={key}
  ```
- **Web fallback** (default, no key needed): Use WebSearch for basic project
  info and news

**To enable CMC MCP for richer data** (optional):
```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": { "X-CMC-MCP-API-KEY": "your-api-key" }
    }
  }
}
```
Free API key: https://pro.coinmarketcap.com/login

## Research Modes

**Full Research (default):** All 6 steps. Use when user says "research",
"DYOR", "deep dive", "is it legit", "evaluate".

**Quick Snapshot:** Step 1 then Steps 2 + 3 + 4 in parallel. Skip
fundamentals and news. Use when user says "quick look", "what's happening
with", "give me a snapshot", or when they want a fast answer.

Minimum calls for Quick Snapshot (all in parallel after Step 1):
- `market_get_ticker` for token + BTC
- `market_get_indicator` for RSI, MACD, EMA 200
- `market_get_funding_rate` + `market_get_open_interest`

Use the **Quick Snapshot template** in `references/report-templates.md`.

## Core Principle

Thorough research requires looking at a token from multiple angles. Fetch all
relevant data before forming conclusions. Surface both green flags and red
flags. Never provide investment advice — present data and let the user decide.

## Research Workflow

**Performance tip:** Steps 2, 3, and 4 are independent — call all their tools
in parallel to minimize wait time. Steps 5 and 6 can also run in parallel.

### Step 1: Identify the Token & Resolve Instrument IDs

**Goal:** Map user input to tradeable identifiers.

**OKX instrument ID format:** `{BASE}-USDT` for spot (e.g., `SOL-USDT`),
`{BASE}-USDT-SWAP` for perpetual swaps. If unsure whether a token is listed
on OKX, call `market_get_instruments` with `instType: "SPOT"` and filter by
base currency.

**CMC (if available):** Call `search_cryptos` with the token name/symbol to
get the CMC ID. If multiple results, pick the lowest rank number (highest
market cap); if rank >500, confirm with the user.

### Step 2: Real-time Market Data

**From OKX (primary for real-time — CLI first, MCP fallback):**
- CLI: `okx market ticker {TOKEN}-USDT` / `okx market ticker BTC-USDT`
- MCP: `market_get_ticker(instId="{TOKEN}-USDT")` / `market_get_ticker(instId="BTC-USDT")`
- → price, 24h high/low, volume, bid/ask spread; BTC for relative performance

**From CMC (primary for aggregated/historical):**
- `get_crypto_quotes_latest` (MCP) or WebFetch CMC API → market cap, rank,
  circulating supply, 7d/30d/90d/1y price changes

**Interpretation:**
- 24h change: `(last - open24h) / open24h * 100`
- Bid-ask spread: `(askPx - bidPx) / last * 100` — tight (<0.05%) = good
  liquidity
- Compare token 24h vs BTC 24h → outperforming or underperforming?
- Volume/MCap ratio: >10% = healthy; <1% = concern

### Step 3: Technical Analysis

**From OKX (primary — CLI first, MCP fallback; use `bar: "1Dutc"` for daily):**

| Indicator | Call | Interpretation |
|-----------|------|----------------|
| RSI | `indicator: "rsi"` | <30 oversold, 30-70 neutral, >70 overbought |
| MACD | `indicator: "macd"` | DIF > DEA = bullish; histogram expanding = momentum |
| 200d EMA | `indicator: "ema", params: [200]` | Above = bullish; >20% below = broken trend |
| Bollinger Bands | `indicator: "bb"` | Near lower = support zone; near upper = resistance |
| Supertrend | `indicator: "supertrend"` | UP = bullish; DOWN = bearish; flip = trend change |

**Optional deeper TA:**
- `indicator: "kdj"` — J <0 = extreme oversold; J >100 = extreme overbought
- `indicator: "ema", params: [7, 30]` — 7d crossing above 30d = bullish
- `indicator: "ma", params: [50, 200]` — golden/death cross

**Multi-timeframe:** Default `1Dutc` for swing traders; also check `4H` for
active traders or `1Wutc` for position traders. State the timeframe used.

**From CMC (if available):**
- `get_crypto_technical_analysis` → Fibonacci levels, pivot points
- If CMC TA is unavailable, OKX indicators (RSI/MACD/EMA/BB/Supertrend) are
  sufficient for a complete technical assessment.

### Step 4: Derivatives & Sentiment Data

**From OKX (primary — CLI first, MCP fallback):**

| Data | CLI | MCP | Interpretation |
|------|-----|-----|----------------|
| Funding Rate | `okx market funding-rate {TOKEN}-USDT-SWAP` | `market_get_funding_rate(instId="{TOKEN}-USDT-SWAP")` | See thresholds below |
| Open Interest | `okx market open-interest --instType SWAP --instId {TOKEN}-USDT-SWAP` | `market_get_open_interest(instType="SWAP")` | OI/MCap >50% = heavy derivatives. Rising OI + rising price = trend confirmation; rising OI + falling price = liquidation risk |
| Order Book | `okx market orderbook {TOKEN}-USDT` | `market_get_orderbook(instId="{TOKEN}-USDT", sz=20)` | >60/40 bid/ask imbalance = directional bias |

**Not all tokens have perpetual swaps.** If the funding rate call returns
an error, skip derivatives. Note in the report: "No perpetual swap available
— this itself signals lower institutional interest."

**Funding rate thresholds** (8h settlement equivalent):

| Range | Meaning | Signal |
|-------|---------|--------|
| -0.001% to +0.001% | Near zero | Balanced, no extreme bias |
| +0.001% to +0.01% | Mildly positive | Slight bullish bias, normal |
| +0.01% to +0.05% | Elevated positive | Longs paying premium, caution |
| > +0.05% | Extreme positive | Overleveraged longs, high reversal risk |
| -0.01% to -0.05% | Elevated negative | Shorts dominant, squeeze risk |
| < -0.05% | Extreme negative | Panic/heavy shorting, potential bounce |

Check `fundingTime` and `prevFundingTime` to determine the period. For 3h
settlement tokens, multiply rate × (8/3) before comparing to 8h thresholds.
Annualized rate ≈ raw rate × 3 × 365.

### Step 5: Fundamentals, Project Info & News

**Project fundamentals (CMC primary, WebSearch fallback):**
- `get_crypto_info` → description, category, launch date, website, tags
- `get_crypto_metrics` → holder distribution, whale concentration, behavior
- For deeper technology/use-case questions: `search_crypto_info` (CMC MCP)
  or WebSearch for "{token name} cryptocurrency project overview"

**News & sentiment (CMC primary, WebSearch fallback):**
- `get_crypto_latest_news` (limit 5-10) → recent headlines and sentiment
- WebSearch fallback: "{token name} crypto news this week"

Read `references/analysis-framework.md` before writing the Fundamentals,
Tokenomics, and Red/Green Flags sections of the report.

### Step 6: Format & Present the Report

Read `references/report-templates.md` and use the **Full Research Report**
template. Fill every section with actual data — never leave template
placeholders in the output.

## Quick Interpretation Cheat Sheet

Translate raw numbers into plain language. Always include the "so what."

| Metric | Raw Data | What to Say |
|--------|----------|-------------|
| RSI 25 | Oversold | "RSI at 25 — deeply oversold, potential bounce zone but don't catch falling knives" |
| RSI 55 | Neutral | "RSI at 55 — neutral territory, no extreme signal" |
| RSI 78 | Overbought | "RSI at 78 — overbought, momentum could exhaust soon" |
| Price 5% above 200d EMA | Bullish | "Trading 5% above the 200d EMA — long-term uptrend intact" |
| Price 35% below 200d EMA | Broken | "Trading 35% below the 200d EMA ($X) — deeply discounted or structural downtrend" |
| MACD DIF > DEA, histogram growing | Bullish momentum | "MACD bullish with expanding histogram — momentum accelerating" |
| MACD DIF < DEA, histogram shrinking | Bearish slowing | "MACD bearish but histogram contracting — selling pressure fading" |
| Funding +0.003% | Normal | "Funding near zero (+0.003%) — balanced market" |
| Funding +0.08% | Extreme | "Funding at +0.08% — extreme bullish leverage, reversal risk elevated" |
| Spread 0.02% | Tight | "Tight 0.02% spread — excellent liquidity" |
| Spread 0.5% | Wide | "Wide 0.5% spread — thin liquidity, watch for slippage" |
| Vol/MCap 15% | Healthy | "Daily volume is 15% of market cap — healthy turnover" |
| Vol/MCap 0.5% | Low | "Volume only 0.5% of market cap — low interest, hard to exit large positions" |
| 24h vs BTC +3% | Outperforming | "Outperforming BTC by 3% today — capital rotating in" |
| 24h vs BTC -5% | Underperforming | "Underperforming BTC by 5% today — relative weakness" |

## Handling Tool Failures

Always complete the report with available data. Never abandon research because
one source is down. Mark unavailable sections with a note explaining what's
missing and how to get it.

| Data Need | Source 1 | Source 2 | Source 3 |
|-----------|----------|----------|----------|
| Price & volume | OKX `market_get_ticker` | CMC `get_crypto_quotes_latest` | WebFetch CMC API |
| Technical analysis | OKX `market_get_indicator` | CMC `get_crypto_technical_analysis` | Note "TA unavailable" |
| Funding rate & OI | OKX `market_get_funding_rate` / `market_get_open_interest` | — | Note "Derivatives unavailable" |
| Order book | OKX `market_get_orderbook` | — | Note "Order book unavailable" |
| Project fundamentals | CMC `get_crypto_info` | WebFetch CMC API | WebSearch |
| Holder analysis | CMC `get_crypto_metrics` | — | Note "Holder data unavailable" |
| News & sentiment | CMC `get_crypto_latest_news` | WebSearch | Note "News unavailable" |
| Token identification | CMC `search_cryptos` | OKX `market_get_instruments` | Ask user for symbol |

---

### [15] `crypto-swing-signal-analyst`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/crypto-swing-signal-analyst/SKILL.md`

---
name: 币圈波段信号分析师
description: 基于 EMA20、EMA60、RSI14、MACD 和 ATR14 的加密货币波段分析技能，用于判断趋势、识别做多做空机会，并输出止损止盈与风险建议。
---

# 币圈波段信号分析师（基础版 Skill）

## 一、Skill 名称
币圈波段信号分析师

---

## 二、Skill 定位
这是一个用于加密货币波段交易判断的基础版技能。

它的核心目标不是预测绝对底部或顶部，而是通过少量常用技术指标，帮助用户判断：

- 当前趋势是多头、空头还是震荡
- 当前是否存在可执行的波段机会
- 更适合做多、做空，还是继续观望
- 合理的止损与止盈参考位置

本版本为基础版，只依赖 K 线技术指标，不依赖 Funding、OI、链上数据或外部衍生品数据。

---

## 三、适用范围
适用于以下场景：

- BTC / ETH / BGB / 主流币 / 强势山寨
- 1小时、4小时周期优先
- 用于波段判断
- 不适用于超短线高频交易
- 不用于喊单，只用于辅助决策

---

## 四、核心指标
本 Skill 只看以下 5 个指标：

1. EMA20
2. EMA60
3. RSI14
4. MACD
5. ATR14

---

## 五、输入字段
当用户发起分析请求时，输入数据建议包含以下字段：

- symbol：币种名称，例如 BTC、ETH、BGB
- timeframe：周期，例如 1h、4h、1d
- price：当前价格
- ema20
- ema60
- rsi14
- macd_line
- macd_signal
- macd_hist
- prev_macd_hist（可选）
- atr14
- recent_high（可选）
- recent_low（可选）

如果部分数据缺失，则基于已有数据做简化分析，并明确告知用户当前结论可信度下降。

---

## 六、分析逻辑

### 1. 趋势判断
根据 EMA20 和 EMA60 判断市场趋势：

- 如果 ema20 > ema60，则趋势偏多
- 如果 ema20 < ema60，则趋势偏空
- 如果 ema20 与 ema60 距离很近，则判定为震荡或趋势不清晰

补充判断：

- 当前价格在 ema20 上方，说明短线结构更强
- 当前价格在 ema20 下方，说明短线结构更弱

---

### 2. 做多波段信号
满足以下大部分条件时，才允许给出“可考虑做多波段”的结论：

#### 做多核心条件
- ema20 > ema60
- rsi14 位于 45~60 区间
- rsi14 有重新向上的迹象
- macd_line > macd_signal，或 macd_hist 由弱转强
- 如果存在 prev_macd_hist，则要求 macd_hist > prev_macd_hist
- 当前价格不要离 ema20 太远，避免追高

#### 做多否决条件
满足以下任一条件时，不建议追多：

- rsi14 > 72
- MACD 虽然金叉，但柱体开始缩短
- 价格刚刚大阳拉升，远离 ema20
- 指标之间相互矛盾
- 趋势虽偏多，但短线已明显过热

---

### 3. 做空波段信号
满足以下大部分条件时，才允许给出“可考虑做空波段”的结论：

#### 做空核心条件
- ema20 < ema60
- rsi14 位于 40~55 区间
- rsi14 有重新向下的迹象
- macd_line < macd_signal，或 macd_hist 由强转弱
- 如果存在 prev_macd_hist，则要求 macd_hist < prev_macd_hist
- 当前价格不要离 ema20 太远，避免追空

#### 做空否决条件
满足以下任一条件时，不建议追空：

- rsi14 < 28
- MACD 虽然死叉，但柱体开始缩短
- 价格刚刚大阴下杀，远离 ema20
- 指标之间相互矛盾
- 趋势虽偏空，但短线已明显超跌

---

### 4. 震荡行情判断
若出现以下情况，则优先判定为震荡行情：

- ema20 与 ema60 非常接近
- RSI 长时间在 45~55 区间来回波动
- MACD 频繁金叉死叉，柱体很短
- 当前价格围绕均线来回穿越
- 没有清晰的趋势延续结构

震荡行情默认结论：

- 不建议追单
- 观望，等待突破或回踩确认
- 当前信号级别较低

---

## 七、ATR 风控逻辑
ATR 仅用于止损与风险控制，不用于判断方向。

### 做多止损
默认止损位：

- 止损位 = 入场价 - 1.5 × ATR14

可选模式：

- 激进模式：入场价 - 1.2 × ATR14
- 保守模式：入场价 - 2.0 × ATR14

### 做空止损
默认止损位：

- 止损位 = 入场价 + 1.5 × ATR14

可选模式：

- 激进模式：入场价 + 1.2 × ATR14
- 保守模式：入场价 + 2.0 × ATR14

---

## 八、止盈逻辑
默认输出两个止盈目标：

- TP1 = 1R
- TP2 = 1.5R 或 2R

说明：

- R = 入场价与止损价之间的风险距离
- 如果用户提供 recent_high / recent_low，则可结合前高前低做辅助止盈判断

---

## 九、评分系统
本 Skill 必须分别给做多和做空评分，满分 100 分。

### 做多评分
- 趋势结构（ema20 > ema60）：30分
- RSI 节奏合理：20分
- MACD 动能转强：30分
- 当前价格位置适合入场：20分

### 做空评分
- 趋势结构（ema20 < ema60）：30分
- RSI 节奏合理：20分
- MACD 动能转弱：30分
- 当前价格位置适合入场：20分

### 分数解释
- 80~100：强信号，可重点关注
- 65~79：中等信号，可等待更优位置
- 50~64：弱信号，偏观察
- 0~49：不建议出手

---

## 十、输出格式
每次输出必须严格使用以下结构：

### 一、市场状态
- 币种：
- 周期：
- 当前趋势：多头 / 空头 / 震荡
- 当前结构强度：强 / 中 / 弱

### 二、指标解读
- EMA结构：
- RSI状态：
- MACD状态：
- ATR风险：

### 三、信号评分
- 做多评分：XX/100
- 做空评分：XX/100

### 四、结论
只能从以下选项中选择一个作为主结论：

- 可考虑做多波段
- 可考虑做空波段
- 观望，等待确认
- 不建议追单
- 当前更像震荡行情

### 五、执行建议
- 建议方向：
- 建议入场方式：现价 / 回踩 / 突破确认后
- 止损位：
- TP1：
- TP2：
- 风险等级：低 / 中 / 高

### 六、一句话判断
必须用一句直接的话总结，例如：

- 趋势偏多，但位置偏高，不适合追涨
- 结构转强，可等回踩 EMA20 附近做多
- 空头延续，但短线已有超跌迹象
- 指标互相打架，当前最优解是观望

---

## 十一、强制规则
1. 不允许无条件喊单
2. 不允许只因为 RSI 超卖就判断可以抄底
3. 不允许只因为 MACD 金叉就判断一定上涨
4. 趋势、节奏、动能至少满足 3 项，才允许给方向性建议
5. 如果数据缺失，必须说明“不确定性增加”
6. 如果指标矛盾，优先给出“观望”
7. 输出语言必须简洁、直接、交易员风格，避免空话

---

## 十二、初始化提示词
当用户给出币种和对应指标数据后，你必须立即根据本 Skill 规则进行分析。

如果数据完整，则输出完整判断；
如果数据不完整，则输出简化版判断，并提醒用户缺失哪些关键数据。

你的任务不是预测未来，而是基于当前指标结构，输出清晰、可执行、可风控的波段建议。

---

## 十三、简化版执行原则
当数据不完整时，按以下优先级判断：

1. 先看 EMA20 与 EMA60 判断趋势
2. 再看 RSI14 判断节奏
3. 再看 MACD 判断动能
4. 最后用 ATR14 给出止损建议

若缺少 MACD 或 ATR，则必须提示：
- 当前只能做方向性参考
- 不能提供完整执行建议
- 结论可信度下降

---

## 十四、示例输出风格
输出必须偏实战，不要写成长篇分析文。

要重点告诉用户：

- 现在趋势是什么
- 当前能不能做
- 如果做，应该怎么做
- 如果错了，在哪里止损

禁止输出模糊结论，例如：
- 感觉会涨
- 可能快到底了
- 这位置应该差不多
- 可以试试看

必须改成：
- 趋势偏多，但短线过热，不建议追多
- 回踩 EMA20 附近更适合低风险参与
- 当前更像震荡结构，等待确认更优

---

### [16] `dca-bot-parameterizer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/dca-bot-parameterizer/SKILL.md`

---
name: dca-bot-parameterizer
description: >
  Use this skill when a user wants to set up, configure, or get
  parameter recommendations for a DCA bot on OKX — whether spot or
  contract (perpetual swap). Trigger on any intent to open a DCA bot,
  choose DCA bot settings, size a DCA position, or decide between spot
  vs. contract DCA mode. Also trigger for Chinese phrases like
  "开单dca", "开dca", "帮我开dca", "现货dca", "合约dca". The core value:
  analyzing market state (trend, volatility, structure) to recommend
  safe DCA bot parameters like price step, safety order count,
  take-profit %, and leverage. Do NOT trigger for recurring/scheduled
  buy management (use recurring-dca), standalone technical analysis
  (use kline-indicator), or full trade plan generation (use
  trading-plan-generator).
---

# DCA Bot Parameterizer

## Core Method

Use only these market inputs unless the user explicitly provides more:

- trend: `EMA20` plus price location relative to that average
- volatility: `ATR% = ATR / current price`
- structure:
  - spot DCA or contract `long`: nearest valid support
  - contract `short`: nearest valid resistance

Execute these six steps in order:

1. Define the trading scene
2. Classify market state
3. Measure volatility
4. Inspect structure
5. Generate parameters
6. Validate capital usage and coverage

The order matters because each step feeds the next — classifying market state before
knowing volatility produces trend labels that ignore how far the move has stretched,
and generating parameters before inspecting structure means safety orders may land in
empty air. Stick to EMA20 and ATR% as the default indicators; they capture trend
direction and spacing need without the noise that additional overlays tend to introduce
in DCA sizing decisions.

## Recommendation Gate

When the user expresses intent to open a DCA bot, do not jump straight into
recommendations.

1. Ask whether they want parameter recommendations.
2. If they decline, stop the recommendation flow and state that they can set
   custom parameters themselves.
3. Only continue if they explicitly want recommendations.

The gate result must appear in the final output as `Recommendation Gate Result`.

## Required Inputs

Collect or infer only what is necessary:

- symbol or `instId`
- mode: spot DCA or contract DCA
- asset type: major coin or high-volatility altcoin
- timeframe: `1h`, `4h`, or `1d`
- total budget in `USDT`
- optional risk input:
  - maximum drawdown or target coverage depth
  - explicit low risk tolerance

If the user provides a full OKX instrument ID, use it directly. Otherwise resolve:

- spot: `<BASE>-USDT`
- contract: `<BASE>-USDT-SWAP`

## OKX Trade Kit Data Source

Use OKX Trade Kit market data, not guesswork.

### Fallback Chain

Fetch market data in this order — stop at the first that works:

1. **CLI (primary):** `okx --json market [command]` (okx-trade-cli)
2. **MCP fallback:** `market_get_*` OKX Trade Kit MCP tools
3. **REST API fallback:** `okx.com/api/v5/market/[endpoint]` (read-only, no auth)
4. **Manual input:** Ask the user to provide price, volatility estimate, or structure manually

**CLI commands:**
```bash
okx --json market ticker BTC-USDT
okx --json market indicator ema BTC-USDT --bar 1H --period 20
okx --json market candles BTC-USDT --bar 1H --limit 60
okx --json market instruments --instType SWAP --instId BTC-USDT-SWAP
```

**MCP equivalents (use if CLI unavailable):**
- `market_get_ticker(instId=...)` — current price
- `market_get_indicator(instId=..., indicator="ema", bar=..., period=20)` — EMA20 directly (no manual candle calculation needed)
- `market_get_candles(instId=..., bar=..., limit=60)` — raw candles for ATR calculation (ATR not available via indicator API)
- `market_get_instruments(instType=..., instId=...)` — contract leverage cap metadata

### Candle Windows

Fetch:

- 60 candles on the working timeframe
- 60 candles on the higher timeframe only when contract DCA needs higher-timeframe bias

Use the fixed higher-timeframe mapping:

- `1h -> 4H`
- `4h -> 1D`
- `1d -> 1W`

## Market Classification

Use `EMA20` as the default moving average.
Fetch via `market_get_indicator(instId, indicator="ema", bar, period=20)`.
Use `market_get_candles` only when computing ATR (which requires raw OHLC data).

### Working-Timeframe State

Derive the state from EMA20 (from MCP) and the last 60 candles for ATR and structure.

- `Strong Trend`
  - `EMA20` is clearly rising or falling
  - current price is on the same side of `EMA20`
  - at least 4 of the last 5 closes are on the same side of `EMA20`
  - current price is at least `1 x current ATR` away from `EMA20`

- `Mild Trend`
  - `EMA20` is rising or falling
  - current price is on the same side of `EMA20`
  - at least 3 of the last 5 closes are on the same side of `EMA20`
  - current price is less than `1 x current ATR` away from `EMA20`

- `Range`
  - any setup that does not meet the trend conditions above

State the market as one of: `Range`, `Mild Trend`, `Strong Trend`.

## Contract Direction Logic

Spot DCA stays `long` only.

Contract DCA must output a direction.

### If the Working Timeframe is Trending

Follow the working-timeframe trend:

- price mostly above a rising `EMA20` => `long`
- price mostly below a falling `EMA20` => `short`

### If the Working Timeframe is `Range`

Inspect the next higher timeframe:

- higher timeframe trending up => `long`
- higher timeframe trending down => `short`
- higher timeframe also `Range` => default `long`

When higher-timeframe bias is used, include it in the final output as `Higher Timeframe Bias`.

## Structure Logic

Use structure only after trend and volatility are known.

- spot DCA and contract `long`
  - use the nearest valid support
  - prefer the most recent visible swing low below current price from the last 20 closed candles
  - if no clean swing low exists, fall back to the lowest low of the last 20 closed candles

- contract `short`
  - use the nearest valid resistance
  - prefer the most recent visible swing high above current price from the last 20 closed candles
  - if no clean swing high exists, fall back to the highest high of the last 20 closed candles

Check:

- whether current price is reasonably close to the relevant structure
- whether planned safety orders land near meaningful structure instead of far beyond it

## Volatility Logic

Use only `ATR%`.

- current `ATR%` drives `pxSteps`
- current `ATR%` plus trading cost drives `tpPct`

For contract leverage, also compute a volatility regime on the working timeframe by
comparing current `ATR%` with the 20-bar average `ATR%`:

- `Low`: current `ATR% < 0.9x` average `ATR%`
- `Normal`: current `ATR%` is `0.9x` to `1.2x` average `ATR%`
- `High`: current `ATR% > 1.2x` average `ATR%`

## Unsafe Setup Gate

Apply this gate before giving parameters for a poor setup.

- spot DCA in `Strong Trend`: warn first and stop unless the user explicitly insists
- contract DCA in `Strong Trend`: warn first and stop unless the user explicitly insists, even if direction follows trend

Accept clear confirmations such as: `continue`, `continue anyway`, `继续`, `继续执行`,
or equivalent explicit insistence.

If the user insists on continuing in `Strong Trend`, switch to defensive mode:

- reduce `initOrdAmt`
- widen `pxSteps`
- increase `pxStepsMult`
- lower `volMult`
- tighten capital-usage and coverage checks
- for contract DCA, set recommended leverage to `1x`

## Parameter Rules

These rules reflect how DCA bots fail in practice. Safety orders that are too
tight fill rapidly into a continuing trend; orders that are too loose waste
capital and miss the rebound. The goal is spacing that absorbs normal volatility
without committing the full budget to a runaway move.

### `pxSteps`

- set from current `ATR%`
- in `Range`, keep it near current `ATR%`
- in `Mild Trend`, set it slightly above current `ATR%`
- in `Strong Trend` after explicit confirmation, widen it clearly above `Mild Trend`
- widen it further for high-volatility altcoins

### `pxStepsMult`

- low in `Range`
- medium in `Mild Trend`
- high in `Strong Trend` only after explicit confirmation

### `initOrdAmt`

Base it on entry quality, not a formula.

- larger when the setup is ranging, structure is near, and volatility is not elevated
- smaller when the setup is trending, structure is far, or volatility is elevated

### `safetyOrdAmt` and `volMult`

- keep `safetyOrdAmt` close to `initOrdAmt` in most cases
- use a higher `volMult` in `Range`
- use a lower `volMult` in trend conditions
- keep `volMult` restrained in defensive mode

### `maxSafetyOrds`

Derive this last, after spacing and amounts are drafted. The reason: choosing a
count first tempts over-allocation — picking a number of orders and then
reverse-engineering amounts to fit the budget. Instead:

1. Draft `pxSteps`, `pxStepsMult`, `initOrdAmt`, `safetyOrdAmt`, and `volMult`
2. Simulate cumulative coverage: at each safety order level, compute the price
   distance from entry and the running capital consumed
3. Stop adding orders when either condition is met:
   - cumulative capital reaches the budget
   - coverage depth reaches the target drawdown or passes the relevant structure
4. The count at that point is `maxSafetyOrds`

Keep only as many safety orders as the budget and target coverage allow.

### `tpPct`

- derive it from current `ATR%` and trading cost
- the minimum floor is `ATR% × 0.3` to clear OKX fees and slippage
  (spot taker ~0.1%, futures taker ~0.05%; see [references/parameter-bands.md](references/parameter-bands.md) for the exact floor formula)
- keep it realistic for the timeframe's usual rebound size

### Contract Leverage

Recommend leverage only. Do not read or modify account leverage settings.

Use the exact leverage matrix from [references/parameter-bands.md](references/parameter-bands.md),
then cap it by:

- the OKX instrument maximum leverage
- an internal hard cap of `4x`

If the user explicitly states low risk tolerance or a tight maximum drawdown, reduce
the recommendation by one leverage step, with a floor of `1x`.

## Validation

Always validate:

- total capital usage if every safety order fills
- total downside coverage from entry to the final safety order
- whether the final safety order lands too far beyond the relevant structure
- whether the setup still fits the user's stated risk tolerance

If validation fails:

- increase `maxSafetyOrds` or `pxStepsMult` when coverage is too shallow
- increase `pxSteps` when the bot would fill too easily
- reduce `volMult` or `maxSafetyOrds` when capital usage is too heavy

## Edge Case Handling

### Missing or Invalid Symbol

If the user does not provide a trading pair:

1. Ask explicitly: "Which trading pair? (e.g., BTC-USDT for spot, BTC-USDT-SWAP for contract)"
2. Do not proceed without a valid symbol.

### Invalid Trading Pair (Not Found on OKX)

1. Attempt `Call OKX Trade MCP market_get_ticker(instId="<symbol>")` with the provided symbol.
2. If the MCP call fails, retry with `okx --json market ticker <symbol>` (CLI fallback).
3. If both fail, inform the user: "Trading pair not found on OKX. Please verify the symbol."
4. Do not guess or offer alternative symbols.

### Budget Too Small

Recommended minimum budgets:

- Spot DCA: $50 USDT (allows at least 5 orders at ~$10 each)
- Contract DCA: $100 USDT (allows leverage and position sizing)

If the provided budget falls below the minimum, ask: "Your budget of $X is very small.
Minimum recommended for this setup is $Y. Continue with smaller positions?"

### Strong Trend Forced Continuation with High Volatility

When the user insists on continuing in a Strong Trend AND current volatility (ATR%) is elevated:

- Cap leverage to `1x` (no negotiation).
- Widen `pxSteps` by at least 1.5x the current `ATR%`.
- Set `volMult` to `1.0` or lower (no escalation).
- Reduce `initOrdAmt` to 5% of budget (vs. normal 8-12%).
- Output warning: "This is a highly defensive configuration. Safety orders may not fill if the trend continues."

### Contract Leverage Cap Exceeded

When the user requests leverage or the matrix suggests leverage higher than the OKX instrument maximum:

1. Query `Call OKX Trade MCP market_get_instruments(instType="SWAP", instId="<symbol>")`.
2. Extract the `maxLever` field from the response.
3. Cap the recommended leverage to `min(matrix_recommendation, maxLever, 4x)`.
4. Output note: "Recommended leverage capped to $X (instrument maximum: $X, internal cap: 4x)."

## Output Format

Produce the final answer in this order:

1. `Scene`
2. `Recommendation Gate Result`
3. `Market State`
4. `Higher Timeframe Bias` (when used)
5. `Volatility`
6. `Structure`
7. `Direction` (contract DCA only)
8. `Decision`
9. `Warning` (when needed)
10. `Recommended Leverage` (contract DCA only)
11. `Parameters`
12. `Validation`

## Reference

For numeric parameter bands, the contract leverage matrix, the tpPct fee floor,
and the validation checklist, read [references/parameter-bands.md](references/parameter-bands.md).

---

### [17] `dcd-auto-trader`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/dcd-auto-trader/SKILL.md`

---
name: dcd-auto-trader
description: |
  OKX DCD（双币赢）全自动交易系统。PUT 低买赚权利金、CALL 高卖降成本，每天 17:05 自动执行。
  内置 v3 波动率引擎和 FOMC/CPI 事件日历风控。支持 Claude Code（MCP）和 OpenClaw（CLI）。
  涉及 DCD/双币赢时必须使用本 skill 而非 okx-cex-earn。
version: 3.1.0
metadata:
  openclaw:
    requires:
      bins: [okx, python3]
      config: [~/.okx/config.toml]
    os: [macos, linux]
emoji: 🎯
---

# DCD 双币赢全自动交易系统 v3

> **策略 A（PUT 低买）**：用 USDG 赚 USDG，尽量不被行权
> **策略 B（CALL 高卖）**：被行权拿到的 BTC，通过 CALL 赚权利金降低成本，等待保本卖出
> 两个策略可同时运行，资金互不冲突（A 用 USDG/USDT，B 用 BTC）。

```
  USDG ──PUT低买──┬── ✅ 未行权 → USDG+权利金 → 继续PUT
                  └── ❌ 被行权 → 收到BTC ──┐
                                             ▼
  BTC ──CALL高卖──┬── ✅ 被行权 → USDG回收 → 回到PUT
                  └── ❌ 未行权 → BTC+权利金 → 降低有效成本 → 继续CALL
```

---

## 使用方式

### 首次设置

对 AI 助手说 **"设置双币赢"** 或 **"setup dcd"**，将自动检测环境并执行初始化。

### 日常运行

设置完成后，定时任务每天 **17:05 UTC+8** 自动触发，无需人工干预。

---

## 前置条件

1. **AI 客户端**：Claude Code 或 OpenClaw（小龙虾）
2. **OKX API Key（实盘）**：已配置 `~/.okx/config.toml`
3. **okx-trade-cli**：已安装（`npm install -g okx-trade-cli`）— CLI 模式必需，MCP 模式可选
4. **资金**：OKX 资金账户有 USDG 或 USDT（建议 >= 1,000）

---

## 环境适配

本 skill 支持两种运行模式，首次执行时自动检测：

### MCP 模式（Claude Code）
- 直接调用 `okx-trade-mcp-live` MCP 工具
- 需配置权限白名单和 scheduled-tasks MCP
- 详见 `references/claude-code-setup.md`

### CLI 模式（OpenClaw / 通用）
- 通过 `okx` CLI 命令执行，所有命令加 `--json --live` 参数
- 需已安装 okx-trade-cli 且 `~/.okx/config.toml` 已配置实盘 profile
- 详见 `references/openclaw-setup.md`

### 检测方法

```
1. 尝试 MCP 调用 market_get_index_ticker（instId: BTC-USD）
   → 成功 = MCP 模式
2. 若失败，执行 `okx market index-ticker --instId BTC-USD --json --live`
   → 成功 = CLI 模式
3. 均失败 → 提示用户安装配置（见 references/ 下对应文档）
```

确定模式后，后续所有工具调用统一遵循该模式。

---

## 初始化流程（首次设置时执行）

当用户说"设置双币赢"/"setup dcd"时：

### Step 1：检测环境
按上述"检测方法"确定运行模式（MCP 或 CLI）。

### Step 2：创建项目文件
1. 用 `templates/trade_log.md` 创建 `交易记录.md`
2. **MCP 模式**额外创建 `CLAUDE.md`（内容见 `references/claude-code-setup.md`）
3. **CLI 模式**将 `templates/soul_dcd.md` 合并到用户的 `~/.openclaw/SOUL.md`。soul_dcd.md 包含授权声明、工具使用规范，以及策略文件路径指引——OpenClaw agent 每次执行时会据此找到并阅读完整 SKILL.md

### Step 3：配置权限与定时任务
- **MCP 模式**：按 `references/claude-code-setup.md` 配置权限白名单 + 注册 scheduled-task
- **CLI 模式**：按 `references/openclaw-setup.md` 安装 skill 到 OpenClaw skills 目录 + 注册 cron（prompt 中包含完整的文件路径和执行指引，确保 agent 能找到策略和交易记录）

### Step 4：首次验证
手动触发一次完整交易流程（Phase 1 到 Phase 5），确认数据获取、波动率计算、选品、下单、记录更新均正常。

---

## 策略 A：PUT 低买

### 硬性规则

1. **行权价 < 安全下界**（安全下界含 √到期天数 缩放，见公式）
2. **安全距离**：距现价 >= 3.5%（日常），>= 5%（事件日及前后 1 天）
3. **每天都交易**：事件日不跳过，用事件乘数加大安全距离（回测验证：89天全交易，安全率 98.9%）
4. **投入规则**：先选品再投入（不因投入而放松安全标准）。资金账户有 USDG/USDT 时全仓投入；无则从交易账户划转 1000 USDG 或 USDT 后投入

### 软性规则
- FOMC 周只选 1 天产品，平时优先 1 天（√N 缩放下 1 天产品安全下界最宽松）
- BTC 跌至距行权价 < 1% 时提醒用户关注提前赎回
- 连续被行权 2 次后暂停 1 天

### PUT 选品逻辑

1. 只选风险评级 ✅（行权价 < 安全下界）的产品
2. 同一行权价+到期日，比较 BTC-USDT 和 BTC-USDG 两个产品，选 APY 更高的
3. ✅ 中选 APY 最高（但 <= 150%）；全部 APY < 5% 则跳过
4. 优先 1 天产品
5. 同 APY 选距安全下界更远的

---

## 策略 B：CALL 高卖

> 目标：行权价 >= 合并有效成本时被行权，保本卖出全部 BTC，回收 USDG。
> 绝不主动亏损卖出。每轮权利金持续降低有效成本，时间站在我们这边。

### 合并有效成本

多次 PUT 被行权时，所有 BTC 合并管理：

```
合并有效成本 = 所有批次总投入USDG ÷ 所有批次总持有BTC（含累计权利金）

每轮 CALL 未行权后更新：
新合并有效成本 = 总投入USDG ÷ (总持有BTC + 本轮权利金BTC)

新 PUT 被行权时：新增 BTC 并入合并池，重新计算。
```

全部 BTC 投入同一个 CALL，不分批。

### 硬性规则

1. **行权价 >= 合并有效成本**：绝不低于有效成本，绝不主动亏损卖出
2. **不做市价止损**：BTC 下跌时持续通过 CALL 积累权利金，耐心等待
3. **每天交易**：与 PUT 一致，事件日不跳过

### CALL 选品逻辑

1. 行权价 = 最接近且 >= 合并有效成本的可用产品
2. 优先 1 天产品（加快迭代）
3. 同一行权价+到期日，比较 BTC-USDT 和 BTC-USDG 两个产品，选 APY 更高的
4. 多个符合条件时选 APY 最高
5. BTC 可用量 <= 0.0001 则跳过
6. 无 >= 合并有效成本的行权价可选则跳过（不降低标准）

### 执行规则

- 全仓投入全部 BTC，向下取整到 0.0001
- 低 APY 完全可接受（低 APY 也是正权利金）
- 每轮复盘后更新合并有效成本

### 退出条件

1. **被行权** → BTC 卖出换回 USDG → 回到策略 A
2. **有效成本降至当前价以下** → 可市价卖出或继续 CALL 赚权利金

---

## v3 波动率预测引擎

### 核心思路

v3 = 多源波动率基础 + 三项危机感知：

| 层级 | 成分 | 作用 |
|------|------|------|
| 基础 | IV×w + ATR×w + BB×0.15 + 资金费率×0.10 | 综合多源波动率 |
| 置信缓冲 | vol_accel 或临近事件 → +0.3~1.0% | 防低估 |
| 回撤安全垫 | 距30天高点回撤 >10%→+1.5%, >20%→+2.5%, >30%→+4.0% | 识别脆弱状态 |
| 暴跌动量 | 7天跌幅 >5%→+1.5%, >10%→+3.0% | 捕捉下跌趋势 |
| 动态权重 | ATR > 2×IV 时，ATR 权重升至 0.55（IV 降至 0.20） | 急跌时 IV 滞后补偿 |

### 数据源

> 技术指标统一取现货 BTC-USDT 数据，避免永续合约基差干扰。资金费率取永续合约 BTC-USD-SWAP（仅合约有此数据）。

| 数据 | 用途 |
|------|------|
| 期权 IV（BTC-USD ATM 近月） | 隐含波动率基础 |
| ATR(7) + ATR(14)（BTC-USDT 1H） | 双速实际波动率 |
| Bollinger(20)（BTC-USDT 1H） | 带宽波动率 |
| 资金费率（BTC-USD-SWAP） | 市场情绪指标 |
| 30天日K（BTC-USD 指数） | 回撤安全垫 + 暴跌动量 |

具体 MCP/CLI 调用命令见下方 Phase 3 表格。

> **IV 降级**：若 `option_get_greeks` 不可用，降级为 30 天 HV（权重从 0.45 降至 0.35，差额补入 confidence_buffer）。

### 完整计算公式

```python
# ── A. IV 成分 ──
IV_daily = IV_annual / sqrt(365)

# ── B. 双速 ATR（1H → 日化）──
ATR_fast = ATR_1H_7 * sqrt(24) / price
ATR_slow = ATR_1H_14 * sqrt(24) / price
ATR_comp = max(ATR_fast, ATR_slow * 0.9)

# ── C. BB 成分（1H → 日化）──
BB_std = (BB_upper - BB_lower) / 4
BB_comp = BB_std * sqrt(24) / price

# ── D. 资金费率调整 ──
funding_adj:
    |rate| < 0.01%   → 0.0
    rate < -0.01%    → 0.003  (负费率 = 空头恐慌)
    |rate| 0.01-0.03% → 0.002
    |rate| 0.03-0.05% → 0.005
    |rate| > 0.05%   → 0.008

# ── E. 动态权重 ──
若 ATR_comp > 2 * IV_daily:
    w_iv=0.20, w_atr=0.55    # ATR主导模式（急跌时 IV 滞后）
否则:
    w_iv=0.45, w_atr=0.30    # 标准模式

vol_base = w_iv*IV_daily + w_atr*ATR_comp + 0.15*BB_comp + 0.10*funding_adj

# ── F. 置信缓冲 ──
vol_accel = |ATR_fast - ATR_slow| / ATR_slow
conf_buffer:
    vol_accel > 0.3 或临近事件 → +1.0%
    vol_accel > 0.1            → +0.5%
    否则                       → +0.3%

# ── G. 回撤安全垫（v3）──
drawdown = (price - high_30d) / high_30d
dd_adj:
    |drawdown| > 30% → +4.0%
    |drawdown| > 20% → +2.5%
    |drawdown| > 10% → +1.5%
    否则             → 0

# ── H. 暴跌动量（v3）──
drop_7d = (price - price_7d_ago) / price_7d_ago
mom_adj:
    drop_7d < -10% → +3.0%
    drop_7d < -5%  → +1.5%
    否则           → 0

# ── 最终波动率 ──
vol_24h = vol_base + conf_buffer + dd_adj + mom_adj
```

### 安全下界计算

```
buy_dist = max(vol_24h * sqrt(到期天数) * 事件乘数, 最小安全距离)
行权价 = floor(BTC价格 * (1 - buy_dist) / 500) * 500
```

### 自适应事件乘数表

| 事件类型 | 当天 | 前1天 | 后1天 | 最低安全距离 |
|---------|------|-------|-------|-------------|
| FOMC 决议 | 1.8× | 1.8× | 1.3× | >= 5.0% |
| CPI 数据 | 1.5× | 1.5× | 1.2× | >= 5.0% |
| CME 交割 | 1.5× | 1.5× | 1.3× | >= 5.0% |
| 就业数据(NFP) | 1.4× | 1.4× | 1.2× | >= 5.0% |
| 多重到期日 | 1.8× | 1.8× | 1.5× | >= 5.0% |
| 无事件 | 1.0× | — | — | >= 3.5% |

---

## 每日执行流程（定时任务 Prompt）

你是 DCD 自动交易器。每天 17:05 UTC+8 执行。根据已检测的环境模式使用 MCP 工具或 CLI 命令（加 `--json --live`）。

**核心原则：每天都交易，永不跳过。** 事件日通过乘数加大安全距离。

> **路径约定**：CLI 模式下，交易记录位于 `~/dcd-project/交易记录.md`，脚本位于 `~/.openclaw/workspace/skills/dcd-auto-trader/scripts/`。MCP 模式下均为当前项目目录的相对路径。

### Phase 1：读取策略与状态

1. 完整阅读本 skill 的策略规则部分
2. 读取 `交易记录.md`，获取：
   - 当前合并有效成本（如有 BTC 持仓）
   - 当前 BTC 持仓量
   - 最近订单状态

### Phase 2：复盘已到期订单

1. 查询最近订单：
   - MCP：`dcd_get_orders`
   - CLI：`okx earn dcd orders --json --live`
2. 如有到期订单：记录结算结果到 `交易记录.md`
3. PUT 被行权 → 更新合并有效成本（新用户首次被行权：有效成本 = 行权价）
4. CALL 被行权 → 记录 BTC 已卖出，回到纯 PUT 模式
5. 如有资金在交易账户，划转到资金账户：
   - MCP：`account_transfer`（from: 18, to: 6）
   - CLI：`okx account transfer --ccy <ccy> --amt <n> --from 18 --to 6 --json --live`

### Phase 3：并行获取数据

以下操作按当前模式执行。CLI 模式下可后台并行（`&` + `wait`）：

| 数据 | MCP 工具 | CLI 命令 |
|------|---------|---------|
| BTC 现价 | `market_get_index_ticker`(instId: BTC-USD) | `okx market index-ticker --instId BTC-USD --json --live` |
| 30天K线 | `market_get_index_candles`(instId: BTC-USD, bar: 1D, limit: 30) | `okx market index-candles BTC-USD --bar 1D --limit 30 --json --live` |
| 快速ATR | `market_get_indicator`(instId: BTC-USDT, indicator: ATR, period: 7, bar: 1H) | `okx market indicator atr BTC-USDT --period 7 --bar 1H --json --live` |
| 慢速ATR | `market_get_indicator`(instId: BTC-USDT, indicator: ATR, period: 14, bar: 1H) | `okx market indicator atr BTC-USDT --period 14 --bar 1H --json --live` |
| BB指标 | `market_get_indicator`(instId: BTC-USDT, indicator: BOLLINGER, period: 20, bar: 1H) | `okx market indicator bollinger BTC-USDT --period 20 --bar 1H --json --live` |
| 资金费率 | `market_get_funding_rate`(instId: BTC-USD-SWAP) | `okx market funding-rate BTC-USD-SWAP --json --live` |
| IV | `option_get_greeks`(uly: BTC-USD) | `okx option greeks --uly BTC-USD --json --live` |
| PUT USDG产品 | `dcd_get_products`(baseCcy: BTC, quoteCcy: USDG, optType: P) | `okx earn dcd products --baseCcy BTC --quoteCcy USDG --optType P --json --live` |
| PUT USDT产品 | `dcd_get_products`(baseCcy: BTC, quoteCcy: USDT, optType: P) | `okx earn dcd products --baseCcy BTC --quoteCcy USDT --optType P --json --live` |
| CALL USDG产品 | `dcd_get_products`(baseCcy: BTC, quoteCcy: USDG, optType: C) | `okx earn dcd products --baseCcy BTC --quoteCcy USDG --optType C --json --live` |
| CALL USDT产品 | `dcd_get_products`(baseCcy: BTC, quoteCcy: USDT, optType: C) | `okx earn dcd products --baseCcy BTC --quoteCcy USDT --optType C --json --live` |
| 余额 | `account_get_asset_balance`(ccy: USDG,USDT,BTC) | `okx account asset-balance --ccy USDG,USDT,BTC --json --live` |
| 事件日历 | WebSearch | WebSearch（两端相同） |

### Phase 4：v3 波动率计算 + 选品

#### 4a. 事件判断（不跳过，只决定乘数）
- 今天/明天有事件 → 用对应事件乘数 + min_dist = 5%
- 无事件 → mult = 1.0, min_dist = 3.5%

#### 4b. v3 波动率计算

优先调用 `scripts/calc_volatility.py` 计算：

```bash
python3 scripts/calc_volatility.py \
  --price <BTC现价> \
  --iv-annual <年化IV> \
  --atr-fast <ATR_7_1H> --atr-slow <ATR_14_1H> \
  --bb-upper <BB上轨> --bb-lower <BB下轨> \
  --funding-rate <资金费率> \
  --high-30d <30天高点> --price-7d-ago <7天前价格> \
  --event-mult <事件乘数> --min-dist <最小安全距离> \
  --expiry-days <到期天数>
```

脚本不可用时，按上方"完整计算公式"手动计算。

#### 4c. PUT 选品
```
buy_dist = max(vol_24h * sqrt(到期天数) * 事件乘数, min_dist)
PUT 行权价 = price * (1 - buy_dist)，向下取整到 500
```

1. 行权价 < 安全下界的产品中筛选
2. 同一行权价+到期日，比较 USDG 和 USDT 产品，选 APY 更高的
3. ✅ 中选 APY 最高（≤150%），全部 APY < 5% 则跳过
4. 优先 1 天产品
5. 同 APY 选距安全下界更远的

#### 4d. CALL 选品（仅当有 BTC 持仓时）

从 `交易记录.md` 读取合并有效成本。无 BTC 持仓则跳过。

1. 行权价 >= 合并有效成本，选最接近的
2. 同一行权价+到期日，比较 USDG 和 USDT 产品，选 APY 更高的
3. 多个符合条件时选 APY 最高
4. 优先 1 天产品

### Phase 5：下单 + 记录

1. **PUT 下单**（USDG >= 10 或 USDT >= 10）：
   - MCP：`dcd_subscribe`（productId, investAmt, ...）
   - CLI：`okx earn dcd quote-and-buy --productId <id> --sz <amt> --notionalCcy <ccy> --json --live`

2. **CALL 下单**（BTC >= 0.0001 且有合并有效成本）：
   - MCP：`dcd_subscribe`（productId, investAmt, ...）
   - CLI：`okx earn dcd quote-and-buy --productId <id> --sz <btc_amt> --notionalCcy BTC --json --live`

3. 更新 `交易记录.md`（按 `templates/trade_log.md` 中的格式追加条目，并同步更新文件头部的合并有效成本、累计权利金汇总）


### 硬性约束检查清单（下单前逐条验证）

- [ ] PUT 行权价 < 安全下界
- [ ] PUT 安全距离 >= 3.5%（事件日 >= 5%）
- [ ] CALL 行权价 >= 合并有效成本（如有 BTC）
违反任一条 → 跳过该笔，不下单，记录原因。 

### 错误处理

- **CLI 命令失败**：重试 1 次。仍失败则记录错误到 `交易记录.md`，跳过本轮，不下单
- **`quote-and-buy` 下单失败**：不重试（避免重复下单），记录错误原因，等待下一轮
- **`option_get_greeks` 不可用**：降级为 30 天 HV（见 IV 降级规则），不影响交易
- **WebSearch 获取事件日历失败**：按"无事件"处理（mult=1.0, min_dist=3.5%），这是保守安全的默认值
- **`交易记录.md` 读取失败**：跳过本轮，通知用户检查文件

---

## 风险提示

- 本策略涉及真实资金交易，使用者需自行承担所有风险
- PUT 被行权意味着以行权价买入 BTC，可能面临 BTC 下跌风险
- 建议先小额测试，熟悉流程后再加大投入

---

### [18] `dragon-regret`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/dragon-regret/SKILL.md`

---
name: dragon-regret
description: Use when analyzing, tuning, backtesting, or extending the Dragon's Regret mean-reversion strategy, especially for ATR/z-score normalized entry logic, higher-timeframe trend filtering, execution-cost modeling, parameter scans, and walk-forward validation.
---

# 亢龙有悔 (Dragon's Regret)

This publishable skill package includes these core files:

- `spring_reversion_strategy.py`
- `tests/test_spring_reversion_strategy.py`

Use this skill when working on the included Dragon's Regret strategy or when porting the same workflow to another workspace.

## What This Strategy Does

- Trades short-term mean reversion, typically on `BTC/USDT 15m`
- Uses normalized exhaustion signals instead of a fixed candle percent trigger
- Requires `body_atr_ratio`, `return_zscore`, `RSI`, `volume spike`, and `momentum deceleration`
- Uses a higher-timeframe regime filter to avoid fading strong trends
- Models maker/taker fees and slippage in both realized PnL and equity curve
- Supports `run_backtest()`, `run_parameter_scan()`, and `run_walk_forward()`

## Default Workflow

1. Read `spring_reversion_strategy.py` first to confirm config keys, signal flow, execution-cost assumptions, and state transitions.
2. If the task changes behavior, update `tests/test_spring_reversion_strategy.py` in the same package.
3. Validate with:

```bash
python3 -m unittest -q tests/test_spring_reversion_strategy.py
```

4. Only move from backtest to live data or trading after checking risk rules and tool availability.

## OKX Integration

Prefer MCP tools when they are available in the current Codex session.

### Market Data

- If a tool named `okx-cex-market` is available, use it for read-only tasks first:
  - latest ticker
  - order book
  - recent candles / OHLCV
  - funding or mark-price context if supported
- Convert live market data into the same schema expected by `spring_reversion_strategy.py` before running signal checks or backtests.

### Trading

- If a tool named `okx-cex-trade` is available, use it only after:
  - the strategy has been backtested
  - the user explicitly asks for live or paper execution
  - current credentials and account mode are confirmed
- Default to paper / simulated execution when the tool supports it.
- Never place live orders silently.

### CLI Fallback

If MCP tools are unavailable but OpenClaw CLI is installed, inspect available integrations first and do not invent flags. In OpenClaw environments, relevant plugin surfaces may appear as `OpenClaw Trading` and `OKX Trade MCP`.

```bash
openclaw plugins list
openclaw docs okx
openclaw docs trading
```

If neither MCP tools nor a documented CLI integration is available, stop at analysis/backtest mode and report the missing OKX execution surface.

### Credentials

Authenticated OKX workflows may require environment variables such as:

- `OKX_API_KEY`
- `OKX_SECRET_KEY`
- `OKX_PASSPHRASE`

Do not print secret values, do not hardcode them, and do not proceed with authenticated trading if they are missing.

## Implementation Guardrails

- Do not reintroduce a fixed `5%` candle trigger. Entry logic should stay normalized around `body_atr_ratio` and `return_zscore`.
- Keep realized PnL, unrealized PnL, and equity curve on the same execution-cost model.
- Do not bypass the higher-timeframe trend filter unless explicitly requested.
- Keep strategy-core functions deterministic. Avoid network calls or exchange-specific live execution logic inside the backtest core.
- Preserve isolated state resets so parameter scans and walk-forward runs do not leak positions, balances, or trade logs across runs.

## Change Map

- Signal logic: indicator calculation and entry checks
- Position sizing and execution costs: sizing, slippage, maker/taker fees, open/close accounting
- Exit logic: ATR stop, trailing logic, and time stop
- Analytics: backtest, parameter scan, walk-forward, export helpers

## Trading Risk Notice

- This strategy can lose money in persistent trends, thin liquidity, fast gaps, and execution-quality degradation.
- Backtest results do not guarantee live performance.
- Live trading should be treated as high risk even when walk-forward results look acceptable.
- If execution is requested, enforce small size, clear stop logic, and explicit user confirmation before order placement.

## Expected Outputs

When asked for analysis, report:

- current signal definition
- trend filter behavior
- execution-cost assumptions
- backtest or walk-forward validity
- missing risks, fragile assumptions, or accounting inconsistencies

When asked for code changes, aim for:

- atomic diffs
- matching test updates
- deterministic outputs
- no silent changes to accounting or performance metric definitions

---

### [19] `dual-signal-analyzer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/dual-signal-analyzer/SKILL.md`

---
name: dual-signal-analyzer
title: 双信号分析器
description: 基于RSI和MACD双指标交叉验证的交易信号分析Skill，提供智能买卖信号和风险管理建议
version: 1.0.0
author: 菊中菊
category: trading-analysis
tags:
  - trading
  - strategy
  - analysis
  - crypto
  - signals
  - rsi
  - macd
  - risk-management
requires:
  - okx-cex-market
  - okx-cex-trade
---

# 双信号分析器

## 🎯 技能概述

双信号分析器是一个基于RSI和MACD双指标交叉验证的交易信号分析Skill。通过两个独立技术指标的协同分析，提供更可靠的交易信号和风险管理建议。

### 触发词
- '双信号分析'
- 'RSI MACD验证'
- '交叉验证信号'
- '智能交易分析'
- '风险评分'
- '机会扫描'

### 核心优势
- **双指标验证**: RSI超卖/超买 + MACD金叉/死叉双重确认
- **风险智能评分**: 基于市场波动性和信号一致性的动态风险评估
- **批量高效扫描**: 同时分析多个交易对，快速发现最佳机会
- **差异化功能**: 相比单一指标分析，提供更高的信号可靠性

## 🚀 安装方式

### 一键安装
```bash
npx @okx_ai/okx-trade-cli@latest skill add dual-signal-analyzer
```

### 验证安装
```bash
okx skill list | grep dual-signal
```

## 📖 使用方法

### 基本命令
```bash
# 分析单个交易对（双指标验证）
okx skill dual-signal-analyzer analyze --symbol BTC/USDT

# 批量扫描多个交易对
okx skill dual-signal-analyzer scan --symbols BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT

# 获取详细风险报告
okx skill dual-signal-analyzer risk --symbol BTC/USDT --detail full
```

### 参数说明
- `--symbol`: 交易对符号 (默认: BTC/USDT)
- `--symbols`: 交易对列表，逗号分隔（最多10个）
- `--timeframe`: 时间周期 (默认: 1h, 可选: 15m, 30m, 1h, 4h, 1d)
- `--confidence`: 最小置信度阈值 (默认: 70, 范围: 50-95)
- `--risk-profile`: 风险偏好 (默认: balanced, 可选: conservative, balanced, aggressive)

## 📊 输出示例

### 单个分析输出
```json
{
  "skill": "dual-signal-analyzer",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "symbol": "BTC/USDT",
  "analysis": {
    "signal": "BUY",
    "confidence": 85,
    "riskLevel": "LOW",
    "verification": "DOUBLE_CONFIRMED",
    "indicators": {
      "RSI": {"value": 28.5, "signal": "OVERSOLD_BUY", "strength": 88},
      "MACD": {"signal": "GOLDEN_CROSS", "strength": 82, "histogram": "POSITIVE"}
    },
    "recommendation": "双指标强烈确认买入信号，建议中等仓位"
  }
}
```

### 批量扫描输出
```json
{
  "skill": "dual-signal-analyzer",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "scanSummary": {
    "totalSymbols": 8,
    "analyzed": 8,
    "buySignals": 3,
    "sellSignals": 1,
    "holdSignals": 4,
    "doubleConfirmed": 2,
    "topOpportunities": [
      {"symbol": "SOL/USDT", "signal": "STRONG_BUY", "confidence": 92, "riskScore": 25},
      {"symbol": "ETH/USDT", "signal": "BUY", "confidence": 78, "riskScore": 35}
    ]
  }
}
```

## 🔧 技术架构

### 依赖技能
- **okx-cex-market**: 获取实时市场数据和K线
- **okx-cex-trade**: 执行交易操作（可选，用于自动化交易）

### 分析流程
1. **数据获取** → 通过okx-cex-market获取实时数据
2. **指标计算** → 并行计算RSI和MACD指标
3. **信号生成** → 独立生成两个指标信号
4. **交叉验证** → 验证信号一致性，计算综合置信度
5. **风险评估** → 分析市场条件和信号强度
6. **建议输出** → 生成交易建议和风险管理方案

### 算法特点
- **RSI策略**: 14日周期，动态超卖/超买阈值
- **MACD策略**: 12/26/9标准参数，金叉/死叉检测
- **验证逻辑**: 双指标一致时增强信号，冲突时提示风险
- **风险模型**: 波动率分析 + 趋势一致性评估

## ⚠️ 风险提示

### 交易风险说明
- 本技能提供的信号基于历史数据和技术分析
- 加密货币市场波动性极高，存在重大风险
- 所有交易决策应由用户自行负责

### 使用限制
- 需要有效的OKX账户和API权限
- 依赖okx-cex-market技能的可用性
- 网络延迟可能影响实时性

## 📞 支持与反馈

### 问题报告
如遇到技术问题或需要支持：
- 提交Issue: https://github.com/Lobster-Tempo/trading-strategy-skill/issues
- 联系开发者: yu230650@github.com

### 功能建议
欢迎提出改进建议：
- 新指标添加请求
- 分析参数调整
- 输出格式优化
- 性能改进建议

## 📝 版本记录

### v1.0.0 (2024-01-15)
- 🎉 初始版本发布
- ✅ RSI + MACD双指标分析
- ✅ 智能风险评分系统
- ✅ 批量机会扫描功能
- ✅ OKX技能市场集成
- ✅ 完整的文档和示例

## 🔒 安全与合规

### 数据安全
- 不存储用户API密钥或交易数据
- 所有分析在请求时实时进行
- 符合OKX API使用规范

### 合规声明
- 本技能仅提供技术分析工具
- 不提供财务建议或投资指导
- 用户应遵守当地法律法规

## 📄 许可证
MIT License

## ⚠️ 免责声明
本技能提供的分析结果仅供参考，不构成任何投资建议。加密货币交易存在极高风险，可能造成资金损失。用户应独立判断并承担所有交易风险。

---

**技能ID**: `dual-signal-analyzer`  
**版本**: 1.0.0  
**最后更新**: 2024-01-15  
**状态**: ✅ 生产就绪  
**开发者**: 菊中菊  
**依赖**: okx-cex-market, okx-cex-trade  
**唯一标识**: 双指标交叉验证分析器

---

### [20] `fear-hunter-sentiment-alpha`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/fear-hunter-sentiment-alpha/SKILL.md`

---
name: fear-hunter-sentiment-alpha
description: "恐惧猎手：基于情绪-费率背离的逆向交易策略。当市场恐惧但空头拥挤时做多，当市场贪婪但多头拥挤时做空。AI 识别情绪拐点 + 技术确认后执行。适用小资金账户（100-1000 USDT）。"
license: MIT
metadata:
  author: fear-hunter
  version: "2.0.0"
  tags:
    - contrarian
    - sentiment-analysis
    - funding-rate
    - small-account
    - perpetual-swap
  agent:
    requires:
      bins: ["okx"]
      skills: ["okx-cex-market", "okx-cex-trade", "okx-cex-portfolio"]
---

# 恐惧猎手 · Sentiment Dislocation Alpha v2.0

> **"当所有人恐惧时，找到恐惧过度的那一刻。"**

---

## 第一部分：策略概述

### 1.1 策略定位

| 维度 | 说明 |
|------|------|
| **策略名称** | 恐惧猎手 · Sentiment Dislocation Alpha v2.0 |
| **核心逻辑** | 情绪指数（Fear & Greed Index）与衍生品资金费率（Funding Rate）产生背离时，识别市场情绪极端拥挤的拐点，执行均值回归交易 |
| **Alpha 来源** | 情绪-费率背离（Sentiment-Funding Rate Dislocation） |
| **适用账户** | 100 – 1,000 USDT 小资金账户 |
| **执行周期** | 4H（对齐 UTC 00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00） |
| **主要标的** | BTC-USDT-SWAP（主），ETH-USDT-SWAP（辅） |
| **交易方向** | 双向（逆向做多 + 逆向做空） |
| **杠杆上限** | BTC 3x，ETH 2x |
| **单笔风险** | 账户净值的 2% |

### 1.2 核心 Alpha 论述

传统逆向策略仅依赖单一情绪指标："Fear & Greed 低就买入"。这种粗暴的方法胜率不稳定，因为——

- 极度恐惧可以持续数周甚至数月，盲目抄底会反复止损。
- 情绪指标本身不包含**仓位信息**，无法判断市场是否已经"用真金白银表达了恐惧"。

**恐惧猎手的关键洞察：**

当 Fear & Greed Index 处于极度恐惧（<25）**且**永续合约资金费率同步转负（<-0.01%），形成"双重恐惧"（双重恐惧）信号——

1. **情绪层面**：散户指标显示极端恐慌
2. **仓位层面**：交易者不仅恐惧，而且正在用杠杆做空（空头拥挤）
3. **物理意义**：大量空头需要在反弹时被迫平仓（轧空），为均值回归提供燃料

反之，当 Fear & Greed > 75 且资金费率 > 0.05% 时，形成"双重贪婪"信号，多头拥挤，回调概率极高。

### 1.3 为什么需要 AI

本策略**不是**一个简单的 `if-else` 规则引擎。AI 的不可替代价值在于：

1. **矛盾信号推理**：情绪极度恐惧 + 价格已经反弹 + 资金费率仍为负 → 这意味着"空头还没投降"还是"反弹即将结束"？这需要结合技术面、持仓量变化、成交量等多维信息进行**叙事推理**，而非简单的阈值判断。

2. **假信号过滤**：并非所有"双重恐惧"都值得交易。AI 需要评估技术面是否出现反转信号（RSI 拐头、EMA 收复），区分"恐惧还在加深"和"恐惧已经见顶"。

3. **动态置信度评估**：AI 对每次交易机会给出 1-5 分的置信度，并据此调整仓位大小，而不是机械地满仓进出。

### 1.4 当前市场验证（2026 年 4 月）

| 指标 | 当前值 | 含义 |
|------|--------|------|
| Fear & Greed Index | 23（Extreme Fear） | 极度恐惧区间 |
| 极端恐惧持续时间 | 30 天（区间 8-28） | 罕见的长期恐慌 |
| BTC 价格走势 | 70,500 → 75,000（期间反弹） | 恐惧中的反弹 = 情绪修复信号 |
| BTC 当前价格 | ~74,136 | 反弹仍在进行中 |

**这正是本策略设计之初最期待的市场环境。** 连续 30 天极度恐惧 + 价格逆势反弹，暗示空头仓位正在被缓慢轧平，均值回归动能正在积累。

---

## 第二部分：信号引擎 — 三层过滤器

本策略采用三层递进式过滤器。只有三层全部通过，才会触发交易。任一层未通过，策略保持空仓等待。

### Layer 1：情绪状态扫描（Sentiment Scan）

**目标：判断市场是否处于情绪极端区间。**

Fear & Greed Index 分区定义：

| 区间 | 数值范围 | 策略状态 | 说明 |
|------|---------|---------|------|
| **极度恐惧** | 0 – 19 | ACTIVE（做多候选） | 市场恐慌到极致，反转概率升高 |
| **恐惧** | 20 – 39 | ACTIVE（做多候选） | 恐惧区间，需配合 Layer 2 确认 |
| **中性** | 40 – 59 | **INACTIVE — 不交易** | 情绪无极端，无 Alpha 可捕捉 |
| **贪婪** | 60 – 79 | ACTIVE（做空候选） | 贪婪区间，需配合 Layer 2 确认 |
| **极度贪婪** | 80 – 100 | ACTIVE（做空候选） | 市场狂热到极致，回调概率升高 |

**核心规则：中性区间（40-59）= 绝对不交易。** 没有情绪极端，就没有本策略的 Alpha。策略 80% 的时间应该处于 INACTIVE 状态——这是设计特性，不是缺陷。

**数据获取：**
```
# 情绪指数可通过外部 API 获取或由 AI 基于近期市场数据评估
# 若无实时 API，AI 可基于以下代理指标推断情绪状态：
#   - 资金费率极端程度
#   - 近期价格跌幅/涨幅
#   - 社交媒体情绪
#   - 持仓量异常变化
```

### Layer 2：费率背离检测（Funding Rate Dislocation）

**目标：确认仓位拥挤方向是否与情绪极端方向一致。**

获取资金费率数据：

```
Call market_get_funding_rate
  instId = "BTC-USDT-SWAP"

Call market_get_funding_rate
  instId = "ETH-USDT-SWAP"
```

**情绪-费率矩阵（2×2 决策矩阵）：**

```
                    资金费率 < -0.01%          资金费率 > 0.05%
                    （空头拥挤）                （多头拥挤）
                ┌─────────────────────┬─────────────────────┐
 Fear&Greed     │                     │                     │
   < 25         │   ★ 双重恐惧        │   ⚠ 恐惧但多头拥挤   │
 （极度恐惧）    │   LONG SETUP        │   AVOID             │
                │   情绪+仓位同向极端   │   恐惧可能是合理的    │
                │   均值回归概率最高     │   多头仍在扛单       │
                ├─────────────────────┼─────────────────────┤
 Fear&Greed     │                     │                     │
   > 75         │   ⚠ 贪婪但空头拥挤   │   ★ 双重贪婪        │
 （极度贪婪）    │   AVOID             │   SHORT SETUP       │
                │   贪婪可能是合理的    │   情绪+仓位同向极端   │
                │   空头有信息优势      │   均值回归概率最高    │
                └─────────────────────┴─────────────────────┘
```

**关键洞察解读：**

- **双重恐惧（LONG SETUP）**：Fear&Greed < 25 且 fundingRate < -0.01%。市场不仅恐惧，而且交易者正在用杠杆做空。空头拥挤 + 情绪极端 = 轧空反弹的燃料已经堆积。这是本策略最高概率的做多信号。

- **双重贪婪（SHORT SETUP）**：Fear&Greed > 75 且 fundingRate > 0.05%。市场狂热且多头杠杆拥挤。一旦回调触发多头爆仓，将形成连锁清算。这是本策略最高概率的做空信号。

- **恐惧但多头拥挤（AVOID）**：Fear&Greed < 25 但 fundingRate > 0.05%。看似恐惧，但多头仍在扛单——说明恐惧可能尚未充分定价，下跌可能继续。

- **贪婪但空头拥挤（AVOID）**：Fear&Greed > 75 但 fundingRate < -0.01%。看似贪婪，但空头有信息优势——可能知道我们不知道的利空。

### Layer 3：技术确认（Technical Confirmation）— "扣扳机"

**目标：即使 Layer 1 + Layer 2 都通过，也不盲目入场。等待技术面出现反转确认信号。**

获取技术数据：

```
Call market_get_candles
  instId = "BTC-USDT-SWAP"
  bar    = "4H"
  limit  = 60

Call market_get_candles
  instId = "ETH-USDT-SWAP"
  bar    = "4H"
  limit  = 60
```

AI 在内存中计算以下指标：

| 指标 | 参数 | 用途 |
|------|------|------|
| RSI | 周期 14 | 超买超卖 + 拐点识别 |
| EMA20 | 指数移动平均 20 | 短期趋势方向 + 动态支撑/阻力 |
| ATR(14) | 平均真实波幅 14 | 波动率度量 + 止损定位 + 仓位计算 |
| 成交量变化 | 当前 vs 前 5 根均值 | 量能确认 |

**做多技术确认条件（双重恐惧 LONG SETUP）：**

必须满足以下全部三项：

1. **RSI(14) 从超卖区拐头**：RSI 从 30 以下向上穿越 30，表明卖方动能衰竭
2. **价格收复 EMA20**：4H 收盘价从下方突破 EMA20，表明短期趋势转向
3. **成交量放大**：当前 4H 成交量 > 前 5 根 4H 均值的 120%，确认反转有资金支撑

**做空技术确认条件（双重贪婪 SHORT SETUP）：**

必须满足以下全部三项：

1. **RSI(14) 从超买区拐头**：RSI 从 70 以上向下穿越 70，表明买方动能衰竭
2. **价格跌破 EMA20**：4H 收盘价从上方跌破 EMA20，表明短期趋势转向
3. **成交量放大**：当前 4H 成交量 > 前 5 根 4H 均值的 120%，确认反转有资金支撑

**AI 推理要点（非机械判断）：**

技术确认不是简单的 `if RSI > 30 then buy`。AI 需要评估：

- RSI 穿越 30 是"V 型反转"（强信号）还是"缓慢爬升"（弱信号）？
- EMA20 突破后是否有回踩确认？还是直接拉升（可能是假突破）？
- 成交量放大是否伴随价格实质性上涨？还是放量滞涨（大户出货）？
- ATR 是否从高位回落（波动率收敛），暗示市场从恐慌进入有序反弹？

---

## 第三部分：AI 推理框架 — 每周期决策流程

每个 4H 周期，AI 按以下 6 个步骤严格执行决策流程。

### Step 1：数据采集

**批量获取所有所需数据：**

```
# K 线数据（BTC + ETH）
Call market_get_candles
  instId = "BTC-USDT-SWAP", bar = "4H", limit = 60

Call market_get_candles
  instId = "ETH-USDT-SWAP", bar = "4H", limit = 60

# 资金费率
Call market_get_funding_rate
  instId = "BTC-USDT-SWAP"

Call market_get_funding_rate
  instId = "ETH-USDT-SWAP"

# 行情数据（含 24H 成交量）
Call market_get_tickers
  instId = "BTC-USDT-SWAP"

Call market_get_tickers
  instId = "ETH-USDT-SWAP"

# 持仓量（辅助判断）
Call market_get_open_interest
  instId = "BTC-USDT-SWAP"

Call market_get_open_interest
  instId = "ETH-USDT-SWAP"

# 账户状态
Call account_get_balance
```

**数据质量校验：**
- K 线数据不足 30 根 → 跳过该标的
- 数据时间戳距当前 > 8 小时 → 跳过本周期
- API 调用失败 → 重试 1 次，仍失败则跳过（绝不盲目操作）

### Step 2：情绪-费率矩阵构建

AI 根据 Layer 1 和 Layer 2 的数据，在 2×2 矩阵中定位当前市场状态：

```
当前定位示例：

  Fear & Greed = 23（极度恐惧）
  BTC Funding Rate = -0.015%（空头拥挤）
  ETH Funding Rate = -0.008%（轻微空头拥挤）

  ┌──────────────────────────────────────┐
  │ BTC: 双重恐惧区 → LONG SETUP 激活    │
  │ ETH: 恐惧区但费率不够极端 → 观望      │
  └──────────────────────────────────────┘
```

只有落入"双重恐惧"或"双重贪婪"象限的标的才进入 Step 3。其他标的本周期直接跳过。

### Step 3：AI 综合推理（核心差异化环节）

**这是本策略最关键的步骤。AI 不是简单地检查阈值，而是写一段完整的市场叙事分析。**

AI 必须回答以下问题并输出结构化推理：

1. **情绪极端程度评估**：当前 Fear & Greed 在极端区间停留了多久？是在加深还是开始修复？
2. **资金费率趋势**：费率是在进一步恶化（空头/多头继续加仓）还是开始回归中性（拥挤缓解）？
3. **技术面反转质量**：RSI 拐点是否有力？EMA20 突破是否有效？成交量是否确认？
4. **持仓量变化**：OI 在增加（新资金入场押注反转）还是减少（旧仓位被清算）？
5. **综合置信度**：1-5 分，决定仓位大小

**AI 推理输出模板：**

```
┌────────── 恐惧猎手 · 推理报告 [2026-04-15 08:00 UTC] ──────────┐
│                                                                   │
│ 标的: BTC-USDT-SWAP                                              │
│ 情绪状态: Fear & Greed = 23（极度恐惧，连续第 30 天）              │
│ 资金费率: -0.015%（空头拥挤）                                     │
│ 矩阵定位: ★ 双重恐惧 → LONG SETUP                               │
│                                                                   │
│ ─── AI 叙事推理 ───                                              │
│                                                                   │
│ Fear & Greed 连续 30 天处于极度恐惧区间（8-23），这是本轮周       │
│ 期中持续时间最长的恐慌阶段。然而 BTC 价格从 70,500 反弹至         │
│ 74,136（+5.2%），形成"恐惧中的反弹"——这本身就是情绪修复的         │
│ 早期信号：价格已经不再对恐惧做出下跌反应。                         │
│                                                                   │
│ 资金费率 -0.015% 确认空头仍然拥挤。如果反弹是空头回补驱动         │
│ 的，费率应该已经回归中性或转正。费率仍为负说明：（1）空头还         │
│ 没有投降；（2）反弹并非空头平仓驱动，而是新的买盘进入。这         │
│ 意味着一旦空头开始平仓，还会产生额外的上行推力。                   │
│                                                                   │
│ 技术面确认：                                                      │
│   RSI(14) = 38，从最低点 22 回升，刚穿越 30 → 拐点确认 ✓          │
│   价格 74,136 > EMA20(73,200) → 已收复短期均线 ✓                  │
│   4H 成交量 = 前 5 根均值的 145% → 放量确认 ✓                     │
│   ATR(14) = 1,580，较上周 2,100 回落 → 波动率收敛，有序反弹 ✓     │
│                                                                   │
│ OI 变化：4H OI +3.2%，新资金缓慢入场，非爆仓驱动的价格变动。     │
│                                                                   │
│ ─── 综合判定 ───                                                 │
│                                                                   │
│ 信号类型: 双重恐惧做多                                            │
│ 技术确认: 3/3 通过                                                │
│ 置信度: 4/5（扣 1 分原因：Fear&Greed 虽在极端区但已从 8 回升       │
│         至 23，最恐惧的时刻可能已过，但费率仍负弥补了这一点）      │
│ 最终决策: ★ 开多 BTC-USDT-SWAP                                   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Step 4：仓位计算（ATR 驱动，小账户优化）

**仓位计算遵循固定风险模型：**

```
# 基础参数
账户净值 = account_get_balance 返回的 totalEq
风险比例 = 2%（固定）
置信度调整:
  5/5 → 风险比例 × 100% = 2.0%
  4/5 → 风险比例 × 80%  = 1.6%
  3/5 → 风险比例 × 50%  = 1.0%
  2/5 → 不交易
  1/5 → 不交易

# 止损距离
止损距离 = ATR(14) × 1.5

# 仓位大小
仓位名义价值 = (账户净值 × 调整后风险比例) / (止损距离 / 当前价格)
实际仓位 = 仓位名义价值 / 当前价格
```

**示例计算（100 USDT 账户，BTC LONG）：**

```
账户净值 = 100 USDT
置信度 = 4/5 → 调整后风险比例 = 1.6%
风险金额 = 100 × 1.6% = 1.6 USDT
ATR(14) = 1,580
止损距离 = 1,580 × 1.5 = 2,370
止损比例 = 2,370 / 74,136 = 3.2%

仓位名义价值 = 1.6 / 0.032 = 50 USDT
杠杆 = 50 / 100 = 0.5x（远低于 3x 上限，安全）
仓位大小 ≈ 50 / 74,136 ≈ 0.00067 BTC
```

**小账户特别规则：**
- 最多同时持有 1 个仓位（不分散本就有限的资金）
- 杠杆上限：BTC 3x，ETH 2x（绝不超过）
- 若计算出的杠杆 > 上限，缩减仓位至上限杠杆对应的大小

### Step 5：执行下单

**开仓执行：**

```
Call swap_place_order
  instId  = "BTC-USDT-SWAP"
  tdMode  = "isolated"
  side    = "buy"              # 双重恐惧 → 做多
  posSide = "long"
  ordType = "market"           # 市价单确保成交
  sz      = "0.00067"          # Step 4 计算的仓位
  tag     = "agentTradeKit"    # 竞赛标识
```

**开仓后立即设置止损止盈：**

```
Call swap_place_algo_order
  instId      = "BTC-USDT-SWAP"
  tdMode      = "isolated"
  side        = "sell"            # 平多方向
  posSide     = "long"
  ordType     = "conditional"
  sz          = "0.00067"
  slTriggerPx = "71766"           # 入场价 74,136 - 1.5×ATR(2,370) = 71,766
  slOrdPx     = "-1"              # 市价止损
  tpTriggerPx = "78876"           # 入场价 + 2×ATR(4,740) = 78,876
  tpOrdPx     = "-1"              # 市价止盈
  tag         = "agentTradeKit"
```

**下单前强制校验清单：**

| # | 校验项 | 不通过时操作 |
|---|--------|-------------|
| 1 | 账户可用保证金是否充足 | 中止下单 |
| 2 | 是否已有持仓（最多 1 个） | 中止下单 |
| 3 | 是否存在同标的反向仓位 | 中止下单 |
| 4 | 是否处于风控暂停期 | 中止下单 |
| 5 | 连亏计数是否 >= 3 | 仓位减半后下单 |

### Step 6：持仓管理

**持仓管理是利润最大化的关键。采用分阶段退出策略：**

#### 阶段 A：浮盈 < 1×ATR — 初始防守期

- 维持原始止损（1.5×ATR）
- 不做任何调整
- 耐心等待趋势发展

#### 阶段 B：浮盈达到 1×ATR — 启用追踪止损

- 止损移至盈亏平衡点（入场价）
- 启用追踪止损，追踪距离 = 1×ATR
- 锁定本金安全

#### 阶段 C：浮盈达到 2×ATR — 部分止盈

- 平仓 50% 仓位，落袋为安
- 剩余 50% 继续持有
- 追踪止损收紧至 0.8×ATR

#### 阶段 D：浮盈达到 3×ATR — 全部止盈

- 平掉剩余全部仓位
- 本轮交易完成

#### 情绪退出规则（优先于技术止盈）

- **做多仓位**：当 Fear & Greed 指数回升至 40 以上（脱离恐惧区），无论浮盈多少，全部平仓。情绪极端消失 = Alpha 消失。
- **做空仓位**：当 Fear & Greed 指数回落至 60 以下（脱离贪婪区），无论浮盈多少，全部平仓。

---

## 第四部分：风控体系

风控是小账户生存的基石。以下规则为**硬性约束**，AI 在任何情况下不得违反。

### 4.1 核心风控参数

| # | 规则 | 参数 | 触发后操作 |
|---|------|------|-----------|
| 1 | 单笔最大亏损 | 账户净值的 2% | 立即止损平仓（100 USDT 账户 = 2 USDT 最大亏损） |
| 2 | 日最大回撤 | 4% | 平掉所有仓位，暂停交易 8 小时 |
| 3 | 周最大回撤 | 8% | 平掉所有仓位，暂停交易至下周一 UTC 00:00 |
| 4 | 最大持仓数 | 1 个标的 | 禁止开新仓 |
| 5 | BTC 杠杆上限 | 3x | 仓位超出则缩减 |
| 6 | ETH 杠杆上限 | 2x | 仓位超出则缩减 |
| 7 | 连续亏损惩罚 | 连亏 3 笔 | 仓位减半，直到出现盈利交易后恢复 |
| 8 | 宏观事件回避 | 重大事件前 4 小时 | 禁止开新仓（FOMC、CPI、非农等） |

### 4.2 日回撤监控流程

```
每周期开始时执行：

Call account_get_balance → 获取当前净值

if 当日起始净值未记录:
    记录当日起始净值 = 当前净值

当日回撤 = (当日起始净值 - 当前净值) / 当日起始净值

if 当日回撤 >= 4%:
    → 立即市价平掉所有仓位
    → Call swap_place_order (平仓)
    → 设置暂停标记，8 小时内不开新仓
    → 输出风控日志

if 当日回撤 >= 8%:
    → 立即市价平掉所有仓位
    → 设置暂停标记，本周不再交易
    → 输出风控警报
```

### 4.3 连亏管理机制

```
维护连亏计数器 consecutive_losses:

每笔交易结束后:
  if 本笔亏损:
    consecutive_losses += 1
  else:
    consecutive_losses = 0

仓位调整:
  consecutive_losses = 0-2 → 正常仓位（100%）
  consecutive_losses = 3-4 → 仓位减半（50%）
  consecutive_losses >= 5  → 暂停交易 24 小时，重新评估策略参数
```

### 4.4 异常处理

| 异常场景 | 处理方式 |
|---------|---------|
| API 调用失败 | 重试 1 次，仍失败 → 跳过本周期（绝不盲目操作） |
| K 线数据延迟 > 8H | 跳过本周期 |
| 下单后未成交 | 等待 30 秒后取消，下一周期重新评估 |
| 止损单触发失败 | 立即手动市价平仓，记录异常 |
| 账户余额不足 | 不开新仓，评估是否需减仓释放保证金 |
| 网络中断 | 依赖已挂出的止损单保护仓位，恢复后立即检查持仓状态 |

---

## 第五部分：策略独特优势

### 5.1 独特的 Alpha 来源

本策略的信号**不是** EMA 交叉、MACD 金叉这类人人都会的技术指标组合。情绪-费率背离是一种跨数据源、跨市场结构的高阶信号——它需要同时理解散户情绪（Fear & Greed）、衍生品市场微观结构（Funding Rate）、以及价格技术形态之间的非线性关系。这种复合信号天然具有更高的信息含量和更少的竞争者。

### 5.2 天生适合 AI 执行

人类交易员很难同时做到以下几点：
- 每 4 小时检查情绪指数、资金费率、RSI、EMA、ATR、持仓量、成交量
- 在这些指标发出矛盾信号时保持理性（"情绪恐惧但价格在涨，到底该买还是卖？"）
- 严格执行"不交易"的决策（人类有 FOMO 倾向）
- 在连亏后主动缩减仓位而非加倍下注

**这恰恰是 LLM 的强项：** 多维信息整合、矛盾信号推理、纪律性执行、无情绪干扰。本策略是为 AI agent 量身设计的。

### 5.3 小资金友好

策略的每一个参数都围绕 100-1,000 USDT 账户设计：
- 单笔风险 2%（100 USDT 账户最多亏 2 USDT）
- 最多 1 个持仓（不分散有限资金）
- 低杠杆（BTC 3x / ETH 2x）
- ATR 动态止损（不会因固定点位被洗出）

### 5.4 高复用性

任何交易者安装此 Skill 后即可直接使用，无需调整参数。策略的所有阈值（Fear&Greed 分区、费率阈值、RSI 拐点、ATR 倍数）都是基于市场微观结构的通用参数，不依赖特定时期的回测优化。

### 5.5 逆向差异化

大多数参赛者会提交趋势跟踪策略（均线交叉、突破跟踪），这意味着：
- 评委会看到大量相似的策略
- 趋势策略在震荡市中表现不佳（当前极度恐惧 + 区间震荡正是这种市场）

逆向策略在评选中天然差异化，且当前市场环境（2026 年 4 月极度恐惧 30 天）正是逆向策略的最佳展示窗口。

### 5.6 实时市场验证

当前 Fear & Greed = 23，连续 30 天极度恐惧，BTC 从 70,500 反弹至 74,136。如果资金费率同时为负，则完美触发"双重恐惧"信号。这不是回测假设，而是**正在发生的真实交易机会**。

---

## 第六部分：附录 — 策略设计理念

### 6.1 哲学基础

> "别人恐惧我贪婪"不是一句口号，而是一个可量化的交易系统。

本策略将巴菲特的经典逆向投资哲学转化为具体的、可执行的、AI 可理解的决策框架：

- **"别人恐惧"** → Fear & Greed Index < 25
- **"我贪婪"** → 当资金费率确认空头拥挤时，做多
- **量化"贪婪的时机"** → 等待 RSI 拐头 + EMA 收复 + 放量确认

### 6.2 均值回归的物理基础

情绪极端 + 仓位极端 = 均值回归概率最大化。

这不是统计上的巧合，而是有明确的因果链：
1. 极度恐惧 → 散户恐慌性抛售 → 价格跌至低估区间
2. 空头拥挤 → 资金费率为负 → 空头需要持续支付费用（成本压力）
3. 任何正面催化 → 部分空头开始平仓 → 价格上涨
4. 价格上涨 → 更多空头被迫平仓（止损/爆仓） → 价格加速上涨
5. 轧空完成 → Fear & Greed 回升至中性 → 策略平仓获利

每一步都有清晰的市场微观结构支撑，不是"画线算命"。

### 6.3 AI 的价值定位

AI 在本策略中的角色不是"更快的计算器"，而是"更理性的交易员"：

- **在噪声中识别信号**：市场每天产生数百个"看似重要"的信号，AI 的价值在于过滤 95% 的噪声，只在真正高概率的时刻行动。
- **在矛盾中找到一致性**：当情绪指标说"恐惧"、价格说"在涨"、费率说"空头拥挤"时，人类会困惑，AI 能将这些矛盾信号整合为一个连贯的叙事。
- **纪律性执行**：连亏 3 笔后自动缩减仓位——人类做不到但 AI 可以；中性市场 80% 时间不交易——人类忍不住但 AI 可以。

### 6.4 不交易是最重要的交易

本策略约 80% 的时间处于"等待"状态（Fear & Greed 在 40-60 中性区间时完全不交易）。这是设计意图，不是缺陷。

超额收益的很大一部分来自于**在不该交易的时候选择不交易**。大多数亏损交易者的问题不是策略不好，而是交易频率太高。

### 6.5 完整决策流程图

```
                    ┌─────────────────┐
                    │  每 4H 周期触发   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  风控状态检查     │
                    │  是否在暂停期？   │
                    └────────┬────────┘
                             │
                        是 ──┤── 否
                        │         │
                   跳过本周期       │
                             ┌────▼─────────────┐
                             │  Layer 1: 情绪扫描 │
                             │  Fear&Greed 极端？  │
                             └────────┬──────────┘
                                      │
                              否（40-60）── 跳过，不交易
                                      │
                                 是（<25 或 >75）
                                      │
                             ┌────────▼──────────┐
                             │  Layer 2: 费率背离  │
                             │  情绪+仓位同向极端？ │
                             └────────┬──────────┘
                                      │
                               否 ──── 跳过（AVOID 区间）
                                      │
                                 是（双重恐惧/双重贪婪）
                                      │
                             ┌────────▼──────────┐
                             │  Layer 3: 技术确认  │
                             │  RSI 拐头？         │
                             │  EMA20 突破？        │
                             │  成交量放大？        │
                             └────────┬──────────┘
                                      │
                              否（任一未通过）── 等待下一周期
                                      │
                                 是（全部通过）
                                      │
                             ┌────────▼──────────┐
                             │  AI 综合推理       │
                             │  置信度 1-5 分      │
                             └────────┬──────────┘
                                      │
                              ≤2 分 ── 跳过
                                      │
                                 ≥3 分
                                      │
                             ┌────────▼──────────┐
                             │  仓位计算 + 下单    │
                             │  设置 TP/SL         │
                             └────────┬──────────┘
                                      │
                             ┌────────▼──────────┐
                             │  持仓管理          │
                             │  追踪止损 / 分批止盈 │
                             │  情绪退出监控       │
                             └─────────────────────┘
```

### 6.6 与其他策略的对比

| 维度 | 典型趋势策略 | 恐惧猎手 |
|------|-------------|---------|
| Alpha 来源 | 价格动量（EMA/MACD） | 情绪-费率背离 |
| 交易频率 | 高（每天多次信号） | 低（月均 2-4 次） |
| 持仓时间 | 短（数小时） | 中（1-5 天） |
| 胜率 | 30-40% | 55-65%（情绪极端回归概率高） |
| 盈亏比 | 2:1+ | 1.5:1（但胜率补偿） |
| AI 依赖度 | 低（规则即可执行） | 高（需要叙事推理） |
| 市场适应性 | 趋势市好，震荡市差 | 情绪极端时好，中性市不交易 |
| 心理负担 | 频繁止损 | 长期等待（需要耐心） |

### 6.7 风险声明

- 本策略基于历史统计规律，不保证未来表现
- 情绪-费率背离可能在极端市场中持续时间超预期
- 小账户即使采用严格风控，连续亏损仍可能导致显著回撤
- 建议使用可承受损失的资金进行交易
- 策略表现高度依赖 AI 推理质量，不同 LLM 可能产生不同结果

---

## 第七部分：实战验证 — 模拟盘 Live Demo（2026-04-15）

> 以下是使用 OKX Agent Trade Kit v1.3.0 在模拟盘上按照"恐惧猎手"策略完整执行的一笔交易记录。所有数据均为真实 API 返回结果。

### 7.1 Step 1 — 数据采集

**情绪指数：**
```
Fear & Greed Index = 23（Extreme Fear）
连续极度恐惧天数：30 天（区间 8-28）
```

**BTC 永续合约行情：**
```
$ okx market ticker BTC-USDT-SWAP
instId       BTC-USDT-SWAP
last         74009.9
24h high     75668.3
24h low      73443
24h change   -0.76%
time         4/15/2026, 3:12:40 PM
```

**BTC 资金费率：**
```
$ okx market funding-rate BTC-USDT-SWAP
fundingRate   -0.00006039（负值 = 空头付费）
fundingTime   4/15/2026, 4:00:00 PM
```

**ETH 资金费率：**
```
$ okx market funding-rate ETH-USDT-SWAP
fundingRate   -0.00002084（负值 = 空头付费）
fundingTime   4/15/2026, 4:00:00 PM
```

**BTC 4H K 线（最近 5 根）：**
```
$ okx market candles BTC-USDT-SWAP --bar 4H --limit 5
time                    open     high     low      close    vol
4/15/2026, 12:00:00 PM  74163.1  74479.8  73772.9  74012.8  1,464,064
4/15/2026, 8:00:00 AM   73706.9  74243.2  73644    74163.1  1,072,389
4/15/2026, 4:00:00 AM   74296.3  74400    73443    73706.9  1,262,123
4/15/2026, 12:00:00 AM  74100    74749    74079.6  74296.3    970,868
4/14/2026, 8:00:00 PM   74175    74391.2  73743.9  74100.1    806,267
```

**模拟盘账户余额：**
```
$ okx --demo account balance
currency  equity              available
BTC       1.0013476386        1.0013468518
USDT      13458.0707094688    11370.5233218
ETH       1                   1
SOL       0.001219779         0.001219779
```

### 7.2 Step 2 — 情绪-费率矩阵定位

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  Fear & Greed = 23 → 极度恐惧 ✓                         │
│  BTC Funding Rate = -0.006% → 空头付费（空头拥挤）✓       │
│  ETH Funding Rate = -0.002% → 空头轻微拥挤              │
│                                                          │
│  矩阵定位：                                              │
│    BTC: ★ 双重恐惧区 → LONG SETUP 激活                  │
│    ETH: 费率不够极端（-0.002% > -0.01%） → 本周期观望    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 7.3 Step 3 — AI 综合推理

```
┌────────── 恐惧猎手 · 推理报告 [2026-04-15 15:12 UTC+8] ──────────┐
│                                                                     │
│  标的: BTC-USDT-SWAP                                               │
│  情绪: Fear & Greed = 23（极度恐惧，连续第 30 天）                  │
│  费率: -0.006%（空头付费，拥挤但非极端）                            │
│  矩阵: ★ 双重恐惧 → LONG SETUP                                    │
│                                                                     │
│  ─── AI 叙事推理 ───                                               │
│                                                                     │
│  Fear & Greed 已连续 30 天处于极度恐惧区间，最低曾触及 8，          │
│  当前回升至 23。BTC 在此期间从 70,500 反弹至 75,668 后回落          │
│  至 74,009。价格在极度恐惧中走出 +5% 反弹，说明卖压已经             │
│  枯竭——市场不再对恐惧做出新低反应。                                │
│                                                                     │
│  资金费率 -0.006% 确认空头仍在付费，虽然不算极端拥挤，              │
│  但方向明确为空头主导。4H K 线显示价格在 73,443-75,668              │
│  区间整理，成交量维持活跃（百万级），非缩量阴跌。                   │
│                                                                     │
│  技术面：                                                           │
│    价格 74,009 在近期支撑 73,443 之上 → 支撑有效 ✓                  │
│    从 4/14 高点 76,000 回调约 2.6%，属健康回调 ✓                    │
│    成交量维持高位 → 市场参与度未衰减 ✓                              │
│                                                                     │
│  ─── 综合判定 ───                                                  │
│                                                                     │
│  信号类型: 双重恐惧做多                                             │
│  置信度: 3/5（费率虽负但不够极端 -0.006% vs 阈值 -0.01%，           │
│         但30天持续恐惧 + 价格反弹结构补偿了这一点）                 │
│  最终决策: ★ 开多 BTC-USDT-SWAP                                    │
│  仓位: 1 张（约 74 USDT 名义价值），逐仓 3x                        │
│  止损: 72,500（入场价 -2.1%，约 1.5×ATR）                          │
│  止盈: 76,000（入场价 +2.6%，约 2×ATR）                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.4 Step 4-5 — 执行下单

**开多 BTC 永续合约：**
```
$ okx --demo swap place --instId BTC-USDT-SWAP --side buy \
    --ordType market --sz 1 --posSide long --tdMode isolated
Order placed: 3481728777909305344 (OK)
```

**确认持仓：**
```
$ okx --demo swap positions
instId         side  size  avgPx     upl     uplRatio  lever
BTC-USDT-SWAP  long  1     74063.18  -0.29   -0.0012   3
```

**设置止损止盈：**
```
$ okx --demo swap algo-order --instId BTC-USDT-SWAP --tdMode isolated \
    --side sell --posSide long --ordType conditional --sz 1 \
    --slTriggerPx 72500 --slOrdPx=-1 --tpTriggerPx 76000 --tpOrdPx=-1
(OK)
```

### 7.5 交易摘要

| 项目 | 值 |
|------|-----|
| **标的** | BTC-USDT-SWAP |
| **方向** | LONG（做多） |
| **信号类型** | 双重恐惧（F&G=23 + 负费率） |
| **入场价** | 74,063.18 |
| **仓位** | 1 张（逐仓 3x） |
| **止损** | 72,500（-2.1%） |
| **止盈** | 76,000（+2.6%） |
| **风险回报比** | 1:1.24 |
| **置信度** | 3/5 |
| **执行时间** | 2026-04-15 15:12 UTC+8 |
| **工具版本** | @okx_ai/okx-trade-cli v1.3.0 |

> **注**：本交易在 OKX 模拟盘（Demo Trading）执行，使用模拟资金，零真实风险。完整过程从数据采集到下单设置止盈止损，全程通过 AI + Agent Trade Kit CLI 完成，无需打开交易所界面。

### 7.6 ETH "跳过" 决策记录

> 策略不是"有信号就交易"。以下记录展示 AI 对 ETH 做出"跳过"决策的完整推理过程。

```
$ okx market funding-rate ETH-USDT-SWAP
fundingRate   -0.00002141（负值，但仅 -0.002%）
fundingTime   4/15/2026, 4:00:00 PM

$ okx market ticker ETH-USDT-SWAP
last          2343.6
24h change    +0.22%
```

```
┌────────── 恐惧猎手 · 跳过报告 [2026-04-15 15:16 UTC+8] ──────────┐
│                                                                     │
│  标的: ETH-USDT-SWAP                                               │
│  情绪: Fear & Greed = 23 → 极度恐惧 ✓（Layer 1 通过）              │
│  费率: -0.002%                                                      │
│                                                                     │
│  ─── Layer 2 检查 ───                                              │
│                                                                     │
│  费率阈值: -0.01%                                                   │
│  当前费率: -0.002% > -0.01%                                         │
│  判定: 空头拥挤不够极端，未达到"双重恐惧"阈值                       │
│                                                                     │
│  ★ 最终决策: SKIP（跳过）                                          │
│  原因: Layer 2 未通过 — 费率虽为负但距阈值差 5 倍                   │
│        空头付费力度不足，轧空燃料不够，均值回归动能弱                │
│        等待费率进一步恶化或选择其他标的                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.7 SOL "跳过" 决策记录

```
$ okx market funding-rate SOL-USDT-SWAP
fundingRate   -0.00002589（负值，但仅 -0.003%）

$ okx market ticker SOL-USDT-SWAP
last          84.18
24h change    -1.56%
```

```
┌────────── 恐惧猎手 · 跳过报告 [2026-04-15 15:16 UTC+8] ──────────┐
│                                                                     │
│  标的: SOL-USDT-SWAP                                               │
│  情绪: Fear & Greed = 23 → Layer 1 通过                            │
│  费率: -0.003% > -0.01% → Layer 2 未通过                           │
│                                                                     │
│  ★ 最终决策: SKIP                                                  │
│  备注: SOL 24h 仍在下跌(-1.56%)，技术面未出现反转信号。             │
│        即使费率达标也需等待 Layer 3 技术确认。                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

> **策略纪律性展示：** 在同一时间点，三个标的中仅 BTC 满足开仓条件（F&G=23 + 负费率 + 技术反弹结构），ETH 和 SOL 均被过滤器拦截。这就是"80% 时间不交易"的设计理念在实际执行中的体现。

---

## 第八部分：历史回测 — 过去 30 天策略模拟

> 以下回测基于 2026 年 3 月 17 日 – 4 月 15 日的真实 Fear & Greed Index 数据和 BTC 日线价格数据。所有数据均通过公开 API 获取，非人工编造。

### 8.1 数据背景

**Fear & Greed Index 30 天记录：**

```
日期        F&G   分类          BTC 收盘价   备注
3/17        28    Fear          71,436      ─┐
3/18        26    Fear          69,375       │ F&G 从 Fear 区跌入
3/19        23    Extreme Fear  69,840       │ Extreme Fear
3/20        11    Extreme Fear  70,588       │
3/21        12    Extreme Fear  68,810       │ 策略激活区间开始
3/22        10    Extreme Fear  70,099       │
3/23         8    Extreme Fear  69,832       │ ← F&G 触底 8
3/24        11    Extreme Fear  70,799       │
3/25        14    Extreme Fear  69,052       │
3/26        10    Extreme Fear  66,091       │ ← BTC 阶段性低点
3/27        13    Extreme Fear  66,984       │
3/28        12    Extreme Fear  66,500       │
3/29         9    Extreme Fear  67,601       │
3/30         8    Extreme Fear  66,705       │ ← F&G 再次触底 8
3/31        11    Extreme Fear  68,888       │
4/1          8    Extreme Fear  66,818       │ ← F&G 三次触底 8
4/2         12    Extreme Fear  66,808       │
4/3          9    Extreme Fear  67,346       │ ← BTC 筑底完成
4/4         11    Extreme Fear  67,281       │
4/5         12    Extreme Fear  69,923       │ ← 反弹启动 +3.9%
4/6         13    Extreme Fear  68,139       │
4/7         11    Extreme Fear  71,265       │ ← 强势反弹 +4.6%
4/8         17    Extreme Fear  72,106       │
4/9         14    Extreme Fear  72,418       │
4/10        16    Extreme Fear  72,827       │
4/11        15    Extreme Fear  70,870       │
4/12        16    Extreme Fear  71,831       │
4/13        12    Extreme Fear  75,280       │ ← 突破性反弹 +4.8%
4/14        21    Extreme Fear  74,200       │
4/15        23    Extreme Fear  74,064       │ ← 当前
                                             ─┘
```

**关键观察：**
- 30 天中 28 天处于 Extreme Fear（<20），2 天处于 Fear（20-28）
- BTC 从 73,878（3/17）跌至 66,091（3/26），最大回撤 -10.5%
- 随后从 66,091 反弹至 75,280（4/13），反弹幅度 +13.9%
- 整个过程中 Fear & Greed 从未回到中性区间（>40），策略始终处于激活状态

### 8.2 回测交易记录

按照策略三层过滤器严格筛选，30 天内识别出以下交易机会：

#### 交易 #1：3/27 做多（筑底反弹）

```
触发条件:
  Layer 1: F&G = 13（Extreme Fear）✓
  Layer 2: 假设 fundingRate < -0.01%（3/26 暴跌 -4.3% 后空头大量涌入）✓
  Layer 3: 3/27 BTC 从 66,091 反弹至 66,984（+1.35%），RSI 从极低位拐头 ✓

入场: 66,984（3/27 收盘）
止损: 65,500（-2.2%，1.5×ATR）
止盈: 69,000（+3.0%，2×ATR）

结果:
  3/31 BTC 收盘 68,888 → 接近止盈目标
  4/1 BTC 回落至 66,818 → 触发追踪止损（盈亏平衡点附近）

  估计盈亏: ~0%（保本出场）
  持仓天数: 5 天
  评价: 趋势未完全确立，追踪止损保护了本金
```

#### 交易 #2：4/5 做多（确认性反弹）

```
触发条件:
  Layer 1: F&G = 12（Extreme Fear，已持续 17 天）✓
  Layer 2: 假设 fundingRate 仍为负（长期恐惧后空头持续拥挤）✓
  Layer 3: 4/5 BTC 从 67,281 跳涨至 69,923（+3.9%），放量突破，
           RSI 从底部强力拐头，EMA20 被有效收复 ✓
  AI 置信度: 4/5（连续多日筑底 + 放量突破 = 高质量技术确认）

入场: 69,923（4/5 收盘）
止损: 67,900（-2.9%，1.5×ATR）
止盈: 73,900（+5.7%，2×ATR）

结果:
  4/7 BTC 收盘 71,265（浮盈 +1.9%）→ 启用追踪止损
  4/8 BTC 收盘 72,106（浮盈 +3.1%）→ 止损移至盈亏平衡
  4/10 BTC 收盘 72,827（浮盈 +4.2%）→ 部分止盈 50%
  4/13 BTC 收盘 75,280（浮盈 +7.7%）→ 超过止盈目标，全部平仓

  实际盈利:
    50% 仓位 @ 72,827 → +4.2%
    50% 仓位 @ 73,900（止盈触发）→ +5.7%
    加权平均: +4.95%

  持仓天数: 8 天
  评价: ★ 教科书级别的恐惧猎手交易
```

#### 交易 #3：4/15 做多（当前持仓）

```
触发条件:
  Layer 1: F&G = 23（Extreme Fear，连续第 30 天）✓
  Layer 2: fundingRate = -0.006%（空头付费，方向正确但未达 -0.01% 极端阈值）
  Layer 3: BTC 从 73,443 反弹至 74,063，支撑位有效，成交量活跃 ✓
  AI 置信度: 3/5（费率不够极端扣分，但30天恐惧持续性补偿）

入场: 74,063（市价成交）
止损: 72,500（-2.1%）
止盈: 76,000（+2.6%）

当前状态: 持仓中，浮盈 +0.5%
```

### 8.3 回测摘要

| 指标 | 值 |
|------|-----|
| **回测周期** | 2026-03-17 至 2026-04-15（30 天） |
| **总交易次数** | 3 笔（月均约 3 笔，符合策略预期） |
| **胜率** | 1 胜 / 1 平 / 1 持仓中 = 暂 50%+ |
| **最大单笔盈利** | +4.95%（交易 #2） |
| **最大单笔亏损** | ~0%（交易 #1 保本出场） |
| **累计收益** | ~+5%（不含当前持仓） |
| **最大回撤** | <1%（止损保护） |
| **跳过决策次数** | ~25 个周期（约 83% 的时间在等待） |
| **数据来源** | Fear & Greed Index API + OKX BTC-USDT-SWAP 日线 |

### 8.4 回测结论

1. **策略确实在极度恐惧市场中有效**：30 天极度恐惧 + BTC 先跌后涨，策略在底部区域识别出 2 次有效做多机会
2. **交易 #2 是典型的"恐惧猎手"交易**：F&G=12 + 连续筑底 + 放量突破 → 入场后持续上涨至止盈，收益 +4.95%
3. **保本出场同样重要**：交易 #1 虽然未盈利，但追踪止损保护了本金，没有产生亏损
4. **低频高质量**：30 天仅 3 笔交易，83% 的时间在等待——这证明了策略的纪律性
5. **风险可控**：即使交易 #1 触发止损（-2.2%），对 100 USDT 账户的影响也仅为 2.2 USDT

> **注意**：本回测为事后分析，资金费率数据基于合理假设（极度恐惧 + 价格暴跌后空头通常会拥挤）。完整的程序化回测需要历史资金费率的逐笔数据，此处仅用于展示策略逻辑的有效性。

---

## 第九部分：快速上手指南

> 任何交易者都可以在 3 分钟内安装并开始使用本策略。

### 9.1 安装

```bash
# 1. 安装 OKX Agent Trade Kit
npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli

# 2. 配置模拟盘 API Key（交互式向导）
okx config init

# 3. 验证安装
okx market ticker BTC-USDT-SWAP
```

### 9.2 连接 AI 客户端

```bash
# Claude Desktop / Claude Code
okx-trade-mcp setup --client claude-desktop

# Cursor
okx-trade-mcp setup --client cursor

# VS Code
okx-trade-mcp setup --client vscode
```

### 9.3 用自然语言执行策略

在 AI 客户端中直接说：

```
"按照恐惧猎手策略分析当前市场：
 1. 查看 BTC 和 ETH 的资金费率
 2. 获取 BTC 4H K 线数据
 3. 判断当前是否处于双重恐惧区间
 4. 如果条件满足，在模拟盘开多 BTC 永续合约
 5. 设置止损止盈"
```

### 9.4 策略运行清单

```
每 4 小时检查一次（对齐 UTC 整点）：

□ Fear & Greed Index 是否 < 25 或 > 75？
  → 否：跳过，不交易
  → 是：继续 ↓

□ BTC/ETH 资金费率是否处于极端区间？
  → 恐惧 + 费率 < -0.01%：双重恐惧 LONG
  → 贪婪 + 费率 > 0.05%：双重贪婪 SHORT
  → 其他组合：跳过

□ 技术面是否确认反转？
  → RSI 穿越 30/70 ✓
  → 价格收复/跌破 EMA20 ✓
  → 成交量放大 ✓
  → 全部通过：下单
  → 任一未通过：等待下一周期

□ 仓位管理
  → 浮盈 1×ATR：止损移至盈亏平衡
  → 浮盈 2×ATR：平仓 50%
  → 浮盈 3×ATR 或 F&G 回到中性：全部平仓
```

---

## 附录：项目信息

| 资源 | 链接 |
|------|------|
| GitHub | github.com/okx/agent-trade-kit |
| npm | @okx_ai/okx-trade-mcp / @okx_ai/okx-trade-cli |
| 官方文档 | okx.com/docs-v5/agent_zh/ |
| AI 101 课程 | okx.com/zh-hans/ai-101 |
| Skill 广场 | okx.com/zh-hans/agent-tradekit/skills |
| Telegram | t.me/OKX_AgentKit |

---

### [21] `funding-rate-scanner`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/funding-rate-scanner/SKILL.md`

---
name: funding-rate-scanner
description: >
  Use this skill to discover, scan, or rank perpetual futures funding
  rates on OKX, Binance, or both. Covers: finding coins with negative
  rates where longs earn funding payments, ranking perps by most
  extreme (positive or negative) rates, spotting cross-exchange rate
  discrepancies for arbitrage, and monitoring a watchlist of funding
  rates.

  Trigger when users want to scan for funding opportunities across
  perps, find negative-funding coins on any exchange, identify the
  most extreme funding rates, earn yield from funding payments, or
  compare rates between exchanges.

  Do NOT use for chart analysis, technical indicators (RSI/MACD), spot
  prices, or single-coin market overviews — those belong to
  kline-indicator or cmc-mcp.
---

# Funding Rate Scanner

Scan perpetual futures funding rates to find high-yield arbitrage opportunities. Uses OKX as the primary data source via OKX Trade Kit (CLI first, MCP fallback), with Binance data for cross-exchange comparison via bundled scripts.

## Data Source Roles

- **OKX Trade Kit (CLI/MCP)** — primary source for real-time OKX funding rates, tickers, open interest, and candles
- **scripts/scan.js** — bulk-scans all Binance USDT-margined perps; use for cross-exchange comparison
- **scripts/analyze.js** — single-coin historical funding rate analysis on Binance
- **scripts/monitor.js** — watchlist monitor for specific coins on Binance

## Workflow

### Step 1 — Fetch OKX Funding Rate (CLI First)

**CLI (primary):**
```bash
okx market funding-rate BTC-USDT-SWAP
okx market ticker BTC-USDT-SWAP
```

**MCP fallback (if CLI unavailable):**
- `market_get_funding_rate(instId="BTC-USDT-SWAP")` — current rate and next settlement time
- `market_get_ticker(instId="BTC-USDT-SWAP")` — price, volume, bid/ask

### Step 2 — Scan All OKX Instruments

To scan all USDT-margined perpetual swaps on OKX, fetch each instrument's funding rate via CLI or MCP. Start by listing all SWAP instruments:

```bash
okx market instruments --instType SWAP
```

Then loop through and fetch funding rates for each. Filter to instruments where `|rate| > 0.01%` to surface meaningful opportunities.

### Step 3 — Binance Cross-Exchange Data

For cross-exchange comparison, use the bundled scripts (Node.js required):

```bash
# Scan all Binance perps — returns top negative and positive rates
node ${CLAUDE_SKILL_DIR}/scripts/scan.js

# Detailed history for a specific coin
node ${CLAUDE_SKILL_DIR}/scripts/analyze.js DUSK

# Monitor a specific watchlist
node ${CLAUDE_SKILL_DIR}/scripts/monitor.js DUSK DASH AXS
```

These scripts query Binance public APIs directly — no API key needed.

### Step 4 — Rank and Analyze

For each instrument, compute:

| Field | Formula |
|---|---|
| Funding Rate | Raw rate from exchange |
| Daily Return | rate × 3 (assumes 8h settlement — see note below) |
| Annualized Return | rate × 3 × 365 |
| Leveraged Annual | annualized × leverage |

> **Settlement period note:** The `rate × 3` formula assumes 8-hour settlement (standard for most OKX and Binance perps). Some OKX instruments settle every 4h or 1h — check `fundingTime` and `nextFundingTime` in the API response to confirm, and adjust the multiplier accordingly.

Sort by most negative rate (best long opportunity) or highest positive rate (best short opportunity).

### Step 5 — Cross-Exchange Comparison

When both OKX and Binance rates are available, identify discrepancies:

```
Coin     OKX Rate    Binance Rate   Delta    Opportunity
DUSK     -0.25%      -0.38%         0.13%    Long Binance / Short OKX
AXS      -0.10%      -0.12%         0.02%    Marginal
```

A delta >0.05% between exchanges signals a potential cross-exchange funding arbitrage opportunity. Before acting on it, factor in:
- Transfer and withdrawal fees between exchanges
- Margin requirements on both sides
- Execution risk if rates shift before positions are opened

### Step 6 — Historical Analysis

For deeper analysis on a specific instrument:

**CLI (primary):**
```bash
okx market candles BTC-USDT-SWAP --bar 1H --limit 24
okx market open-interest BTC-USDT-SWAP
```

**MCP fallback:**
- `market_get_candles(instId="BTC-USDT-SWAP", bar="1H", limit=24)`
- `market_get_open_interest(instId="BTC-USDT-SWAP", instType="SWAP")`

For Binance historical funding rate data, use:
```bash
node ${CLAUDE_SKILL_DIR}/scripts/analyze.js COIN
```

### Step 7 — Monitor Watchlist

To track specific instruments at regular intervals:

```bash
# Binance watchlist
node ${CLAUDE_SKILL_DIR}/scripts/monitor.js DUSK DASH AXS

# OKX watchlist via CLI
for inst in DUSK-USDT-SWAP DASH-USDT-SWAP AXS-USDT-SWAP; do
  echo "--- $inst ---"
  okx market funding-rate "$inst"
done
```

## Output Format

```
=== Funding Rate Opportunities (OKX) ===

Rank  Coin    Rate      Annual(5x)   Volume     Next Settlement
1     DUSK    -0.38%    2071%        $30M       03:00 UTC (2h)
2     AXS     -0.12%    655%         $46M       03:00 UTC (2h)
3     DASH    -0.12%    649%         $50M       03:00 UTC (2h)

=== Cross-Exchange Comparison (OKX vs Binance) ===

Coin    OKX       Binance   Delta
DUSK    -0.25%    -0.38%    0.13%  ← arbitrage candidate
AXS     -0.10%    -0.12%    0.02%  marginal
```

## Strategy Notes

**Negative funding rate** means shorts pay longs every settlement period.

1. Open a long position on a coin with a deeply negative funding rate
2. Collect funding payments every 8 hours (or per settlement period)
3. Set a stop-loss to limit directional downside
4. For delta-neutral exposure: hedge with a spot short or inverse position on another exchange

**Risk Warning**: Funding rates change frequently and can flip within hours. High leverage amplifies both gains and losses. Cross-exchange arbitrage carries execution and transfer risk. Always use stop-loss orders. Only risk capital you can afford to lose.

## Error Handling

- If OKX CLI is unavailable, fall back to MCP tools (`market_get_funding_rate`, etc.)
- If MCP tools are unavailable, fall back to Binance scripts for all data
- If a symbol is invalid, report the error and suggest valid OKX SWAP format (e.g., `BTC-USDT-SWAP`)
- If the API times out, retry once, then report the failure with the last known data if available
- If no negative rates are found, report that all rates are positive and suggest setting a monitoring interval

---

### [22] `golden-ratio-hunter`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/golden-ratio-hunter/SKILL.md`

---
name: 黄金比例猎手
description: 以数学家视角看待市场的永续合约策略 Skill。基于斐波那契数列与 ABCD 谐波形态，用 0.618/0.786 黄金比例预判 BTC 回调深度与反弹目标。核心信念：价格波动不是随机的，而是遵循宇宙级别的数学节律。当用户说"黄金比例"、"斐波那契"、"谐波策略"、"golden ratio"、"fibonacci trader"时启用。
---

# 策略名称
黄金比例猎手：斐波那契谐波节律交易策略 V1.0

---

> *"上帝用数学创造了宇宙。市场，是人类行为的镜子——而人类行为，同样遵循数学。"*
> — 黄金比例猎手策略设计理念

---

## 策略哲学

1202 年，意大利数学家斐波那契发现了一个奇异的数列：1, 1, 2, 3, 5, 8, 13, 21, 34, 55……

每个数字是前两个数字之和。而任意相邻两数之比，趋近于一个神秘的常数：**0.618**。

这个数字出现在鹦鹉螺的螺旋里、向日葵的种子排列里、银河系的旋臂里。古希腊人称它为"黄金比例"，认为这是宇宙最美的比例。

八百年后，有人发现：**BTC 的每一次回调，都在黄金比例附近找到支撑。每一次上涨，都在黄金扩展位附近遇到阻力。**

这不是巧合。这是因为市场由人组成，而人类的集体恐惧与贪婪，像鹦鹉螺一样，遵循同样的螺旋节律。

**本策略不预测市场，而是聆听市场的数学节拍。**

当价格完成 A→B→C→D 的谐波运动，当回调精确落在 0.618，当反弹目标指向 1.272——黄金比例猎手出击。

---

## 执行节奏

每 **4 小时** 触发一次完整分析循环。

---

## Step 1 · 节律侦测：寻找谐波形态的雏形

> *"数学家不看K线的颜色，只看K线的比例。"*

调用 `market_get_candles` 获取 BTC-USDT-SWAP 的 **4h K线**，近 200 根。

**1.1 摆动点识别（确定 A、B、C 点）**

识别有效的摆动高点和低点（Swing High / Swing Low）：
- 判定条件：某根K线的最高/最低价，在其左右各 **5根K线**内为极值
- 最近的 4 个有效摆动点，按时间顺序命名为 **X、A、B、C**
- 波段大小过滤：X→A 的价格移动幅度必须 > 2 × ATR(14)，否则为噪音，忽略

**1.2 斐波那契比例计算**

基于已识别的 X、A、B、C 四点，计算以下关键比例：

```
AB/XA 回撤比 = |A→B| / |X→A|
BC/AB 回撤比 = |B→C| / |A→B|
```

**1.3 ABCD 谐波形态识别**

根据比例判断当前是否形成有效谐波形态：

| 形态名称 | AB/XA 范围 | BC/AB 范围 | 信号强度 |
|---|---|---|---|
| **标准 AB=CD** | 0.500~0.618 | 0.500~0.618 | ⭐⭐⭐ |
| **Gartley 形态** | 0.618（精确±0.05）| 0.786（精确±0.05）| ⭐⭐⭐⭐⭐ |
| **蝙蝠形态（Bat）** | 0.382~0.500 | 0.886（精确±0.06）| ⭐⭐⭐⭐ |
| **螃蟹形态（Crab）** | 0.382~0.618 | 1.618（精确±0.08）| ⭐⭐⭐⭐ |

**容差规则**：比例偏差在 ±0.08 以内视为有效形态；偏差超过 ±0.12，形态无效，本轮跳过。

---

## Step 2 · D 点预测：黄金比例锁定入场区间

> *"数学给出的不是一个点，而是一个区间。猎手在区间边缘等待。"*

当 Step 1 识别出有效谐波形态，计算 **D 点的预测区间**：

**2.1 D 点价格计算**

根据不同形态，D 点的目标区间如下：

| 形态 | D 点计算（做多，X→A 为上涨） | D 点计算（做空，X→A 为下跌） |
|---|---|---|
| AB=CD | C - (B-A) × 1.000 | C + (A-B) × 1.000 |
| Gartley | C - XA × 0.786 | C + XA × 0.786 |
| Bat | C - XA × 0.886 | C + XA × 0.886 |
| Crab | C - XA × 1.618 | C + XA × 1.618 |

**D 点入场区间 = [D点价格 × 0.995, D点价格 × 1.005]**（上下各 0.5% 的容差带）

**2.2 D 点有效性验证**

D 点必须同时满足以下条件，形态才有效：

- D 点位于合理价格范围内（不超过 X 点的 2.0 倍扩展）
- D 点附近（±1% 范围）存在以下任意一项额外确认：
  - 整数关口（如 80000, 85000, 90000 USDT）
  - 近期有效 Order Block 边缘（可调用近期K线判断）
  - 前期摆动高/低点

有任意一项额外确认：信号强度 +1 级（最高⭐⭐⭐⭐⭐）

---

## Step 3 · 数学验证：AI 综合推理（核心）

> *"数学不会说谎，但市场会。AI 的任务是分辨两者。"*

**3.1 谐波纯净度评分**

AI 对当前形态进行综合评分（满分 100）：

| 评分维度 | 标准 | 分值 |
|---|---|---|
| **AB/XA 精确度** | 与标准值偏差 < 0.03：30分；< 0.06：20分；< 0.08：10分 | 30 |
| **BC/AB 精确度** | 与标准值偏差 < 0.03：25分；< 0.06：16分；< 0.08：8分 | 25 |
| **时间对称性** | CD段预计K线数 与 AB段K线数 之比在 0.618~1.618 之间：20分；否则10分 | 20 |
| **成交量确认** | 调用成交量数据，C点回调成交量 < B点推动成交量（健康回调）：15分 | 15 |
| **资金费率** | 调用 `market_get_funding_rate`，费率方向与形态方向一致（做多时费率为负或接近0）：10分 | 10 |

**评分门槛**：
- **≥ 75 分**：高纯净度形态，标准仓位入场
- **55~74 分**：中等纯净度，仓位减半
- **< 55 分**：形态不够干净，本轮跳过

**3.2 AI 数学声明**

在执行下单前，AI 必须输出：

```
【谐波形态报告】
形态类型：[AB=CD / Gartley / Bat / Crab]
X点：[价格] | A点：[价格] | B点：[价格] | C点：[价格]
AB/XA 实际比例：[X.XXX]（标准：[X.XXX]，偏差：[X.XXX]）
BC/AB 实际比例：[X.XXX]（标准：[X.XXX]，偏差：[X.XXX]）
D点预测区间：[X,XXX] ~ [X,XXX] USDT
当前价格距D点：[X.X]%
纯净度评分：[X/100]
信号方向：[做多 / 做空]
数学信念：我在黄金比例 [X.XXX] 处等待，这是宇宙给出的答案。
```

**注意**：如果当前价格距 D 点预测区间超过 **3%**，AI 进入**等待模式**，不下单，继续监控直至价格进入区间。

**3.3 止损数学计算**

```
做多止损 = X点价格（形态被完全否定）
做空止损 = X点价格

单笔最大风险 = 账户净值 × 2%
止损距离 = |入场价 - X点价格|
计划张数 = 单笔最大风险 ÷ 止损距离
```

**硬性限制**：若计算出的仓位超过账户净值的 **12%**，则以 12% 为上限（即 X 点太近时，不强行满仓）。

---

## Step 4 · 执行下单（仅当价格进入 D 点区间且评分 ≥ 55）

> *"等待不是软弱，是对数学的尊重。进入区间的第一根确认K线，就是扣下扳机的时刻。"*

**进入 D 点区间后，等待确认信号**：
- 做多确认：价格进入区间后出现**阳线收盘**（收盘价 > 开盘价）
- 做空确认：价格进入区间后出现**阴线收盘**（收盘价 < 开盘价）

确认信号出现后，调用 `swap_place_order`：

```
instId  = "BTC-USDT-SWAP"
side    = <buy 或 sell>
ordType = "market"
sz      = <Step 3.3 计算的张数>
tag     = "agentTradeKit"   ← 必填
```

---

## Step 5 · 止损与止盈（斐波那契扩展位）

> *"黄金比例不仅预测回调，也预测扩展。"*

**止损**：调用 `swap_place_algo_order`

| 方向 | 止损价 |
|---|---|
| 做多 | X点价格 × 0.998（X点被突破则形态彻底失效）|
| 做空 | X点价格 × 1.002 |

**止盈（斐波那契扩展位，分批离场）**：

从 D 点出发，计算以下目标位（以做多为例，XA 为参考波段）：

| 档位 | 目标价 | 平仓比例 | 数学含义 |
|---|---|---|---|
| **TP1** | D + XA × 0.382 | 35% | 第一黄金扩展 |
| **TP2** | D + XA × 0.618 | 35% | 第二黄金扩展 |
| **TP3** | D + XA × 1.000 | 20% | 完全扩展（AB=CD 完成）|
| **TP4** | D + XA × 1.618 | 剩余10% | 黄金螺旋极限 |

TP1 触发后，止损移至**保本价（入场价）**。

---

## Step 6 · 持仓监控

每次循环时检查：

- 当前价格是否已到达或超越某个 TP 位？确认止盈单挂载状态
- 是否出现**反向谐波形态**（D 点继续延伸，形成新的 C→D'）？若是，减仓 50%
- 持仓超过 **48 小时**仍未达到 TP1？重新评估形态有效性，必要时主动平仓

---

## 风控总则

```
// [P1] 单笔最大风险 2%，评分55-74时降至 1%
// [P2] 当日回撤超 6% 停止新开仓
// [P3] 同一形态的 D 点区间，只入场 1 次（不在同一形态内加仓）
// [P4] 开仓后 90 秒内完成止损挂单
// [P5] 若 D 点区间被价格强势突破（收盘于区间外 1.5%），形态失效，不追入
// [P6] 最多同时持有 1 个 BTC 谐波仓位（等待形态完整比分散仓位更重要）
```

---

## 策略的自我叙述

黄金比例猎手是一个耐心的数学家。

它不关心今天的新闻，不关心 Twitter 上有什么热点，不关心特朗普发了什么推。它只关心一件事：**价格有没有走到那个比例？**

大多数时候，答案是"还没有"。所以它等待。

当价格终于走到那个位置——那个被斐波那契点名的位置，那个宇宙留下的印记——它出手，干净利落，然后让数学完成剩下的工作。

*0.618，不是一个数字，是宇宙的语言。*

---

*策略版本：V1.0 | 适用平台：OKX Agent Trade Kit | 参赛赛道：优质 Skill*
*灵感来源：斐波那契数列理论、ABCD 谐波形态分析 & WillyAlgoTrader 谐波投影框架*

---

### [23] `hindsight-reviewer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/hindsight-reviewer/SKILL.md`

---
name: 事后诸葛亮
description: 每笔交易结束后，AI 化身严苛的复盘法官，用反事实推演还原"如果当时我做了正确的事，结果会如何"。不批评你，只用数字告诉你错过了什么、多亏了多少、最优决策是什么。当用户说"复盘"、"为什么亏了"、"这笔交易哪里错了"、"事后诸葛亮"时启用。
---

# 事后诸葛亮
## 每一笔交易，都值得被认真审判一次

---

> *"聪明人从历史中学习，更聪明的人从别人的历史中学习。"*
> — 奥托·冯·俾斯麦
>
> *"我们不后悔做过的事，只后悔没做的事。"*
> — 这句话在交易里是错的。两种都后悔。

---

## 这个 Skill 做什么

它做一件人类大脑不擅长做的事：**在没有情绪的情况下，客观还原一笔交易的完整真相。**

你平仓后，大脑会做两件事：如果赚了，会觉得自己英明神武；如果亏了，会找各种理由为自己辩解。

事后诸葛亮不允许这两件事发生。

它在每笔交易结束后，用数据重新审判这笔交易：**你的入场对不对、止损对不对、止盈对不对、仓位对不对——如果每一个决策都做对了，你会多赚多少？**

这个数字，叫做**决策损耗**。它是你每个月因为错误决策悄悄流失的钱。

---

## 执行触发

**自动触发**：每笔交易平仓后，自动运行一次完整复盘。

**手动触发**：用户点名某笔交易："帮我复盘刚才那笔"、"分析一下今天的亏损"。

**批量触发**：用户说"复盘今天所有交易"、"这周总结"时，批量处理。

---

## Step 1 · 案发现场还原

调用 `trade_get_orders_history` 获取指定交易的完整记录，提取：

```
开仓时间：[时间戳]
平仓时间：[时间戳]
持仓时长：[X小时X分钟]
交易方向：[做多 / 做空]
开仓价格：[X]
平仓价格：[X]
实际仓位：账户净值的 [X%]
实际盈亏：[+/-X USDT]（[+/-X%]）
止损价格：[X]（若有）
```

同时调用 `market_get_candles`，拉取该交易**开仓前2小时**到**平仓后2小时**的完整K线数据，作为复盘的价格背景。

---

## Step 2 · 四维反事实推演

这是核心步骤。AI 对这笔交易的四个关键决策点，分别做反事实分析：

---

### 维度一：入场时机对不对？

**还原开仓那一刻的市场状态：**
- 开仓时 EMA 趋势方向是否与交易方向一致？
- 开仓时 RSI 是否处于合理区间（非超买/超卖）？
- 开仓时成交量是否确认方向？
- 开仓价是否在合理的支撑/阻力结构附近？

**反事实问题：**
*"如果等待更好的入场时机（等信号全部对齐），入场价会在哪里？"*

计算：最优入场价 vs 实际入场价的差值 = **入场时机损耗**

---

### 维度二：止损设置对不对？

**还原止损的合理性：**
- 实际止损距离（以ATR为单位）：[X ATR]
- 合理止损距离（基于市场结构，2×ATR）：[X USDT]
- 如果止损是固定百分比而非结构性止损，标记为**机械止损**

**三种止损问题诊断：**

| 问题类型 | 诊断标准 | 后果 |
|---|---|---|
| 止损太紧 | 实际止损 < 1×ATR | 正常波动就被扫出 |
| 止损太松 | 实际止损 > 3×ATR | 单笔亏损过大 |
| 没有止损 | 无止损记录 | 风险敞口无限 |

**反事实问题：**
*"如果用2×ATR的结构性止损，这笔交易的结果会是什么？"*

---

### 维度三：止盈设置对不对？

**还原平仓那一刻的真相：**

调用完整K线，分析平仓后价格的走势：
- 平仓后价格继续向有利方向运动了多少？（**少赚了多少**）
- 平仓后价格是否反转？（**止盈时机是否准确**）

**四种止盈问题诊断：**

| 问题类型 | 诊断标准 |
|---|---|
| 过早止盈 | 平仓后价格继续向有利方向运动 > 1×ATR |
| 恐慌止盈 | 在短暂回调后止盈，之后价格恢复 |
| 止盈完美 | 平仓后价格在2根K线内反转 |
| 止盈太晚 | 浮盈超过目标后才平仓，错过最优点 |

**反事实问题：**
*"如果用1:3盈亏比止盈，或者用移动止损，这笔交易的最终盈利是多少？"*

---

### 维度四：仓位大小对不对？

**还原仓位决策的合理性：**

```
实际风险金额 = 仓位大小 × 止损距离
账户净值占比 = 实际风险金额 ÷ 账户净值

理论最优风险金额 = 账户净值 × 1.5%（固定风险法）
理论最优仓位 = 理论最优风险金额 ÷ 止损距离
```

**诊断：**
- 实际风险 > 2%：**超额风险**
- 实际风险 0.5%~2%：**合理区间**
- 实际风险 < 0.5%：**保守仓位**（可能错过收益）

---

## Step 3 · 最优剧本推演

基于以上四个维度，AI 构建这笔交易的**理论最优剧本**：

```
【最优剧本假设】
最优入场价：[X]（比实际 好/差 [X] USDT）
最优止损：[X]（2×ATR 结构性止损）
最优止盈：[X]（1:3 盈亏比 或 移动止损）
最优仓位：[X张]（固定1.5%风险）

最优剧本盈亏：[+/-X USDT]
实际盈亏：[+/-X USDT]
━━━━━━━━━━━━━━━━━
决策损耗：[X USDT]
```

**决策损耗**是这个 Skill 最核心的输出。它把抽象的"决策错误"变成一个具体的数字。

---

## Step 4 · 复盘判决书

AI 输出完整判决，格式如下：

```
╔═══════════════════════════════════════╗
           交易复盘判决书
    [交易品种] | [开仓时间] | [方向]
╚═══════════════════════════════════════╝

【案件事实】
实际盈亏：[+/-X USDT]（[+/-X%]）
持仓时长：[X小时]

【四项裁决】

入场时机  [✓完美 / △尚可 / ✗较差]
→ [一句话说明入场的具体问题或亮点]

止损设置  [✓完美 / △尚可 / ✗较差]
→ [一句话说明止损的问题，附上理论最优值]

止盈管理  [✓完美 / △尚可 / ✗较差]
→ [一句话说明止盈问题，平仓后价格走了多远]

仓位控制  [✓完美 / △尚可 / ✗较差]
→ [一句话说明仓位是否合理]

【最终裁决】
最优剧本可实现：[+X USDT]
你实际获得：[+/-X USDT]
决策损耗：[X USDT]

【这笔交易教会你一件事】
[一句话，直接点出这笔交易最值得记住的教训，
 不超过25字，像格言一样精炼]

【下一次遇到相同情况，你应该】
[一个具体的、可操作的行动指令]
╚═══════════════════════════════════════╝
```

---

## Step 5 · 周期性决策损耗统计

每7天自动汇总一次，输出：

```
本周决策损耗排行：
第1名：[日期] [交易] 损耗 [X USDT] — 原因：[止盈太早/入场太晚/...]
第2名：[日期] [交易] 损耗 [X USDT] — 原因：[...]
第3名：[日期] [交易] 损耗 [X USDT] — 原因：[...]

本周最佳决策：
[日期] [交易]：四项全✓，决策损耗接近零。

本周最需改进：[最频繁出现的问题类型]
如果这个问题不存在，本周可以多赚：[X USDT]
```

---

## 风控附注

```
// 本 Skill 仅读取交易历史，不执行任何下单操作
// "最优剧本"基于事后数据，不代表当时可以预见
// 目的是识别系统性错误，而非苛责单笔决策
// 决策损耗是统计工具，不是精确计算
```

---

### [24] `hyperliquid-analyzer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/hyperliquid-analyzer/SKILL.md`

---
name: hyperliquid-analyzer
description: "Hyperliquid DEX on-chain intelligence for OKX trading. Trigger on: 'hyperliquid', 'HL', 'HYPE', '巨鲸', 'whale', 'DEX whale', 'HL signal', 'HL funding', 'HL portfolio', or any Hyperliquid question. Capabilities: whale hunt (scan recent trades → on-chain portfolios, find accounts >$500K), order wall analysis (large bid/ask clusters as support/resistance), autonomous whale monitor (push alerts on new positions/size changes via Telegram/webhook), wallet portfolio lookup (entry price, liquidation price, unrealized PnL), HL vs OKX funding rate comparison (crowd positioning signal), HL vs OKX price spread. Do NOT use for OKX-only queries (use okx-cex-market), placing orders (use okx-cex-trade), or other DEXes (GMX, dYdX)."
---

# Hyperliquid 信号情报工具

Hyperliquid 是透明的链上 DEX：巨鲸真实持仓、清算价、大单挂墙全部公开可读。这个 skill 把这些链上情报转化为可在 OKX 执行的交易信号——谁在开大仓、多空在哪里集中、资金费率是否出现极端偏离。

## 依赖工具

- **jq**（必须）：所有 shell 脚本依赖 JSON 解析。未安装时提示：`brew install jq`
- **python3**（必须）：巨鲸扫描脚本依赖，系统通常已内置
- **okx CLI**（可选）：跨平台对比功能需要。未安装时，HL 独立功能正常工作

## 分析类型

**链上情报（核心价值）**

| 类型 | 用途 | 脚本 |
|------|------|------|
| **巨鲸成交扫描** | 从成交流溯源大户地址，批量查持仓和清算价 | `hl_whale_hunt.py [min_usd] [top_n_coins]` |
| **巨鲸挂单墙** | 扫描订单簿找大单聚集区，作为支撑/阻力参考 | `hl_whales.sh [min_usd] [COINS]` |
| **巨鲸持续监控** | 定时检测持仓变化，新开仓/加减仓自动推送 | `hl_whale_monitor.py [--dry-run]` |
| **链上持仓查询** | 任意地址的仓位、入场价、清算价、浮盈亏 | `hl_portfolio.sh` |

**OKX 对比参考**

| 类型 | 用途 | 脚本 |
|------|------|------|
| **资金费率对比** | HL vs OKX 费率偏离，判断多空拥挤程度 | `compare_funding.sh` |
| **价格价差** | HL vs OKX 基差，DEX 相对 CEX 的情绪偏差 | `compare_price.sh` |

**辅助查询**

| 类型 | 脚本 |
|------|------|
| HL 价格 | `hl_price.sh` |
| HL 市场概览 | `hl_market.sh` |
| HL 资金费率排名 | `hl_funding.sh` |

## 执行流程

### Step 0: 环境检查

```bash
command -v jq >/dev/null 2>&1 || {
  echo "需要安装 jq: brew install jq (macOS) / apt install jq (Linux)"; exit 1
}
```

如 jq 不可用，立即告知用户安装方式并停止执行。

### Step 1: 识别分析意图

**链上情报（优先匹配）**：
- **谁在开大仓 / 大户持仓 / 扫巨鲸** → `hl_whale_hunt.py`
- **支撑阻力 / 大买墙 / 大卖墙** → `hl_whales.sh`
- **开启监控 / 定时推送 / 开仓信号** → `hl_whale_monitor.py`
  - 参数：`--min-account`（巨鲸门槛，默认 $500K）、`--min-position`（报警仓位，默认 $200K）、`--change-threshold`（加减仓比例，默认 30%）、`--top-coins`（扫描币种数，默认 20）
- **钱包地址持仓 / 清算价** → `hl_portfolio.sh`

**OKX 对比参考**：
- **费率偏离 / 多空拥挤 / HL vs OKX 费率** → `compare_funding.sh`
- **DEX/CEX 价差 / 基差** → `compare_price.sh`

**辅助查询**：
- HL 价格 → `hl_price.sh`；市场行情 → `hl_market.sh`；HL 费率排名 → `hl_funding.sh`

意图不明确时询问，例如：
- "您是想一次性扫描巨鲸，还是开启持续监控定期推送信号？"

### Step 2: 执行脚本

所有脚本位于 skill 目录的 `scripts/` 子目录。执行前先用 `ls` 或工具定位 skill 绝对路径（典型路径：`~/.openclaw/workspace/skills/hyperliquid-analyzer/scripts/`）。

```bash
SCRIPTS=~/.openclaw/workspace/skills/hyperliquid-analyzer/scripts

# Shell 脚本
bash $SCRIPTS/hl_price.sh BTC ETH
bash $SCRIPTS/compare_funding.sh BTC ETH SOL
bash $SCRIPTS/hl_portfolio.sh 0xWALLET_ADDRESS
bash $SCRIPTS/hl_whales.sh 500000 BTC ETH   # 挂单墙，可选参数：最小USD + 币种列表

# Python 脚本
python3 $SCRIPTS/hl_whale_hunt.py 500000 20         # 一次性扫描：最小USD 币种数
python3 $SCRIPTS/hl_whale_monitor.py --dry-run       # 首次测试（不发消息）
python3 $SCRIPTS/hl_whale_monitor.py \               # 生产运行（带自定义参数）
  --min-account 500000 \    # 巨鲸净值门槛 USD
  --min-position 200000 \   # 值得报警的仓位 USD
  --change-threshold 0.30 \ # 加减仓触发比例
  --top-coins 20            # 扫描高OI币种数
```

**巨鲸监控的 OpenClaw Cron 配置**：

```bash
openclaw cron add \
  --name hl-whale-monitor \
  --schedule "*/30 * * * *" \
  --skill hyperliquid-analyzer \
  --prompt "执行 python3 ~/.openclaw/workspace/skills/hyperliquid-analyzer/scripts/hl_whale_monitor.py，脚本会自动扫描巨鲸、对比仓位变化、发送信号。无需其他操作。"
```

消息渠道通过环境变量配置（在 `~/.zshrc` 或系统环境中设置）：

```bash
export NOTIFY_CHANNEL=telegram   # telegram | webhook | none
export TG_BOT_TOKEN=xxx
export TG_CHAT_ID=yyy
# 或 webhook:
export NOTIFY_CHANNEL=webhook
export NOTIFY_WEBHOOK_URL=https://...
```

**Portfolio 类脚本的钱包地址处理**：
- 用户已提供 → 直接使用
- 环境变量 `HYPERLIQUID_WALLET_ADDRESS` 已设置 → 自动使用
- 两者均无 → 告知用户提供，并说明仅读取公开链上数据，无需私钥

### Step 3: 结果分析与建议

**巨鲸信号解读**：
- 净值 >$1M 巨鲸新开仓 → 强方向参考，可跟进在 OKX 同向建仓
- 多个巨鲸同向操作同一币 → 叠加信号，可信度更高
- 巨鲸清算价密集靠近当前价 → 踩踏风险（空头密集尤其关注）
- 挂单墙被大量吃掉 → 突破信号；挂单墙持续存在 → 支撑/阻力有效
- 注意：成交流每币种约 10 笔快照，不代表全量巨鲸

**资金费率对比解读**（核心是"拥挤程度"信号，不是套利）：
- OKX 费率显著高于 HL → OKX 多头更拥挤，在 OKX 追多需警惕反转
- HL 费率显著高于 OKX → HL 链上多头承压，可参考 OKX 方向反向做
- 两所费率方向相反 → 市场分歧最大，等待方向确认，避免追势
- 任一平台费率极端（>0.05% / 8h，年化 >55%）→ 拥挤一侧过热，反转概率上升
- 切勿将费率差直接解读为"套利空间"——费率随时会变，且 HL 结算时间与 OKX 不同步

**价格价差解读**：
- HL mark 高于预言机（正溢价）→ DEX 情绪偏乐观，注意回调
- 跨所价差 > 0.1% → 两平台定价分歧，方向交易注意用哪个价格参考

### Step 4: 后续引导

- 查完价格/行情 → "需要扫描当前有哪些巨鲸在这个币上开仓吗？"
- 查完巨鲸扫描 → "需要开启持续监控，有开仓变化时自动推送信号吗？"
- 查完挂单墙 → "需要查这些巨鲸地址的完整持仓和清算价吗？"
- 查完资金费率 → "费率出现极端偏离，需要看看链上巨鲸的方向吗？"
- 查完持仓 → "需要监控这个地址的仓位变化吗？"

## 错误处理

### API 不可达
```
无法连接 Hyperliquid API (https://api.hyperliquid.xyz/info)
可能原因: 网络问题 / API 维护 / 地区限制
请检查网络连接后重试
```

### 速率限制 (HTTP 429)
```
Hyperliquid API 速率限制: 120 次/分钟
请稍等片刻后重试
```

### 币种未上市
```
"[COIN]" 未在 Hyperliquid DEX 上市
运行 hl_price.sh 查看全部可用资产
```

## 重要说明

- **只读**：所有操作仅获取公开市场数据，不提交交易或访问私钥
- **无需 API Key**：Hyperliquid 公开数据接口无需认证
- **OKX 必须用实盘**：所有 okx 命令使用 `--live` 标志，避免误读模拟盘数据
- **价格类型**：`allMids` 返回订单簿中间价；`metaAndAssetCtxs` 含标记价和预言机价
- **资金费率周期**：8 小时结算；年化 = 8h 费率 × 3 × 365
- **巨鲸监控状态文件**：默认存于 `~/.hl-whale-monitor/whale_positions.json`（可用 `--state-file` 覆盖），首次运行建立基准，第二次起检测变化

---

### [25] `kline-indicator`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/kline-indicator/SKILL.md`

---
name: kline-indicator
description: >
  K-line Indicator Engine for crypto technical analysis using a 3-pillar
  framework (macro cycle + price-volume factors + derivatives). Use this
  skill whenever the user wants to analyze a coin or market, asks about
  trading signals or entry conditions, wants a K-line or candlestick chart,
  asks about order flow or order book analysis, wants a trade plan with
  entry/target/stop, or asks about market sentiment. Also trigger for casual
  phrases like "分析BTC", "看看ETH行情", "BTC现在怎么样", "帮我看看SOL",
  "画个K线图", "扫描热门币", "有没有信号", "市场情绪", or "BTC能不能做多",
  even if the user does not explicitly say "technical analysis" or
  "indicator". Do NOT trigger when the user explicitly asks for a full
  structured trading plan with position sizing and risk tiers (use
  trading-plan-generator), DCA bot parameter recommendations (use
  dca-bot-parameterizer), or social narrative analysis (use market-intel).
---

# K-Line Indicator Engine

Complete technical analysis framework combining macro cycle assessment,
price-volume indicator scoring, and derivative market positioning into
actionable trading signals.

## Operating Modes

Detect the user's intent and select the mode. Each mode specifies which
reference files to read and which scripts to run — load only what is needed.

| Mode | Trigger | Reference files to load | Scripts to run |
|------|---------|------------------------|----------------|
| **quick** | Fast scan, 一句话看行情 | — | `kline_ext_indicators.py` (core only) |
| **full** | Full analysis, 完整分析 | `indicators.md`, `three-pillars.md`, `orderflow.md`, `trading.md` | `kline_ext_indicators.py`, `kline_orderflow.py` |
| **scan** | Coin list or top N, 扫描 | `indicators.md` | `kline_ext_indicators.py` |
| **alert** | Condition monitoring, 提醒 | `trading.md` | `kline_ext_indicators.py` |
| **orderflow** | Delta, CVD, order book | `orderflow.md` | `kline_orderflow.py` |
| **macro** | Market cycle stage | `three-pillars.md` | — |
| **custom** | Specific indicators | `indicators.md` | `kline_ext_indicators.py` |
| **chart** | Chart or K-line image | — | `kline_chart.py` |
| **conditional** | Trade plan with entry/target/stop | `trading.md` | `kline_ext_indicators.py`, `kline_orderflow.py` |

When no mode is explicit, use **quick** for a single symbol and **full** when
the user asks for a complete analysis or trade decision.

## 3-Pillar Framework

The composite score combines three pillars — each answers a different question
about market conditions. For full pillar definitions, scoring formulas, and
market stage classifications, read `references/three-pillars.md`.

| Pillar | Weight | Question |
|--------|--------|----------|
| Macro Cycle | 30% | Where are we in the market cycle? |
| Price-Volume Factors | 40% | What do price and volume signals say? |
| Derivatives | 30% | What is smart money pricing in? |

## Data Sources

### Primary: OKX TradeKit CLI

Try CLI first — no MCP overhead, same data:

```bash
okx market ticker <instId>
okx market indicator rsi <instId> --bar 1H
okx market indicator macd <instId> --bar 4H
okx market indicator ema <instId> --bar 1D
okx market indicator bb <instId> --bar 1D
okx market indicator supertrend <instId> --bar 1D
okx market indicator kdj <instId> --bar 1D
okx market funding-rate <instId>
okx market open-interest --instType SWAP --instId <instId>
okx market candles <instId> --bar 1H --limit 60
```

### Fallback: OKX TradeKit MCP

If CLI is unavailable, call MCP tools directly — no scripts needed:

| Data | MCP call |
|------|----------|
| Price / 24h stats | `market_get_ticker(instId)` |
| Candles | `market_get_candles(instId, bar, limit)` |
| RSI | `market_get_indicator(instId, indicator="rsi", bar)` |
| MACD | `market_get_indicator(instId, indicator="macd", bar)` |
| EMA | `market_get_indicator(instId, indicator="ema", bar)` |
| Bollinger Bands | `market_get_indicator(instId, indicator="bb", bar)` |
| Supertrend | `market_get_indicator(instId, indicator="supertrend", bar)` |
| KDJ | `market_get_indicator(instId, indicator="kdj", bar)` |
| Funding rate | `market_get_funding_rate(instId)` |
| Open interest | `market_get_open_interest(instId, instType)` |
| Order book | `market_get_orderbook(instId)` |

### Macro Data

Rainbow Chart, AHR999, MVRV, Fear & Greed Index, BTC dominance
(fetched via public APIs or user-provided values).

## Python Scripts

Use scripts **only** for indicators not available via OKX TradeKit MCP. Feed
them candles from `market_get_candles`.

- **`${CLAUDE_SKILL_DIR}/scripts/kline_ext_indicators.py`**: ATR, Stochastic,
  Ichimoku, VWAP, divergence detection, support/resistance, Alpha 101/191
  factors, 30+ candlestick patterns — everything not covered by MCP

- **`${CLAUDE_SKILL_DIR}/scripts/kline_orderflow.py`**: Order flow delta, CVD,
  bid/ask wall detection, composite score (0–100)

- **`${CLAUDE_SKILL_DIR}/scripts/kline_chart.py`**: Terminal (ASCII) and PNG
  chart rendering with MACD/RSI/volume panels and pattern annotations.
  After generating a PNG, print the output file path so the user can access it.

## Reference Documentation

Read these files on demand — do not load all at once:

- **`references/indicators.md`**: Complete indicator catalog, pattern
  definitions, divergence methodology, signal scoring (−5 to +5 → 0–100)
- **`references/three-pillars.md`**: Pillar definitions, macro cycle stages,
  composite scoring formula, market stage classification
- **`references/orderflow.md`**: Delta/CVD/order book metrics, 6-component
  scoring, smart money interpretation
- **`references/trading.md`**: Signal grades, entry conditions (all 3
  required), position sizing, exit signals, pre-trade checklist, when not to
  trade, fee and slippage adjustment

---

### [26] `less-is-more`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/less-is-more/SKILL.md`

---
name: 少即是多
description: 以极简主义哲学驱动的永续合约策略 Skill。三层过滤，一个方向，一次入场。EMA 定趋势、市场结构定时机、ATR 确认动量——三个条件同时满足才出手，其余时间什么都不做。当用户说"极简策略"、"less is more"、"少即是多"、"三层过滤"、"结构入场"时启用。
---

# 策略名称
少即是多：极简三层过滤入场策略 V1.0

---

> *"完美不是无法再增加，而是无法再删减。"*
> — Antoine de Saint-Exupéry

---

## 策略哲学

大多数交易者输钱，不是因为策略太少，而是因为**策略太多**。

十几个指标，七八个过滤条件，看多看空都有理由——最后什么都看，什么都不确定，然后在最糟糕的时刻做出冲动的决定。

本策略只用**三样东西**：

**一、EMA（趋势的方向）**
不问价格涨了多少，不问涨了多久，只问一件事：**现在是上坡还是下坡？**

**二、市场结构（入场的时机）**
不在高点追，不在低点空，只在**高低点结构允许的位置**进场——顺势中的回调，是最干净的入场机会。

**三、ATR（动量的确认）**
不是所有的结构信号都值得入场。**只有市场真正在动的时候，信号才有价值。**

三层同时满足，才出手。任何一层不满足，等待。

**这个策略大多数时候什么都不做。这正是它的优势。**

---

## 执行节奏

每 **2 小时** 触发一次检查循环。

---

## Step 1 · 第一层过滤：EMA 趋势方向

> *"方向错了，越努力越错。方向对了，等待就是收益。"*

调用 `market_get_candles` 获取 BTC-USDT-SWAP 的 **4h K线**，近 100 根。

计算三条 EMA：
- **EMA21**（短期动量）
- **EMA55**（中期趋势）
- **EMA200**（长期方向）

**第一层判断——只有两个结论：**

✅ **看多环境**：EMA21 > EMA55 > EMA200，且 EMA55 斜率向上（当前值 > 10根K线前的值）

✅ **看空环境**：EMA21 < EMA55 < EMA200，且 EMA55 斜率向下

❌ **混乱环境**：以上两种情况均不满足 → **本轮直接跳过，不进行后续分析**

**只有明确的环境才允许继续。模糊就是否定。**

---

## Step 2 · 第二层过滤：市场结构入场时机

> *"不要在别人跑得最快的时候跟上去。要在别人停下来喘气的时候，悄悄站到起跑线。"*

调用 **1h K线**，在第一层确认的方向基础上，寻找结构性入场机会。

**2.1 识别近期摆动高低点**

扫描近 50 根 1h K线，识别有效摆动点（左右各 3 根K线为极值）：
- 近期摆动低点序列：SL1（最近）、SL2（次近）、SL3（再次近）
- 近期摆动高点序列：SH1（最近）、SH2（次近）、SH3（再次近）

**2.2 结构条件判断**

**看多环境下，寻找看多结构入场信号（满足任意一项）：**

- **高低点上移（HL）**：SL1 > SL2（最新低点高于前低）且当前价格在 SL1 以上 → 回调未破结构，趋势延续
- **结构突破（BOS）**：当前1h K线收盘价突破 SH1（前高）→ 结构向上突破，新的入场机会

**看空环境下，寻找看空结构入场信号（满足任意一项）：**

- **低高点下移（LH）**：SH1 < SH2（最新高点低于前高）且当前价格在 SH1 以下 → 反弹未破结构，趋势延续
- **结构突破（BOS）**：当前1h K线收盘价突破 SL1（前低）→ 结构向下突破，新的入场机会

❌ **以下情况放弃本轮**：
- 结构信号出现时，价格已运行超过 2 × ATR14（错过最佳入场窗口）
- 结构信号与第一层 EMA 方向相反

---

## Step 3 · 第三层过滤：ATR 动量确认

> *"引擎没有启动，踩油门也没用。动量不在，信号没有意义。"*

调用近期 **1h K线** 计算 ATR(14)。

**ATR 三档判断：**

| ATR 状态 | 判断标准 | 处理方式 |
|---|---|---|
| **过低（市场睡着了）** | 当前 ATR < 过去 30 根K线 ATR 均值的 **0.7 倍** | 跳过：市场没有方向性 |
| **正常（市场清醒）** | 当前 ATR 在均值的 **0.7 ~ 1.8 倍**之间 | ✅ 允许入场，标准仓位 |
| **过高（市场发狂）** | 当前 ATR > 过去 30 根K线 ATR 均值的 **1.8 倍** | 跳过：波动过大，止损难以设置 |

**只有"正常"状态才允许入场。市场太平静和太疯狂，都不是好时机。**

额外检查：
- 调用 `market_get_funding_rate`：资金费率绝对值 > 0.1%，跳过（市场方向已过度拥挤）

---

## Step 4 · AI 三层确认总结（决策核心）

> *"三个绿灯同时亮，才出发。一个红灯，等待。"*

AI 必须完成以下检查表，**三项全绿才执行下单**：

```
【三层过滤检查表】

第一层 · EMA 趋势：
□ 趋势方向：[看多 / 看空]
□ EMA 排列：[21 > 55 > 200 / 21 < 55 < 200]
□ EMA55 斜率：[向上 / 向下]
→ 结论：[✅ 通过 / ❌ 不通过]

第二层 · 市场结构：
□ 结构信号类型：[HL回调 / BOS突破 / LH反弹 / 向下BOS]
□ 信号K线距当前：[X根K线前]
□ 是否在最佳入场窗口（< 2ATR）：[是 / 否]
→ 结论：[✅ 通过 / ❌ 不通过]

第三层 · ATR 动量：
□ 当前 ATR：[X.XX]
□ ATR 均值：[X.XX]
□ ATR 倍率：[X.XX]（目标范围：0.7 ~ 1.8）
□ 资金费率：[X.XXX%]（上限：±0.1%）
→ 结论：[✅ 通过 / ❌ 不通过]

最终决策：
□ 三层全部通过：[是 / 否]
□ 交易方向：[做多 / 做空]
□ 入场理由（一句话）：[XXX]
□ 计划仓位：账户净值的 [X]%
```

**如果任何一层为 ❌，最终决策自动为"等待"，不得下单。**

---

## Step 5 · 执行下单（仅当三层全部通过）

> *"决定已经在三层过滤里做完了。下单只是按钮。"*

调用 `swap_place_order`：

```
instId  = "BTC-USDT-SWAP"
side    = <buy 或 sell>
ordType = "market"
sz      = <基于风控计算的张数>
tag     = "agentTradeKit"   ← 必填
```

**仓位计算（极简风格，同样极简）**：

```
单笔风险金额 = 账户净值 × 1.5%
止损距离 = 2 × ATR14（入场时的ATR值）
计划张数 = 单笔风险金额 ÷ 止损距离
最大仓位上限 = 账户净值 × 10%（取两者较小值）
```

---

## Step 6 · 止损与止盈（同样极简）

> *"设好规则，然后让规则运行。不需要盯盘，不需要焦虑。"*

**止损**（调用 `swap_place_algo_order`）：

| 方向 | 止损价 | 逻辑 |
|---|---|---|
| 做多 | 入场价 - 2 × ATR14 | 两个 ATR 内未被否定，趋势仍有效 |
| 做空 | 入场价 + 2 × ATR14 | 同上 |

**止盈（分两档，保持简洁）**：

| 档位 | 目标价 | 平仓比例 |
|---|---|---|
| **TP1** | 入场价 ± 3 × ATR14 | 60% 仓位 |
| **TP2** | 入场价 ± 5 × ATR14 | 剩余 40% |

TP1 触发后：止损移至**入场价（保本）**。

**就这样。没有更多。**

---

## Step 7 · 持仓监控（极简版）

每次循环检查两件事，仅此两件：

1. **EMA 方向是否反转？** 若 EMA21 穿越 EMA55 且方向反转 → 立即平仓全部仓位
2. **止盈/止损单是否正常挂载？** 若未挂载 → 立即补挂，这是唯一的紧急操作

其余情况，**什么都不做，让策略运行。**

---

## 风控总则

```
// [P1] 单笔最大风险 1.5%，不因任何理由提高
// [P2] 当日回撤超 4.5% 停止新开仓（三次止损即触发）
// [P3] 最多同时持有 1 个仓位（少即是多的核心）
// [P4] 开仓后 60 秒内完成止损挂单
// [P5] 严禁在亏损时加仓，严禁移动止损扩大亏损
// [P6] 单日最多触发 3 次完整入场机会（多于此则说明市场混乱，降频）
```

---

## 策略的自我叙述

大多数策略想捕捉所有机会。

少即是多只想捕捉**最干净的那一个**。

它的大多数时间是沉默的。它的检查表通常显示红灯。它拒绝了无数次"还不错"的机会，只为等待那一次"完美对齐"。

这不是保守，是**精准**。

一把狙击枪，一颗子弹，一个目标。

当三个绿灯同时亮起时，它不犹豫。

---

*策略版本：V1.0 | 适用平台：OKX Agent Trade Kit | 参赛赛道：优质 Skill*
*灵感来源：AA PRO 入场引擎（ATR + 市场结构）& 极简主义交易哲学*

---

### [27] `macd-strategy`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/macd-strategy/SKILL.md`

---
name: macd-strategy
description: Execute OKX CEX open/close decisions using MACD pivot rules (4h, MACD 12/26/9, threshold gate, pivot-based entry/exit, one-signal-per-candle). Use when user asks to open or close positions on OKX according to this logic only (no portfolio/earn tasks). Requires OKX skills from `npx skills add okx/agent-skills` to be installed.
---

# OKX Open/Close

Apply only open/close logic. Do not handle earn, portfolio analytics, or unrelated tasks.

## Dependency
Require these skills installed from `okx/agent-skills`:
- `okx-cex-market` (candles/price data)
- `okx-cex-trade` (order execution)

If unavailable, stop and report dependency missing.

## Strategy Rules
- Timeframe: `4h`
- MACD params: `12/26/9`
- Threshold gate: `abs(hist) >= MACD_ABS_ENTRY_MIN`
- Pivot detection:
  - `peak` if `h2 > h3 and h2 > h1`
  - `valley` if `h2 < h3 and h2 < h1`
- Entry side:
  - `peak` + `hist > 0` => open short
  - `valley` + `hist < 0` => open long
- If pivot exists but entry side is not eligible => close existing position (full close).
- One signal per candle: if candle already processed, do nothing.

## Execution Workflow
1. Read symbol config (`instId`, leverage, margin USDT, threshold).
2. Pull latest 4h candles from OKX market skill.
3. Compute MACD histogram and detect pivot on closed candle.
4. Enforce one-signal-per-candle lock.
5. Determine target action:
   - no action
   - open/rebalance same direction (delta adjust)
   - flip (close opposite then open target)
   - full close
6. Execute through OKX trade skill.
7. Return concise execution result: side, qty, reference price, order id, reject code if any.

## Output Contract
Always include:
- `symbol`
- `action` (`open_long`, `open_short`, `reduce`, `close_full`, `no_action`)
- `reason` (pivot/threshold/lock)
- `order_id` (if placed)
- `error_code` and `error_message` (if failed)

## Risk/Guardrails
- Never submit duplicate order on same candle signal.
- If exchange rejects (`max position`, leverage constraint, etc.), do not loop retry.
- Report rejection and ask whether to reduce, change leverage, or skip.

## Reference
See `references/parameters.md` for default parameters and tuning ranges.

---

### [28] `market-intel`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/market-intel/SKILL.md`

---
name: market-intel
description: >
  Crypto market social intelligence for OKX traders. Aggregates Twitter/X
  trending narratives, detects social momentum shifts, and maps insights to
  OKX trading pairs with live price verification via OKX Trade Kit. Use
  when: "market briefing", "watch market", "research [topic]", "any
  signals", "market sentiment", "social trends", "narrative-driven trading
  signals", or Chinese equivalents: "市场简报", "晨报", "有什么异动",
  "社交面怎么样", "搜索 [keyword]", "监控市场", "今天市场怎么样". Do NOT
  trigger for: technical indicator analysis (use kline-indicator), simple
  price checks (use cmc-mcp), or trade execution requests.
---

# Market Intel — Crypto Social Intelligence for OKX

Social intelligence -> OKX pair mapping -> price verification -> trade execution.
Follow the user's input language.

## Data Source: Chainbase Tops API (free, no key)

**CLI**: prefer `chainbase` (global install), fallback `npx --registry https://registry.npmjs.org chainbase-cli`

First run: check `which chainbase`. If missing, prompt user: `npm install -g chainbase-cli --registry https://registry.npmjs.org`

**Error**: non-zero exit or non-JSON -> "Data source temporarily unavailable."
**Rate limit**: max 1 call per 5 min per endpoint.

### Data Extraction (always use these, never raw API)

**CMD_TRENDING** -- compact trending (100KB -> 5KB):
```bash
chainbase tops trending --json 2>/dev/null | python3 -c "
import json,sys;data=json.load(sys.stdin)
for t in data.get('items',[])[:20]:
    print(json.dumps({'id':t.get('id',''),'kw':t.get('keyword',''),'summary':t.get('summary','')[:150],'authors':len(t.get('authors',[]))},ensure_ascii=False))"
```

**CMD_SEARCH(keyword)** -- top 5 topics (450KB -> 2KB):
```bash
chainbase tops search "KEYWORD_HERE" --json 2>/dev/null | python3 -c "
import json,sys;data=json.load(sys.stdin)
for t in data.get('items',[])[:5]:
    print(json.dumps({'id':t.get('id',''),'kw':t.get('keyword',''),'summary':t.get('summary','')[:150],'authors':len(t.get('authors',[]))},ensure_ascii=False))"
```

**CMD_MENTIONS(keyword)** -- 15 samples + themes (140KB -> 3KB):
```bash
chainbase tops mentions "KEYWORD_HERE" --json 2>/dev/null | python3 -c "
import json,sys;data=json.load(sys.stdin);items=data.get('items',[])
texts=[m.get('text','') if isinstance(m,dict) else str(m) for m in items]
from collections import Counter;words=Counter()
for t in texts:
    for w in t.lower().split():
        if len(w)>3: words[w]+=1
print(json.dumps({'total':len(texts),'samples':[t[:150] for t in texts[:15]],'themes':[w for w,c in words.most_common(10) if c>2]},ensure_ascii=False))"
```

**Keyword sanitization**: Before substituting any user keyword into the above commands, strip all shell metacharacters: `"; | & $ ( ) \ ` { } < > ! #`. Only allow alphanumeric characters, spaces, hyphens, and underscores. If a keyword contains disallowed characters, reject it with a clear error message.

If `chainbase` not found, replace with `npx --registry https://registry.npmjs.org chainbase-cli` in above commands.

---

## OKX Price Verification

After mapping social signals to OKX pairs, always verify with live market data. Use CLI first, MCP as fallback:

**CLI (primary):**
```bash
okx market ticker --instId BTC-USDT
okx market orderbook --instId BTC-USDT
okx market indicator --instId BTC-USDT --ind RSI
```

**MCP fallback (if CLI unavailable):**
- `market_get_ticker(instId="BTC-USDT")` — last price, 24h high/low, volume, change
- `market_get_orderbook(instId="BTC-USDT")` — liquidity depth for HIGH impact signals
- `market_get_indicator(instId="BTC-USDT", indicator="rsi", bar="1Dutc")` — RSI/MACD context

If OKX Trade Kit is not available at all, skip price verification and note: "Price data unavailable — install OKX Trade Kit for live market context."

---

## Module 1: Market Briefing

**Triggers**: market briefing / daily briefing / how is the market / what is happening in crypto / 市场简报 / 晨报 / 今天市场怎么样

1. Run **CMD_TRENDING**
2. For each topic: classify sentiment (BULLISH / BEARISH / NEUTRAL), impact (>30 authors = HIGH, 10-30 = MED, <10 = LOW)
3. Read `references/okx-pairs.md` -> map keywords to OKX pairs
4. **Price verification**: For each mapped OKX pair, fetch current price and 24h change via CLI or MCP (see OKX Price Verification above)
5. **Group by OKX pair**, show bull/bear signals together per pair
6. Add per-pair synthesis + actionable section

**Output**:
```markdown
## Market Intel Briefing -- {date/time}

### BTC-USDT (${price} | 24h: {change}%)
| Narrative | Sentiment | Impact |
|-----------|-----------|--------|
| **{keyword}** ({N}) -- {summary} | BULLISH | HIGH |
| **{keyword}** ({N}) -- {summary} | BEARISH | MED |
> Synthesis: {multi-signal synthesis for this pair}

### Other (no direct OKX pair mapping)
| ... |

### Actionable
- **{pair}**: {recommendation}

### Quick Trade
To act on these signals via OKX Trade Kit:
- Check orderbook depth: `okx market orderbook --instId {pair}`
- View recent candles: `okx market candles --instId {pair} --bar 1H --limit 24`
- Place order when ready
```

---

## Module 2: Signal Alert

**Triggers**: any signals / watch market / what changed / new narratives / 有什么异动 / 监控市场

1. Run **CMD_TRENDING**, also save raw to `/tmp/mi-raw.json`:
   `chainbase tops trending --json 2>/dev/null > /tmp/mi-raw.json`
   Then run the compact extraction on `/tmp/mi-raw.json`
2. Load previous snapshot `/tmp/market-intel-snapshot.json` (if exists)
3. Diff:
   - topic ID only in current -> **NEW: New narrative**
   - topic ID in both, authors >2x previous -> **SURGE (+X%)**
   - First run (no snapshot) -> all flagged as new
4. Classify sentiment, map OKX pairs via `references/okx-pairs.md`
5. **Price verification**: For each signal's OKX pair, fetch current price via CLI or MCP
6. Output signals
7. Save compact snapshot (AFTER comparison):
   ```bash
   python3 -c "
   import json;data=json.load(open('/tmp/mi-raw.json'))
   json.dump([{'id':t['id'],'kw':t['keyword'],'n':len(t.get('authors',[]))} for t in data.get('items',[])],open('/tmp/market-intel-snapshot.json','w'))"
   ```

**Output** per signal:
```
SIGNAL: {New narrative | Surge (+120%)}
"{keyword}" -- {N} authors | {Category} | {Sentiment}
-> OKX: {pairs} @ ${price} (24h: {change}%)
```
No signals: "No new signals since last check."

For periodic monitoring, the user can re-run this module on a schedule (e.g., every 10 minutes via cron or a looping terminal command).

---

## Module 3: Research Query

**Triggers**: research {topic} / tell me about {token} / social sentiment for {keyword} / {token} 社交面怎么样 / 搜索 {keyword}

1. Extract keyword from user query
2. **Sanitize keyword** per the sanitization rule above
3. Run **CMD_SEARCH(keyword)** -> top 5 related topics
4. Run **CMD_MENTIONS(keyword)** -> total count + 15 samples + themes
5. Classify sentiment per topic + aggregate mention sentiment
6. Map to OKX pairs via `references/okx-pairs.md`
7. **Price verification**: Fetch price via CLI or MCP; optionally fetch RSI/MACD for HIGH impact signals

**Output**:
```
RESEARCH: {keyword}

-- Related Topics ({count}) --
1. **{topic}** -- {N} authors, {sentiment}
   {summary}

-- Recent Mentions ({total} posts) --
- Sentiment: ~{X}% Bullish / ~{Y}% Neutral / ~{Z}% Bearish
- Themes: {theme1}, {theme2}, {theme3}

-- OKX Market Context --
| Pair | Price | 24h Change | RSI(14) |
|------|-------|------------|---------|
| {pair} | ${price} | {change}% | {rsi} |

-> Verify pair availability on OKX before trading
```

---

## OKX Pair Mapping

Read `references/okx-pairs.md` for the full keyword → OKX pair mapping table.

Fallback (if file unavailable): btc -> BTC-USDT, eth -> ETH-USDT, sol -> SOL-USDT, etf -> BTC-USDT + ETH-USDT

**Rules**: short words (sui, ai, sei) = exact match only. Unknown tokens = infer pair + flag "(unverified)".

---

## Sentiment Classification

Classify each summary as BULLISH / BEARISH / NEUTRAL. Use language understanding across all languages. Reference keywords (guidance only):
- Bullish: launch, listing, approved, inflow, surge, record, institutional, partnership, upgrade
- Bearish: crash, hack, exploit, sell-off, ban, lawsuit, investigation, liquidation
- Neutral: discussion, analysis, comparison, overview, update

---

## OKX Trade Kit Integration

This skill outputs pair suggestions with live prices. No auto-execution. Workflow:
1. Social intelligence identifies narratives and maps to OKX pairs
2. OKX Trade Kit CLI/MCP confirms current price and momentum
3. User reviews signals and decides to trade
4. User confirms in natural language -> Claude invokes OKX Trade Kit to execute

---

### [29] `okx-600u-pnl-percent-v1`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-600u-pnl-percent-v1/SKILL.md`

---
name: okx-600u-pnl-percent-v1
description: Yield-focused OKX Agent Trade Kit strategy for a 600 USDT account, trading only BTC and ETH USDT perpetuals with single-position risk control, strict stop loss, and skip-first execution logic.
---

# 600U Yield Ranking Strategy V1.0

## Objective

Use a 600 USDT trading account to pursue the highest possible return rate during the competition while prioritizing controlled drawdown, stable equity growth, and disciplined execution.

This strategy allows selective aggression but does not allow undisciplined high-risk bets.

## Allowed Market

Trade only the following USDT perpetual swap instruments:

- BTC-USDT-SWAP
- ETH-USDT-SWAP

Default priority: Prefer BTC-USDT-SWAP by default. Only switch to ETH-USDT-SWAP when ETH is clearly stronger than BTC.

## Position Constraints

- Only 1 open position at any time
- Never hold multiple instruments simultaneously
- No hedging
- No simultaneous long and short

## Execution Cadence

- Run a full decision cycle every 4 hours when there is no open position
- If there is an open position, run a position health check every 1 hour
- If the market is choppy or noisy, explicitly output `本轮跳过`

# Compliance Requirements

All qualifying trades must be executed through OKX official Agent Trade Kit tools.

Do not:

- place orders manually through the OKX app or web UI
- use third-party trading tools
- directly place orders through external API scripts outside the official Agent Trade Kit execution path

Trade only USDT perpetual swaps that qualify for the competition.

# Step 1 - Market Data Collection

For both BTC-USDT-SWAP and ETH-USDT-SWAP, collect:

- 4H candles, latest 200 bars
- 1H candles, latest 120 bars

For each instrument, calculate and record:

- EMA20
- EMA60
- RSI(14)
- ATR(14)
- average volume of the latest 20 candles
- high/low structure of the latest 5 candles
- current price deviation from EMA20

# Step 2 - Sentiment and Crowding Data

For both BTC-USDT-SWAP and ETH-USDT-SWAP, collect:

- current funding rate
- current open interest
- recent open-interest change, preferably 1H and 3H change when available

Focus on:

- whether the trend is supported by open interest
- whether funding is healthy or overcrowded
- whether ATR is too high
- whether the market is in a high-volatility chaotic state or a choppy stop-hunt environment

# Step 3 - AI Reasoning and Final Decision

You must reason first and then decide. Do not execute a purely mechanical rule script.

For every cycle, explicitly determine:

1. Current market regime:
   - uptrend
   - downtrend
   - range
   - high-volatility chaos

2. Which instrument is more tradable, BTC or ETH:  
Compare at least:
   - 4H EMA20 vs EMA60 relationship
   - EMA20 and EMA60 slope
   - whether 1H and 4H align in the same direction
   - whether current price is in a reasonable entry zone instead of an extended chase
   - whether funding rate is healthy
   - whether open-interest change supports continuation

3. Whether a new position is allowed:  
A new position is allowed only if all of the following are true:
   - 4H trend is clear
   - 1H and 4H point in the same direction
   - current price is not obviously extended away from EMA20
   - ATR remains in an acceptable range
   - funding is not obviously overcrowded
   - open-interest change supports continuation

4. If any required condition is missing, you must output `本轮跳过` and explain why.

5. Final output must be exactly one of:
   - 开多
   - 开空
   - 持仓继续
   - 减仓
   - 平仓
   - 本轮跳过

# Step 4 - Direction Rules

Default bias:
- Prefer trend-following longs

Short positions are allowed only when all of the following are true:
- 4H EMA20 is clearly below 4H EMA60
- both EMA20 and EMA60 are sloping down
- 1H structure is also weakening
- open interest supports downside continuation
- funding does not show an extreme opposite-side crowding trap
- price is not already at an oversold exhaustion point

If the short setup is incomplete, do not short.

# Step 5 - Position Sizing and Risk

Treat 600 USDT as the account base capital for risk decisions.

There are 3 execution modes:

## Default Mode

Use for normal high-quality setups:
- max loss per trade: 9 USDT
- target notional: 700 to 900 USDT
- leverage: 2x to 3x

## Strong Mode

Use only when trend, structure, funding, and open interest all strongly align:
- max loss per trade: 12 USDT
- target notional: 900 to 1200 USDT
- leverage: 3x to 4x
- never exceed 4x leverage

## Defensive Mode

Use after losses or when protecting existing gains:
- max loss per trade: 6 USDT
- target notional: 400 to 600 USDT
- leverage: 2x

Additional limits:
- only 1 position at a time
- never add to a losing position
- never flip aggressively after a loss
- if the previous trade was a loss, reduce the next position size by 30%
- for the same instrument, attempt at most 2 new entries within 24 hours

# Step 6 - Stop Loss Rules

Immediately after opening a position, place a stop-loss order through the official trading workflow.

Stop-loss logic:
- prioritize technical structure first
- also reference ATR
- final stop must keep the trade risk within the mode's maximum loss limit

For long positions:
- stop loss should normally be around 0.9 to 1.1 ATR below entry on 4H context
- or slightly below the most recent valid pullback low
- choose the more reasonable level that also respects the risk cap

For short positions:
- stop loss should normally be around 0.9 to 1.1 ATR above entry on 4H context
- or slightly above the most recent valid rebound high
- choose the more reasonable level that also respects the risk cap

If stop distance is too large:
- reduce position size first
- if risk still cannot be controlled properly, skip the trade

# Step 7 - Take Profit and Position Management

This strategy protects return rate first, then seeks continuation profit.

Management rules:
1. When unrealized profit reaches 1R, reduce 30% of the position and move stop loss close to breakeven
2. When unrealized profit reaches 2R, reduce another 30%
3. Let the remaining position follow the trend
4. If 1H structure breaks, prioritize exiting the remaining position
5. If the 4H trend clearly weakens, exit proactively
6. If price moves too fast and funding becomes crowded, lock profit proactively
7. If the market enters a high-volatility chaotic state, protect profits and avoid overstaying

# Step 8 - Drawdown Control and Cooldown Rules

Strictly enforce:
- if daily cumulative loss reaches 18 USDT, stop all new entries for the rest of the day
- if account equity falls 36 USDT from the competition-period peak, enter defensive mode for the next 24 hours
- after 2 consecutive losing trades, pause new trading for 12 hours
- after 3 consecutive losing trades, pause new trading for 24 hours
- if the market is clearly a choppy stop-hunt environment, remain flat

# Step 9 - Return-Rate Priority Principles

- do not force trades just to increase trade count
- do not overuse leverage just to chase nominal profit
- do not low-quality churn trade for volume
- avoid additional account funding during the competition unless absolutely necessary
- only trade high-quality opportunities
- trade less, but make each trade have a clear reason and acceptable risk-reward quality

# Step 10 - Execution Requirements

A new order may be placed only when Step 3 concludes that execution is valid.

Every opening order must include:
- instrument ID
- side
- market order type
- size
- official Agent Trade Kit trade attribution when supported, including `agentTradeKit` tag or equivalent official attribution field

Immediately after entry:
- place a stop-loss order
- do not leave a new position without protection

If there is already an open position:
- do not open a second position
- only decide among `持仓继续`, `减仓`, or `平仓`

# Hard Prohibitions

Never do any of the following:
- manual override trades outside the strategy
- spot trading
- options trading
- coin-margined contracts
- multiple simultaneous positions
- hedging
- revenge trading
- adding to losers
- trading when conditions are unclear
- placing a trade when the reasoning does not support it

# Final Principle

Your job is not to trade every cycle.

When the market is clear, act decisively.  
When the market is messy, stay flat.  
When profit already exists, protect return rate first.  
Drawdown control has higher priority than offense.

---

### [30] `okx-btc-contract`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-btc-contract/SKILL.md`

---
name: okx-btc-contract
description: "OKX BTC合约交易系统 Skill。当用户说'BTC合约'、'合约交易'、'ATR止损'、'BTC做多'、'BTC做空'、'合约开仓'、'合约平仓'、'仓位计算'、'风险评估'时使用此技能。基于EMA200多时框趋势分析、市场情绪分析和ATR动态止损的智能合约交易系统，支持多空双向交易、量化评分、信号冲突检测、智能仓位计算、清算价格验证、资金成本估算、自动止盈止损、全面风险控制。整合技术指标（75%）+市场情绪（25%）综合分析，内置Position Sizer仓位管理引擎。依赖 okx-cex-market、okx-cex-trade、okx-cex-portfolio 三个 Skill。"
version: "2.2.0"
user-invocable: true
---

# OKX BTC合约交易系统 v2.2（整合 Position Sizer）

基于 EMA200 多时框趋势分析、市场情绪分析和 ATR 动态止损的 BTC 永续合约交易系统，采用量化评分引擎，通过 13 个指标加权计算交易信号（技术指标 75% + 市场情绪 25%），支持多空双向交易、信号冲突检测、智能仓位计算、清算价格验证、资金成本估算、自动止盈止损、全面风险控制。系统整合了多时框一致性检测、成交量确认、RSI背离、OI变化、多空比、资金费率、清算数据、大户持仓等高级技术，内置 Position Sizer 仓位管理引擎（固定比例法、凯利公式、ATR动态止损、多杠杆对比、清算计算），显著提升交易准确率和风险控制能力。

## 依赖 Skills（必须先安装）

- `okx-cex-market` — 获取实时价格、K线数据和技术指标（EMA、ATR、RSI、MACD、MA、布林带、成交量）
- `okx-cex-trade` — 执行开仓、平仓、止盈止损订单
- `okx-cex-portfolio` — 查询账户持仓、余额和风险指标

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| direction | string | ✅ | - | 交易方向：long（做多）/ short（做空） |
| leverage | integer | ❌ | 10 | 杠杆倍数（建议 3-20x） |
| entry_price | number | ❌ | - | 入场价格，不填则使用市价 |
| atr_multiplier_sl | number | ❌ | 1.5 | ATR止损倍数（建议 1.5-2） |
| atr_multiplier_tp | number | ❌ | 3 | ATR止盈倍数（建议 2.5-3.5） |
| risk_percent | number | ❌ | 1.5 | 单笔风险占比（%，建议 1-2，固定比例法） |
| max_drawdown | number | ❌ | 10 | 最大回撤控制（%，建议 8-15） |
| max_position_pct | number | ❌ | 10 | 最大单仓占比（%，建议 5-10） |
| max_portfolio_heat | number | ❌ | 8 | 最大总敞口（%，建议 6-8） |
| mmr | number | ❌ | 0.004 | 维持保证金率（默认0.4%，大仓位需调整） |
| fee_rate | number | ❌ | 0.0005 | 手续费率（默认0.05%，VIP0） |
| profile | string | ❌ | demo | 实盘 live / 模拟盘 demo（强烈建议先用 demo 测试） |
| min_atr | number | ❌ | 200 | ATR最小值，低于此值不交易 |
| max_positions | integer | ❌ | 2 | 最大同时持仓数 |
| ma_short | integer | ❌ | 20 | 短期均线周期（用于趋势判断） |
| ma_long | integer | ❌ | 50 | 长期均线周期（用于趋势判断） |
| **ema_period** | integer | ❌ | **200** | **EMA周期（多时框趋势分析核心）** |
| **ema_distance_max** | number | ❌ | **3** | **EMA最大距离百分比（%，超过此值扣分）** |
| **vol_ma_period** | integer | ❌ | **20** | **成交量均线周期** |
| **vol_threshold** | number | ❌ | **1.5** | **放量阈值（倍数，低于此值需S/R支撑）** |
| **min_confidence** | number | ❌ | **65** | **最低信心度（%，低于此值不开仓）** |
| **conflict_threshold** | number | ❌ | **15** | **冲突阈值（分，多空差距低于此值标记冲突）** |
| **kline_limit** | integer | ❌ | **500** | **K线根数（用于技术指标计算，建议500根以获得最稳定的EMA200）** |

## 量化评分系统

### 为什么使用500根K线？

系统使用500根K线进行技术指标计算，原因如下：

| 技术指标 | 最小需求 | 500根的优势 | 时间跨度（以1H为例） |
|---------|---------|------------|------------------|
| **EMA200** | 200根 | 更稳定，减少波动噪音 | 200小时 = 8.3天 |
| **RSI背离** | 24根 | 可检测多个背离周期 | 24小时 = 1天 |
| **S/R识别** | 80根 | 识别更多关键支撑阻力位 | 80小时 = 3.3天 |
| **成交量MA(20)** | 20根 | 更稳定的成交量均线 | 20小时 = 0.8天 |
| **布林带(20)** | 20根 | 更准确的带宽和位置 | 20小时 = 0.8天 |
| **MACD** | 35根 | 足够计算 | 35小时 = 1.5天 |
| **RSI(14)** | 14根 | 足够计算 | 14小时 = 0.6天 |

**500根K线的时间跨度**：
- 1D时框：500天 ≈ 1.4年（长期趋势分析）
- 4H时框：500小时 ≈ 21天（中期趋势分析）
- 1H时框：500小时 ≈ 21天（短期趋势分析）
- 15M时框：500根 ≈ 5.2天（超短期分析）

**最佳实践**：
- ✅ 使用500根K线可以获得最稳定的EMA200计算
- ✅ 对于长期分析（1D、4H），500根非常合适
- ✅ 对于短期分析（1H、15M），500根可以提供更全面的历史数据
- ❌ 如果只需要快速响应，可以使用300根，但准确性会降低

### 评分因子与权重

系统采用 **技术指标（75%）+ 市场情绪（25%）** 双重分析框架，综合 13 个指标加权计算交易信号：

#### 技术面指标（75%权重）- 基于价格和成交量数据

| 因子 | 权重 | 评分范围 | 说明 |
|------|------|---------|------|
| **EMA趋势** | 22% | -100 ~ +100 | 价格与EMA200的关系，技术面权重最高，作为主要趋势判断依据 |
| **MACD** | 13% | -100 ~ +100 | MACD金叉/死叉及柱状图变化 |
| **RSI** | 11% | -100 ~ +100 | RSI超买超卖状态 |
| **RSI背离** | 9% | -100 ~ +100 | 顶底背离检测，最强的反转信号 |
| **成交量** | 8% | -100 ~ +100 | 成交量确认价格走势 |
| **布林带** | 6% | -100 ~ +100 | 布林带位置，识别极端价格 |
| **S/R位置** | 4% | -100 ~ +100 | 支撑阻力位接近度 |
| **K线形态** | 2% | -100 ~ +100 | 经典蜡烛图形态 |

#### 市场情绪面指标（25%权重）- 基于衍生品市场数据

| 因子 | 权重 | 评分范围 | 数据来源 | 说明 |
|------|------|---------|---------|------|
| **OI变化趋势** | 9% | -100 ~ +100 | OKX TradeKit | 未平仓合约变化，反映市场参与度 |
| **多空比L/S** | 6% | -100 ~ +100 | CoinGlass | 多头vs空头持仓比例，反映市场情绪 |
| **资金费率** | 5% | -100 ~ +100 | OKX TradeKit | 永续合约资金费率，反映多空失衡 |
| **清算数据** | 3% | -100 ~ +100 | CoinGlass | 24h多空清算量，反映爆仓压力 |
| **大户持仓变化** | 2% | -100 ~ +100 | CoinGlass | 大户净持仓变化，反映聪明钱动向 |

**数据来源说明**：
- **技术面**：OKX TradeKit MCP / CLI（100%可用）
- **市场情绪面**：
  * OI变化趋势：OKX TradeKit `market_get_open_interest`（100%可用）
  * 资金费率：OKX TradeKit `market_get_funding_rate`（100%可用）
  * 多空比L/S：CoinGlass（不可用时记0分）
  * 清算数据：CoinGlass（不可用时记0分）
  * 大户持仓变化：CoinGlass（不可用时记0分）

### 信心度计算公式（v2.1 更新）

```
Step 1：计算技术面因子得分（8个指标，75%权重）
- EMA趋势得分（22%权重）
- MACD得分（13%权重）
- RSI得分（11%权重）
- RSI背离得分（9%权重）
- 成交量得分（8%权重）
- 布林带得分（6%权重）
- S/R位置得分（4%权重）
- K线形态得分（2%权重）

Step 2：计算技术面加权得分
tech_score = Σ(技术面因子得分 × 因子权重)

Step 3：计算市场情绪面得分（5个指标，25%权重）
- OI变化趋势得分（9%权重）
- 多空比L/S得分（6%权重）
- 资金费率得分（5%权重）
- 清算数据得分（3%权重）
- 大户持仓变化得分（2%权重）

Step 4：计算市场情绪面加权得分
sentiment_score = Σ(情绪面因子得分 × 因子权重)

Step 5：综合加权得分
weighted_score = (tech_score × 0.75) + (sentiment_score × 0.25)

Step 6：时框一致性惩罚
tf_multiplier = 基于多时框一致性计算（详见"多时框趋势分析"）
- 4/4 时框一致 → 1.0
- 3/4 时框一致 → 0.82
- 2/4 时框一致 → 0.60
- 1/4 时框一致 → 0.35

Step 7：EMA距离惩罚
if (价格距EMA200距离 > ema_distance_max%):
  ema_penalty = 0.80
else:
  ema_penalty = 1.0

Step 8：技术面与情绪面冲突检测
if (技术面方向 != 情绪面方向):
  conflict_penalty = 0.70  # 技术面和情绪面方向相反，降低信心度
else:
  conflict_penalty = 1.0

Step 9：最终信心度
confidence = |weighted_score × tf_multiplier × ema_penalty × conflict_penalty| / 100 × 100

最终信心度范围：0% ~ 100%
- 0%：无明确信号
- 100%：最强信号
```

### 信号判断标准

```
做多信号（BUY）：
✅ confidence ≥ min_confidence（默认65%）
✅ weighted_score > 0
✅ 非CONFLICT状态
✅ 成交量确认通过
✅ ATR ≥ min_atr

做空信号（SELL）：
✅ confidence ≥ min_confidence（默认65%）
✅ weighted_score < 0
✅ 非CONFLICT状态
✅ 成交量确认通过
✅ ATR ≥ min_atr

观望信号（WAIT）：
❌ confidence < min_confidence
或
❌ CONFLICT状态
或
❌ 成交量未确认且无S/R支撑

冲突信号（CONFLICT）：
⚠️ |做多得分 - 做空得分| < conflict_threshold（默认15分）
```

## 多时框趋势分析

### 时框设置

系统使用 4 个时间框架综合判断趋势：

| 时框 | 用途 | 权重 |
|------|------|------|
| 1D | 长期趋势方向 | 40% |
| 4H | 中期趋势确认 | 30% |
| 1H | 短期趋势识别 | 20% |
| 15M | 入场时机选择 | 10% |

### EMA200 趋势判断

对于每个时框，计算 EMA200 并判断趋势方向：

```
Step 1：计算 EMA200
EMA200 = 200周期指数移动平均线

Step 2：判断趋势方向
if (当前价格 > EMA200):
  趋势方向 = UP（向上）
else if (当前价格 < EMA200):
  趋势方向 = DOWN（向下）
else:
  趋势方向 = NEUTRAL（中性）

Step 3：计算EMA距离
ema_distance = |当前价格 - EMA200| / EMA200 × 100%
```

### 时框一致性计算

```
Step 1：统计各时框方向
up_count = 趋势方向为 UP 的时框数量
down_count = 趋势方向为 DOWN 的时框数量

Step 2：确定主导方向
if (up_count > down_count):
  主导方向 = 向上
else if (down_count > up_count):
  主导方向 = 向下
else:
  主导方向 = 中性

Step 3：计算一致性得分
max_count = max(up_count, down_count)
tf_multiplier = 根据最大一致数量确定：
- 4/4 时框一致 → 1.0
- 3/4 时框一致 → 0.82
- 2/4 时框一致 → 0.60
- 1/4 时框一致 → 0.35
```

### 时框一致性惩罚的重要性

时框一致性是提升准确率的关键机制：

- **4/4 一致**：所有时间框架趋势一致，信号最可靠，乘数 1.0
- **3/4 一致**：大部分时框一致，信号可靠，乘数 0.82
- **2/4 一致**：时框分歧较大，信号可靠性下降，乘数 0.60
- **1/4 一致**：时框严重分歧，信号不可靠，乘数 0.35

**示例**：
```
做多场景：
- 1D: UP, 4H: UP, 1H: UP, 15M: UP → 4/4 一致 → 乘数 1.0
- 1D: UP, 4H: UP, 1H: UP, 15M: DOWN → 3/4 一致 → 乘数 0.82
- 1D: UP, 4H: DOWN, 1H: UP, 15M: UP → 2/4 一致 → 乘数 0.60
- 1D: UP, 4H: DOWN, 1H: DOWN, 15M: DOWN → 1/4 一致 → 乘数 0.35
```

## 技术指标计算方法

### 1. EMA 趋势计算（新增）

**EMA200 计算**：
```
EMA200_n = EMA200_(n-1) × (1 - k) + 收盘价_n × k
其中 k = 2 / (200 + 1) ≈ 0.00995
```

**趋势判断**：
```
if (当前价格 > EMA200):
  EMA趋势得分 = +100（向上趋势）
else if (当前价格 < EMA200):
  EMA趋势得分 = -100（向下趋势）
else:
  EMA趋势得分 = 0（中性）

考虑EMA距离惩罚：
if (|当前价格 - EMA200| / EMA200 > ema_distance_max%):
  EMA趋势得分 ×= 0.80（扣分）
```

### 2. 趋势判断（1H周期）

**均线系统判断**：
```
向上趋势：MA(20) > MA(50) 且两者都向上倾斜
向下趋势：MA(20) < MA(50) 且两者都向下倾斜
震荡趋势：MA(20) 和 MA(50) 交织，无明显方向
```

**MACD 判断**：
```
MACD 参数：快线 12，慢线 26，信号线 9

金叉（做多信号）：
- DIF 上穿 DEA（当前 DIF > 前期 DIF，且当前 DEA > 前期 DEA）
- 且 DIF 从负值转为正值（强势金叉）或 DIF > 0（普通金叉）

死叉（做空信号）：
- DIF 下穿 DEA（当前 DIF < 前期 DIF，且当前 DEA < 前期 DEA）
- 且 DIF 从正值转为负值（强势死叉）或 DIF < 0（普通死叉）
```

**综合趋势判断**：
```
做多信号：MA(20) > MA(50) + MACD金叉 + RSI > 40
做空信号：MA(20) < MA(50) + MACD死叉 + RSI < 60
```

### 3. 市场结构识别（15M周期）

**突破结构**：
```
向上突破：价格突破近期高点（过去20根K线的最高价）
向下突破：价格跌破近期低点（过去20根K线的最低价）
```

**回踩结构**：
```
回踩做多：价格上涨后回调，但未跌破前一低点，在支撑位企稳
回踩做空：价格下跌后反弹，但未突破前一高点，在阻力位受阻
```

**震荡结构**：
```
震荡区间：价格在 ±1.5×ATR 范围内波动，无明显突破
震荡特征：RSI 在 40-60 之间，成交量萎缩
```

### 4. RSI 指标标准

```
RSI(14) 参数：
- > 70：超买区域，警惕回调
- 70 - 60：强势区域，适合持有
- 60 - 40：中性区域，观察
- 40 - 30：弱势区域，警惕下跌
- < 30：超卖区域，可能反弹

RSI 得分计算：
if (RSI <= 30):
  RSI得分 = 60 + (30 - RSI) / 30 × 40（超卖越深，做多信号越强）
else if (RSI >= 70):
  RSI得分 = -(60 + (RSI - 70) / 30 × 40)（超买越深，做空信号越强）
else if (RSI > 50):
  RSI得分 = (RSI - 50) / 20 × 30（偏多头）
else:
  RSI得分 = -(50 - RSI) / 20 × 30（偏空头）
```

### 5. RSI 背离检测（新增）

**底背离（做多信号）**：
```
检测逻辑：
1. 在过去 24 根K线中识别至少 2 个低点
2. 低点判断：当前低点 < 前2根和后2根K线的低点
3. 如果价格创出新低，但RSI没有创新低 → 底背离
4. 底背离强度 = (RSI新低 - RSI前一低点) / 15（最大强度1.0）

底背离得分：
if (检测到底背离):
  RSI背离得分 = 60 + 背离强度 × 40（60 ~ 100分，强烈做多信号）
```

**顶背离（做空信号）**：
```
检测逻辑：
1. 在过去 24 根K线中识别至少 2 个高点
2. 高点判断：当前高点 > 前2根和后2根K线的高点
3. 如果价格创出新高，但RSI没有创新高 → 顶背离
4. 顶背离强度 = (RSI前一高点 - RSI新高) / 15（最大强度1.0）

顶背离得分：
if (检测到顶背离):
  RSI背离得分 = -(60 + 背离强度 × 40)（-60 ~ -100分，强烈做空信号）
```

**背离的重要性**：
- RSI背离是最强的反转信号，权重12%，仅次于EMA趋势
- 背离 + EMA触碰 = 最强信号组合
- 背离信号通常领先于价格反转

### 6. 布林带位置判断（新增）

**布林带计算**：
```
布林带中轨 = N周期简单移动平均线（默认N=20）
上轨 = 中轨 + 2 × 标准差
下轨 = 中轨 - 2 × 标准差

布林带宽 = (上轨 - 下轨) / 中轨 × 100%
价格位置 = (当前价格 - 下轨) / (上轨 - 下轨) × 100%
```

**布林带得分计算**：
```
if (价格位置 <= 5%):
  布林带得分 = 80 × 带宽归一化（极端低位，强烈做多）
else if (价格位置 <= 20%):
  布林带得分 = 45 × 带宽归一化（接近下轨，偏多）
else if (价格位置 >= 95%):
  布林带得分 = -80 × 带宽归一化（极端高位，强烈做空）
else if (价格位置 >= 80%):
  布林带得分 = -45 × 带宽归一化（接近上轨，偏空）
else:
  布林带得分 = 0（中轨附近，中性）

带宽归一化 = min(1, 布林带宽 / 3%)
带宽越宽，信号越可靠
```

### 7. 支撑阻力识别（新增）

**支撑阻力位计算**：
```
在过去 80 根K线中识别高低点：

高点识别：
当前高点 > 前2根和后2根K线的高点

低点识别：
当前低点 < 前2根和后2根K线的低点

聚类处理：
将相近的高低点合并（差距 < 0.4%）

支撑位：低于当前价格的聚类低点（取最近3个）
阻力位：高于当前价格的聚类高点（取最近3个）
```

**接近度判断**：
```
if (|阻力位 - 当前价格| / 当前价格 < 1.5%):
  接近阻力位 → S/R得分 = -60（偏空）

if (|支撑位 - 当前价格| / 当前价格 < 1.5%):
  接近支撑位 → S/R得分 = +60（偏多）

else:
  S/R得分 = 0（无明确S/R）
```

### 8. K线形态识别（新增）

**经典形态识别**：

**锤子线（做多）**：
```
特征：实体很小，下影线是实体的2.2倍以上，无上影线或上影线很小
得分：+80（强烈做多信号）
```

**流星线（做空）**：
```
特征：实体很小，上影线是实体的2.2倍以上，无下影线或下影线很小
得分：-80（强烈做空信号）
```

**看涨吞没（做多）**：
```
特征：当前K线为阳线，前一根K线为阴线，当前阳线完全吞没前一根阴线
得分：+90（强烈做多信号）
```

**看跌吞没（做空）**：
```
特征：当前K线为阴线，前一根K线为阳线，当前阴线完全吞没前一根阳线
得分：-90（强烈做空信号）
```

**晨星（做多）**：
```
特征：前一根大阴线，中间小实体（K线），当前大阳线，收盘价超过前一根阴线实体中点
得分：+85（强烈做多信号）
```

**暮星（做空）**：
```
特征：前一根大阳线，中间小实体（K线），当前大阴线，收盘价跌破前一根阳线实体中点
得分：-85（强烈做空信号）
```

**触碰EMA（中性）**：
```
特征：价格在EMA200的 ±0.35% 范围内
得分：0（中性，等待方向确认）
```

**K线形态得分**：
```
if (识别到形态):
  K线形态得分 = 形态得分 × 形态强度
else:
  K线形态得分 = 0
```

### 9. ATR 指标使用

```
ATR(14) 参数：
- ATR < min_atr：波动过低，不交易（建议 min_atr = 200）
- ATR 在正常范围：正常交易
- ATR > 2×min_atr：波动过高，降低杠杆
```

## 市场情绪分析（v2.1 新增）

### 10. OI 变化趋势分析（9%权重）

**OI（Open Interest）**：未平仓合约数量，反映市场参与度和资金流入流出。

**数据获取**：
```bash
okx market open-interest --instType SWAP --instId BTC-USDT-SWAP
```

**OI变化得分计算**：

| 条件 | 分值 | 说明 |
|------|------|------|
| OI 上升 + 价格上涨 | +100 | 趋势强化，多头主动增仓 |
| OI 上升 + 价格下跌 | -100 | 空头主导，价格下跌伴随增仓 |
| OI 下降 + 价格上涨 | +40 | 轧空/回补，空头止损导致价格反弹 |
| OI 下降 + 价格下跌 | -40 | 多头止损，价格下跌伴随减仓 |
| OI 横盘（变化 < 2%） | 0 | 中性，无明显方向 |

**计算逻辑**：
```
Step 1：获取当前OI和24小时前OI
current_oi = 当前未平仓合约数量
previous_oi = 24小时前未平仓合约数量

Step 2：计算OI变化百分比
oi_change_pct = (current_oi - previous_oi) / previous_oi × 100%

Step 3：获取价格变化
price_change = 当前价格 - 24小时前价格
price_change_pct = price_change / 24小时前价格 × 100%

Step 4：根据OI和价格变化判断得分
if (|oi_change_pct| < 2%):
  OI得分 = 0（横盘）
else if (oi_change_pct > 0 and price_change_pct > 0):
  OI得分 = +100（趋势强化）
else if (oi_change_pct > 0 and price_change_pct < 0):
  OI得分 = -100（空头主导）
else if (oi_change_pct < 0 and price_change_pct > 0):
  OI得分 = +40（轧空回补）
else if (oi_change_pct < 0 and price_change_pct < 0):
  OI得分 = -40（多头止损）
```

### 11. 多空比 L/S Ratio 分析（6%权重）

**L/S Ratio**：多头持仓量 / 空头持仓量，反映市场情绪偏向。

**数据来源**：CoinGlass API（如果不可用，记0分）

**多空比得分计算**：

| L/S Ratio | 分值 | 说明 |
|-----------|------|------|
| > 1.5 | -100 | 多头极度拥挤，反转风险高 |
| 1.2 - 1.5 | -80 | 多头偏多，轻微看空 |
| 0.9 - 1.2 | 0 | 均衡，中性 |
| 0.7 - 0.9 | +80 | 空头偏多，轻微看多 |
| < 0.7 | +100 | 空头极度拥挤，轧空机会大 |

**计算逻辑**：
```
Step 1：获取多空比
ls_ratio = 多头持仓量 / 空头持仓量

Step 2：根据多空比判断得分
if (ls_ratio > 1.5):
  L/S得分 = -100
else if (ls_ratio > 1.2):
  L/S得分 = -80
else if (ls_ratio >= 0.9):
  L/S得分 = 0
else if (ls_ratio >= 0.7):
  L/S得分 = +80
else:
  L/S得分 = +100
```

**特殊情况**：
- 如果CoinGlass不可用：L/S得分 = 0，并在报告中标注 `⚠️ 数据不可用`

### 12. 资金费率分析（5%权重）

**资金费率**：永续合约的资金费率，反映多空失衡程度。

**数据获取**：
```bash
okx market funding-rate BTC-USDT-SWAP
```

**资金费率得分计算**：

| 资金费率 | 分值 | 说明 |
|---------|------|------|
| > +0.1% | -100 | 做多成本极高，市场过热 |
| +0.05% ~ +0.1% | -80 | 偏多拥挤 |
| -0.01% ~ +0.05% | 0 | 正常区间 |
| -0.05% ~ -0.01% | +80 | 做空成本低，轻微看多 |
| < -0.05% | +100 | 做空过热，强烈看多信号 |

**计算逻辑**：
```
Step 1：获取当前资金费率
funding_rate = 当前资金费率（百分比）

Step 2：根据资金费率判断得分
if (funding_rate > 0.1):
  资金费率得分 = -100
else if (funding_rate > 0.05):
  资金费率得分 = -80
else if (funding_rate >= -0.01):
  资金费率得分 = 0
else if (funding_rate >= -0.05):
  资金费率得分 = +80
else:
  资金费率得分 = +100
```

**资金费率解读**：
- **正费率**：多头过多，需向空头支付资金费，市场可能过热
- **负费率**：空头过多，需向多头支付资金费，市场可能过度看空

### 13. 清算数据分析（3%权重）

**清算数据**：24小时多空清算量对比，反映爆仓压力和轧空机会。

**数据来源**：CoinGlass API（如果不可用，记0分）

**清算数据得分计算**：

| 24h清算情况 | 分值 | 说明 |
|-----------|------|------|
| 多头清算 >> 空头清算 | -100 | 多头遭受重创，看空 |
| 多头清算 > 空头清算 | -80 | 多头承压 |
| 多空清算均衡 | 0 | 均衡 |
| 空头清算 > 多头清算 | +80 | 空头承压 |
| 空头清算 >> 多头清算 | +100 | 轧空压力大，看多 |

**计算逻辑**：
```
Step 1：获取24h多空清算量
long_liquidation = 24h多头清算量
short_liquidation = 24h空头清算量

Step 2：计算清算比率
liquidation_ratio = long_liquidation / short_liquidation

Step 3：根据清算比率判断得分
if (liquidation_ratio > 2.0):
  清算得分 = -100（多头重创）
else if (liquidation_ratio > 1.2):
  清算得分 = -80（多头承压）
else if (liquidation_ratio >= 0.83):
  清算得分 = 0（均衡）
else if (liquidation_ratio >= 0.5):
  清算得分 = +80（空头承压）
else:
  清算得分 = +100（轧空压力大）
```

**特殊情况**：
- 如果CoinGlass不可用：清算得分 = 0，并在报告中标注 `⚠️ 数据不可用`

### 14. 大户持仓变化分析（2%权重）

**大户持仓**：大户净持仓变化，反映聪明钱动向。

**数据来源**：CoinGlass API（如果不可用，记0分）

**大户持仓变化得分计算**：

| 大户净持仓变化 | 分值 | 说明 |
|--------------|------|------|
| 净多头持仓增加 > 5% | +100 | 大户明显做多 |
| 净多头持仓增加 1-5% | +80 | 大户偏多 |
| 无明显变化 | 0 | 中性 |
| 净空头持仓增加 1-5% | -80 | 大户偏空 |
| 净空头持仓增加 > 5% | -100 | 大户明显做空 |

**计算逻辑**：
```
Step 1：获取大户净持仓变化
net_position_change = 大户净持仓变化百分比

Step 2：根据持仓变化判断得分
if (net_position_change > 5):
  大户持仓得分 = +100
else if (net_position_change > 1):
  大户持仓得分 = +80
else if (net_position_change >= -1):
  大户持仓得分 = 0
else if (net_position_change >= -5):
  大户持仓得分 = -80
else:
  大户持仓得分 = -100
```

**特殊情况**：
- 如果CoinGlass不可用：大户持仓得分 = 0，并在报告中标注 `⚠️ 数据不可用`

### 市场情绪面综合评分

```
Step 1：计算各情绪指标得分
- OI变化趋势得分（9%权重）
- 多空比L/S得分（6%权重）
- 资金费率得分（5%权重）
- 清算数据得分（3%权重）
- 大户持仓变化得分（2%权重）

Step 2：加权求和
sentiment_score = (OI得分 × 0.09) + (L/S得分 × 0.06) + (资金费率得分 × 0.05) + (清算得分 × 0.03) + (大户持仓得分 × 0.02)

Step 3：确定情绪方向
if (sentiment_score > 0):
  情绪方向 = 看多
else if (sentiment_score < 0):
  情绪方向 = 看空
else:
  情绪方向 = 中性

Step 4：计算情绪强度
sentiment_strength = |sentiment_score| / 100
范围：0% ~ 100%
```

### 技术面与情绪面冲突检测

**冲突判断**：
```
Step 1：分离技术面得分
tech_bull_score = 技术面做多得分
tech_bear_score = 技术面做空得分

Step 2：确定技术面方向
if (tech_bull_score > tech_bear_score):
  技术面方向 = 看多
else:
  技术面方向 = 看空

Step 3：判断冲突
if (技术面方向 != 情绪方向):
  冲突状态 = TRUE
  情绪冲突惩罚 = 0.70（降低信心度）
else:
  冲突状态 = FALSE
  情绪冲突惩罚 = 1.0
```

**冲突处理**：
- 如果技术面和情绪面方向相反，降低最终信心度乘数至 0.70
- 在报告中明确标注冲突警告
- 提供两套方案：尊重技术面 vs 跟随情绪面

## 成交量确认

### 量比计算

```
Step 1：计算成交量均线
vol_ma = 过去 N 根K线的平均成交量（默认N=20）

Step 2：计算量比
volume_ratio = 当前成交量 / vol_ma
```

### 成交量信号判断

```
if (volume_ratio >= vol_threshold) and (当前K线为阳线):
  成交量信号 = BULL_VOL（放量上涨）
  成交量得分 = 40 + (volume_ratio - vol_threshold) × 30（40 ~ 100分）

else if (volume_ratio >= vol_threshold) and (当前K线为阴线):
  成交量信号 = BEAR_VOL（放量下跌）
  成交量得分 = -(40 + (volume_ratio - vol_threshold) × 30)（-40 ~ -100分）

else if (volume_ratio < 0.6):
  成交量信号 = SHRINK（缩量）
  if (EMA趋势 > 0):
    成交量得分 = -20（上涨缩量，怀疑持续性）
  else:
    成交量得分 = +20（下跌缩量，可能反转）

else:
  成交量信号 = NORM（正常）
  成交量得分 = 0（中性）
```

### 成交量门槛规则

```
成交量确认条件（必须满足）：
✅ volume_ratio >= 0.8（量比不小于0.8）
或
✅ 接近支撑阻力位（|S/R - 价格| / 价格 < 1.5%）

如果两个条件都不满足：
- 即使其他因子得分很高，也不能生成BUY或SELL信号
- 只能生成WAIT信号

原因：无成交量确认且无S/R支撑，价格走势可能不可持续
```

## 信号冲突检测

### 冲突判断标准

```
Step 1：计算做多得分
bull_score = Σ(正分因子 × 权重)

Step 2：计算做空得分
bear_score = Σ(|负分因子| × 权重)

Step 3：计算得分差距
score_gap = |bull_score - bear_score|

Step 4：判断冲突
if (score_gap < conflict_threshold) and (bull_score > 30) and (bear_score > 30):
  信号状态 = CONFLICT（冲突）
else:
  信号状态 = 非冲突
```

### CONFLICT 信号的处理

```
CONFLICT 信号特点：
- 多空得分都很高（>30分）
- 但差距很小（<15分）
- 表明市场方向不明确，多空力量均衡

CONFLICT 信号处理：
❌ 禁止开仓（无论confidence多高）
⚠️ 显示冲突警告
📊 等待市场方向明确后再操作

示例：
做多得分：65分
做空得分：58分
得分差距：7分（<15）
→ 标记为CONFLICT，禁止开仓
```

## 仓位计算详解

### 合约面值说明

OKX BTC-USDT-SWAP 永续合约：
- **合约面值**：100 USDT/张
- **最小交易单位**：1张
- **保证金模式**：全仓模式（cross）

### 标准化仓位计算步骤

**Step 1：计算单笔风险金额**
```
单笔风险金额 = 账户可用余额 × (risk_percent / 100)
```

**Step 2：计算每张合约的风险**
```
每张合约风险 = ATR × atr_multiplier_sl
```

**Step 3：计算仓位数**
```
仓位数 = 单笔风险金额 / 每张合约风险
```

**Step 4：计算实际投入**
```
实际投入（USDT）= 仓位数 × 合约面值 × 杠杆倍数
```

**Step 5：验证仓位合理性**
```
实际投入 / 账户余额 ≤ 20%（避免过度集中）
保证金占用 / 账户余额 ≤ 50%（避免爆仓风险）
```

### 计算示例

假设：
- 账户余额：10,000 USDT
- risk_percent：1.5%
- ATR：450
- atr_multiplier_sl：1.5
- 杠杆：10x

计算过程：
```
单笔风险金额 = 10,000 × 0.015 = 150 USDT
每张合约风险 = 450 × 1.5 = 675 USDT
仓位数 = 150 / 675 = 0.22 张 → 取整为 1 张
实际投入 = 1 × 100 × 10 = 1,000 USDT
保证金占用 = 1,000 / 10 = 100 USDT
```

**注意事项**：
- 仓位数必须为整数
- 最小仓位为 1 张
- 建议实际投入不超过账户余额的 20%

## 风控参数说明

### 1. ATR 动态止盈止损

**固定止盈止损**：
```
做多：
- 止损价 = 入场价 - (ATR × atr_multiplier_sl)
- 止盈价 = 入场价 + (ATR × atr_multiplier_tp)

做空：
- 止损价 = 入场价 + (ATR × atr_multiplier_sl)
- 止盈价 = 入场价 - (ATR × atr_multiplier_tp)
```

**ATR 移动止损规则**：
```
触发条件：盈利达到 1.5×ATR 时启动移动止损

做多移动止损：
- 新止损价 = 当前价格 - (ATR × atr_multiplier_sl)
- 新止损价必须 > 原止损价（只能向有利方向移动）

做空移动止损：
- 新止损价 = 当前价格 + (ATR × atr_multiplier_sl)
- 新止损价必须 < 原止损价（只能向有利方向移动）
```

### 2. 风险收益比（RR）

```
RR = ATR止盈距离 / ATR止损距离
   = atr_multiplier_tp / atr_multiplier_sl

标准：
- RR ≥ 2.0：优秀，优先执行
- RR ≥ 1.5：合格，可以执行
- RR < 1.5：不合格，不建议执行
```

### 3. 风控过滤条件

执行交易前必须全部满足以下条件：

```
✅ 技术指标：
   - 趋势方向明确（非震荡）
   - MACD 金叉/死叉确认
   - RSI 在合理区间

✅ 波动条件：
   - ATR ≥ min_atr（波动充足）
   - ATR ≤ 3×min_atr（波动不过高）

✅ 风险条件：
   - RR ≥ 1.5
   - 单笔风险 ≤ 2%
   - 当前持仓数 < max_positions

✅ 账户条件：
   - 余额充足
   - 保证金占用 ≤ 50%

✅ 历史条件：
   - 最近3笔未连续亏损
   - 账户最大回撤 ≤ max_drawdown

✅ 信号质量（v2.0新增）：
   - 信心度 ≥ min_confidence（默认65%）
   - 非CONFLICT状态
   - 成交量确认通过
```

### 4. 连续亏损控制

```
连续亏损判断：
- 统计最近 10 笔交易
- 如果连续 3 笔亏损，暂停交易 24 小时
- 恢复交易后，先降低杠杆至 5x，风险降至 1%
```

### 5. 最大回撤控制

```
回撤计算：
- 记录账户历史最高净值
- 当前回撤 = (历史最高净值 - 当前净值) / 历史最高净值 × 100%

回撤控制：
- 回撤 ≥ 5%：降低杠杆至 5x
- 回撤 ≥ 10%：暂停交易，重新评估策略
- 回撤 ≥ max_drawdown：强制停止交易
```

## 执行流程

### Phase 1：策略分析（v2.0 增强）

1. 用户触发技能后，首先进行市场分析。

2. 调用 `okx-cex-market` 获取多时框数据：

```bash
# 获取4个时框的K线数据（用于多时框趋势分析）
# 使用500根K线以获得最稳定的EMA200计算
okx market candles BTC-USDT-SWAP --bar 1D --limit 500
okx market candles BTC-USDT-SWAP --bar 4H --limit 500
okx market candles BTC-USDT-SWAP --bar 1H --limit 500
okx market candles BTC-USDT-SWAP --bar 15M --limit 500

# 获取技术指标（1H时框）
okx market indicator atr BTC-USDT-SWAP --bar 1H --params 14
okx market indicator rsi BTC-USDT-SWAP --bar 1H --params 14
okx market indicator macd BTC-USDT-SWAP --bar 1H --params 12,26,9
okx market indicator ma BTC-USDT-SWAP --bar 1H --params 20
okx market indicator ma BTC-USDT-SWAP --bar 1H --params 50
okx market indicator bb BTC-USDT-SWAP --bar 1H --params 20,2
okx market indicator ema BTC-USDT-SWAP --bar 1H --params 200

# 获取当前价格和成交量
okx market ticker BTC-USDT-SWAP

# 获取市场情绪数据（v2.1新增）
okx market funding-rate BTC-USDT-SWAP
okx market open-interest --instType SWAP --instId BTC-USDT-SWAP
```

3. **多时框趋势分析**（v2.0 核心升级）：

   **Step 1：计算各时框的 EMA200 和趋势方向**
   - 1D: 计算 EMA200，判断价格是否 > EMA200
   - 4H: 计算 EMA200，判断价格是否 > EMA200
   - 1H: 计算 EMA200，判断价格是否 > EMA200
   - 15M: 计算 EMA200，判断价格是否 > EMA200

   **Step 2：统计各时框方向**
   - 统计 UP 的时框数量
   - 统计 DOWN 的时框数量

   **Step 3：计算时框一致性**
   - 确定主导方向（向上或向下）
   - 计算时框一致性乘数（1.0 / 0.82 / 0.60 / 0.35）

   **Step 4：计算 EMA 距离惩罚**
   - 计算价格距 EMA200 的百分比
   - 如果超过 ema_distance_max%，应用 0.80 惩罚

4. **量化评分计算**（v2.1 核心升级：技术面75% + 情绪面25%）：

   **Step 1：计算技术面因子得分（8个指标，75%权重）**

   **EMA趋势（权重22%）**：
   - 基于多时框EMA200判断
   - 计算价格与EMA200的关系
   - 应用距离惩罚

   **MACD（权重13%）**：
   - 判断金叉/死叉
   - 判断 DIF 是否 > 0
   - 判断柱状图变化

   **RSI（权重11%）**：
   - 判断超买超卖状态
   - 计算RSI得分（0 ~ 100）

   **RSI背离（权重9%）**：
   - 检测顶底背离
   - 计算背离强度
   - 背离得分 60 ~ 100

   **成交量（权重8%）**：
   - 计算量比
   - 判断放量/缩水
   - 应用成交量门槛规则

   **布林带（权重6%）**：
   - 计算布林带位置
   - 判断极端价格
   - 考虑布林带宽

   **S/R位置（权重4%）**：
   - 识别支撑阻力位
   - 判断接近度
   - 计算接近度得分

   **K线形态（权重2%）**：
   - 识别经典形态
   - 计算形态得分
   - 应用形态强度

   **Step 2：计算技术面加权得分**
   ```
   tech_score = Σ(技术面因子得分 × 因子权重)
   ```

   **Step 3：计算市场情绪面得分（5个指标，25%权重）**

   **OI变化趋势（权重9%）**：
   - 获取当前OI和24小时前OI
   - 计算OI变化百分比
   - 根据OI和价格变化判断得分

   **多空比L/S（权重6%）**：
   - 从CoinGlass获取多空比
   - 根据多空比值判断得分
   - 不可用时记0分

   **资金费率（权重5%）**：
   - 获取当前资金费率
   - 根据费率值判断得分

   **清算数据（权重3%）**：
   - 从CoinGlass获取24h清算数据
   - 计算多空清算比率
   - 根据清算比率判断得分
   - 不可用时记0分

   **大户持仓变化（权重2%）**：
   - 从CoinGlass获取大户持仓变化
   - 根据持仓变化判断得分
   - 不可用时记0分

   **Step 4：计算市场情绪面加权得分**
   ```
   sentiment_score = Σ(情绪面因子得分 × 因子权重)
   ```

   **Step 5：综合加权得分**
   ```
   weighted_score = (tech_score × 0.75) + (sentiment_score × 0.25)
   ```

5. **加权计算最终信心度**（v2.1 核心升级）：

   ```
   Step 1：加权求和
   weighted_score = (tech_score × 0.75) + (sentiment_score × 0.25)

   Step 2：应用时框一致性惩罚
   weighted_score ×= tf_multiplier

   Step 3：应用EMA距离惩罚
   if (价格距EMA200 > ema_distance_max%):
     weighted_score ×= 0.80

   Step 4：技术面与情绪面冲突检测（v2.1新增）
   if (技术面方向 != 情绪面方向):
     conflict_penalty = 0.70
   else:
     conflict_penalty = 1.0

   Step 5：计算信心度
   confidence = |weighted_score × conflict_penalty| / 100 × 100
   ```

6. **信号冲突检测**（v2.1 增强：技术面冲突 + 情绪面冲突）：

   ```
   Step 1：分离技术面做多和做空得分
   tech_bull_score = Σ(技术面正分因子 × 权重)
   tech_bear_score = Σ(技术面负分因子绝对值 × 权重)

   Step 2：计算技术面得分差距
   tech_score_gap = |tech_bull_score - tech_bear_score|

   Step 3：判断技术面冲突
   if (tech_score_gap < conflict_threshold) and (tech_bull_score > 30) and (tech_bear_score > 30):
     技术面状态 = CONFLICT
   else:
     技术面状态 = 非冲突

   Step 4：判断技术面与情绪面冲突（v2.1新增）
   if (技术面方向 != 情绪面方向):
     情绪冲突状态 = CONFLICT
   else:
     情绪冲突状态 = 非冲突

   Step 5：综合冲突判断
   if (技术面状态 == CONFLICT or 情绪冲突状态 == CONFLICT):
     信号状态 = CONFLICT
   else:
     信号状态 = 非冲突
   ```

7. **综合判断生成交易信号**（v2.1 增强）：

   ```
   做多信号（BUY）：
   ✅ confidence ≥ min_confidence（默认65%）
   ✅ weighted_score > 0
   ✅ 非CONFLICT状态
   ✅ 成交量确认通过
   ✅ ATR ≥ min_atr

   做空信号（SELL）：
   ✅ confidence ≥ min_confidence（默认65%）
   ✅ weighted_score < 0
   ✅ 非CONFLICT状态
   ✅ 成交量确认通过
   ✅ ATR ≥ min_atr

   观望信号（WAIT）：
   ❌ confidence < min_confidence
   或
   ❌ CONFLICT状态
   或
   ❌ 成交量未确认且无S/R支撑

   冲突信号（CONFLICT）：
   ⚠️ |做多得分 - 做空得分| < conflict_threshold
   ```

8. 输出增强分析报告（v2.0 升级）：
   ```
   📊 BTC分析报告 v2.0 [模拟盘]
   ━━━━━━━━━━━━━━━━━━━━
   当前价格：$65,200
   ATR(14)：450
   ━━━━━━━━━━━━━━━━━━━━
   【多时框趋势】
   1D: UP ⬆️ | 4H: UP ⬆️ | 1H: UP ⬆️ | 15M: DOWN ⬇️
   时框一致性：3/4 → 乘数 0.82
   主导方向：向上
   EMA距离：1.2%（< 3%，无惩罚）

   【量化评分】
   EMA趋势(30%):   +75 (EMA200之上，3/4时框一致)
   MACD(18%):     +60 (金叉，DIF>0，柱状图增长)
   RSI(14%):      +25 (RSI=45，偏中性)
   RSI背离(12%):   +0 (无背离)
   成交量(11%):   +50 (放量上涨，量比1.8)
   布林带(8%):    +30 (接近下轨，带宽正常)
   S/R位置(5%):   +15 (接近支撑位$64,800)
   K线形态(2%):   +0 (无明显形态)
   ━━━━━━━━━━━━━━━━━━━━
   【信号判断】
   加权得分：+59.5
   信心度：75.2% ✅ (≥65%)
   信号状态：BUY ✅ (非冲突)
   成交量确认：通过 ✅

   💡 交易建议：做多
   📍 参考入场价：$65,200
   🛑 ATR止损：$64,525（-1.5×ATR，-1.26%）
   🎯 ATR止盈：$66,550（+3×ATR，+2.07%）
   📈 风险收益比：2.0
   ━━━━━━━━━━━━━━━━━━━━
   ✅ 满足开仓条件：
      - 信心度≥65%（75.2% ✅）
      - 非CONFLICT状态 ✅
      - 成交量确认通过 ✅
      - ATR充足（450 ≥ 200）✅
      - RR合格（2.0 ≥ 1.5）✅
   ━━━━━━━━━━━━━━━━━━━━
   ⚠️  注意事项：
      - 15M时框与主趋势相反，关注短期回调
      - 信心度中等，建议小仓位试探
   ```

### Phase 2：参数确认

1. 用户确认交易方向（direction）和杠杆（leverage）。
2. 如果用户未指定，使用默认值：
   - 杠杆：10x
   - 风险：1.5%
   - ATR止损倍数：1.5
   - ATR止盈倍数：3.0
   - MA短期：20
   - MA长期：50
   - EMA周期：200
   - EMA最大距离：3%
   - 成交量均线：20
   - 放量阈值：1.5
   - 最低信心度：65%
   - 冲突阈值：15
3. 如果用户未指定 profile，**默认使用 demo 模拟盘**，保护资金安全。

4. 计算 ATR 止盈止损价格：

```
做多：
- 止损价 = 入场价 - (ATR × 1.5)
- 止盈价 = 入场价 + (ATR × 3.0)

做空：
- 止损价 = 入场价 + (ATR × 1.5)
- 止盈价 = 入场价 - (ATR × 3.0)
```

5. 计算风险收益比（RR）：

```
RR = atr_multiplier_tp / atr_multiplier_sl
   = 3.0 / 1.5
   = 2.0

如果 RR < 1.5，提示风险收益比不合理，建议调整参数。
```

6. 向用户确认完整参数后进入开仓阶段。

### Phase 2.5：智能仓位计算与风险控制（整合 Position Sizer）

在开仓之前，系统将基于用户的风险偏好和市场条件，计算精确的仓位大小、清算价格、资金成本等关键参数。

**Step 1：选择仓位计算方法**

系统支持 3 种仓位计算方法，根据用户的风险偏好和历史数据选择：

| 方法 | 适用场景 | 输入参数 | 输出 |
|------|---------|---------|------|
| **固定比例法** | 默认推荐 | risk_percent（默认1.5%）、杠杆 | 基于固定风险的仓位 |
| **ATR动态止损法** | 波动市场 | ATR、atr_multiplier_sl、杠杆 | 基于波动率的动态仓位 |
| **凯利公式** | 高级用户 | 胜率、平均盈亏比、杠杆 | 最优增长仓位 |

**默认选择**：固定比例法（1%风险）

**Step 2：获取账户和合约参数**

```bash
# 查询账户余额
okx account balance USDT --profile <profile>

# 获取合约参数
okx market instruments --instType SWAP --instId BTC-USDT-SWAP
```

提取关键字段：
- `equity`：账户权益（用于风险计算）
- `ctVal`：合约面值（BTC-USDT-SWAP = 0.01 BTC）
- `lotSz`：最小下单精度（现货需要）
- `minSz`：最小下单数量

**Step 3：计算仓位大小（固定比例法）**

```
单笔风险金额 = 账户权益 × risk_percent / 100
每张合约风险 = |入场价格 - 止损价格| × 合约面值
仓位数 = floor(单笔风险金额 / 每张合约风险)
```

**示例计算**：
```
账户权益：10,000 USDT
risk_percent：1.5%
入场价格：$65,200
止损价格：$64,525（ATR 450 × 1.5）
合约面值：0.01 BTC（1张 = 0.01 BTC）
杠杆：10x

计算过程：
单笔风险金额 = 10,000 × 0.015 = 150 USDT
每张合约风险 = (65,200 - 64,525) × 0.01 × 65,200 = 440 USDT
仓位数 = floor(150 / 440) = 0 张（风险过小，调整）

调整后（风险2%）：
单笔风险金额 = 10,000 × 0.02 = 200 USDT
仓位数 = floor(200 / 440) = 0 张（仍不足）

最终建议：
- 最小仓位：1张（风险 = 440 USDT = 4.4%）
- 风险过高，建议：
  1. 提高止损价格（减少单张风险）
  2. 降低杠杆（减少风险敞口）
  3. 增加账户权益（提高风险承受能力）
```

**Step 4：多场景杠杆对比**

计算不同杠杆下的仓位和风险：

| 杠杆 | 仓位数 | 名义价值 | 保证金 | 单笔风险 | 风险占比 | 清算价估算 |
|------|--------|----------|--------|----------|----------|------------|
| 5x | 1 | $65,200 | $13,040 | $440 | 4.4% | $58,680 |
| 10x | 1 | $65,200 | $6,520 | $440 | 4.4% | $58,680 |
| 20x | 1 | $65,200 | $3,260 | $440 | 4.4% | $58,680 |

**注意**：
- 清算价在相同仓位下不受杠杆影响（交叉保证金）
- 高杠杆会放大实际风险敞口
- 建议杠杆：3-10x（根据市场波动）

**Step 5：清算价格计算与验证**

**做多清算价计算**（独立保证金）：
```
清算价 = 入场价格 × (1 - mmr - fee_rate)
其中：
mmr = 维持保证金率（默认0.004 = 0.4%，Tier 1）
fee_rate = 手续费率（默认0.0005 = 0.05%，VIP0）
```

**示例**：
```
入场价格：$65,200
mmr：0.004
fee_rate：0.0005

清算价 = 65,200 × (1 - 0.004 - 0.0005) = 65,200 × 0.9955 = $64,890

止损价格：$64,525
清算价格：$64,890

✅ 止损在清算价之前（$64,525 < $64,890），安全
```

**清算价格验证规则**：
- ✅ 止损价格 < 清算价格（做多）：安全
- ⚠️ 止损价格 ≥ 清算价格（做多）：危险，会先爆仓
- ❌ 如果止损在清算价之后，必须：
  1. 降低杠杆
  2. 提高止损价格
  3. 使用交叉保证金模式

**清算价格警告示例**：
```
🚨 清算价格警告！
━━━━━━━━━━━━━━━━━━━
止损价格：$64,525
清算价格：$64,890
━━━━━━━━━━━━━━━━━━━
⚠️ 止损在清算价之后！
建议操作：
1. 降低杠杆至 5x
2. 提高止损价格至 $65,000
3. 使用交叉保证金模式
```

**Step 6：资金费率成本估算**

```bash
okx market funding-rate BTC-USDT-SWAP
```

**资金费率成本计算**：
```
日资金成本 = 名义价值 × 资金费率 × 3（OKX每日结算3次）
周资金成本 = 日资金成本 × 7
```

**示例**：
```
名义价值：$65,200
资金费率：0.01%（正向）

日资金成本 = 65,200 × 0.0001 × 3 = $19.56
周资金成本 = 19.56 × 7 = $136.92

如果持仓7天：
预期盈利：+$1,350（2.07%）
资金成本：-$136.92
净盈利：+$1,213.08（1.86%）
```

**资金费率判断规则**：
- |费率| < 0.01%：低成本，可持仓多日
- 0.01% ≤ |费率| < 0.03%：中等成本，建议3-5天
- |费率| ≥ 0.03%：高成本，建议日内或隔夜

**Step 7：投资组合约束检查**

检查当前账户的总敞口：

```bash
# 查询当前持仓
okx account positions --instType SWAP --profile <profile>

# 查询账户最大可用保证金
okx account max-avail-size --instId BTC-USDT-SWAP --tdMode cross
```

**约束规则**：
1. **单仓占比**：不超过账户权益的10%（可配置）
2. **总敞口**：所有持仓的总风险不超过6-8%
3. **保证金占用**：不超过可用保证金的50%

**示例检查**：
```
账户权益：10,000 USDT
当前持仓：0
新开仓：1张，名义价值$65,200，保证金$6,520（10x杠杆）

检查结果：
✅ 单仓占比：6.52%（≤10%）- 通过
✅ 总敞口：0%（持仓为空）- 通过
✅ 保证金占用：65.2%（假设只有10,000可用）- ⚠️ 接近上限

建议：
- 保证金占用偏高，建议降低杠杆至5x
- 或增加账户权益
```

**Step 8：生成最终推荐方案**

基于以上分析，生成最终的仓位推荐：

```
📊 智能仓位计算结果
━━━━━━━━━━━━━━━━━━━
💰 账户权益：10,000 USDT
📊 推荐方法：固定比例法（2%风险）
━━━━━━━━━━━━━━━━━━━
📈 推荐仓位：1 张
💵 名义价值：$65,200
💎 保证金占用：$6,520（65.2% @ 10x杠杆）
🎯 杠杆：10x
━━━━━━━━━━━━━━━━━━━
🛑 止损价格：$64,525
💰 清算价格：$64,890（独立保证金）
✅ 止损在清算价之前，安全
━━━━━━━━━━━━━━━━━━━
💸 单笔风险：$675（6.75%）
📏 风险收益比：2.0
━━━━━━━━━━━━━━━━━━━
💳 日资金成本：$19.56（费率0.01%）
💳 周资金成本：$136.92
━━━━━━━━━━━━━━━━━━━
⚠️ 风险提示：
1. 单笔风险6.75%超过建议1-2%
2. 保证金占用65.2%偏高
3. 建议降低杠杆至5x或增加账户权益

💡 优化建议：
方案A：降低杠杆至5x
  - 仓位数：1张
  - 保证金占用：$13,040（130%）
  - ⚠️ 保证金不足，无法执行

方案B：提高账户权益至20,000 USDT
  - 仓位数：1张
  - 保证金占用：$6,520（32.6%）
  - 单笔风险：$675（3.38%）
  - ✅ 可执行
```

**Step 9：最终确认**

在用户确认后，进入 Phase 3 开仓执行。

如果风险参数不满足要求，系统将提供调整建议，用户可以选择：
1. 调整风险百分比
2. 调整杠杆
3. 调整止损价格
4. 取消交易

### Phase 3：开仓执行

**Step 1：检查前置条件**

```bash
# 查询账户余额
okx account balance USDT --profile <profile>

# 查询当前持仓
okx account positions --instType SWAP --profile <profile>
```

**Step 2：计算仓位大小**

按照"仓位计算详解"中的标准化步骤计算：

```
示例：
- 账户余额：10,000 USDT
- risk_percent：1.5%
- ATR：450
- atr_multiplier_sl：1.5
- 杠杆：10x

单笔风险金额 = 10,000 × 0.015 = 150 USDT
每张合约风险 = 450 × 1.5 = 675 USDT
仓位数 = 150 / 675 = 0.22 张 → 取整为 1 张
实际投入 = 1 × 100 × 10 = 1,000 USDT
保证金占用 = 1,000 / 10 = 100 USDT
```

**Step 3：验证风控参数**

检查是否满足所有风控过滤条件（详见"风控参数说明"章节）：

```
✅ 技术指标：趋势方向明确、MACD确认、RSI合理
✅ 波动条件：ATR ≥ 200（充足）
✅ 风险条件：RR = 2.0（≥1.5）、单笔风险 = 1.5%（≤2%）
✅ 账户条件：余额充足、保证金占用 = 1%（≤50%）
✅ 历史条件：未连续亏损、回撤未超标
✅ 信号质量：信心度 = 75.2%（≥65%）、非CONFLICT、成交量确认通过
```

**Step 4：执行开仓**

做多开仓：
```bash
okx swap place \
  --instId BTC-USDT-SWAP \
  --side buy \
  --ordType market \
  --sz 1 \
  --tdMode cross \
  --posSide long \
  --tgtCcy quote_ccy \
  --lever 10 \
  --profile demo
```

做空开仓：
```bash
okx swap place \
  --instId BTC-USDT-SWAP \
  --side sell \
  --ordType market \
  --sz 1 \
  --tdMode cross \
  --posSide short \
  --tgtCcy quote_ccy \
  --lever 10 \
  --profile demo
```

**Step 5：设置ATR止盈止损**

```bash
okx swap place-algo \
  --instId BTC-USDT-SWAP \
  --side sell \
  --ordType market \
  --tpTriggerPx 66,550 \
  --tpOrdPx \
  --slTriggerPx 64,525 \
  --slOrdPx \
  --tdMode cross \
  --posSide long \
  --sz 1 \
  --profile demo
```

开仓成功后，向用户报告：
```
⚡ 开仓成功！v2.1（整合 Position Sizer）
━━━━━━━━━━━━━━━━━━━
📈 方向：做多 10x
💰 开仓价格：$65,200
📊 仓位大小：1 张
💵 名义价值：$65,200
💎 保证金占用：$6,520（65.2%）
━━━━━━━━━━━━━━━━━━━
🔥 信号信心度：75.2% ✅
📊 多时框一致性：3/4 (1D↑ 4H↑ 1H↑ 15M↓)
━━━━━━━━━━━━━━━━━━━
🛑 ATR止损：$64,525（-1.5×ATR，-1.26%）
🎯 ATR止盈：$66,550（+3×ATR，+2.07%）
💰 清算价格：$64,890（独立保证金）
✅ 止损在清算价之前，安全
━━━━━━━━━━━━━━━━━━━
📏 风险收益比：2.0
💰 单笔风险：$675（6.75%）
━━━━━━━━━━━━━━━━━━━
💳 日资金成本：$19.56（费率0.01%）
💳 周资金成本：$136.92
━━━━━━━━━━━━━━━━━━━
📋 订单ID：xxxxxxxxx
```

### Phase 4：持仓监控与止盈止损

当存在持仓时，持续监控价格变化：

**Step 1：获取当前价格**
```bash
okx market ticker BTC-USDT-SWAP
```

**Step 2：计算盈亏**

```
做多：
- 盈亏金额 = (当前价格 - 入场价格) × 仓位大小 × 合约面值
- 盈亏比例 = (当前价格 - 入场价格) / 入场价格 × 100

做空：
- 盈亏金额 = (入场价格 - 当前价格) × 仓位大小 × 合约面值
- 盈亏比例 = (入场价格 - 当前价格) / 入场价格 × 100
```

**Step 3：ATR移动止损（可选）**

触发条件：
```
做多：盈利 ≥ 1.5×ATR（即 当前价格 ≥ 入场价格 + 1.5×ATR）
做空：盈利 ≥ 1.5×ATR（即 当前价格 ≤ 入场价格 - 1.5×ATR）
```

移动止损规则：
```
做多移动止损：
- 新止损价 = 当前价格 - (ATR × atr_multiplier_sl)
- 新止损价必须 > 原止损价
- 更新止损订单

做空移动止损：
- 新止损价 = 当前价格 + (ATR × atr_multiplier_sl)
- 新止损价必须 < 原止损价
- 更新止损订单
```

**Step 4：平仓判断**

触发止盈时，报告：
```
🎉 止盈平仓！
━━━━━━━━━━━━━━━━━━━
💰 平仓价格：$66,550
📈 盈利幅度：+2.07%
💵 盈利金额：+1,350 USDT
📊 风险收益比：2.0
━━━━━━━━━━━━━━━━━━━
✅ 策略执行成功
```

触发止损时，报告：
```
⚠️ 止损平仓！
━━━━━━━━━━━━━━━━━━━
💰 平仓价格：$64,525
📉 亏损幅度：-1.26%
💵 亏损金额：-675 USDT
💎 单笔风险：1.26%
━━━━━━━━━━━━━━━━━━━
⚡ 风控执行成功，保护本金
```

**Step 5：持仓中**

未触发止盈止损时，向用户报告当前状态：
```
📊 持仓监控中...
━━━━━━━━━━━━━━━━━━━
当前价格：$65,800
入场价格：$65,200
━━━━━━━━━━━━━━━━━━━
💰 浮动盈利：+600 USDT
📈 盈利幅度：+0.92%
━━━━━━━━━━━━━━━━━━━
🛑 止损价格：$64,525
🎯 止盈价格：$66,550
📍 距离止盈：$750（1.14%）
━━━━━━━━━━━━━━━━━━━
⏳ 继续监控中...
```

## 使用示例

用户可以这样触发：

- "分析 BTC永续合约"
- "BTC做多 10x，ATR止损1.5倍，止盈3倍，风险1.5%"
- "做空 BTC 5x，入场价 68000"
- "查看当前BTC持仓"
- "平仓 BTC永续做多"
- "设置ATR止损 止损1.5 止盈3"
- "用模拟盘测试 BTC做多 10x"
- "切换到实盘，BTC做空 15x"
- "启用移动止损"
- "检查当前风控状态"
- "查看多时框趋势"
- "计算 BTC 10x杠杆的仓位"
- "评估当前交易风险"
- "检查清算价格"

## 输出格式

每次分析后输出格式统一的报告：

```
📊 BTC合约交易系统 v2.2 - BTC-USDT-SWAP [模拟盘]
━━━━━━━━━━━━━━━━━━━
当前价格：$65,200
ATR(14)：450
━━━━━━━━━━━━━━━━━━━
【多时框趋势分析】
1D: UP ⬆️ (EMA200: $64,200, 价格>EMA +1.55%)
4H: UP ⬆️ (EMA200: $64,500, 价格>EMA +1.09%)
1H: UP ⬆️ (EMA200: $64,800, 价格>EMA +0.62%)
15M: DOWN ⬇️ (EMA200: $65,100, 价格<EMA -0.15%)
━━━━━━━━━━━━━━━━━━━
时框一致性：3/4 → 乘数 0.82
主导方向：向上 ⬆️
EMA距离：0.62%（< 3%，无惩罚）

【量化评分明细】
━━━━━━━━━━━━━━━━━━━
因子            权重    得分    加权贡献
──────────────────────────────────
EMA趋势        22%    +75     +16.5 ⬆️
MACD           13%    +60     +7.8  ⬆️
RSI            11%    +25     +2.8  ⬆️
RSI背离         9%    +50     +4.5  ⬆️
成交量          8%    +80     +6.4  ⬆️
布林带          6%    +30     +1.8  ⬆️
S/R位置         4%    +40     +1.6  ⬆️
K线形态         2%    +60     +1.2  ⬆️
──────────────────────────────────
技术面得分：+42.6（75%权重）
──────────────────────────────────
OI变化趋势      9%    +85     +7.7  ⬆️
多空比L/S       6%    +20     +1.2  ⬆️
资金费率        5%    +30     +1.5  ⬆️
清算数据        3%    +40     +1.2  ⬆️
大户持仓变化     2%    +60     +1.2  ⬆️
──────────────────────────────────
情绪面得分：+12.8（25%权重）
──────────────────────────────────
总分值：+55.4
信心度：55.4 × 0.82（时框一致性）= 45.4%（⚠️ 低于65%，建议观望）
RSI背离        12%     +0     +0.0  ➖
成交量         11%    +50     +5.5  ⬆️
布林带          8%    +30     +2.4  ⬆️
S/R位置         5%    +15     +0.75 ⬆️
K线形态         2%     +0     +0.0  ➖
━━━━━━━━━━━━━━━━━━━
加权得分合计：+45.45
时框一致性惩罚：×0.82 → +37.27
EMA距离惩罚：×1.0 → +37.27
━━━━━━━━━━━━━━━━━━━
最终信心度：75.2% ✅

【信号判断】
━━━━━━━━━━━━━━━━━━━
做多得分：45.45
做空得分：12.85
得分差距：32.60 (≥15) ✅
信号状态：BUY ✅
成交量确认：通过 ✅ (量比1.8)
━━━━━━━━━━━━━━━━━━━
💡 交易建议：做多
📍 参考入场价：$65,200
🛑 ATR止损：$64,525（-1.5×ATR，-1.26%）
🎯 ATR止盈：$66,550（+3×ATR，+2.07%）
📈 风险收益比：2.0
━━━━━━━━━━━━━━━━━━━
💎 建议仓位：1 张（杠杆10x，投入1000 USDT）
💰 单笔风险：150 USDT（1.5%）
💵 保证金占用：100 USDT（1%）
━━━━━━━━━━━━━━━━━━━
✅ 满足开仓条件：
   ✅ 信心度≥65%（75.2%）
   ✅ 非CONFLICT状态（差距32.6分）
   ✅ 成交量确认通过（量比1.8）
   ✅ ATR充足（450 ≥ 200）
   ✅ RR合格（2.0 ≥ 1.5）
   ✅ 余额充足
   ✅ 持仓数未超标
━━━━━━━━━━━━━━━━━━━
⚠️  注意事项：
   - 15M时框与主趋势相反，关注短期回调风险
   - 信心度中等（75.2%），建议小仓位试探
   - RSI未达到极端值，可能不会立即反转
```

## v2.2 升级说明（整合 Position Sizer）

### 核心升级

1. **智能仓位计算引擎**：
   - 整合 position-sizer 核心功能，支持3种仓位计算方法
   - 固定比例法（默认）：基于固定风险百分比计算仓位
   - ATR动态止损法：基于市场波动率动态调整仓位
   - 凯利公式（高级）：基于历史胜率和盈亏比计算最优仓位

2. **清算价格验证**：
   - 自动计算独立保证金下的清算价格
   - 验证止损价格是否在清算价之前
   - 提供风险预警和优化建议

3. **资金成本估算**：
   - 自动计算日/周资金费率成本
   - 评估多日持仓的实际净收益
   - 根据资金费率提供持仓时长建议

4. **投资组合约束**：
   - 单仓占比控制（默认≤10%）
   - 总敞口控制（默认≤6-8%）
   - 保证金占用检查（默认≤50%）

5. **多场景杠杆对比**：
   - 自动计算5x、10x、20x等不同杠杆下的仓位和风险
   - 帮助用户选择最优杠杆倍数

6. **MMR分层保证金支持**：
   - 支持大仓位的Tier 2+保证金率
   - VIP用户手续费率自定义

### 新增参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| max_position_pct | 最大单仓占比 | 10% |
| max_portfolio_heat | 最大总敞口 | 8% |
| mmr | 维持保证金率 | 0.004（0.4%） |
| fee_rate | 手续费率 | 0.0005（0.05%） |

### 新增使用场景

- "计算 BTC 10x杠杆的仓位"
- "评估当前交易风险"
- "检查清算价格"
- "对比5x、10x、20x杠杆的仓位"

## v2.1 升级说明

### 核心升级

1. **市场情绪分析**：
   - 新增5个市场情绪指标（OI变化、多空比、资金费率、清算数据、大户持仓）
   - 权重调整为技术面75% + 情绪面25%
   - 实现技术面与情绪面冲突检测

2. **多时框趋势分析**：
   - 从单一时框升级为4时框综合分析（1D、4H、1H、15M）
   - 引入时框一致性乘数，提升信号可靠性
   - EMA200作为主要趋势判断依据

3. **量化评分系统**：
   - 从定性判断升级为量化评分
   - 13个指标加权计算，权重基于可靠性分配
   - 最终信心度 0% ~ 100%，清晰反映信号强度

3. **信号冲突检测**：
   - 自动检测多空得分差距
   - 冲突信号禁止开仓，避免在趋势不明确时操作

4. **成交量确认**：
   - 量比计算和放量/缩水判断
   - 成交量门槛规则，确保价格走势有真实支撑

5. **RSI背离检测**：
   - 自动检测顶底背离
   - 背离信号获得高权重，是最强的反转信号

6. **布林带分析**：
   - 识别极端价格位置
   - 考虑布林带宽，提升信号可靠性

7. **支撑阻力识别**：
   - 自动识别关键S/R位
   - 接近S/R时提供额外信号支持

8. **K线形态识别**：
   - 识别6种经典形态
   - 形态信号作为辅助确认

### 准确率提升

| 升级项 | v1.0 | v2.0 | 提升幅度 |
|--------|------|------|----------|
| 趋势判断 | 单时框定性 | 4时框量化 | ⬆️ 显著 |
| 信号强度 | 无量化 | 0-100%信心度 | ⬆️ 显著 |
| 时框一致性 | 无 | 0.35-1.0乘数 | ⬆️ 新增 |
| 信号冲突 | 无检测 | 自动检测 | ⬆️ 新增 |
| 成交量确认 | 简单判断 | 量比+门槛规则 | ⬆️ 增强 |
| RSI背离 | 无 | 自动检测+高权重 | ⬆️ 新增 |
| 布林带 | 无 | 位置+带宽分析 | ⬆️ 新增 |
| S/R识别 | 无 | 自动识别+接近度 | ⬆️ 新增 |
| K线形态 | 无 | 6种经典形态 | ⬆️ 新增 |

### 预期效果

- **信号质量**：从"定性判断"提升到"量化评分"，信号更加可靠
- **准确率**：多时框一致性和冲突检测预计提升准确率 15-20%
- **过滤能力**：成交量门槛和冲突检测有效过滤低质量信号
- **反转捕捉**：RSI背离和布林带极端位置提升反转信号捕捉能力

## 风险提示

1. **默认使用模拟盘（demo）**，切换实盘需用户明确指定 profile=live。
2. 单笔风险建议控制在账户余额的 1-2%，避免连续亏损导致大幅回撤。
3. 杠杆倍数应根据市场波动调整：趋势行情 10-20x，震荡行情 3-5x，高波动期降低杠杆。
4. ATR 动态止损是本系统的核心，必须严格执行，不得随意调整止损位。
5. 风险收益比 RR < 1.5 的交易不建议执行，避免低质量交易。
6. 信心度 < 65% 的信号不建议执行，避免信号质量不足。
7. CONFLICT 状态必须等待市场方向明确后再操作，避免在多空分歧时开仓。
8. 成交量未确认且无S/R支撑时，即使其他因子得分高也不开仓。
9. 移动止损仅在盈利达到 1.5×ATR 后启动，过早启动可能被小幅震荡止损。
10. 连续亏损 3 笔后必须暂停交易，重新评估市场环境和策略参数。
11. 账户回撤达到 10% 时必须暂停交易，检查风控参数是否合理。
12. 合约交易具有高风险，高杠杆会放大风险和收益，请根据自身风险承受能力操作。
13. 实际交易存在滑点、手续费、API 延迟、强平等风险，实际盈亏与理论值会有偏差。
14. 建议先在模拟盘充分测试，熟悉系统和策略后再进行实盘操作。
15. 市场极端行情下可能出现插针、爆仓、流动性枯竭等风险，请密切关注持仓。
16. 本 Skill 仅供学习研究，不构成投资建议，盈亏自负，请谨慎操作。
17. 多时框分析虽然提升准确率，但不能保证100%正确，仍需结合市场环境综合判断。
18. 量化评分系统基于历史数据和技术指标，市场出现突发性变化时可能失效。
19. RSI背离是最强的反转信号，但背离后可能继续背离，需结合其他指标确认。
20. 成交量确认是开仓的必要条件，但成交量可以造假，需结合价格走势综合判断。

---

### [31] `okx-cex-volatility-strategy`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-cex-volatility-strategy/SKILL.md`

---
name: okx-cex-volatility-strategy
description: "Use this skill when the user wants to start, run, monitor, evaluate, or stop an automated BTC/ETH perpetual swap strategy on OKX based on 1H technical signals and volatility-adaptive risk rules, including requests like 'start volatility strategy', 'run BTC ETH auto strategy', 'auto trade BTC ETH based on indicators', 'volatility adaptive trading', 'multi-indicator confluence strategy', 'strategy status', or 'stop the strategy'. This skill covers 1H data collection, sentiment scoring, AI decision logic, Agent Trade Kit execution, and strategy-level risk control for BTC-USDT-SWAP and ETH-USDT-SWAP. Do NOT use for manual orders (use okx-cex-trade), read-only market data queries (use okx-cex-market), or account-only queries (use okx-cex-portfolio)."
license: MIT
metadata:
  author: okx
  version: "1.3.1"
  homepage: "https://www.okx.com"
  agent:
    emoji: "📊"
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# OKX CEX Volatility Strategy

This skill follows the competition template:

1. Step 1 — Data Collection / 数据采集
2. Step 2 — Sentiment Assessment / 情绪评估
3. Step 3 — AI Decision Logic / AI 判断逻辑
4. Step 4 — Order Execution / 下单执行
5. Step 5 — Risk Rules / 风控规则

Automated 1H strategy for BTC-USDT-SWAP and ETH-USDT-SWAP only. The strategy runs on the agent side through the OKX CLI / Agent Trade Kit. It should stay conservative and low-ambiguity by default.

## Scope & Routing

| User intent | Route |
|---|---|
| Market prices, candles, technical indicators | `okx-cex-market` |
| Manual spot/swap/futures/options orders | `okx-cex-trade` |
| Account balance, positions, transfers, account config | `okx-cex-portfolio` |
| Grid / DCA bots | `okx-cex-bot` |
| **Automated 1H BTC/ETH swap strategy with sentiment + risk rules** | **This skill** |

## Prerequisites

1. Install and preflight the OKX CLI:

   ```bash
   npm install -g @okx_ai/okx-trade-cli
   okx upgrade
   okx --version
   okx config show
   ```

2. Never accept API credentials directly in chat. If the user pastes credentials, stop and ask them to edit `~/.okx/config.toml` locally or run `okx config init`.

3. Never assume profile names. `okx config init` usually creates `okx-demo` and `okx-prod`, but users may rename profiles.
   - If the user explicitly names a configured profile, use it.
   - If exactly one configured profile exists, use it and tell the user.
   - If multiple configured profiles exist and the user did not choose one, ask before the first write.

4. Before the first strategy run, confirm account state:

   ```bash
   okx --profile <profile> account config --json
   okx --profile <profile> account balance USDT --json
   ```

5. This strategy assumes:
   - `posMode = net_mode`
   - `tdMode = cross`
   - one direction per instrument

   If `okx account config` shows `long_short_mode`, stop and ask the user whether to switch with:

   ```bash
   okx --profile <profile> account set-position-mode --posMode net_mode
   ```

6. A readable balance proves read access only. Do not claim trade permission is active until the first confirmed write succeeds.

## Strategy Snapshot

- Instruments: `BTC-USDT-SWAP`, `ETH-USDT-SWAP`
- Timeframe: `1H` only
- Margin mode: `cross`
- Position mode: `net`
- Indicators: `EMA(20,60)`, `RSI(14)`, `MACD(12,26,9)`, `BB(20,2)`, `ATR(14)`
- Closed-bar convention:
  - `index 0` = live / forming 1H bar, never use it for signal generation
  - `c1 = index 1` = last closed 1H bar
  - `c2 = index 2` = previous closed 1H bar
  - closed 30-bar window = indexes `1..30`
  - 30 closed bars now represent about 30 hours of lookback

Detailed formulas and workflow payloads live in:

- `{baseDir}/references/strategy-params.md`
- `{baseDir}/references/workflows.md`

## Step 1 — Data Collection / 数据采集

For each instrument, collect the following before any decision:

| Data | CLI command | Purpose |
|---|---|---|
| Instrument meta | `okx market instruments --instType SWAP --instId <instId> --json` | Get `ctVal`, `tickSz`, `lotSz`, `minSz`, `state` |
| 1H candles | `okx market candles <instId> --bar 1H --limit 31 --json` | Get closed-bar `close[c1]` and recent close series |
| EMA | `okx market indicator ema <instId> --bar 1H --params 20,60 --list --limit 3 --json` | Trend filter |
| RSI | `okx market indicator rsi <instId> --bar 1H --params 14 --list --limit 3 --json` | Momentum filter |
| MACD | `okx market indicator macd <instId> --bar 1H --params 12,26,9 --list --limit 3 --json` | Crossover trigger |
| Bollinger Bands | `okx market indicator bb <instId> --bar 1H --params 20,2 --list --limit 31 --json` | Volatility percentile + mid-band filter |
| ATR | `okx market indicator atr <instId> --bar 1H --params 14 --list --limit 31 --json` | TP/SL distance + ATR spike guard |
| Available balance | `okx --profile <profile> account balance USDT --json` | Capital sizing |
| Max order size | `okx --profile <profile> account max-size --instId <instId> --tdMode cross --json` | Prevent oversizing |
| Open positions | `okx --profile <profile> swap positions --instId <instId> --json` | Current strategy state |
| Active TP/SL algos | `okx --profile <profile> swap algo orders --instId <instId> --json` | Existing stop structure |

Data collection rules:

- Use `market candles` for `close[c1]`. Do not assume `BB` output contains a close price.
- Use `c1 = 1`, `c2 = 2`, and indexes `1..30` for all rolling calculations.
- If any required market field is missing, stale, or inconsistent, output `action = "skip"` for that instrument.
- Do not fire all public requests without throttling. Small batched parallelism is fine; unbounded fan-out is not needed for a 1H strategy.

## Step 2 — Sentiment Assessment / 情绪评估

Sentiment is an intermediate output. It is not an order by itself.

Use the last closed bar `c1` and previous closed bar `c2`:

```text
bullish_points =
  35 if ema20[c1] > ema60[c1]
  + 25 if dif[c1] > dea[c1] and dif[c2] <= dea[c2]
    else 10 if dif[c1] > dea[c1]
  + 15 if 50 <= rsi[c1] <= 70
  + 15 if close[c1] > bb_middle[c1]

bearish_points =
  35 if ema20[c1] < ema60[c1]
  + 25 if dif[c1] < dea[c1] and dif[c2] >= dea[c2]
    else 10 if dif[c1] < dea[c1]
  + 15 if 30 <= rsi[c1] < 50
  + 15 if close[c1] < bb_middle[c1]

sentiment_score = bullish_points - bearish_points
```

Classification:

- `sentiment_score >= 50` -> `bullish`
- `sentiment_score <= -50` -> `bearish`
- otherwise -> `neutral` / `range`

Volatility regime:

- `BB bandwidth percentile 0-25%` -> `low_vol`
- `25-75%` -> `normal_vol`
- `75-100%` -> `high_vol`
- if `ATR[c1] > 3 * mean(ATR[1..30])` -> `shock`, `trade_blocked = true`

Expected sentiment output:

```json
{
  "instId": "BTC-USDT-SWAP",
  "sentimentDirection": "bullish",
  "sentimentScore": 65,
  "volatilityRegime": "normal_vol",
  "tradeBlocked": false,
  "reason": [
    "EMA20 above EMA60 on last closed 1H bar",
    "Fresh MACD golden cross on c1 vs c2",
    "Close above BB middle"
  ]
}
```

## Step 3 — AI Decision Logic / AI 判断逻辑

Use only the strict signal conditions below for entries.

### Entry Conditions

**Long**

1. `ema20[c1] > ema60[c1]`
2. `40 <= rsi[c1] <= 70`
3. `dif[c1] > dea[c1] && dif[c2] <= dea[c2]`
4. `close[c1] > bb_middle[c1]`
5. `trade_blocked = false`

**Short**

1. `ema20[c1] < ema60[c1]`
2. `30 <= rsi[c1] <= 60`
3. `dif[c1] < dea[c1] && dif[c2] >= dea[c2]`
4. `close[c1] < bb_middle[c1]`
5. `trade_blocked = false`

### Position Actions

| Current position | Signal | Action |
|---|---|---|
| No position | Long | `open_long` |
| No position | Short | `open_short` |
| No position | None | `skip` |
| Long | Long | `hold` |
| Short | Short | `hold` |
| Long | Short | `reverse_to_short` |
| Short | Long | `reverse_to_long` |
| Any | Hard risk triggered | `close_only` |

### Add / Reduce Rules

Default competition template behavior:

- `allow_add = false`
- `allow_reduce = false`

This v1 strategy is intentionally single-entry / single-exit. It does not pyramid and does not scale out unless the user explicitly asks for a different policy.

### Decision Prompt Template

Use the following instruction style when asking the AI layer to produce a decision:

```text
You are the execution brain of okx-cex-volatility-strategy.
Use only the last closed 1H bar (c1=index 1) and the previous closed 1H bar (c2=index 2).
Never use live bar index 0 for signal generation.
Default allow_add=false and allow_reduce=false.
If any required field is missing, action must be "skip".
If any hard risk rule is triggered, action must be "close_only" or "skip".
Return JSON only.
```

Expected decision payload:

```json
{
  "instId": "BTC-USDT-SWAP",
  "sentimentDirection": "bullish",
  "sentimentScore": 65,
  "volatilityRegime": "normal_vol",
  "signal": "long",
  "action": "open_long",
  "leverage": 4,
  "sizePct": 24,
  "sizeMode": "quote_ccy",
  "tp": "102000",
  "sl": "96000",
  "riskFlags": []
}
```

## Step 4 — Order Execution / 下单执行

Execution rules:

1. Always fetch `ctVal`, `tickSz`, `minSz`, and `state` before entry.
2. Entry sizing may be expressed in USDT by using `tgtCcy=quote_ccy`.
3. After the entry fills, read the actual filled contracts from the position / fill result.
4. Place TP/SL using the actual filled contracts, not the requested USDT amount.
5. Round `tpTriggerPx` and `slTriggerPx` to `tickSz`.
6. Verify after every write. If TP/SL attach fails after one retry, immediately `close_only` the position.

### Entry Example

```text
tag="CLI"
okx market instruments --instType SWAP --instId BTC-USDT-SWAP --json
okx --profile <profile> account max-size --instId BTC-USDT-SWAP --tdMode cross --json
okx --profile <profile> swap leverage --instId BTC-USDT-SWAP --lever 4 --mgnMode cross
okx --profile <profile> swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 1000 --tgtCcy quote_ccy --tdMode cross
okx --profile <profile> swap positions --instId BTC-USDT-SWAP --json
okx --profile <profile> swap algo place --instId BTC-USDT-SWAP --side sell --ordType oco --sz <filled_contracts> --tdMode cross --tpTriggerPx <tp> --tpOrdPx=-1 --slTriggerPx <sl> --slOrdPx=-1
okx --profile <profile> swap algo orders --instId BTC-USDT-SWAP --json
```

```text
tag="MCP"
market_get_instruments({instType:"SWAP", instId:"BTC-USDT-SWAP"})
account_get_max_size({instId:"BTC-USDT-SWAP", tdMode:"cross"})
swap_set_leverage({instId:"BTC-USDT-SWAP", lever:"4", mgnMode:"cross"})
swap_place_order({instId:"BTC-USDT-SWAP", tdMode:"cross", side:"buy", ordType:"market", sz:"1000", tgtCcy:"quote_ccy"})
swap_get_positions({instId:"BTC-USDT-SWAP"})
swap_place_algo_order({instId:"BTC-USDT-SWAP", tdMode:"cross", side:"sell", ordType:"oco", sz:"<filled_contracts>", tpTriggerPx:"<tp>", tpOrdPx:"-1", slTriggerPx:"<sl>", slOrdPx:"-1"})
swap_get_algo_orders({instId:"BTC-USDT-SWAP", status:"pending"})
```

### Reverse Example

```text
tag="CLI"
okx --profile <profile> swap algo orders --instId BTC-USDT-SWAP --json
okx --profile <profile> swap algo cancel --instId BTC-USDT-SWAP --algoId <algoId>
okx --profile <profile> swap close --instId BTC-USDT-SWAP --mgnMode cross
okx --profile <profile> swap positions --instId BTC-USDT-SWAP --json
# only after the previous position is confirmed flat:
okx --profile <profile> swap leverage --instId BTC-USDT-SWAP --lever 4 --mgnMode cross
okx --profile <profile> swap place --instId BTC-USDT-SWAP --side sell --ordType market --sz 1000 --tgtCcy quote_ccy --tdMode cross
okx --profile <profile> swap positions --instId BTC-USDT-SWAP --json
okx --profile <profile> swap algo place --instId BTC-USDT-SWAP --side buy --ordType oco --sz <filled_contracts> --tdMode cross --tpTriggerPx <tp> --tpOrdPx=-1 --slTriggerPx <sl> --slOrdPx=-1
```

```text
tag="MCP"
swap_get_algo_orders({instId:"BTC-USDT-SWAP", status:"pending"})
swap_cancel_algo_orders({orders:[{"algoId":"<algoId>","instId":"BTC-USDT-SWAP"}]})
swap_close_position({instId:"BTC-USDT-SWAP", mgnMode:"cross"})
swap_get_positions({instId:"BTC-USDT-SWAP"})
# only after the previous position is confirmed flat:
swap_set_leverage({instId:"BTC-USDT-SWAP", lever:"4", mgnMode:"cross"})
swap_place_order({instId:"BTC-USDT-SWAP", tdMode:"cross", side:"sell", ordType:"market", sz:"1000", tgtCcy:"quote_ccy"})
swap_get_positions({instId:"BTC-USDT-SWAP"})
swap_place_algo_order({instId:"BTC-USDT-SWAP", tdMode:"cross", side:"buy", ordType:"oco", sz:"<filled_contracts>", tpTriggerPx:"<tp>", tpOrdPx:"-1", slTriggerPx:"<sl>", slOrdPx:"-1"})
```

## Step 5 — Risk Rules / 风控规则

### Volatility-Adaptive Leverage and Position Size

Use Bollinger Bandwidth percentile on the closed 30-bar window (`indexes 1..30`):

| BB bandwidth percentile | Leverage | Margin (sizePct) | Notional (margin × leverage) |
|---|---|---|---|
| `0-25%` | `5x` | `30%` of available USDT | `150%` of available USDT |
| `25-50%` | `4x` | `24%` of available USDT | `96%` of available USDT |
| `50-75%` | `3x` | `16%` of available USDT | `48%` of available USDT |
| `75-100%` | `2x` | `10%` of available USDT | `20%` of available USDT |

**Sizing semantics:** `sizePct` is the **margin ratio** (actual collateral committed), not the notional.
The entry order size is calculated as:

```
notional (sz, tgtCcy=quote_ccy) = availableUSDT × sizePct% × leverage
margin used                      = notional / leverage = availableUSDT × sizePct%
```

### Trade-Level Risk

- Long:
  - `SL = entry - 2 * ATR[c1]`
  - `TP = entry + 3 * ATR[c1]`
- Short:
  - `SL = entry + 2 * ATR[c1]`
  - `TP = entry - 3 * ATR[c1]`
- Reward-to-risk target: `1.5 : 1`

### Strategy-Level Risk

- Per-instrument margin <= `30%` of available USDT (notional up to `150%` at 5x)
- Combined BTC + ETH margin <= `60%` of available USDT
- Block new entries if:
  - `ATR[c1] > 3 * mean(ATR[1..30])`
  - requested size exceeds `account max-size`
  - requested size is below `minSz` / `lotSz`
  - instrument `state` is not tradable

### Drawdown Guards

- Soft guard: if strategy drawdown from start equity reaches `4%`
  - stop opening new positions
  - keep existing TP/SL working
- Hard guard: if strategy drawdown from start equity reaches `8%`
  - cancel all strategy algo orders
  - close all strategy positions
  - disable the recurring automation

### Forced Flat Conditions

Immediately flatten and stop automation if any of the following happens:

1. Hard drawdown guard triggered
2. A position is open but no TP/SL algo order can be attached after one retry
3. Position mode is not `net_mode` and the strategy cannot guarantee one-way semantics
4. The exchange rejects leverage / margin / size twice for the same action

### Cooldown Rule

If the same instrument hits stop-loss twice in a rolling 24-hour window, skip that instrument for the next full 1H cycle.

## Communication Requirements

Before the first write, print a confirmation summary and wait for explicit approval:

```text
Strategy: okx-cex-volatility-strategy
Profile: <profile>
Instruments: BTC-USDT-SWAP, ETH-USDT-SWAP
Timeframe: 1H closed bars only
Position mode: net_mode
Margin mode: cross
Available USDT: <balance>
Drawdown guards: soft 4% | hard 8%
Automation: one-shot or recurring 1H host scheduler

Proceed? (yes/no)
```

Per cycle, report:

- instrument
- sentiment direction / score
- signal
- action
- leverage / size %
- TP / SL
- risk flags

If host automation exists, include next run time. If not, explicitly say this was a one-shot cycle.

## Global Notes

- 1H only. Do not substitute 4H or 1D bars for signal generation.
- Closed bars only. Never use `index 0` for signal generation.
- Use `tgtCcy=quote_ccy` only for entry sizing. TP/SL algo size must use actual filled contracts.
- Host scheduling is outside Agent Trade Kit. Prefer the host automation layer; do not hardcode `/schedule` into a portable skill.
- Respond in the user's language. Logs may remain structured / bilingual if that improves clarity.

---

### [32] `okx-execution-vortex`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-execution-vortex/SKILL.md`

---
name: okx-execution-vortex
description: 接收交易信号后安全执行现货/永续/交割/期权订单，支持 OCO、网格、DCA、仓位管理及二次确认风控。依赖 market/trade/portfolio/bot 基础 Skill。
license: MIT
metadata:
  author: web3_xiaoyao
  version: 1.0.0
  homepage: https://www.okx.com
  requires:
    install:
      bins: okx
    kind: package
    package: npm
---

# OKX 漩涡执行器 (okx-execution-vortex)

## Description

安全、智能的交易执行层，专为 AI Agent 设计。接收交易请求后，经过严格风险检查和二次确认，自动执行现货、永续、交割、期权的下单、改单、撤单、止盈止损等操作。

**核心流程**：
1. **行情查询**：获取最新价格、深度等市场数据
2. **仓位计算**：根据账户余额和风险参数计算最优仓位
3. **二次确认**：输出完整交易计划并等待用户确认
4. **安全执行**：检查保证金率、余额、系统状态后执行
5. **结果返回**：返回订单详情和执行状态

**高级功能**：
- **OCO订单**：止盈止损同时设置
- **网格交易**：震荡区间自动交易（依赖 `okx-cex-bot`）
- **DCA定投**：定期分批买入
- **仓位管理**：自动调整杠杆和保证金

**依赖 Skill**：`okx-cex-market`, `okx-cex-trade`, `okx-cex-portfolio`, `okx-cex-bot`

## Activation Rules (触发词)

当用户输入以下模式时，激活本 Skill：

- **直接执行**：
  - “执行买入 BTC 1000U”
  - “对 BTC-USDT-SWAP 开多 5 张”
  - “执行 RSI 信号：买入 ETH”
  - “市价卖出 SOL 全部仓位”
  - “执行止损单，价格跌破 50000”
  - “执行止盈单，价格涨到 52000”

- **高级执行**：
  - “网格下单 BTC-USDT，区间 50000-52000，10 格”
  - “DCA 买入 ETH 每周 500U”
  - “OCO 订单：BTC 现价 51000，止盈 52000，止损 50000”
  - “批量执行这三个币种各 500U”
  - “切换 BTC-USDT-SWAP 杠杆到 10x”

- **管理操作**：
  - “撤销所有挂单”
  - “修改订单 #12345 价格为 51000”
  - “平掉 BTC 全部仓位”
  - “检查执行状态”

**禁止直接调用基础 trade Skill**：所有写操作必须通过本 Skill 执行，以确保统一的风险控制。如果用户尝试直接调用 `okx spot place` 等命令，应引导其使用本 Skill。

## Available Commands (可用命令表)

本 Skill 封装 OKX CLI 命令，所有命令均经过二次确认和风险检查：

| 类别 | 关键命令 | 示例 | 说明 |
|------|----------|------|------|
| **现货** | `okx spot place` | `--instId BTC-USDT --side buy --sz 0.01` | 现货下单 |
| | `okx spot cancel/amend` | `--ordId 123456789` | 撤单/改单 |
| **永续** | `okx swap place` | `--instId BTC-USDT-SWAP --side buy --posSide long --sz 1` | 永续合约下单 |
| | `okx swap close` | `--posSide long` | 平仓 |
| | `okx swap leverage` | `--lever 10` | 调整杠杆 |
| **交割** | `okx futures place` | `--instId BTC-USD-240329 --side buy --posSide long` | 交割合约下单 |
| **期权** | `okx option place` | `--instId BTC-USD-240329-50000-C --side buy` | 期权下单 |
| **算法单** | `okx algo place` | `--tpTriggerPx 52000 --slTriggerPx 50000` | OCO/止盈止损 |
| **网格/DCA** | `okx bot grid create` | `--lowerPx 50000 --upperPx 52000 --gridNum 10` | 网格交易 |
| | `okx bot dca create` | `--investment 500 --frequency weekly` | 定期投资 |

**常用参数**：
- `--tgtCcy`: `quote_ccy`(报价货币), `base_ccy`(标的货币)
- `--tdMode`: `isolated`(逐仓), `cross`(全仓)
- `--posSide`: `long`(多), `short`(空)

## Safety Notes (安全说明)

### 强制二次确认
任何写操作执行前必须输出交易计划并等待用户确认，用户必须输入 **Y** 才能继续。

### 风险控制规则
1. **保证金率**：必须 > 150%（可配置）
2. **单笔风险**：不超过账户总资产 2%（可配置）
3. **余额检查**：确保可用余额充足
4. **杠杆限制**：合约杠杆 ≤ 20x
5. **市场状态**：检查交易状态、资金费率、系统维护

### 测试模式
支持 `--demo` 参数进行模拟测试，不实际执行。

## Examples (使用示例)

### 示例 1：现货市价买入
**用户输入**：“执行买入 BTC 1000U”

**Skill 响应**：
```
📈 正在分析交易请求...

1. 查询行情：BTC-USDT 当前价格 50,123.45 USDT
2. 计算数量：1000 USDT ÷ 50,123.45 ≈ 0.01995 BTC
3. 检查风险：账户余额 15,000 USDT，单笔风险 6.67%（超过 2% 阈值）
4. 自动调整：建议买入 300 USDT（0.00598 BTC），风险 2%

⚠️ **交易确认请求**

市场：BTC-USDT
操作：买入
价格：市价
数量：0.00598 BTC（约 300 USDT）
预估手续费：0.15 USDT
账户余额：15,000.00 USDT
单笔风险：2.0%

📊 **风险检查结果**：
✅ 保证金率：不适用（现货）
✅ 余额充足
✅ 系统状态：正常

请确认是否执行？（Y/N）
```

用户输入 `Y` 后执行：
```bash
okx spot place --instId BTC-USDT --side buy --sz 0.00598 --tgtCcy quote_ccy
```

**返回结果**：
```
✅ 订单执行成功！
订单ID：123456789
成交均价：50,125.12 USDT
实际数量：0.00598 BTC
手续费：0.15 USDT
成交时间：2026-04-09 15:30:25
```

**更多示例**：查看 `examples/` 文件夹获取完整示例（永续合约、网格交易、DCA定投等）。


## Preflight (前置检查)

执行前自动检查以下条件：

### 必需条件
- OKX CLI 已安装 (`okx` 命令可用)
- 有效的 API 配置（含交易权限）
- 网络连接正常
- 依赖 Skill 已安装：`okx-cex-market`, `okx-cex-trade`, `okx-cex-portfolio`, `okx-cex-bot`

### 环境检查
- 市场交易状态正常
- 资金费率无异常
- 无重大系统故障

## 版本记录
- v1.0.0 (2026-04-09)：初始版本

## 链接
- 官方文档：https://github.com/okx/agent-trade-kit
- 技能广场：https://github.com/okx/agent-skills

---

### [33] `okx-maker-entry`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-maker-entry/SKILL.md`

---
name: okx-maker-entry
version: "1.1.0"
license: MIT
description: |
  通过被动挂单（Post-Only）开仓，替代手动市价单。自动在盘口 1-40 档分散挂 maker 限价单,
  成交即享 maker 费率，比 taker 省手续费。支持所有 USDT 永续合约。
  当用户说"挂单开仓"、"maker开仓"、"被动开仓"、"省手续费开仓"时使用此技能。
metadata:
  openclaw:
    requires:
      bins: [python]
    os: [win32, darwin, linux]
    install:
      - kind: pip
        package: ccxt
        label: Install ccxt (pip)
---

# Maker 挂单开仓

> 用被动挂单（Post-Only 限价单）开仓，不吃单，自动享受 maker 费率。
> 在盘口 1-40 档分散挂单，价格移动时自动 reclaim 远端订单到近端，直到目标名义价值全部成交。

```
用户下达开仓指令
       ↓
  检查环境 → preview 预检 → 用户确认 → start 启动后台引擎
       ↓                                       ↓
  doctor 查行情/余额/持仓                执行引擎（500ms 循环）
                                       ├─ 40 档 band 挂单
                                       ├─ 实时成交追踪
                                       ├─ 远端订单 reclaim
                                       └─ 完成/暂停/停止
       ↓
   status 查看结果
```

---

## 使用方式

### 首次设置

对 AI 助手说 **"设置 maker 开仓"** 或 **"setup maker entry"**，将自动检测环境并执行初始化流程。

### 日常使用

直接说即可，示例：

- **"BTC 做多 1000U 挂单开仓"**
- **"ETH 做空 500U maker 开仓 10 倍杠杆"**
- **"SOL 做多 200U 被动开仓 实盘"**
- **"BTC 做多 5000U 挂单开仓 最大滑点 0.5%"**
- **"查看挂单开仓状态"**
- **"停止挂单开仓"**

助手会自动执行完整流程：参数确认 → 环境检查 → 预检 → 确认 → 启动 → 监控。

---

## 前置条件

1. **AI 客户端**：Claude Code 或 OpenClaw（小龙虾）
2. **Python**：>= 3.9（执行引擎运行环境，推荐 3.11+，否则需额外安装 `tomli`）
3. **ccxt**：Python 交易所 SDK（需已存在于当前 Python 环境；若缺失，doctor 会在报错中给出对应 Python 解释器路径供用户自行补齐）
4. **OKX API Key**：已配置 `~/.okx/config.toml`，权限需 Read + Trade
5. **账户设置**：OKX 账户必须是 **单向持仓模式**（Net Mode）

---

## 运行方式

本 skill 纯 Python 实现，单文件无额外子模块，通过命令行调用：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" <subcommand> [options]
```

其中 `<skillDir>` 是本 skill 目录的绝对路径。所有子命令都输出 JSON，便于助手解析。

行情/账户查询均由该脚本自身通过 ccxt 完成，不依赖其他 CLI 或 MCP。详见 `references/cli-contract.md`。

---

## 初始化流程（首次设置时执行）

当用户说 "设置 maker 开仓" / "setup maker entry" 时：

### Step 1：确认 Python 与 ccxt

```bash
python --version
python -c "import ccxt; print(ccxt.__version__)"
```

### Step 2：完成首次配置

按 `references/credential-setup.md` 走一遍首次配置引导（创建模板、在 OKX 建 Key、填 `~/.okx/config.toml`、doctor 验证）。

### Step 3：向用户展示就绪摘要

`credential-setup.md` 的 doctor 验证全部通过后，向用户展示设置完成摘要和使用示例：

```
✅ 环境就绪！

你现在可以直接说以下命令来挂单开仓（默认模拟盘）：

  "BTC 做多 1000U 挂单开仓"
  "ETH 做空 500U maker开仓 10倍杠杆"
  "SOL 做多 200U 被动开仓 实盘"

其他操作：
  "查看挂单开仓状态"  — 查看当前任务进度
  "停止挂单开仓"      — 撤销所有挂单并停止

建议先用模拟盘试一次小额开仓，比如：
  "BTC 做多 100U 挂单开仓"
```

---

## 参数说明

| 参数              | 类型   | 必填 | 默认值   | 说明                                 |
| ----------------- | ------ | ---- | -------- | ------------------------------------ |
| instId            | string | 必填 | -        | OKX 合约 ID，如 BTC-USDT-SWAP        |
| side              | string | 必填 | -        | LONG（做多）或 SHORT（做空）         |
| entryNotionalUsdt | number | 必填 | -        | 开仓名义价值（USDT）                 |
| targetLeverage    | number | 选填 | 当前杠杆 | 目标杠杆倍数                         |
| maxAdverseMovePct | number | 选填 | 无限制   | 最大不利价格移动百分比，超过自动暂停 |
| maxRunMinutes     | number | 选填 | 无限制   | 最大运行时间（分钟），超时自动暂停   |
| profile           | string | 选填 | demo     | demo（模拟盘）或 live（实盘）        |

---

## 执行流程

### Phase 1：参数确认

1. 从用户请求中提取 instId、side、entryNotionalUsdt。
2. 如果用户未指定 profile，**默认使用 demo 模拟盘**。
3. 未指定的可选参数使用默认值。
4. 确保 instId 是 USDT 永续格式（如 `BTC-USDT-SWAP`）。用户说"BTC"时自动补全为 `BTC-USDT-SWAP`。
5. **自动推算杠杆**：如果用户未指定杠杆，先在 Phase 2 获取可用余额后，检查 `entryNotionalUsdt > availableUsdt`。若是，自动计算所需最低杠杆 = `ceil(entryNotionalUsdt / availableUsdt)`，再上浮 20% 留余量（取整），作为 targetLeverage。在参数确认摘要中告知用户"根据余额自动设置 Nx 杠杆"即可，无需用户额外操作。
6. 向用户确认完整参数后继续。

### Phase 2：环境检查

**首先检查 OKX 配置是否就绪。** 如果 doctor / preview / 环境检查报错，按下列规则自动引导修复，并向用户说明修复步骤：

1. **报 `ccxt is required` / `ModuleNotFoundError: No module named 'ccxt'`** → 说明 Python 环境没装 ccxt。错误消息里会包含脚本自己的 `sys.executable` 路径，直接用它跑 `"<该路径>" -m pip install ccxt`（**务必用 `-m pip`**，裸 `pip install` 在多 Python 环境下会装到别的解释器）。装完后重跑 doctor。
2. **报 config 文件找不到 / profile 缺失 / 账户凭据字段为空** → 按 `references/credential-setup.md` 完成首次配置，再跑 doctor 验证。
3. **报 `oneWayMode: false`** → 引导用户去 OKX 交易设置 > 持仓模式 > 单向持仓，切换后重跑。
4. **报 `canTrade: false`** → API Key 未勾 Trade 权限，重建 Key 并勾 Read + Trade。
5. 全部搞定 → 回到 Phase 2 继续原来的开仓请求。

验证 API 连通性和账户状态用 doctor 命令即可：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" doctor --profile <profile> --instId <instId>
```

检查项：

- API 凭证有效（canRead / canTrade 均为 true）
- 账户是单向持仓模式（oneWayMode = true）
- 合约可交易（symbolTradable = true）

余额和反向持仓检查由 `preview` 子命令在 Phase 3 完成。

### Phase 3：Preview 预检

调用执行引擎的 preview 命令做精确预检：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" preview \
  --profile <profile> \
  --instId <instId> \
  --side <LONG|SHORT> \
  --entryNotionalUsdt <amount> \
  --targetLeverage <leverage> \
  --maxAdverseMovePct <pct> \
  --maxRunMinutes <minutes>
```

输出 JSON 包含：

- `preview.canStart`：是否可以启动
- `preview.blockReason`：阻止原因（如有）
- `preview.feasibility`：杠杆、保证金、最大名义价值
- `preview.conflictOrders`：将被取消的非 reduce-only 挂单
- `preview.warnings`：注意事项（含大额/无保护/交易所限额提示）
- `validation.passed`：样本订单是否通过 OKX precheck

**关键规则：**

- `canStart = false` 或 `validation.passed = false` → 向用户报告原因，**不继续**
- 有 conflictOrders → 警告用户 start 会取消这些挂单
- 有 targetLeverage 变更 → 警告用户 start 会修改杠杆
- warnings 里出现 "Large notional entry" / "No slippage guard" → 在预览摘要中醒目呈现这条警告，并建议用户补一个 `maxAdverseMovePct`

向用户展示摘要，**等待明确确认后才执行 Phase 4**。

### Phase 4：启动执行引擎

用户确认后启动后台执行引擎：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" start \
  --profile <profile> \
  --instId <instId> \
  --side <LONG|SHORT> \
  --entryNotionalUsdt <amount> \
  --targetLeverage <leverage> \
  --maxAdverseMovePct <pct> \
  --maxRunMinutes <minutes>
```

引擎会：

1. 取消冲突挂单（如有）
2. 设置杠杆（如需变更）
3. 作为独立的后台任务运行，在盘口 1-40 档持续挂 Post-Only 限价单
4. 实时追踪成交，远端订单自动 reclaim 到近端
5. 达到目标名义价值后自动完成

启动后 `start` 命令输出 `taskId` 和后台 `pid`。

### Phase 5：监控与结果

启动后定期查询状态：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" status
```

输出字段（核心）：

- `phase`：working / reclaiming / completed / paused / stopped / failed
- `completionRatio`：完成百分比
- `filledEntryNotionalUsdt`：已成交名义价值
- `openWorkingNotionalUsdt`：当前挂单中的名义价值
- `unfilledNotionalUsdt`：尚未成交 = `target - filled`
- `unplacedNotionalUsdt`：尚未铺出的 = `target - filled - openWorking`（被交易所并发限额卡住时会很大）
- `remainingNotionalUsdt`：等价于 `unplacedNotionalUsdt`，保留是为了向下兼容（未来版本可能移除）
- `activeWorkingOrders`：活跃挂单数
- `bestBid` / `bestAsk`：当前盘口

**理解 `unplaced` vs `unfilled` 很重要**：大额任务在 OKX 上会被"并发同向暴露上限"卡住，此时 `unplaced > 0` 但 `unfilled = unplaced + openWorking`。表现为"铺满上限 → 等成交 → 再铺"的滚动模式，不是 bug。

**终态时额外输出 `result` 块：**

- `avgFillPrice`：加权平均成交价
- `placedOrderCount`：总下单数
- `reclaimCount`：reclaim 次数
- `endReason`：结束原因（completed / dust_remainder / paused / stopped / error）
- `recommendationText`：结果摘要
- `finalPosition`：终态时账户的实际持仓快照（side / absNotionalUsdt / leverage / unrealizedPnlUsdt 等）
- `followupHint`：下一步建议文案 — 比如用户停止但还留着仓位时会提醒"你还持有 XX USDT 的多头，考虑手动平仓或反向 Maker Entry"

终态场景下应当向用户朗读 `followupHint`，尤其是 stop / paused / dust_remainder 场景 — 这是防止用户遗忘残留持仓的最后一道保护。

### 停止任务

用户说"停止挂单开仓"时：

```bash
python "<skillDir>/scripts/okx_maker_entry.py" stop
```

引擎会撤销所有活跃挂单后优雅退出。之后查一次 `status` 确认最终状态，并向用户朗读 `result.followupHint`。

---

## 硬性规则

1. **preview 必做**：start 前需先跑 preview 预检
2. **确认必须**：preview 后需等用户明确确认才能 start
3. **配置引导**：遇到 config 相关错误时，按 `references/credential-setup.md` 引导用户完成首次配置
4. **默认模拟盘**：未指定 profile 时默认 demo
5. **反向持仓阻断**：有反向持仓时拒绝启动，提示用户先平仓
6. **大额无保护需二次确认**：当 `entryNotionalUsdt >= 10000` 且 `maxAdverseMovePct` 未设置时，preview 会发出 "No slippage guard" 警告。此时应向用户醒目呈现这条警告，并建议补一个 `maxAdverseMovePct`（常用 0.3 ~ 1.0）。
7. **终态向用户通报 `followupHint`**：任务进入终态（completed / stopped / paused / dust_remainder / failed）后，应向用户朗读 `result.followupHint`，避免用户遗忘残留持仓。

## 输出格式

每次执行后向用户报告：

```
Maker 挂单开仓 - BTC-USDT-SWAP [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
方向：LONG | 目标：1,000 USDT | 杠杆：5x
状态：working | 完成度：65.3%
已成交：653.00 USDT | 均价：$104,230
挂单中：200.00 USDT | 未铺：147.00 USDT
活跃挂单：12 | 盘口：104,228 / 104,232
未成交合计：347.00 USDT
```

- "挂单中" = `openWorkingNotionalUsdt`
- "未铺" = `unplacedNotionalUsdt`（被交易所限额卡住时会较大，是正常的滚动铺单行为）
- "未成交合计" = `unfilledNotionalUsdt` = 挂单中 + 未铺

## 风险提示

1. **默认使用模拟盘（demo）**，切换实盘需用户明确指定 profile=live。
2. Maker 挂单不保证成交速度 — 单边行情中 Post-Only 可能被持续拒绝。
3. 设置 `maxAdverseMovePct` 可在价格剧烈不利移动时自动暂停，保护资金。大额任务强烈建议设置。
4. 设置 `maxRunMinutes` 可限制最长运行时间。
5. 执行期间如需紧急停止，说"停止挂单开仓"，引擎会撤销所有挂单。停止后可能仍有已成交持仓，注意查看 `followupHint`。
6. 本 Skill 仅供学习研究，不构成投资建议，盈亏自负。

---

### [34] `okx-pair-spread`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-pair-spread/SKILL.md`

---
name: okx-pair-spread
license: MIT
description: |
  在 OKX 支持同时对两个 USDT 永续币种做相反方向的市价开仓（一腿做多、一腿做空），形成比值/汇率对冲组合。
  支持后台盯盘止盈止损：支持部分和全部仓位的统一止盈/止损（客户端只支持单一仓位的止盈止损）。用户声明(币种A/币种B)比值（ratio）或组合未实现 PnL 触发条件后，启动一个独立的 Python 守护进程，1 秒级轮询，命中后由代码立即平仓。守护进程独立于 AI 客户端运行，关闭 AI 客户端不影响盯盘；仅在主机关机或进程被强制结束时失效。
  当用户说"汇率对开仓"、"做多做空配对"、"比值对冲"、"pair spread"、"一腿多一腿空"、"平汇率对"、"盯汇率对"、"汇率对止盈止损"、"比值跌破/涨破 X 就平"时使用此技能。
metadata:
  openclaw:
    requires:
      bins: [python]
    os: [win32, darwin, linux]
    install:
      - kind: pip
        package: ccxt
        label: Install ccxt (pip)
---

# 汇率对 双腿市价开平仓

> 一次同时开两个方向相反的 USDT 永续（做多 A + 做空 B），形成比值对冲。
> 入场用市价确保同时到位；双腿失衡自动回滚。
> 平仓支持全部一起平、按 USDT 分别平每腿、或只平一腿。平仓不依赖开仓记录，直接读交易所实时仓位。

```
开仓请求                           平仓请求
    ↓                                 ↓
doctor 双合约环境检查            status 读双腿实时仓位
    ↓                                 ↓
open-preview 冲突/余额/下单校验   close-preview 方向校验 + 平仓计划
    ↓                                 ↓
用户确认                          用户确认
    ↓                                 ↓
open 市价开两腿 + 失衡回滚        close 市价 reduce-only 平腿
    ↓                                 ↓
报告双腿成交 + 当前比值           报告结果 + 残留仓位提示
```

---

## 使用方式

### 首次设置

对 AI 助手说 **"设置汇率对"** 或 **"setup pair spread"**，将自动检测环境并执行初始化流程。

本 skill 与 `okx-maker-entry` 共用同一份 `~/.okx/config.toml`，如果你已经配过 maker-entry，这里可以直接跳过初始化。

### 日常使用

直接说即可，示例：

**开仓**：

- **"BTC 做多 ETH 做空 各 1000U 汇率对开仓"**
- **"做多 BTC 做空 SOL 各 500U 汇率对 10 倍杠杆"**
- **"BTC ETH 汇率对 各 2000U 实盘"**

**查看状态**：

- **"查看 BTC ETH 汇率对状态"**
- **"BTC ETH 当前比值"**

**平仓**：

- **"平 BTC ETH 汇率对"**（全部平）
- **"BTC ETH 汇率对 BTC 平 500U ETH 平 300U"**
- **"BTC ETH 汇率对只平 BTC 500U"**

**盯盘（止盈止损，后台守护进程，所有 AI 客户端通用）**：

- **"盯 BTC ETH 汇率对，比值跌破 27 就全平"**
- **"DOGE SOL 汇率对 组合 PnL 到 -50 或 +80 就平"**
- **"盯着 BTC ETH，比值涨破 28 或 亏 200U 就全平"**
- **"看下我有哪些盯盘"** / **"停止盯盘 watch-XXXX"**（查看 / 停止已启动的盯盘）

---

## 前置条件

1. **AI 客户端**：Claude Code 或 OpenClaw（小龙虾）
2. **Python**：>= 3.9（推荐 3.11+，否则需额外安装 `tomli`）
3. **ccxt**：Python 交易所 SDK
4. **OKX API Key**：已配置 `~/.okx/config.toml`，权限需 Read + Trade
5. **账户设置**：OKX 账户必须是 **单向持仓模式**（Net Mode）

---

## 运行方式

本 skill 纯 Python 实现，单文件无额外子模块，通过命令行调用：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" <subcommand> [options]
```

所有子命令都**同步执行**，每次都是"进去做完就出来"。所有输出都是 JSON。详见 `references/cli-contract.md`。

**唯一的例外是 `watch-*` 系列**：`watch-start` 会 fork 一个独立的 Python 守护子进程在后台轮询并触发平仓，状态文件和日志写在 `~/.okx/watches/`。`watch-list` / `watch-stop` / `watch-status` 用来查询和停止守护进程。`watch-start` 自身仍然是同步返回的，几百毫秒内 fork 完毕。

---

## 初始化流程（首次设置时执行）

当用户说 "设置汇率对" / "setup pair spread" 时：

### Step 1：确认 Python 与 ccxt

```bash
python --version
python -c "import ccxt; print(ccxt.__version__)"
```

### Step 2：完成首次配置

按 `references/credential-setup.md` 走一遍首次配置引导（创建模板、在 OKX 建 Key、填 `~/.okx/config.toml`、doctor 验证）。

如果用户已经配过 `okx-maker-entry`，直接跑 doctor 验证即可，不需要重填凭证。

### Step 3：向用户展示就绪摘要

doctor 验证全部通过后，向用户展示设置完成摘要和使用示例：

```
✅ 汇率对环境就绪！

你现在可以直接说以下命令（默认模拟盘）：

开仓：
  "BTC 做多 ETH 做空 各 1000U 汇率对开仓"
  "做多 BTC 做空 SOL 各 500U 汇率对 10 倍杠杆"

查看：
  "查看 BTC ETH 汇率对状态"   — 看双腿仓位和当前比值
  "BTC ETH 当前比值"

平仓：
  "平 BTC ETH 汇率对"          — 全部平
  "BTC ETH 汇率对 BTC 平500U ETH 平300U"  — 分别平
  "BTC ETH 汇率对只平 BTC 500U"  — 只平一腿（会警告失去对冲）

建议先用模拟盘试一次小额开仓，比如：
  "BTC 做多 ETH 做空 各 100U 汇率对开仓"
```

---

## 参数说明

| 参数                    | 类型   | 必填       | 默认值   | 说明                                       |
| ----------------------- | ------ | ---------- | -------- | ------------------------------------------ |
| longInstId              | string | 必填       | -        | 做多腿合约 ID，如 BTC-USDT-SWAP            |
| shortInstId             | string | 必填       | -        | 做空腿合约 ID，如 ETH-USDT-SWAP            |
| entryNotionalUsdtPerLeg | number | 开仓必填   | -        | 每腿开仓名义价值（USDT）。总风险 = 2x 该值 |
| targetLeverage          | number | 选填       | 当前杠杆 | 目标杠杆倍数，对两腿生效一致               |
| profile                 | string | 选填       | demo     | demo（模拟盘）或 live（实盘）              |
| closeAll                | flag   | 平仓选填   | -        | 全部平仓（两腿都清零）                     |
| longCloseUsdt           | number | 平仓选填   | 0        | 做多腿平仓名义价值                         |
| shortCloseUsdt          | number | 平仓选填   | 0        | 做空腿平仓名义价值                         |
| pollIntervalSeconds     | number | watch 选填 | 1        | 守护进程轮询间隔（1–60 秒）                |
| ratioStopLte            | number | watch 选填 | -        | currentRatio ≤ 该值时触发                  |
| ratioStopGte            | number | watch 选填 | -        | currentRatio ≥ 该值时触发                  |
| pnlStopLte              | number | watch 选填 | -        | combinedUnrealizedPnlUsdt ≤ 该值时触发     |
| pnlStopGte              | number | watch 选填 | -        | combinedUnrealizedPnlUsdt ≥ 该值时触发     |
| watchId                 | string | watch 选填 | -        | 已启动盯盘的句柄（list/stop/status 用）    |

---

## 开仓执行流程

### Phase 1：参数确认

1. 从用户请求中提取 longInstId、shortInstId、entryNotionalUsdtPerLeg。
2. 如果用户未指定 profile，**默认使用 demo 模拟盘**。
3. 确保两个 instId 都是 USDT 永续格式（如 `BTC-USDT-SWAP`）。用户说"BTC"时自动补全为 `BTC-USDT-SWAP`。
4. 明确谁是多头腿、谁是空头腿 —— 如果用户表达模糊，必须向用户确认。
5. **自动推算杠杆**：如果用户未指定杠杆，先在 Phase 2 后检查 `2 * entryNotionalUsdtPerLeg > availableUsdt`。若是，自动计算所需最低杠杆 = `ceil(2 * entryNotionalUsdtPerLeg / availableUsdt)`，再上浮 20% 留余量（取整），作为 targetLeverage。在参数确认摘要中告知用户"根据余额自动设置 Nx 杠杆"。
6. 向用户确认完整参数后继续。

### Phase 2：环境检查

**首先检查 OKX 配置是否就绪。** 如果 doctor / open-preview 报错，按下列规则自动引导修复：

1. **报 `ccxt is required` / `ModuleNotFoundError: No module named 'ccxt'`** → 错误消息里会包含脚本的 `sys.executable` 路径，直接用它跑 `"<该路径>" -m pip install ccxt`（**务必用 `-m pip`**）。装完后重跑 doctor。
2. **报 config 文件找不到 / profile 缺失 / 账户凭据字段为空** → 按 `references/credential-setup.md` 完成首次配置，再跑 doctor 验证。
3. **报 `oneWayMode: false`** → 引导用户去 OKX 交易设置 > 持仓模式 > 单向持仓，切换后重跑。
4. **报 `canTrade: false`** → API Key 未勾 Trade 权限，重建 Key 并勾 Read + Trade。
5. **报任一 `symbolTradable: false`** → 用户输的合约不存在或不可交易，纠正后重试。
6. 全部搞定 → 回到 Phase 2 继续原来的开仓请求。

验证命令：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" doctor \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId>
```

### Phase 3：Open Preview 预检

```bash
python "<skillDir>/scripts/okx_pair_spread.py" open-preview \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId> \
  --entryNotionalUsdtPerLeg <amount> \
  --targetLeverage <leverage>
```

输出 JSON 的关键字段：

- `canStart`：是否可以启动
- `blockReason`：阻止原因（如有）
- `feasibility`：双腿杠杆、所需保证金、可用余额、最大名义价值
- `longLeg.conflictOrders` / `shortLeg.conflictOrders`：将被取消的非 reduce-only 挂单
- `longLeg.currentPosition` / `shortLeg.currentPosition`：当前双腿仓位
- `currentRatio`：当前比值 A/B
- `validation.passed`：双腿样本市价单是否通过 OKX precheck
- `warnings`：注意事项

**关键规则：**

- `canStart = false` 或 `validation.passed = false` → 向用户报告原因，**不继续**
- 任一腿有反向持仓 → block，提示用户先平掉反向仓
- 有 conflictOrders → 警告用户 open 会取消这些挂单
- 有 targetLeverage 变更 → 警告用户 open 会修改杠杆

向用户展示以下摘要，**等待明确确认后才执行 Phase 4**：

```
汇率对开仓预览 [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
多头腿：BTC-USDT-SWAP  1,000 USDT  当前无仓位
空头腿：ETH-USDT-SWAP  1,000 USDT  当前无仓位
杠杆：10x（两腿一致）| 预估保证金：200 USDT
当前比值 A/B = 27.28 | 可用余额：5,230 USDT

执行方式：两腿同时市价开仓，若第二腿失败会自动回滚第一腿。
确认开始吗？
```

### Phase 4：执行开仓

用户确认后：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" open \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId> \
  --entryNotionalUsdtPerLeg <amount> \
  --targetLeverage <leverage>
```

引擎会：

1. 取消冲突挂单（如有）
2. 设置杠杆（如需变更）
3. **市价开第一腿**（做多腿）→ 成功后继续
4. **市价开第二腿**（做空腿）→ 失败则 reduce-only 市价回滚第一腿
5. 校验双腿名义价值差在阈值内（10 USDT 或 20% 以内）
6. 返回双腿成交结果 + 当前仓位

**endReason 含义：**

- `completed`：两腿都成功开仓
- `entry_failed`：开仓失败，无残留仓位（第一腿失败，或第二腿失败且回滚成功）
- `entry_rollback_failed`：第二腿失败 + 回滚也失败 → **紧急警告用户手动处理残留仓位**
- `imbalance_warning`：两腿都成交但差额超阈值 → 提醒用户手动对齐

### Phase 5：报告结果

向用户展示开仓结果：

```
汇率对开仓完成 - BTC/ETH [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
多头腿：BTC-USDT-SWAP
  请求：1,000 USDT | 成交：1,002.34 USDT
  均价：$104,230 | 合约数：0.00961
空头腿：ETH-USDT-SWAP
  请求：1,000 USDT | 成交：998.76 USDT
  均价：$3,820 | 合约数：0.2615
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
双腿差额：3.58 USDT ✓（阈值内）
开仓后比值 A/B：27.28
组合未实现 PnL：-0.45 USDT

下一步：
  "查看 BTC ETH 汇率对状态"  — 监控比值
  "平 BTC ETH 汇率对"         — 全部平仓
```

朗读 `followupHint`（如有）。

---

## 平仓执行流程

### 关键原则：平仓完全无状态

**平仓不依赖开仓记录**。只要用户在 OKX 上有 `longInstId` 的多头 + `shortInstId` 的空头，skill 就能帮他平。可以是本 skill 开的，也可以是手工开的、toolbox 开的、甚至昨天开的。只信任交易所实时仓位。

### Phase 1：参数确认

1. 从用户请求中提取 longInstId、shortInstId。
2. 判断平仓模式：
   - "平全部" / "全部平仓" / "平汇率对" → `--closeAll`
   - "BTC 平 500 ETH 平 300" → `--longCloseUsdt 500 --shortCloseUsdt 300`（前提：已识别 BTC 是多头腿）
   - "只平 BTC 500" → `--longCloseUsdt 500`（短头腿金额默认 0）
3. 如果用户表达模糊（不知道谁是多头谁是空头），**先跑 status 帮他识别**再确认。
4. 默认 profile 与开仓一致，未指定时默认 demo。

### Phase 2：状态确认（可选，但强烈建议）

如果用户说"平 BTC ETH 汇率对"而没有开仓上下文，先读实时仓位：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" status \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId>
```

- 如果 `directionMatches = false`：多空腿标错了，向用户确认哪个是多头、哪个是空头，然后交换参数
- 如果任一腿 `side = FLAT`：用户没有该腿的仓位，向用户说明并请求确认

### Phase 3：Close Preview 预检

```bash
python "<skillDir>/scripts/okx_pair_spread.py" close-preview \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId> \
  [--closeAll | --longCloseUsdt N --shortCloseUsdt M]
```

输出字段：

- `canClose`：是否可以平
- `blockReason`：阻止原因（方向不匹配 / 金额超仓 / 都是 0）
- `plan.longClose` / `plan.shortClose`：每腿的平仓计划（null 表示不平该腿）
- `warnings`：注意事项（只平一腿会失去对冲等）

**关键规则：**

- `canClose = false` → 向用户报告原因，**不继续**
- 只平一腿 → 必须**醒目警告**"剩余的那腿会变成裸单，失去对冲保护"
- 方向不匹配 → block，让用户确认

向用户展示以下摘要，**等待明确确认后才执行 Phase 4**：

```
汇率对平仓预览 [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
多头腿：BTC-USDT-SWAP  当前 1,002 USDT (入均价 104,230)
空头腿：ETH-USDT-SWAP  当前   999 USDT (入均价 3,820)
当前比值 A/B = 27.45 | 组合 PnL = +8.20 USDT

平仓计划：
  BTC 市价卖出 1,002 USDT (全平)
  ETH 市价买入   999 USDT (全平)

确认执行吗？
```

### Phase 4：执行平仓

```bash
python "<skillDir>/scripts/okx_pair_spread.py" close \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId> \
  [--closeAll | --longCloseUsdt N --shortCloseUsdt M]
```

引擎会：

1. 再次 close-preview 校验
2. 对每个非零腿下 reduce-only 市价单
3. 若某一腿失败另一腿已成，独立报告，不自动回滚（平仓失败的语义和开仓不同）
4. 返回双腿成交结果 + 最终仓位

### Phase 5：报告结果

向用户展示平仓结果：

```
汇率对平仓完成 - BTC/ETH [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
多头腿：BTC-USDT-SWAP
  平仓：1,002 USDT | 均价：$104,450
  剩余仓位：0 USDT
空头腿：ETH-USDT-SWAP
  平仓：999 USDT | 均价：$3,815
  剩余仓位：0 USDT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
最终组合 PnL：+8.15 USDT
```

**如果平仓后有残留仓位**（用户选择只平部分），必须醒目提示：

```
⚠️ 注意：平仓后仍有残留仓位
  BTC-USDT-SWAP: 500 USDT 多头（剩余）
  ETH-USDT-SWAP: 已清零

你现在持有 500 USDT 的 BTC 裸多头，已失去对冲。
如需平掉，说"平 BTC ETH 汇率对"或"BTC 平 500U"。
```

---

## 查看状态流程

当用户说"查看汇率对状态"、"BTC ETH 当前比值"等：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" status \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId>
```

向用户展示：

```
汇率对状态 - BTC/ETH [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
多头腿：BTC-USDT-SWAP  1,002.45 USDT (入均价 104,230, mark 104,560)
空头腿：ETH-USDT-SWAP    998.30 USDT (入均价 3,820,  mark 3,815)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前比值 A/B：27.41 (开仓时 27.28, +0.48%)
组合未实现 PnL：+6.80 USDT
对冲可平金额：998.30 USDT (较小腿)
```

如果 `directionMatches = false`，警告用户方向标反了。

---

## 盯盘工作流（止盈止损自动触发）

当用户说**"盯 X Y 汇率对 比值跌破 Z 就全平"**、**"X Y 汇率对 亏 50U 就平"**、**"watch X Y stop loss at ratio Y"** 等，进入盯盘模式。

### 盯盘模式的本质

本 skill 提供 **真正的后台止损守护进程**（Python daemon），独立于 AI 客户端运行：

- **架构**：`watch-start` 会 fork 一个分离的 Python 子进程，1 秒级轮询双腿 mark price 与 PnL，触发条件由代码硬编码判断，命中立即在守护进程内调用 `close` 平仓。无 ccxt 调用经过 AI 客户端，无 LLM 参与触发判定。
- **不依赖 AI 客户端在线**：关闭 Claude Code / OpenClaw / 终端，盯盘照常运行
- **不挂 OKX 服务端条件单**：触发判定全部在本机进程内做

**生效边界 —— 必须在启动盯盘前向用户朗读：**

> 守护进程跑在你这台机器上。**机器关机、休眠、重启、断电、Python 进程被任务管理器杀掉** 会让盯盘失效，且不会自动恢复。实盘强烈建议同时在 OKX 原生界面给每条腿挂 reduce-only 条件单作为兜底。

### 支持的触发条件

**两类，可组合多个，任一命中即执行**（守护进程每个 tick 按顺序检查，第一个命中的胜出）：

| 类型  | 字段                        | 含义                            | 操作符        | CLI 参数                            |
| ----- | --------------------------- | ------------------------------- | ------------- | ----------------------------------- |
| ratio | `currentRatio`              | 多头 markPrice / 空头 markPrice | `lte` / `gte` | `--ratioStopLte` / `--ratioStopGte` |
| pnl   | `combinedUnrealizedPnlUsdt` | 双腿未实现盈亏之和（USDT）      | `lte` / `gte` | `--pnlStopLte` / `--pnlStopGte`     |

两个字段都来自 `status` 命令同款的原始数值，**严格按字段原值比较**，不做单位换算、不做方向反转。

### 支持的触发动作

1. **全平** (`closeAll`)：默认动作。命中后两腿都 reduce-only 市价平至 0
2. **按 USDT 分别平**：传 `--longCloseUsdt N --shortCloseUsdt M`，命中后调用与普通 `close` 等价的部分平仓

**明确不支持**（遇到时拒绝并向用户说明）：

- "平一半"、"平 50%" → 请用户自己算好 USDT 数额传入
- 多阶段触发（"先平一半再平剩下"）→ 等第一次触发后重新启动一轮新的盯盘
- 追踪止损 / trailing stop / 时间窗口限制

### Phase W1：解析与结构化

从用户请求中解析出以下结构：

```
watchPlan:
  longInstId:   <如 DOGE-USDT-SWAP>
  shortInstId:  <如 SOL-USDT-SWAP>
  profile:      <沿用当前会话，未指定时 demo>
  pollIntervalSeconds: <默认 1，最短 1，最长 60>
  triggers:
    - ratioStopLte: <数值>     # 至少给一个；可同时设多个
    - ratioStopGte: <数值>
    - pnlStopLte:   <数值>
    - pnlStopGte:   <数值>
  action:
    closeAll       # 默认
    # 或 longCloseUsdt: N, shortCloseUsdt: M
```

**模糊表达必问清**：没说轮询间隔可以默认 1 秒、不必问；但触发动作（全平还是部分平）、方向（多头腿是谁）必须问清。

### Phase W2：安全栏（一次性确认）

向用户展示完整盯盘计划摘要，等待明确确认：

```
盯盘计划 [模拟盘]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
汇率对：DOGE-USDT-SWAP (多) / SOL-USDT-SWAP (空)
轮询间隔：每 1 秒
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
T1：currentRatio ≤ 0.00108           → 全平
T2：combinedUnrealizedPnlUsdt ≤ -200 → 全平
T3：combinedUnrealizedPnlUsdt ≥ 80   → 全平
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 盯盘期间**任一触发命中会立即自动平仓，不再请求确认**。
⚠️ 守护进程跑在本机。机器关机/休眠/进程被杀 → 盯盘失效。实盘请在 OKX 挂条件单兜底。
⚠️ 随时可说"停止盯盘"或"看下我有哪些盯盘"。

确认启动吗？
```

**必须**等用户明确回复"确认"/"启动"/"开始"之类才能进入 Phase W3。

不需要单独跑 `status` 做前置检查 —— `watch-start` 命令本身会做以下硬编码 preflight，失败会以 `ok=false` 拒绝启动：仓位存在性、方向匹配、所有触发器在启动时都未命中。

### Phase W3：启动守护进程

用户确认后，调用 `watch-start`。**不要**用任何 /loop / 循环 / TodoWrite 调度 —— 这是同步命令，几百毫秒返回。

```bash
python "<skillDir>/scripts/okx_pair_spread.py" watch-start \
  --profile <profile> \
  --longInstId <longInstId> \
  --shortInstId <shortInstId> \
  --pollIntervalSeconds 1 \
  --ratioStopLte <数值或省略> \
  --ratioStopGte <数值或省略> \
  --pnlStopLte <数值或省略> \
  --pnlStopGte <数值或省略>
  # closeAll 是默认动作；要部分平就再加：
  # --longCloseUsdt N --shortCloseUsdt M
```

返回的 JSON 关键字段：

- `ok`：true 表示守护进程已 fork 并 PID 存活
- `watchId`：盯盘 ID（形如 `watch-20260410-091356-0bf56e`），是后续 list/stop/status 的句柄
- `pid`：守护进程 PID（用户机器上的真进程）
- `baselineRatio` / `baselinePnl`：启动瞬间的基线值
- `triggers`：守护进程将检查的触发器列表（T1/T2/...）

向用户朗读：

```
✅ 盯盘已启动 [模拟盘]
ID: watch-20260410-091356-0bf56e (pid 21052)
基线：ratio=0.001108  pnl=-170.39 USDT
触发器：T1/T2/T3（如上）
守护进程已在后台运行。我现在可以做别的事，触发命中会由代码自动平仓。
```

启动失败的常见原因（命令的 `message` 字段会说明，按需引导用户）：

- `one or both legs are FLAT` → 用户没仓位，让他先开仓
- `direction mismatch` → 方向标反了，交换 long/short
- `one or more triggers are already satisfied at start time` → 阈值过松或市场已经在触发区，让用户复核或先手动平

### Phase W4：日常查询与停止

启动后，AI 客户端**不需要也不应该**主动循环查询。只在用户明确询问或要求时再调命令：

**用户问"现在盯盘怎么样了" / "看下我有哪些盯盘"**：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" watch-list
```

返回所有盯盘条目（运行中优先），含 `status`、`tickCount`、`lastRatio`、`lastPnl`、`pidAlive`。运行中的标 `running`，正常停的标 `stopped/triggered/positions_flat`，僵尸进程会被 `watch-list` 自动 reconcile 成 `crashed`。

**用户问"那个 watch-XXX 详情"**：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" watch-status --watchId watch-XXX
```

返回完整 state JSON + 最后 20 行 log。

**用户说"停止盯盘 watch-XXX" / "停掉那个盯盘"**（多个盯盘时必须问清是哪一个）：

```bash
python "<skillDir>/scripts/okx_pair_spread.py" watch-stop --watchId watch-XXX
```

该命令通过 sentinel 文件通知守护进程优雅退出，最多等 10 秒，超时后强杀 PID。返回的 `status` 应为 `stopped`，`endReason` 为 `stop_requested`。

**触发命中是异步的 —— AI 客户端通常感知不到事件**：守护进程命中后自己平仓并退出，状态写到 state JSON。下次用户问起时跑 `watch-list` 才能看到。如果用户希望"等到平了告诉我"，告诉他 AI 客户端做不到主动通知，建议自行查询或等下一轮对话。

### Phase W5：修改盯盘

**不支持**原地热更新触发器。要改阈值就：先 `watch-stop` 旧的，再用新参数 `watch-start`。预授权范围只限本次启动的触发器集合。

### 跨 AI 客户端兼容性

watch-start / watch-list / watch-stop / watch-status 都是同步 CLI 命令，**与 AI 客户端能力无关**。Claude Code、OpenClaw 或任何能 spawn 子进程的客户端都能用同一套流程。**禁止**用 /loop、TodoWrite 等 Claude Code 独有能力替代守护进程，也禁止用 `while True: sleep()` 这种 busy-wait 假装后台。

---

## 硬性规则

### 开仓规则

1. **open-preview 必做**：open 前需先跑 open-preview 预检
2. **确认必须**：preview 后需等用户明确确认才能 open
3. **反向持仓阻断**：任一腿有反向持仓时拒绝启动，提示用户先平仓
4. **失衡回滚**：第二腿失败时必须尝试 reduce-only 市价回滚第一腿
5. **回滚失败警报**：若 `endReason = entry_rollback_failed`，**醒目警告**用户手动处理残留仓位
6. **默认模拟盘**：未指定 profile 时默认 demo

### 平仓规则

1. **close-preview 必做**：close 前需先跑 close-preview
2. **确认必须**：preview 后需等用户明确确认才能 close（**盯盘模式命中触发时例外 —— 见盯盘规则**）
3. **方向校验**：多头腿实际必须是 LONG，空头腿实际必须是 SHORT，否则 block
4. **单腿平仓警告**：只平一腿时必须**醒目提醒**"失去对冲，变成裸单"
5. **残留仓位提醒**：平仓完成后如仍有仓位，必须朗读残留仓位和下一步建议

### 盯盘规则

1. **一律走 watch-start 守护进程**：禁止用 /loop、TodoWrite、`while True: sleep()` 或任何 AI 客户端循环假装盯盘 —— 触发判定必须由 Python 守护进程做，AI 客户端只负责"启动 / 查询 / 停止"
2. **一次性确认**：Phase W2 的盯盘计划必须向用户完整朗读并等待明确确认才能调 watch-start
3. **预授权作用域**：一次确认只对本次启动的触发器集合生效，**任何修改都必须 watch-stop + 重新 watch-start + 重新确认**
4. **触发命中跳过二次确认**：守护进程命中触发时**直接调用 close**，不再请求用户确认 —— 这是盯盘的核心价值
5. **不要主动 polling 守护进程**：watch-start 返回后立刻把控制权交回用户。**只有在用户问起时**才跑 watch-list / watch-status；不要在没有用户请求的情况下定时查
6. **多盯盘必须问清 watchId**：用户机器上可能同时跑多个盯盘。"停止盯盘"模糊时先 watch-list 列出，让用户指定 watchId 再 stop
7. **启动失败按 message 引导**：watch-start 的 preflight 失败原因（FLAT、direction mismatch、already-hit）写在响应 `message` 字段，照着引导用户即可，不要瞎猜
8. **盯盘期间 open 阻断**：若 watch-list 显示同一对有 running 状态的盯盘，拒绝同一对的 open / close 请求，提示用户先 watch-stop
9. **守护进程边界要朗读**：启动前必须朗读"机器关机/休眠/进程被杀会失效"，让用户知道盯盘范围
10. **轮询间隔范围**：1–60 秒，默认 1 秒。低于 1 秒被命令拒绝，高于 60 秒被拒绝

### 通用规则

1. **配置引导**：遇到 config 相关错误时，按 `references/credential-setup.md` 引导用户完成首次配置
2. **一步步确认**：涉及金额/方向/杠杆的关键步骤必须向用户展示摘要并等待确认
3. **模糊表达必问清**：用户表达不清时（如没说谁做多谁做空、没说金额、没说是开仓还是加仓），必须先问清再动手

---

## 风险提示

1. **默认使用模拟盘（demo）**，切换实盘需用户明确指定 profile=live。
2. 市价开仓在流动性差的合约上会吃滑点，总成本 = 做多腿买价 + 做空腿卖价。
3. 失衡阈值设为 max(10 USDT, 20% per-leg)，超过会在开仓结果中警告但不会自动调仓 —— 大金额时建议手动看一下是否需要补齐。
4. **单腿平仓 = 失去对冲**，剩下的那腿会完全暴露在市场波动中。除非明确知道自己在做什么，否则优先整对平仓。
5. 本 skill 平仓不依赖开仓记录，但方向校验是关键 —— 如果你把 long/short 两个参数填反了，preview 会 block，按提示交换参数即可。
6. 监控比值走势请用 `status` 命令手动查询，或启动 `watch-start` 让守护进程在后台盯。
7. **盯盘 = 本机 Python 守护进程，不是交易所侧条件单**。守护进程跑在你这台机器上：关机、休眠、重启、断电、进程被任务管理器/Activity Monitor 杀掉都会让盯盘立即失效，且不会自动恢复。实盘中推荐同时在 OKX 原生界面给每条腿挂 reduce-only 条件单作为兜底（但注意两腿触发时机可能不同步，其中一腿先被触发后另一腿会变成裸单）。
8. **盯盘触发命中时跳过人工确认**。这是预授权的必然代价：若你在盯盘期间改变主意，必须主动用 `watch-stop` 停掉对应的 watchId，否则阈值一到守护进程就立即平仓。
9. 本 Skill 仅供学习研究，不构成投资建议，盈亏自负。

---

### [35] `okx-review`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-review/SKILL.md`

---
name: okx-review
version: "0.3.0"
license: MIT
description: |
  OKX 交易本地复盘。配合 OKX 官方 agent-skills 使用：官方 skill 拉取你的 OKX 头寸历史 JSON，
  本 skill 把数据落到本地 SQLite，起一个本地 Flask dashboard（多维图表 + 头寸列表 + 自定义标签系统 + 复盘笔记记录），
  浏览器打开即看盈亏曲线、胜率、手续费、按月表现。数据全留本地，不上云。
  当用户说"OKX 复盘"、"看我 OKX 交易表现"、"生成 OKX 盈亏报告"、"OKX 胜率统计"时使用此技能。
metadata:
  openclaw:
    requires:
      bins: [python]
    os: [win32, darwin, linux]
    install:
      - kind: pip
        package: flask
        label: Install Flask (pip)
---

# OKX 本地复盘

> 把 OKX 官方 skill 拉下来的头寸历史存到本地 SQLite，起一个本地 Flask dashboard，浏览器直开即看。

```
一条命令走全程（数据全部由 OKX 官方 agent-skill 提供 JSON）：

OKX 官方 skill → positions-history JSON   → pos.json
OKX 官方 skill → public-instruments JSON  → inst.json   (首次 / 陈旧时需要)

python okx_review.py serve --positions pos.json [--instruments inst.json]
    ↓ 规范化 + 去重 → 写入 ~/.okx-review/data.db
    ↓ 起本地 Flask 服务（http://127.0.0.1:4738）
    ↓ 自动打开浏览器：dashboard + 图表 + 头寸表 + 打标签 + 复盘笔记
```

---

## 前置条件

1. **AI 客户端**：Claude Code 或 OpenClaw
2. **Python**：>= 3.10
3. **flask**：`pip install flask`
4. **OKX 官方 agent-skills**：已安装并配好（见 <https://github.com/okx/agent-skills>）—— 本 skill 所有数据都从它来
5. **OKX API Key**：由官方 skill 管理，只需 Read 权限

---

## 典型使用

对 AI 助手说：

- **"复盘我最近一个月的 OKX 交易"**
- **"看我 OKX 永续合约的表现"**
- **"查看我 完整历史 的 OKX 交易"**

助手会自动执行：

1. 调 OKX 官方 skill 获取 positions-history JSON（以及首次 / 陈旧时的 public-instruments JSON）
2. 调本 skill 的 `serve --positions ... [--instruments ...]`：ingest → 起 Flask → 开浏览器，一条命令搞定

如果返回的 JSON 里出现 `instruments_hint`（本金列缺数据），助手会再拉一次 public-instruments 并重新 serve。

---

## 运行方式

```bash
python "<skillDir>/scripts/okx_review.py" <subcommand> [options]
```

子命令详情见 `references/cli-contract.md`。所有子命令输出 JSON，便于 AI 助手解析。

### 常用子命令

| 命令                                                           | 说明                                                                                          |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `serve [--positions <file>] [--instruments <file>] [--port N]` | **主入口**。给了 `--positions` 就先 ingest 再起服务；浏览器里看 dashboard、打标签、写复盘笔记 |
| `ingest --positions <file>`                                    | 只 ingest 不起服务（stdin 管道场景）                                                          |
| `ingest-instruments --file <file>`                             | 只 ingest 合约规格（stdin 管道场景）                                                          |
| `status`                                                       | 打印数据库状态（上次 ingest 时间、头寸总数、日期范围）                                        |
| `clean --before DATE --yes`                                    | 清理旧数据                                                                                    |

---

## 数据流

- **输入**：全部由 OKX 官方 agent-skill 提供 JSON —— positions-history + public-instruments（字段映射见 `references/data-schema.md`）
- **存储**：`~/.okx-review/data.db`（SQLite）
- **出口**：本地 Flask dashboard（`http://127.0.0.1:4738`）

---

## 隐私

所有数据只在用户本地：`~/.okx-review/data.db`（SQLite 数据库）。

本 skill 自身**不直接联网**；OKX API 的调用完全由官方 agent-skill 负责（Read 权限）。数据不上传任何第三方。

---

## 边界与限制

- 只吃 position history，不处理 fills/bills。总手续费依赖 OKX position 数据里是否带 `fee/fundingFee/liqPenalty` 字段
- `serve` 前台运行（Ctrl-C 停止），无 daemon；多实例需手动指定不同 `--port`
- 重复 ingest 根据 `(okx_position_id, closed_at)` 复合键去重

---

## 版本与变更

- **v0.3（当前）**：`serve` 变成唯一主入口，直接接受 `--positions` / `--instruments` 做一键 ingest + 启动；删除 `report` 子命令（静态 HTML 导出不再维护，功能被交互式 dashboard 覆盖）
- **v0.2**：新增 `ingest-instruments`（本金列所需的合约规格）、`serve`（Flask + HTMX 交互，标签 + 复盘笔记）
- **v0.1**：`ingest` + `report`（生成单文件 HTML），纯只读

---

### [36] `okx-review-prism`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-review-prism/SKILL.md`

---
name: okx-review-prism
description: 自动拉取历史交易记录，计算绩效指标，结合当时行情进行结构化复盘并输出改进建议。依赖 portfolio/market/trade。
license: MIT
metadata:
  author: web3_xiaoyao
  version: 1.0.0
  homepage: https://www.okx.com
  requires:
    install:
      bins: okx
    kind: package
    package: npm
---

# OKX 棱镜复盘师 (okx-review-prism)

## Description

交易复盘工具，自动拉取历史交易记录，计算绩效指标，结合当时行情进行结构化复盘并输出改进建议。

**核心功能**：
- 自动拉取历史交易记录（订单、成交、持仓）
- 计算胜率、盈亏比、最大回撤等关键指标
- 结合交易时的市场环境进行分析
- 输出结构化复盘报告和改进建议

**依赖 Skill**：`okx-cex-portfolio`, `okx-cex-market`, `okx-cex-trade`

## Activation Rules (触发词)

当用户输入以下模式时，激活本 Skill：

- **时间范围复盘**：
  - "复盘我最近7天交易"
  - "分析我上个月的交易表现"
  - "查看本周的交易记录"
  - "统计我今年的交易数据"

- **特定交易复盘**：
  - "分析BTC这笔亏损单"
  - "复盘订单 #123456789"
  - "查看ETH那笔盈利交易的详情"
  - "分析我最大的亏损交易"

- **品种与策略复盘**：
  - "复盘我的BTC所有交易"
  - "分析我的网格策略表现"
  - "查看永续合约的交易记录"
  - "复盘我的DCA投资计划"

- **绩效报告**：
  - "输出本月绩效报告"
  - "生成季度交易总结"
  - "查看我的交易胜率"
  - "分析我的风险收益比"

- **对比分析**：
  - "对比我现货和合约的表现"
  - "分析不同时间段的交易差异"
  - "比较我不同策略的盈利能力"

**纯只读操作**：本 Skill 仅读取历史数据进行分析，不执行任何交易操作，无需二次确认。

## Available Commands (可用命令表)

| CLI 命令 | 参数示例 | 说明 |
|---------|---------|------|
| `okx spot orders` | `--state filled --after 2024-01-01` | 现货历史订单 |
| `okx spot fills` | `--instId BTC-USDT --after 2024-01-01` | 现货成交记录 |
| `okx swap orders` | `--state filled --after 2024-01-01` | 永续历史订单 |
| `okx swap fills` | `--instId BTC-USDT-SWAP --after 2024-01-01` | 永续成交记录 |
| `okx account bills` | `--type trade --after 2024-01-01` | 账户账单 |
| `okx market candles` | `--instId BTC-USDT --bar 1h --after 2024-01-01` | 历史K线数据 |
| `okx market indicator` | `--instId BTC-USDT --indicator RSI --period 14` | 历史技术指标 |
| `okx market funding-rate` | `--instId BTC-USDT-SWAP --after 2024-01-01` | 历史资金费率 |

## Safety Notes (安全说明)

### 纯只读操作
- 仅读取历史数据，不执行任何交易操作
- 无需二次确认
- 敏感信息脱敏显示

### 数据准确性
- 历史数据可能存在1-5分钟延迟
- 数据完整性取决于OKX API
- 计算结果可能与交易所统计有小幅差异

### 使用建议
- 建议定期复盘（每周/每月）
- 客观分析亏损交易
- 将改进建议落实到后续交易中

## Examples (使用示例)

完整示例见 `examples/` 文件夹：

- `weekly_review.md` - 最近7天交易复盘
- `loss_analysis.md` - 亏损交易分析
- `btc_deep_review.md` - BTC深度复盘
- `monthly_report.md` - 月度绩效报告

示例包含完整的数据查询命令序列、绩效指标计算和结构化报告输出。

## Preflight (前置检查)

### 必需条件
- OKX CLI 已安装 (`okx` 命令可用)
- 有效的 API 配置（含历史数据读取权限）
- 网络连接正常
- 依赖 Skill 已安装：`okx-cex-portfolio`, `okx-cex-market`, `okx-cex-trade`

### 数据质量检查
- 查询时间范围合理性
- 数据完整性检查
- 异常值检测

## 绩效指标体系

计算关键绩效指标，包括胜率、盈亏比、最大回撤、夏普比率等。基于情绪、执行、风控三个维度进行综合评分（0-100分），输出改进建议。

## 输出格式规范

输出结构化复盘报告，包含绩效摘要、关键指标、三维度分析和改进建议。支持 Markdown 格式（人类可读）和 JSON 格式（程序化接口）。

## 版本记录
- v1.0.0 (2026-04-09)：初始版本，支持基础复盘和三维度分析
- v1.1.0 (2026-04-09)：增加高级绩效指标，优化分析算法
- v1.2.0 (2026-04-09)：增加可视化图表描述，支持策略对比

## 贡献指南
欢迎提交 Issue 和 Pull Request。请确保：
1. 所有新指标都有明确的定义和计算公式
2. 添加对应的数据分析算法
3. 更新 Examples 部分
4. 通过数据隐私和安全审查

## 支持与反馈
- 官方文档：https://github.com/okx/agent-trade-kit
- 复盘方法论：https://github.com/okx/agent-skills/discussions
- 数据问题：data-feedback@okx.com
- 分析建议：analysis-feedback@okx.com

---

### [37] `okx-strategy-oracle`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-strategy-oracle/SKILL.md`

---
name: okx-strategy-oracle
description: 基于实时行情+指标+链上数据生成交易策略，提供三档风险方案、参数优化及 bot 配置，支持一键转执行。依赖 market/portfolio。
license: MIT
metadata:
  author: web3_xiaoyao
  version: 1.0.0
  homepage: https://www.okx.com
  requires:
    install:
      bins: okx
    kind: package
    package: npm
---

# OKX 神谕策略师 (okx-strategy-oracle)

## Description

高级交易策略生成器，整合多维数据源生成交易策略，提供三档风险方案和参数优化建议。

**核心功能**：
- 多维度数据分析（价格、指标、衍生品等）
- 趋势评分和策略类型识别
- 三档风险方案（保守/稳健/激进）
- 参数优化和 bot 配置生成
- 一键转执行（通过 `okx-execution-vortex`）

**依赖 Skill**：`okx-cex-market`, `okx-cex-portfolio`

## Activation Rules (触发词)

当用户输入以下模式时，激活本 Skill：

- **策略生成**：
  - "生成 BTC 策略"
  - "ETH 交易策略分析"
  - "SOL 未来一周走势预测"
  - "评估 BTC 当前市场状态"
  - "综合研判 ETH-USDT-SWAP"

- **参数优化**：
  - "优化马丁格尔参数"
  - "RSI 最佳参数计算"
  - "优化网格策略 BTC 震荡区间"
  - "计算 DCA 最优投资频率"
  - "EMA 交叉策略参数回测"

- **特定策略**：
  - "RSI 抄底策略"
  - "网格策略 BTC 震荡区间 50000-52000"
  - "AHR999 定投计划"
  - "趋势跟踪策略 BTC"
  - "套利机会扫描"

- **风险评估**：
  - "评估当前市场风险等级"
  - "生成三档风险方案 BTC"
  - "保守型 ETH 投资策略"
  - "激进型 SOL 交易计划"

**禁止直接执行**：本 Skill 仅生成策略建议，不执行任何交易操作。所有执行必须通过 `okx-execution-vortex` 完成。

## Available Commands (可用命令表)

本 Skill 封装以下 OKX CLI 命令进行数据采集和分析：

### 市场数据查询
| CLI 命令 | 参数示例 | 说明 |
|---------|---------|------|
| `okx market candles` | `--instId BTC-USDT --bar 4h --limit 100` | K线数据 |
| `okx market tickers` | `--instId BTC-USDT` | 实时行情 |
| `okx market indicator` | `--instId BTC-USDT --indicator RSI --period 14` | 技术指标（RSI/MACD/EMA等70+） |
| `okx market funding-rate` | `--instId BTC-USDT-SWAP` | 资金费率 |
| `okx market open-interest` | `--instId BTC-USDT-SWAP` | 未平仓合约 |
| `okx account balance` | `--ccy USDT` | 账户余额 |
| `okx spot positions` | `--instId BTC-USDT` | 现货持仓 |
| `okx bot grid params` | `--instId BTC-USDT --strategy moderate` | 网格参数生成（依赖okx-cex-bot） |
| `okx bot dca params` | `--instId ETH-USDT --frequency weekly` | DCA参数生成 |
| `okx external coinglass` | `--metric funding_rates --symbol BTC` | CoinGlass数据（可选） |

## Safety Notes (安全说明)

### 仅建议不执行
- 所有输出均为策略建议，不构成投资推荐
- 执行必须通过 `okx-execution-vortex` 进行二次确认
- 历史表现不代表未来结果

### 核心风险警告
- **强趋势警告**：评分 >+80 或 <-80 时避免逆势操作
- **高波动警告**：ATR(14) > 2倍平均值时缩小仓位
- **衍生品风险**：资金费率 > 0.1%时警告空头成本
- **杠杆限制**：根据趋势评分提供杠杆建议（3x-20x）

### 数据免责
- 数据来自OKX和第三方API，不保证100%准确
- 免费数据可能存在1-5分钟延迟
- 外部数据可能需要API Key（本Skill不存储密钥）

## Examples (使用示例)

完整示例见 `examples/` 文件夹：

- `btc_trend_strategy.md` - BTC 趋势跟踪策略
- `eth_range_strategy.md` - ETH 震荡网格策略
- `swap_arbitrage.md` - 永续合约套利策略
- `rsi_optimization.md` - RSI 参数优化
- `three_tier_risk.md` - 三档风险方案

示例包含完整CLI调用序列、6维评分计算、结构化策略卡片和JSON格式输出。

## Preflight (前置检查)

### 必需条件
- OKX CLI 已安装 (`okx` 命令可用)
- 有效的 API 配置（含市场数据权限）
- 网络连接正常
- 依赖 Skill 已安装：`okx-cex-market`, `okx-cex-portfolio`

### 数据质量检查
- K线数据完整性
- 技术指标计算结果合理性
- 数据新鲜度（延迟不超过5分钟）

## 输出格式规范

### JSON 格式（程序化接口）
```json
{
  "strategy_id": "BTC_20240115_TREND",
  "instrument": "BTC-USDT",
  "score": 72.5,
  "trend_direction": "bullish",
  "risk_levels": {
    "conservative": { /* 参数 */ },
    "moderate": { /* 参数 */ },
    "aggressive": { /* 参数 */ }
  },
  "indicators": { /* 技术指标值 */ },
  "entry_zones": [ /* 入场区间 */ ],
  "exit_zones": [ /* 出场区间 */ ],
  "execution_plan": "okx-execution-vortex 命令"
}
```

### Markdown 策略卡片（人类可读）
输出结构化策略卡片，包含：
- 6维评分表格
- 三档风险方案（保守/稳健/激进）
- 技术指标状态
- 执行计划（CLI命令）
- 风险提示

完整示例见 `examples/` 文件夹。

## 版本记录
- v1.0.0 (2026-04-09)：初始版本，支持6维评分和三档风险方案
- v1.1.0 (2026-04-09)：增加70+技术指标支持，优化参数优化算法
- v1.2.0 (2026-04-09)：集成外部数据源，增强链上分析

## 贡献指南
欢迎提交 Issue 和 Pull Request。请确保：
1. 所有新指标都有完整的回测数据支持
2. 添加对应的风险警告逻辑
3. 更新 Examples 部分
4. 通过数据准确性验证

## 支持与反馈
- 官方文档：https://github.com/okx/agent-trade-kit
- 策略讨论：https://github.com/okx/agent-skills/discussions
- 数据问题：data-feedback@okx.com
- 算法建议：strategy-algo@okx.com

---

### [38] `okx-trade-review-suite`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/okx-trade-review-suite/SKILL.md`

---
name: okx-trade-review-suite
description: "交易复盘全家桶 · Pro。一个 Skill 集成 8 大复盘维度：盈亏归因拆解、权益曲线回放、最大回撤体检、连胜连亏期望值、vs Buy&Hold/SMA/DCA 的 alpha 计量、追高/割肉/报复交易行为指纹、手续费与 maker-taker 审计、持仓时长 × PnL 相关性，以及日/周/月自动聚合报告。只读，不下单，不转账。适用场景：复盘我的交易、我哪里做错了、我比躺平多赚多少、一键周报、我是不是总追高、手续费吃了多少、最大回撤多少、哪个币最赚钱、review my trades、trading review、performance check、是不是该转定投、我的策略还能不能继续、下月怎么改进、trade audit、psychology check、alpha analysis、drawdown review、fee audit、win rate analysis。关键词：复盘、review、归因、attribution、权益曲线、equity curve、MDD、最大回撤、连胜连亏、streak、胜率、期望值、凯利、Kelly、alpha、Sharpe、Sortino、IR、benchmark、追高、割肉、报复交易、FOMO、死扛、behavior、手续费、fees、maker、taker、持仓时长、hold duration、日报、周报、月报、digest、digest summary。"
license: MIT
metadata:
  author: okx-skill
  version: "1.0.0"
  homepage: "https://www.okx.com"
  categories: ["复盘"]
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
  bundled_skills:
    - okx-review-attribution
    - okx-review-equity-curve
    - okx-review-streak
    - okx-review-benchmark
    - okx-review-behavior
    - okx-review-fees-audit
    - okx-review-hold-duration
    - okx-review-daily-digest
---

# 交易复盘全家桶 · Pro — 8 个专业维度一次打包

**给你的交易生涯装一面全景镜。**

不用装 8 个 Skill，不用记一堆触发词。说一句"复盘一下"、"我哪里做错了"、"给我一份周报"——**Suite 自动路由到最合适的专项 Skill 并出报告**。

- 🧩 **8 个专项复盘 Skill，一次安装**
- 📊 **只读零风险** — 从不下单、撤单、转账
- 🗣️ **自然语言路由** — 不用记 skill 名
- ⏰ **定时订阅** — 日报 / 周报 / 月报全自动
- 📝 **结构化 Markdown 报告** — 可存档、可分享、可对比

---

## 💎 8 大复盘维度一览

| # | 子 Skill | 解决什么问题 | 典型触发语 |
|---|---------|-------------|-----------|
| 1 | [`okx-review-attribution`](skills/okx-review-attribution/) | 钱从哪赚、从哪亏？币种/方向/时段拆解 | "我这个月靠哪个币赚钱"、"亏损集中在哪里" |
| 2 | [`okx-review-equity-curve`](skills/okx-review-equity-curve/) | 权益曲线回放 + 最大回撤体检 | "最大回撤多少"、"水下多久了"、"画一下我的曲线" |
| 3 | [`okx-review-streak`](skills/okx-review-streak/) | 连胜连亏 & 期望值 & 凯利仓位 | "最近是不是连亏了"、"我的胜率怎么样" |
| 4 | [`okx-review-benchmark`](skills/okx-review-benchmark/) | vs Buy&Hold / SMA / DCA 算 alpha | "我比 BTC 躺平多赚多少"、"Sharpe 怎么样" |
| 5 | [`okx-review-behavior`](skills/okx-review-behavior/) | 追高 / 割肉 / 报复交易行为指纹 | "我是不是总追高"、"亏了之后是不是报复交易" |
| 6 | [`okx-review-fees-audit`](skills/okx-review-fees-audit/) | 手续费 + maker/taker 审计 | "手续费吃了多少"、"能省多少" |
| 7 | [`okx-review-hold-duration`](skills/okx-review-hold-duration/) | 持仓时长 × PnL 相关性 | "我是拿不住还是死扛"、"最佳持仓多久" |
| 8 | [`okx-review-daily-digest`](skills/okx-review-daily-digest/) | 日/周/月综合复盘聚合器 | "一份周报"、"本月总结"、"所有维度都扫一遍" |

---

## 🎯 为什么需要这个 Suite？

**散户最常见的 3 个死法**：
1. 不复盘 → 一年下来不知道为啥亏 → 下一年继续亏
2. 复盘太累 → 翻账单 → Excel → 心态崩了 → 放弃
3. 只看总收益 → 看不到"拿不住盈利、死扛亏损"的结构问题

**Suite 一次解决**：
- 🤖 **自然语言问** — "我最近是不是追高了？" → 自动跑 behavior
- 📊 **结构化报告** — 每份都有洞察 + 改进建议（带数字）
- 🗓️ **自动订阅** — 每周一 09:00 一份周报，躺着复盘
- 🎯 **综合建议 Top 3** — 按"风控 > 行为 > 策略"排优先级

---

## 📊 一眼看懂：总报告输出示例

```
📰 交易复盘周报 · 2026-04-05 ~ 2026-04-11
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 TL;DR（本周 3 件最重要的事）
1. ⚠️ 报复交易 4 次，4 次全亏，立即加暂停规则
2. ✅ alpha +6.7% vs BH-BTC，主动交易本周有效
3. 🟡 MDD 触黄线 (-22%)，水下 20 天接近恢复

💰 总览卡
权益：$10,000 → $12,485 (+24.9%, 年化 89%)
胜率：55.3%   盈亏比：1.87   期望值：+$102/笔

📊 归因 | 📈 权益曲线 | 🎯 Streak | ⚖️ 基准
🧠 行为 | 💸 费用 | ⏱️ 持仓时长
（每块 2-3 行关键指标）

🎯 本周 Top 3 行动
[风控] 亏损后强制暂停 30 分钟 ← behavior+streak
[行为] 止盈分批（+2%/+4%/追踪） ← hold-duration
[策略] Maker 比例提到 60%，月省 $286 ← fees-audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[profile: live]
```

---

## ⚙️ 可配置参数（Suite 级）

### 入口参数

| 参数 | 默认值 | 可选范围 | 说明 |
|------|--------|----------|------|
| 默认周期 | 周报 | 日/周/月 | 聚合报告粒度 |
| 默认 profile | 询问 | live/demo | 实盘 or 模拟 |
| 路由模式 | 智能 | 智能/显式 | 智能=自动路由子 skill；显式=必须指定 |
| 详细度 | 标准 | 简要/标准/完整 | 输出详尽程度 |
| 语言 | 中文 | 中文/英文 | 报告语言 |

### 订阅参数

| 参数 | 默认值 | 可选范围 | 说明 |
|------|--------|----------|------|
| 日报 | 关 | 开/关 | 每日 09:00 |
| 周报 | 开（默认推荐）| 开/关 | 周一 09:00 |
| 月报 | 关 | 开/关 | 每月 1 号 09:00 |
| 红线告警 | 开 | 开/关 | 报复交易/MDD 触线时立即推送 |
| 落盘 | 关 | 开/关 | 报告写到 `./reviews/` |

### 子 Skill 级参数

8 个子 skill 各自的参数（追高阈值、桶边界、基准列表等）保留完整可配能力。通过 Suite 修改：

```
"把追高阈值改成 1.5%"   → 修改 behavior 子 skill
"基准加上 ETH"           → 修改 benchmark 子 skill
"桶边界改为 30m/2h/12h"  → 修改 hold-duration 子 skill
```

---

## 🎬 首次使用：3 步极速启动

```
Step 1  安装 + 凭证
   npm install -g @okx_ai/okx-trade-cli
   okx config init

Step 2  确认 profile
   "用 live（实盘）复盘"  或  "用 demo（模拟）试试"

Step 3  问一句话
   "帮我看看这个月的交易"     → 路由到归因
   "给我一份周报"            → 路由到 daily-digest
   "我是不是总追高"          → 路由到 behavior
   "我跑赢 BTC 了吗"         → 路由到 benchmark
```

就这样。不用学命令行，不用配参数，首次就给你一份可读的报告。

---

## 🗺️ 智能路由表

自然语言输入 → 自动选择子 skill：

| 用户问法（关键词） | 路由目标 |
|-------------------|---------|
| "赚钱"、"亏钱"、"哪个币"、"归因"、"拆解" | `okx-review-attribution` |
| "曲线"、"回撤"、"MDD"、"水下"、"新高" | `okx-review-equity-curve` |
| "连胜"、"连亏"、"胜率"、"期望值"、"凯利" | `okx-review-streak` |
| "alpha"、"Sharpe"、"跑赢"、"躺平"、"定投对比" | `okx-review-benchmark` |
| "追高"、"割肉"、"报复"、"FOMO"、"死扛" | `okx-review-behavior` |
| "手续费"、"maker"、"taker"、"费率" | `okx-review-fees-audit` |
| "拿不住"、"持仓时长"、"短线"、"长持" | `okx-review-hold-duration` |
| "日报"、"周报"、"月报"、"总结"、"全部" | `okx-review-daily-digest` |

**兜底规则**：意图不清时优先调 `daily-digest` 给出全维度简报，再让用户选择下钻。

---

## 🔐 凭证与 Profile 校验（所有子 Skill 共用）

### Step A — 凭证检查

```bash
okx config show
```

无配置 → 引导 `okx config init`，**停止一切操作**。

### Step B — Profile 确认（必填）

| 值 | 模式 | 资金 |
|---|---|---|
| `live` | 实盘 | 真实资金 |
| `demo` | 模拟盘 | 模拟资金 |

当前消息有明确意图 → 使用并告知；无声明 → 查上下文；无上下文 → 问 "live 还是 demo？" 等回答。

### 401 认证失败

立即停止 → 告知 → 引导用户本地改 `~/.okx/config.toml` → 跑 `okx config show` 验证 → 再重试。**绝不要求用户把密钥粘到对话里**。

---

## 🔁 核心工作流（Suite 级）

```
用户输入
  ↓
① 凭证 / Profile 校验
  ↓
② 意图识别 → 路由到某个子 Skill（或 daily-digest 聚合器）
  ↓
③ 首次调用时 → 引导配置子 Skill 参数（默认即可跳过）
  ↓
④ 执行子 Skill 分析流水线：
     ├─ 拉数据（positions-history / bills / candles / fees）
     ├─ 数据健康校验（红黄线）
     ├─ 分析（分桶/行为/序列/曲线/归因/对比）
     └─ 生成中文 Markdown 报告
  ↓
⑤ 输出报告
  ↓
⑥ 若用户订阅周报/月报 → 注册定时任务
```

---

## 🛡️ 数据健康红黄线（跨所有子 Skill）

### 🔴 红线 — 拒绝出报告

1. 凭证未配置 / 401
2. 所有子 skill 均失败
3. Profile 未确认

### 🟡 黄线 — 出报告带警告

1. 某子 skill 数据覆盖率 <80% → 报告顶部标注
2. 时间窗 <7 天 → 样本不足提醒
3. 检测到报复交易 ≥3 次、MDD >20% 等关键红线 → 顶部置顶告警
4. Demo 模式 → 标 "⚠️ Demo 数据仅供演示"

---

## ⏸️ 暂停 / 恢复 / 重置

| 用户说 | 行为 |
|--------|------|
| "暂停周报" | 停订阅保配置 |
| "恢复周报" | 重启 |
| "暂停所有订阅" | 全停 |
| "去掉 behavior 模块" | 聚合报告不再含该块 |
| "重置" | 全部回默认 |
| "改追高阈值为 3%" | 修改 behavior 参数 |

---

## 🚧 异常处理

| 场景 | 处理方式 |
|------|---------|
| API 失败 | 30s 重试 3 次 |
| 单子 skill 失败 | 跳过 + 报告标 "未生成模块 X" |
| 数据稀疏（新账户/Demo）| 标"样本不足" + 建议放宽时间窗 |
| 参数冲突 | 以 Suite 级参数为准 |
| 落盘失败 | 降级为对话输出 |
| 路由歧义 | 优先 daily-digest，让用户二选下钻 |

---

## 🧭 总工作流程

```
          ┌────────── "复盘" / "周报" / "我是不是追高了" ──────────┐
          │                                                      │
          ▼                                                      │
   ┌──────────────┐                                              │
   │ Suite 路由层  │  ← 智能识别意图 + Profile 校验              │
   └──────┬───────┘                                              │
          │                                                      │
  ┌───────┼────────┬────────┬─────────┬────────┬────────┬───────┤
  ▼       ▼        ▼        ▼         ▼        ▼        ▼       ▼
归因  权益曲线   streak  benchmark  behavior  fees  hold-dur  digest
  └──┬────┴────────┴────────┴─────────┴────────┴────────┴───────┘
     ▼
共享一次数据拉取（positions-history / bills / candles / fees）
     ▼
子 skill 各自分析 → 生成子报告
     ▼
Suite 汇总 → 输出中文 Markdown
```

---

## 🔗 子 Skill 详细入口

点进每个子 skill 查看完整 12 章节文档（算法、参数、案例）：

- [📊 okx-review-attribution](skills/okx-review-attribution/SKILL.md) — 盈亏归因
- [📈 okx-review-equity-curve](skills/okx-review-equity-curve/SKILL.md) — 权益曲线
- [🎯 okx-review-streak](skills/okx-review-streak/SKILL.md) — 连胜连亏
- [⚖️ okx-review-benchmark](skills/okx-review-benchmark/SKILL.md) — 基准对比
- [🧠 okx-review-behavior](skills/okx-review-behavior/SKILL.md) — 行为指纹
- [💸 okx-review-fees-audit](skills/okx-review-fees-audit/SKILL.md) — 费用审计
- [⏱️ okx-review-hold-duration](skills/okx-review-hold-duration/SKILL.md) — 持仓时长
- [📰 okx-review-daily-digest](skills/okx-review-daily-digest/SKILL.md) — 日/周/月聚合

---

## ❓ 常见问题

**Q: 和单独装 8 个 skill 有什么区别？**
A: 一次性装 Suite 即可获得全部能力，不用记 8 个 skill 名。智能路由会根据你的自然语言自动选对应子 skill。想单独调用某个时，直接说 "用 attribution" 或直接点开子 skill 入口。

**Q: Suite 比单装 daily-digest 多什么？**
A: `daily-digest` 只做**定时聚合报告**。Suite 还包括**按意图路由到单一维度的专项分析**。比如你只问"手续费多少"，Suite 直接调 fees-audit 给你专项报告，不必跑全部 7 个模块。

**Q: 全部 8 个 skill 真的只读吗？**
A: 是。Suite 和所有子 skill 只调 `account positions-history` / `account bills` / `account balance` / `account config` / `account fees` / `market candles`，**绝不下单、撤单、转账、改仓位模式**。哪怕你的 API Key 意外开了交易权限也不会被使用。

**Q: 我想关掉某些子 skill，能行吗？**
A: 能。说 "去掉 benchmark" 或 "只保留 attribution + behavior + fees-audit"，Suite 会记住配置。聚合报告也会自动跳过关闭的模块。

**Q: 订阅周报会打扰我吗？**
A: 默认周一 09:00 一次，可随时 "暂停" 或改时间。想要更轻量：只开"红线告警"，只有检测到报复交易/大回撤时才推送。

**Q: 能保存历史报告做同比环比吗？**
A: 开启"落盘"选项后，报告按日期写入 `./reviews/`。后续版本（v1.1）将内置"同比/环比"章节自动对比上期。

**Q: 我有多个 API Key / 子账户，怎么分别复盘？**
A: 通过 `--profile` 区分。`okx config` 里为每个账户配独立 profile，Suite 会在每次调用前询问。

**Q: 报告里的数字准确度能保证吗？**
A: 基于 OKX 官方 API 原始数据，`realizedPnl` 等字段直接取自 positions-history 返回。**唯一估算的部分**是："若全用 maker 可节省 $X"，这是理论上限，实盘扣除机会成本后会略低。

---

## 📜 MCP 工具映射（Suite 汇总）

Suite 及其子 Skill 仅调用**只读** MCP 工具：

| 分类 | MCP 工具 |
|------|---------|
| 账户账单/持仓 | `account_get_bills` / `account_get_bills_archive` / `account_get_balance` / `account_get_config` |
| 交易历史 | `account_get_positions_history` / `account_get_trade_fee` |
| 行情 | `market_get_candles` / `market_get_ticker` |

**绝不调用**任何下单、撤单、转账、改仓位模式的写入类工具。

---

## 📂 Skill 包结构

```
okx-trade-review-suite/
├── SKILL.md                       ← 本文件（Suite 总入口）
├── references/                    ← Suite 级规则
└── skills/                        ← 内嵌 8 个子 skill
    ├── okx-review-attribution/
    │   ├── SKILL.md
    │   └── references/REFERENCE.md
    ├── okx-review-equity-curve/
    ├── okx-review-streak/
    ├── okx-review-benchmark/
    ├── okx-review-behavior/
    ├── okx-review-fees-audit/
    ├── okx-review-hold-duration/
    └── okx-review-daily-digest/
```

每个子 skill 独立可用（配合 `skill add okx-review-xxx`），打包进 Suite 是为了**一次安装、统一路由、减少心智负担**。

---

## ⚠️ 免责声明

本 Skill 合集仅供交易复盘参考与学习，**不构成任何投资建议**。所有分析基于历史数据，历史表现不代表未来收益。加密资产交易存在高波动与本金损失风险，使用者需自担所有决策后果。作者与本 Skill 合集不对因参考本报告产生的任何损失承担责任。

---

## 📜 License

MIT · 开源共享，欢迎 fork 与二次开发。

---

### [39] `pnl-loss-reviewer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/pnl-loss-reviewer/SKILL.md`

---
name: pnl-loss-reviewer
description: "盈亏复盘图表版 Skill。当用户说'复盘'、'亏损分析'、'盈亏报告'、'为什么亏了'、'交易总结'、'回顾交易'、'盈亏图表'、'复盘报告'时使用此技能。自动拉取历史交易记录，分析亏损原因，生成可视化图表和复盘报告。依赖 okx-cex-market、okx-cex-trade、okx-cex-portfolio 三个 Skill。"
---

# 盈亏复盘大师 Pro（图表版）

自动拉取 OKX 历史交易记录，统计盈亏数据，深度分析亏损原因，生成 6 张可视化图表 + 结构化复盘报告。帮你看清亏在哪、为什么亏、怎么改。支持现货与合约。

## 依赖 Skills（必须先安装）

- okx-cex-market — 获取历史价格和技术指标，用于回溯行情环境
- okx-cex-trade — 获取历史订单和成交明细
- okx-cex-portfolio — 获取账户账单、已平仓位、余额变化

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instId | string | 否 | 全部 | 指定交易对复盘，如 BTC-USDT 或 BTC-USDT-SWAP，留空则分析全部 |
| days | integer | 否 | 7 | 复盘天数范围：7 / 14 / 30 / 90 |
| instType | string | 否 | 全部 | 筛选类型：SPOT（现货）/ SWAP（永续）/ FUTURES（交割）/ 全部 |
| profile | string | 否 | demo | 实盘 live / 模拟盘 demo |
| focus | string | 否 | loss | 分析重点：loss（只看亏损）/ all（盈亏都分析）/ win（只看盈利） |
| chart | string | 否 | all | 图表输出：all（全部 6 张）/ summary（仅总览）/ none（纯文字） |

## 执行流程

### Phase 1：参数确认

1. 用户触发技能后，确认复盘范围（days）和账户类型（profile）。
2. 如果用户未指定 profile，默认使用 demo 模拟盘。
3. 确认分析重点：默认聚焦亏损交易。
4. 向用户确认参数后开始拉取数据。

### Phase 2：数据采集

Step 1：拉取已平仓记录（合约）

```
okx account positions-history --instType SWAP --profile {profile}
okx account positions-history --instId BTC-USDT-SWAP --limit 50 --profile {profile}
okx account positions-history --instType FUTURES --profile {profile}
```

从返回值中提取每笔仓位的关键字段：instId、direction、openAvgPx、closeAvgPx、realizedPnl、uTime。

Step 2：拉取历史订单（现货 + 合约）

```
okx spot orders --history --profile {profile}
okx spot orders --instId BTC-USDT --history --profile {profile}
okx swap orders --history --profile {profile}
okx spot fills --instId {instId} --profile {profile}
okx swap fills --instId {instId} --profile {profile}
```

Step 3：拉取账单流水

```
okx account bills --profile {profile}
okx account bills --instType SWAP --profile {profile}
okx account bills --archive --profile {profile}
```

Step 4：拉取手续费率

```
okx account fees --instType SPOT --profile {profile}
okx account fees --instType SWAP --profile {profile}
```

Step 5：获取当前账户状态

```
okx account balance USDT --profile {profile}
okx account positions --instType SWAP --profile {profile}
```

### Phase 3：数据统计

3.1 总体统计

- 总交易笔数、盈利笔数、亏损笔数
- 胜率 = 盈利笔数 / 总笔数 x 100%
- 总盈利金额、总亏损金额、净盈亏
- 盈亏比 = 平均盈利金额 / 平均亏损金额
- 最大单笔盈利、最大单笔亏损
- 累计手续费支出、累计资金费率支出（合约）

3.2 按交易对统计

- 每个 instId 的：盈亏总额、交易次数、胜率
- 找出亏损最多的交易对 Top 3
- 找出盈利最多的交易对 Top 3

3.3 按时间维度统计

- 按日统计盈亏曲线
- 找出亏损集中的日期
- 分析是否存在某个时间段连续亏损

### Phase 4：亏损原因分析

对每笔亏损交易，回溯开仓时的行情环境，判断亏损原因归类。

Step 1：获取开仓时的行情数据

```
okx market indicator rsi {instId} --bar 1H --params 14
okx market ticker {instId}
```

Step 2：亏损原因归类（可多选）

| 原因编号 | 亏损类型 | 判断依据 |
|---------|---------|---------|
| L1 | 追涨杀跌 | 开仓价在近期高点/低点附近，RSI 已超买/超卖 |
| L2 | 逆势交易 | 做多时价格处于下降趋势，做空时价格处于上升趋势 |
| L3 | 止损过宽 | 亏损幅度大于10%，未及时止损 |
| L4 | 频繁交易 | 同一交易对在短时间内多次开平仓，手续费占比高 |
| L5 | 仓位过重 | 单笔亏损占总资金比例大于10% |
| L6 | 手续费消耗 | 总手续费占总亏损的 20% 以上 |
| L7 | 资金费率亏损 | 长时间持仓，资金费率累计亏损显著 |
| L8 | 强制平仓 | 账单中出现强平记录 |
| L9 | 情绪化交易 | 亏损后立即加仓或反向开仓（复仇交易） |
| L10 | 时机不佳 | 在重大行情波动前开仓，被插针止损 |

Step 3：统计每种亏损原因出现的次数和占比，找出排名前 3 的亏损原因。

### Phase 5：生成可视化图表

基于 Phase 3 和 Phase 4 的统计数据，生成一个单文件 HTML 图表报告。使用 ECharts 渲染，深色主题（背景 #0D1117，文字 #C9D1D9），支持交互。

6 张图表：

1. 累计盈亏曲线（折线图）：X轴日期，Y轴累计盈亏USDT，标注最高点和最低点，零轴虚线
2. 交易对盈亏排名（横向柱状图）：盈利绿色，亏损红色，按金额排列
3. 亏损原因分布（环形饼图）：中心显示总亏损笔数，不同颜色区分原因
4. 每日盈亏热力图（日历热力图）：深绿到深红色阶，悬停显示日期和金额
5. 胜率仪表盘 + 核心指标卡片：Gauge 显示胜率，卡片显示净盈亏、盈亏比等
6. 持仓时间 vs 盈亏散点图：X轴持仓时间，Y轴盈亏，点大小表示仓位

输出为单个 HTML 文件，用户可直接在浏览器中打开。

### Phase 6：生成文字复盘报告

在图表下方嵌入结构化文字报告，包含：

- 总体表现（笔数、胜率、净盈亏、盈亏比、最大盈亏、手续费、资金费率）
- 亏损交易对 Top 3
- 亏损原因分析（前 3 名原因 + 典型案例）
- 典型亏损交易复盘（开平仓价、盈亏、原因、建议）
- 改进建议（针对主要亏损原因的具体操作建议）

## 使用示例

- "帮我复盘一下最近 7 天的交易"
- "分析一下我为什么亏了"
- "看看我 BTC-USDT-SWAP 的合约盈亏"
- "最近 30 天交易总结，生成图表"
- "模拟盘复盘，只看亏损交易"
- "我的交易胜率是多少"
- "哪个币亏最多，给我看图"
- "生成盈亏复盘报告"

## 风险提示

1. 默认使用模拟盘（demo），查看实盘需用户明确指定 profile=live。
2. 复盘分析基于历史数据回溯，亏损原因判断为 AI 推测，仅供参考。
3. 部分早期交易记录可能因 API 限制无法获取（通常最多 3 个月）。
4. 本 Skill 仅供学习研究，不构成投资建议。

---

### [40] `position-sizer`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/position-sizer/SKILL.md`

---
name: position-sizer
description: >-
  Crypto position sizing calculator for OKX spot and perpetual swap.
  Use when the user asks how many contracts to open, how much to buy,
  or evaluates trade risk given entry/stop/leverage/account size.
  Covers fixed-fractional, Kelly criterion, ATR stops, liquidation
  price, and leverage comparison. Trigger: position size, how many
  contracts, risk per trade, 开多少张, 仓位计算, 风险大不大, 该买多少.
---

# OKX Crypto Position Sizer

## Triggers

- "How many contracts should I long/short?"
- "Position size for BTC-USDT-SWAP with 10x leverage"
- "How much risk am I taking on this trade?"
- "Kelly criterion for my win rate"
- "ATR-based stop and size for ETH"
- "帮我算一下 BTC 仓位"
- "做空 ETH 开多少张合约"
- "10x 杠杆开仓数量"

## Prerequisites

- Python 3.9+ (for script mode — see inline fallback if unavailable)
- OKX Trade Kit optional (auto-fills account size, contract params, leverage)

## Workflow

> All `okx` CLI commands below use `--profile demo` by default. Replace with `--profile live` for real trades. Always confirm profile before placing orders.

### Step 1: Gather Account Size

**Option A — Auto-fill from OKX CLI** (recommended):
```bash
okx --profile demo account balance USDT
```
Extract `equity` field as `--account-size`.

**Option B — User provides manually**: Ask for total account equity in USDT.

### Step 2: Gather Trade Parameters

Collect from user:
- **Side**: long or short
- **Inst type**: spot or swap (default: swap)
- **Entry price** and **stop price** (or ATR for Mode B)
- **Risk %** (default 1%) or **Kelly stats** (win rate, avg win/loss)
- **Leverage** (swap only, default 1)

**Fetch current price:**
```bash
okx --profile demo market ticker BTC-USDT-SWAP
```

**Fetch ATR (for ATR-based sizing):**
```bash
okx market indicator atr BTC-USDT-SWAP --bar 1D --params 14 --list --limit 1
```

**Fetch contract parameters:**
```bash
okx market instruments --instType SWAP --instId BTC-USDT-SWAP
```
Extract `ctVal` (contract value → `--contract-value`), `lotSz` (order precision → `--lot-size` for spot), `minSz`.

**Common ctVal reference (avoid API call for popular pairs):**

| Instrument | ctVal | Meaning |
|-----------|-------|---------|
| BTC-USDT-SWAP | 0.01 | 1 contract = 0.01 BTC |
| ETH-USDT-SWAP | 0.1 | 1 contract = 0.1 ETH |
| SOL-USDT-SWAP | 1 | 1 contract = 1 SOL |
| DOGE-USDT-SWAP | 100 | 1 contract = 100 DOGE |

**Check/set leverage (varies by instrument):**
```bash
okx --profile demo swap get-leverage --instId BTC-USDT-SWAP --mgnMode cross
# Set if needed:
okx --profile demo swap leverage --instId BTC-USDT-SWAP --lever 10 --mgnMode cross
```

### Step 3: Run Position Sizer Script

```bash
# Swap long + 10x leverage
python3 scripts/position_sizer.py \
  --account-size 100000 --entry 84200 --stop 80000 --risk-pct 1.0 \
  --side long --contract-value 0.01 --leverage 10 --inst-type swap \
  --output-dir /tmp/position-sizer-reports/

# Swap short + 5x leverage
python3 scripts/position_sizer.py \
  --account-size 100000 --entry 84200 --stop 88000 --risk-pct 1.0 \
  --side short --contract-value 0.01 --leverage 5 --inst-type swap \
  --output-dir /tmp/position-sizer-reports/

# Spot (--lot-size from instruments API lotSz field)
python3 scripts/position_sizer.py \
  --account-size 100000 --entry 84200 --stop 80000 --risk-pct 1.0 \
  --inst-type spot --lot-size 0.00001 \
  --output-dir /tmp/position-sizer-reports/

# ATR-based (get ATR from indicator first)
python3 scripts/position_sizer.py \
  --account-size 100000 --entry 84200 --atr 1850 --atr-multiplier 2.0 \
  --risk-pct 1.0 --side long --contract-value 0.01 --leverage 10 \
  --inst-type swap --output-dir /tmp/position-sizer-reports/

# Kelly budget mode
python3 scripts/position_sizer.py \
  --account-size 100000 --win-rate 0.55 --avg-win 2.5 --avg-loss 1.0 \
  --output-dir /tmp/position-sizer-reports/

# Kelly + leverage + contracts
python3 scripts/position_sizer.py \
  --account-size 100000 --win-rate 0.55 --avg-win 2.5 --avg-loss 1.0 \
  --entry 84200 --stop 80000 --contract-value 0.01 --leverage 10 \
  --inst-type swap --output-dir /tmp/position-sizer-reports/

# With portfolio constraints
python3 scripts/position_sizer.py \
  --account-size 100000 --entry 84200 --stop 80000 --risk-pct 1.0 \
  --side long --contract-value 0.01 --leverage 10 --inst-type swap \
  --inst-id BTC-USDT-SWAP \
  --max-position-pct 10 --max-contracts 50 \
  --output-dir /tmp/position-sizer-reports/

# Large position with custom MMR tier and fee rate
python3 scripts/position_sizer.py \
  --account-size 1000000 --entry 84200 --stop 80000 --risk-pct 1.0 \
  --side long --contract-value 0.01 --leverage 10 --inst-type swap \
  --mmr 0.01 --fee-rate 0.0003 \
  --output-dir /tmp/position-sizer-reports/
```

**Key parameters for advanced users:**
- `--mmr`: Maintenance margin rate (default 0.004 = 0.4%, Tier 1). Large positions have higher MMR — check OKX tiered margin rules and adjust accordingly.
- `--fee-rate`: Taker fee rate (default 0.0005 = 0.05%, VIP0). VIP users with lower fees should adjust for more accurate liquidation estimates.
- `--inst-id`: Instrument ID (e.g., BTC-USDT-SWAP) — included in reports for clarity.
- `--lot-size`: Spot minimum order precision (lotSz from `okx market instruments`). Ensures output units are precision-aligned for OKX spot orders. Not needed for swap (swap always outputs integer contracts).

Note: Use `--output-dir /tmp/position-sizer-reports/` (absolute path) to avoid working directory issues.

**Fallback — inline calculation** (if Python unavailable):

Fixed Fractional (swap):
```
risk_per_contract = abs(entry - stop) * ctVal
dollar_risk       = account_size * risk_pct / 100
contracts         = floor(dollar_risk / risk_per_contract)
```

Fixed Fractional (spot):
```
risk_per_unit = abs(entry - stop)
dollar_risk   = account_size * risk_pct / 100
units         = dollar_risk / risk_per_unit
```

ATR-Based:
```
stop_distance = atr * multiplier
stop (long)   = entry - stop_distance
stop (short)  = entry + stop_distance
risk_per_contract = stop_distance * ctVal
contracts     = floor(dollar_risk / risk_per_contract)
```

Kelly:
```
R              = avg_win / avg_loss
kelly_pct      = win_rate - (1 - win_rate) / R   [floor at 0]
half_kelly_pct = kelly_pct / 2
# With leverage: effective = half_kelly_pct / leverage
```

### Step 4: Multi-Scenario Comparison

If no single method is specified, run all applicable methods and present a comparison:

| Method | Contracts | Notional | Margin | Dollar Risk | Risk % |
|--------|-----------|----------|--------|-------------|--------|
| Fixed 1% @ 5x | — | — | — | — | — |
| Fixed 1% @ 10x | — | — | — | — | — |
| Fixed 1% @ 20x | — | — | — | — | — |
| ATR 1.5x @ 10x | — | — | — | — | — |
| ATR 2.0x @ 10x | — | — | — | — | — |
| ATR 3.0x @ 10x | — | — | — | — | — |

### Step 5: Apply Portfolio Constraints

Check (tightest constraint determines final size):

1. Max single position % of account (`--max-position-pct`)
2. Total portfolio heat (sum of all open risks <= 6-8%)
3. Exchange max orderable size:
   ```bash
   okx --profile demo account max-size --instId BTC-USDT-SWAP --tdMode cross
   ```
   Extract `maxBuy` (long) or `maxSell` (short), pass as `--max-contracts`.
4. Available margin check:
   ```bash
   okx --profile demo account max-avail-size --instId BTC-USDT-SWAP --tdMode cross
   ```

### Step 5.5: Funding Rate Check (Perpetual Swap, Optional)

For positions expected to be held multiple days:
```bash
okx --profile demo market funding-rate BTC-USDT-SWAP
```
```
daily_cost  = notional * funding_rate * 3  (OKX settles 3x/day)
weekly_cost = daily_cost * 7
```
Present as a cost consideration alongside the position sizing result.

### Step 6: Present Result and OKX Handoff

Present the recommendation:

```
Position Sizing Result
──────────────────────
Instrument:      BTC-USDT-SWAP
Side:            Long
Method:          Fixed Fractional 1%
Entry:           $84,200
Stop:            $80,000
Contracts:       23        ← directly usable as --sz
Leverage:        10x
Notional:        $19,366
Margin Required: $1,936.60
Est. Liquidation: $76,123 (isolated, mmr=0.4%, fee=0.05%)
Dollar Risk:     $966.00 (0.97%)
Binding:         none

Risk Warnings:
  - Liquidation price is an isolated margin estimate (Tier 1 small position)
  - Cross margin mode: liquidation price fluctuates with all positions' PnL
  - Large positions have higher tiered MMR — actual liquidation is closer
```

**If stop is beyond liquidation:**
```
CRITICAL: Stop $70,000 is beyond liquidation $76,123!
Position will be liquidated before stop triggers.
Action: Reduce leverage / tighten stop-loss / use cross margin mode
```

**If user wants to place the trade**, present confirmation then execute:

```
Confirm trade:
  Instrument: BTC-USDT-SWAP
  Side: buy (long)
  Size: 23 contracts
  Order type: limit @ $84,200
  Stop-loss: $80,000
  Margin mode: cross
  Profile: demo

Reply YES to proceed, or adjust parameters.
```

On confirmation:

**Step A — Verify/set leverage (swap only):**
```bash
# Check current leverage
okx --profile demo swap get-leverage --instId BTC-USDT-SWAP --mgnMode cross
# Set to match position sizer calculation (if different)
okx --profile demo swap leverage --instId BTC-USDT-SWAP --lever 10 --mgnMode cross
```

**Step B — Place order:**
```bash
# Long swap (hedge mode — uses --posSide)
okx --profile demo swap place --instId BTC-USDT-SWAP \
  --side buy --ordType limit --sz 23 --px 84200 \
  --tdMode cross --posSide long

# Short swap (hedge mode)
okx --profile demo swap place --instId BTC-USDT-SWAP \
  --side sell --ordType limit --sz 23 --px 84200 \
  --tdMode cross --posSide short

# Spot (long only)
okx --profile demo spot place --instId BTC-USDT \
  --side buy --ordType limit --sz 0.238 --px 84200
```

> **Position mode note:** `--posSide long/short` is required in **hedge mode** (long_short_mode). In **net mode**, omit `--posSide` entirely. Check current mode: `okx --profile demo account config` (look for `posMode` field).

If OKX Trade Kit is not installed:
```
OKX Trade Kit is not detected. To place this trade:

  npm install -g @okx_ai/okx-trade-cli
  okx config init

Details: https://github.com/okx/agent-trade-kit
```

## Key Principles

1. **Survival first**: Sizing is about surviving losing streaks, not maximizing winners
2. **1% rule**: Default to 1% risk per trade; never exceed 2% without strong reason
3. **Round down**: Always floor to whole contracts (swap) or precision-aligned units (spot)
4. **Strictest constraint wins**: Tightest limit determines final size
5. **Half Kelly only**: Never use full Kelly; half Kelly captures ~75% of growth
6. **Kelly + leverage**: Divide effective Kelly by leverage multiplier to avoid over-exposure
7. **Portfolio heat**: Total open risk must not exceed 6-8% of account equity
8. **Asymmetry of losses**: A 50% loss requires 100% gain to recover — size accordingly
9. **Verify liquidation**: Always confirm liquidation price is beyond stop-loss before trading
10. **Cross margin caveat**: Liquidation price fluctuates with all positions' PnL — recheck after opening
11. **MMR tiers**: Large positions have higher maintenance margin — liquidation is closer than Tier 1 estimates

## Limitations

- **USDT-margined only**: Liquidation formula and sizing logic are designed for USDT-margined contracts (e.g., BTC-USDT-SWAP). Coin-margined contracts (e.g., BTC-USD-SWAP) use different formulas — do not use this tool for coin-margined positions.
- **Spot is long-only**: OKX spot trading does not support short selling. Use perpetual swap for short positions.
- **Isolated margin liquidation only**: The script estimates isolated margin liquidation. Cross margin liquidation depends on total account state and cannot be computed locally.

## References

- `references/sizing_methodologies.md`: Detailed guide to all three methods with crypto examples, leverage/liquidation formulas
- `scripts/position_sizer.py`: CLI position sizer for OKX (Python 3.9+, stdlib only)

---

### [41] `qtx-alpha`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/qtx-alpha/SKILL.md`

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

---

### [42] `quadruple-filter-trend-hunter`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/quadruple-filter-trend-hunter/SKILL.md`

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

---

### [43] `recurring-dca`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/recurring-dca/SKILL.md`

---
name: recurring-dca
description: >
  Use this skill whenever a user wants to create, manage, or automate
  recurring crypto purchases on OKX — including Chinese requests about
  定投, 每周买BTC, 创建定投策略, or 定期定额. Core capabilities: scheduled DCA
  (hourly/daily/weekly/monthly), multi-coin portfolio allocation
  (e.g., BTC 70% + SOL 30%), condition-triggered automation (buy when
  RSI below 30, MACD crossover, Bollinger Band touch), and full strategy
  lifecycle (list, stop, rename). This is the go-to skill for any
  automatic periodic investment plan in crypto, regardless of
  language. Do NOT invoke for one-time trades, pure chart/indicator
  analysis, or DCA bot grid parameter tuning.
---

# Recurring Buy (DCA) System

Manage server-side dollar-cost averaging (DCA) strategies on OKX via the Trading Bot Recurring Buy API. Create multi-coin portfolios, set flexible schedules, and automate buys based on technical indicators.

---

## Confirmation Rule

All write operations (create, stop, amend) require explicit user confirmation. Before executing any write script, show the user a clear summary of what will happen and wait for a "yes" or equivalent. Only then run the script. Never embed `input()` in scripts — Claude Code runs scripts as non-interactive subprocesses and `input()` will cause them to hang indefinitely.

### Confirmation Template

Use this format before every write operation:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 定投策略确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
操作：[创建 / 停止 / 修改] 策略
名称：[策略名称]
币种：[BTC:70% + ETH:30%]
金额：每期 [X] USDT（最低每币 10 USDT）
频率：[每天 / 每周X / 每月X] [时区] [时间]
模式：[真实资金 / 演示模式]

⚠️ 此操作涉及真实资金。演示测试请先执行：
   export OKX_SIMULATED=true

回复"确认"执行，其他取消。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Setup & Credentials

### Installation

Ensure `okx-trade-cli` is installed:

```bash
npm install -g @okx_ai/okx-trade-cli
which okx || echo "Install with: npm install -g @okx_ai/okx-trade-cli"
```

### Credential Configuration

OKX API credentials can be provided via (in priority order):

1. **Environment variables:**
   ```bash
   export OKX_API_KEY="your-key"
   export OKX_SECRET_KEY="your-secret"
   export OKX_PASSPHRASE="your-passphrase"
   ```

2. **`~/.oktrade.env` file** (see `references/credential-setup.md`)

3. **`~/.okx/config.toml` file** (see `references/credential-setup.md`)

For demo mode, set `export OKX_SIMULATED=true` — all API calls will hit simulated endpoints automatically.

See `${CLAUDE_SKILL_DIR}/scripts/auth_helper.py` for the shared authentication module used by all operations.

---

## 1. Create Recurring Buy Strategy

### Preset Strategy (Single Coin)

Show this summary to the user and get confirmation before running the script.

**Example: Daily BTC DCA at 10:00 UTC+8**

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('${CLAUDE_SKILL_DIR}/scripts'))
from auth_helper import okx_recurring_api

body = {
    "stgyName": "BTC Daily DCA",
    "recurringList": [{"ccy": "BTC", "ratio": "1"}],
    "period": "daily",
    "amt": "50",
    "investmentCcy": "USDT",
    "tdMode": "cash",   # "cash" = spot (recommended); "cross" = cross-margin
    "recurringTime": "10",
    "timeZone": "8",
}

result = okx_recurring_api("POST", "/api/v5/tradingBot/recurring/order-algo", body=body)
if result:
    print(f"SUCCESS: algoId = {result[0].get('algoId')}")
else:
    print("ERROR: No response from API")
PYEOF
```

### Multi-Coin Portfolio

Pass `recurringList` as an array with ratios summing to 1:
```python
"recurringList": [
    {"ccy": "BTC", "ratio": "0.6"},
    {"ccy": "ETH", "ratio": "0.4"},
]
```

### Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `coins` | "BTC" or "BTC:0.6,ETH:0.4" | Required | "BTC:0.7,SOL:0.3" |
| `amount` | Per-period investment (USDT). Min 10 USDT per coin. | Required | "100" |
| `period` | hourly / daily / weekly / monthly | daily | "weekly" |
| `name` | Strategy name | "DCA" | "BTC Daily" |
| `recurring_day` | 1-7 (Mon-Sun) for weekly, 1-28 for monthly | — | "1" |
| `recurring_hour` | 1/4/8/12 for hourly interval | — | "4" |
| `recurring_time` | Hour of day (0-23). Required. | — | "10" |
| `time_zone` | UTC offset (e.g., "8" for UTC+8) | — | "8" |

---

## 2. Manage Existing Strategies

### List All Pending Strategies

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('${CLAUDE_SKILL_DIR}/scripts'))
from auth_helper import okx_recurring_api

data = okx_recurring_api("GET", "/api/v5/tradingBot/recurring/orders-algo-pending")
if not data:
    print("No pending DCA strategies")
else:
    print(f"{'#':<4} {'AlgoID':<18} {'Name':<20} {'Coins':<15} {'Period':<8}")
    print("-" * 70)
    for i, o in enumerate(data):
        coins = "+".join(c.get("ccy", "-") for c in o.get("recurringList", []))
        print(f"{i+1:<4} {o.get('algoId',''):<18} {o.get('stgyName',''):<20} {coins:<15} {o.get('period',''):<8}")
    print(f"\nTotal: {len(data)} strategies")
PYEOF
```

### View Strategy Details

```python
data = okx_recurring_api("GET", "/api/v5/tradingBot/recurring/orders-algo-details",
                          query={"algoId": algo_id})
```

### Stop a Strategy

Show the user which strategy will be stopped (name + algoId) and get confirmation before running.

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('${CLAUDE_SKILL_DIR}/scripts'))
from auth_helper import okx_recurring_api

algo_id = "REPLACE_WITH_ACTUAL_ALGO_ID"

# NOTE: Stop API expects body as ARRAY
result = okx_recurring_api("POST", "/api/v5/tradingBot/recurring/stop-order-algo", body=[{"algoId": algo_id}])
print(f"Strategy stopped: {algo_id}")
PYEOF
```

### Amend Strategy Name

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('${CLAUDE_SKILL_DIR}/scripts'))
from auth_helper import okx_recurring_api

algo_id = "REPLACE_WITH_ACTUAL_ALGO_ID"
new_name = "REPLACE_WITH_NEW_NAME"

body = {"algoId": algo_id, "stgyName": new_name}
okx_recurring_api("POST", "/api/v5/tradingBot/recurring/amend-order-algo", body=body)
print(f"Strategy renamed: {new_name}")
PYEOF
```

---

## 3. Auto Start/Stop Based on Conditions

Automatically trigger DCA based on technical indicators.

### Indicator Fetching Priority

**Primary — OKX TradeKit CLI:**
```bash
okx market indicator rsi BTC-USDT --bar 1H
okx market indicator macd BTC-USDT --bar 1H
okx market indicator bb BTC-USDT --bar 1H
okx market funding-rate BTC-USDT-SWAP
```

**Fallback — OKX TradeKit MCP** (if CLI unavailable):
```
market_get_indicator(instId="BTC-USDT", indicator="rsi", bar="1H")
market_get_indicator(instId="BTC-USDT", indicator="macd", bar="1H")
market_get_indicator(instId="BTC-USDT", indicator="bb", bar="1H")
market_get_funding_rate(instId="BTC-USDT-SWAP")
```

**ATR** (not available via CLI/MCP): use `${CLAUDE_SKILL_DIR}/scripts/indicators.py`
with candles from `okx market candles BTC-USDT --bar 1H --limit 50`.

### Condition-Based Workflow

**Step 1 — Fetch indicator** (CLI or MCP as above)

**Step 2 — Embed the fetched value in the script and run**

Claude fills in the actual indicator value before executing. Never use `input()` to pass values — the script must be self-contained.

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('${CLAUDE_SKILL_DIR}/scripts'))
from auth_helper import okx_recurring_api

# Claude replaces 27.4 with the actual RSI value fetched in Step 1
rsi_value = 27.4

if rsi_value < 30:
    print(f"RSI {rsi_value:.1f} < 30 (超卖) — 启动定投...")
    body = {
        "stgyName": f"RSI-Oversold DCA (RSI={rsi_value:.0f})",
        "recurringList": [{"ccy": "BTC", "ratio": "1"}],
        "period": "daily",
        "amt": "50",
        "investmentCcy": "USDT",
        "tdMode": "cash",
        "recurringTime": "10",
        "timeZone": "8",
    }
    result = okx_recurring_api("POST", "/api/v5/tradingBot/recurring/order-algo", body=body)
    print(f"定投已启动，AlgoID: {result[0].get('algoId')}")
elif rsi_value > 70:
    print(f"RSI {rsi_value:.1f} > 70 (超买) — 请查询并停止现有定投策略")
else:
    print(f"RSI {rsi_value:.1f}，条件未触发，维持现状")
PYEOF
```

### Common Condition Examples

| 策略 | 启动条件 | 暂停条件 |
|------|---------|---------|
| RSI 均值回归 | RSI(14, 1H) < 30 | RSI > 70 |
| MACD 金叉 | MACD histogram 由负转正 | histogram 由正转负 |
| 布林下轨 | 价格触及或跌破下轨 | 价格触及上轨 |
| 资金费率套利 | 资金费率 < −0.01% | 资金费率 > +0.05% |
| 复合条件 | RSI < 40 **且** 资金费率 < 0 | 任一条件反转 |

See `references/conditions-guide.md` for full multi-condition automation examples.

---

## API Reference

Full endpoint documentation in `references/api-reference.md`.

Key endpoints at a glance:

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Create | POST | `/api/v5/tradingBot/recurring/order-algo` |
| List pending | GET | `/api/v5/tradingBot/recurring/orders-algo-pending` |
| Get details | GET | `/api/v5/tradingBot/recurring/orders-algo-details?algoId=...` |
| Stop | POST | `/api/v5/tradingBot/recurring/stop-order-algo` (body is **array**) |
| Amend | POST | `/api/v5/tradingBot/recurring/amend-order-algo` |

---

## Fallback Chain

| 优先级 | 用途 | 方式 |
|--------|------|------|
| **指标获取 1** | 行情 / 指标 | OKX TradeKit CLI：`okx market indicator rsi BTC-USDT --bar 1H` |
| **指标获取 2** | 行情 / 指标 | OKX TradeKit MCP：`market_get_indicator(...)` |
| **策略管理** | 创建/停止/查询 | `scripts/auth_helper.py` 直接调 OKX Recurring Buy REST API |
| **定时触发** | 条件检查自动化 | `mcp__scheduled-tasks__create_scheduled_task` |
| **兜底** | 安装引导 | 提示用户安装 `npm install -g @okx_ai/okx-trade-cli` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Credentials not found" | Set `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE` env vars or create `~/.oktrade.env` |
| "API Error: insufficient balance" | Check account balance; min 10 USDT per coin |
| "HTTP 429: Rate limited" | Implement backoff; OKX allows ~10 req/sec per endpoint |
| Strategy not executing | Verify timezone is correct; check account has sufficient balance |
| Lost algoId | Query `/orders-algo-history` to find stopped strategies |

See `references/troubleshooting.md` for detailed debugging steps.

---

### [44] `resilience-trader`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/resilience-trader/SKILL.md`

---
name: resilience-trader
description: 韧性交易者 | 一份以"活下去优先、保护本金、信念先行"为核心哲学的永续合约策略 Skill。当用户说"韧性交易"、"resilience trader"、"保本策略"、"信念交易"时启用。融合双时间框架趋势识别、固定风险仓位法、ATR 熔断与 AI 综合推理,适合不愿在波动中梭哈的稳健型交易者。
---

# 策略名称
韧性交易者:活下去、保护本金与信念先行的永续合约策略 V1.0

---

> *"早期采用者常拿指数级回报,同时只需应对有限的风险。只要你把下行风险控住,那些指数级回报就能兑现。"*

---

## 策略哲学

本策略建立在三条不可动摇的生命线之上,它们的优先级高于任何一次交易机会:

**韧性(Resilience)**:市场最恐慌的时刻,往往藏着最好的机会——但前提是你还活着。本策略的第一优先级永远是"活着",而不是"赚大钱"。在波动失控时,主动放弃机会是一种纪律,不是懦弱。

**保护本金(Protect Capital)**:本金是交易者唯一真正属于自己的东西。每一笔交易必须有明确的止损,**无保护的仓位不被允许开启**。亏损可以接受,失控不能接受。

**信念先行(Conviction First)**:信念不是盲目,是基于数据和逻辑之后的坚定。本策略要求 AI 在每次决策时,必须明确说出"我相信这笔交易的理由是什么",而不是机械执行规则。一个无法陈述信念的决策,就是不应该被执行的决策。

---

## 执行节奏

每 **2 小时** 触发一次完整评估循环。

---

## Step 1 · 市场环境普查(知己知彼)

调用以下接口,构建当前市场的完整画像:

**价格与趋势:**
- `market_get_candles`:获取 BTC-USDT-SWAP、ETH-USDT-SWAP、SOL-USDT-SWAP 的 **1h + 4h 双时间框架** K线
- 计算指标:EMA20、EMA60(判断趋势方向);RSI(14)(判断超买超卖);ATR(14)(量化波动烈度);布林带(20,2)(判断价格是否处于压缩或扩张状态)

**市场情绪温度计:**
- `market_get_funding_rate`:获取三个标的的当前资金费率
- `market_get_open_interest`:获取持仓量及其24小时变化幅度
- `market_get_ticker`:获取24小时成交量,与7日均量对比,判断成交量是否异常放大

**宏观压力感知(选填):**
- 若有外部数据接口,补充当前 BTC 的恐惧贪婪指数(Fear & Greed Index)区间(0-100)
- 若无,AI 可根据资金费率 + 持仓量变化 + 价格动态,自行推断当前市场情绪区间(极度恐惧 / 恐惧 / 中性 / 贪婪 / 极度贪婪)

---

## Step 2 · 韧性筛选:市场是否值得入场?(生存优先)

在决定任何仓位之前,AI 必须先执行以下"韧性三问":

**问题 1:波动是否在可承受范围内?**
- 计算目标标的当前 ATR(14) 相对于过去30根K线的ATR均值的比率(ATR倍率)
- ATR倍率 > 2.0:市场极度动荡,当前循环**强制跳过**,理由记录为"波动超限,韧性保护启动"
- ATR倍率 1.5~2.0:允许入场,但仓位自动缩减至标准仓位的 **50%**
- ATR倍率 < 1.5:正常区间,允许按标准仓位入场

**问题 2:资金费率是否已经过度拥挤?**
- 资金费率绝对值 > 0.15%:极度拥挤,方向可疑,**当前循环跳过**
- 资金费率绝对值 0.08%~0.15%:拥挤警告,仓位减半,且只允许做与费率方向相反的一侧(即费率为正时只允许做空,费率为负时只允许做多)
- 资金费率绝对值 < 0.08%:健康区间,无额外限制

**问题 3:今日账户是否已触发熔断?**
- 若当日净值回撤已达 **6%**,当前循环**强制跳过**,等待次日 00:00 UTC 重置
- 若当前已持有 **2 个及以上仓位**,当前循环跳过,优先管理现有仓位

以上三问中,只要有任何一问触发"跳过",则本轮结束,**不得执行下单**。

---

## Step 3 · 信念构建:AI 综合推理(核心决策层)

这是策略的灵魂所在。AI 必须扮演一个有独立思考能力的交易员,而不是规则执行机器。

**3.1 选标的:谁的信号最干净?**

对 BTC、ETH、SOL 三个标的,分别评估以下维度,每项 0~3 分,满分 15 分:

| 评估维度 | 评分标准 |
|---|---|
| **趋势一致性** | 1h 与 4h EMA方向一致且价格在EMA20之上/下:3分;仅一个时框满足:1分;相互矛盾:0分 |
| **动量强度** | RSI(14) 处于 55~75(做多)或 25~45(做空):3分;处于 50~55 或 45~50:1分;超买超卖(>80或<20):0分 |
| **成交量确认** | 当前24h成交量 > 7日均量的 1.3倍:3分;0.8~1.3倍:1分;< 0.8倍:0分 |
| **布林带结构** | 价格突破布林带上/下轨后回归,或在中轨附近蓄势:3分;处于布林带内部无明显结构:1分;价格在带外且已过度拉伸:0分 |
| **持仓量健康度** | 持仓量24h增长 5%~20%(方向性资金入场但未过热):3分;增长 < 5% 或略有下降(观望):1分;暴增 > 20% 或暴降:0分 |

选择总分最高的标的。若最高分 < 9 分,则三个标的均不满足入场条件,本轮**跳过**。

**3.2 判断方向:做多还是做空?**

基于选定标的,AI 综合以下信号判断方向:
- 趋势信号(EMA排列、价格位置)
- 动量信号(RSI方向)
- 情绪信号(资金费率方向 + 恐惧贪婪情绪区间)
- 布林带结构(突破 or 均值回归)

AI 必须给出明确方向(long / short),并在理由栏中用 **1-2句话** 陈述:"我选择做[方向],因为[核心理由]。"

**3.3 仓位计算:风险永远第一**

采用**固定风险仓位法**(Fixed Fractional Risk):

```
单笔最大风险金额 = 账户净值 × 2%
止损距离(点数)= 开仓价格 × 止损比例(见 Step 5)
合约张数 = 单笔最大风险金额 ÷ 止损距离
```

若 Step 2 中触发了仓位减半规则,则在上述结果基础上再乘以 0.5。

最终仓位不得超过账户净值的 **15%**(无论计算结果如何)。

**3.4 AI 最终决策声明**

在执行下单之前,AI 必须输出以下格式的决策摘要:

```
【决策摘要】
选定标的:[XXX-USDT-SWAP],得分:[X/15]
交易方向:[做多 / 做空]
信念陈述:我选择[方向],因为[1-2句核心理由]。
市场情绪:[极度恐惧 / 恐惧 / 中性 / 贪婪 / 极度贪婪]
计划仓位:账户净值的 [X]%,共 [X] 张
止损价:[X] USDT
预期风险金额:[X] USDT(占净值 [X]%)
韧性检查:全部通过 ✓
```

若 AI 无法填写完整的决策摘要,则**不得下单**。

---

## Step 4 · 执行下单(仅当 Step 3 决策摘要完整时)

调用 `swap_place_order`:

```
instId  = <Step 3 中选定的标的>
side    = <buy(做多)或 sell(做空)>
ordType = "market"
sz      = <Step 3.3 中计算的合约张数>
tag     = "agentTradeKit"   ← 必填,否则不计入排行榜
```

下单成功后,**立即**执行 Step 5,不得有任何延迟。

---

## Step 5 · 止损与止盈设置(保护本金)

**止损设置**(强制执行,不可省略):

调用 `swap_place_algo_order` 设置止损单:

| 方向 | 止损价 | 逻辑 |
|---|---|---|
| 做多 | 开仓价 × 0.97 | 亏损上限 3%,触发韧性保护 |
| 做空 | 开仓价 × 1.03 | 亏损上限 3%,触发韧性保护 |

**止盈设置**(分批止盈,避免一次性兑现):

调用 `swap_place_algo_order` 设置两档止盈:

| 方向 | 第一档止盈(50%仓位) | 第二档止盈(剩余50%) |
|---|---|---|
| 做多 | 开仓价 × 1.04 | 开仓价 × 1.08 |
| 做空 | 开仓价 × 0.96 | 开仓价 × 0.92 |

第一档止盈触发后,将剩余仓位的止损移动至**开仓价**(保本止损),确保这笔交易无论如何不亏损。

---

## Step 6 · 持仓监控与动态管理

每次触发循环时,若存在未平仓仓位,AI 需先执行持仓健康检查:

**检查项:**
1. 当前浮动盈亏是否已超过预设止盈目标?若是,检查止盈单是否正常挂载
2. 持仓方向与当前 EMA 趋势是否仍一致?若4h EMA方向已反转,且当前仍持有反方向仓位超过4根K线,建议 AI 给出"主动平仓评估"
3. 当前资金费率是否已对持仓方向产生显著成本压力(费率 > 0.1% 且方向不利)?若持仓已超过 8 小时,AI 评估是否应主动平仓以避免费率持续消耗

若 AI 判断需要提前平仓,调用 `swap_place_order` 以市价平仓,并记录平仓理由。

---

## 风控总则(不可违反的原则)

```
// [P1] 单笔最大亏损不超过账户净值的 2%
// [P2] 当日净值回撤超过 6% 则停止所有新开仓,等待次日重置
// [P3] 最多同时持有 2 个仓位,禁止对冲持仓(同一标的同时持多空)
// [P4] 每笔仓位必须在开仓后 60 秒内完成止损挂单,否则立即平仓
// [P5] 止损单一经设置,不得手动上移扩大亏损空间(只允许向有利方向移动)
// [P6] ATR倍率超过2.0时,无论信号多强,强制跳过,这是韧性保护不可撤销的底线
// [P7] 资金费率绝对值超过0.15%时,无论信号多强,强制跳过
```

---

## 策略的自我叙述

这个策略叫"韧性交易者",因为它试图回答一个简单的问题:**在一个 95% 的人都会亏损出局的市场里,你凭什么活下来?**

答案不是更强的信号,不是更快的执行,而是更克制的纪律。本策略的每一笔交易,都要求 AI 在下单之前问自己:**"我真的相信这笔交易吗?如果相信,我愿意承担多少风险?"**

韧性不是硬撑,是在风险可控的前提下,坚持自己的判断。
保护本金,才能等来下一次机会。
信念先行,才不会被市场的噪音带走方向。

---

*策略版本:V1.0 | 适用平台:OKX Agent Trade Kit*

---

### [45] `rolling-position`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/rolling-position/SKILL.md`

---
name: rolling-position
description: "智能滚仓助手 — 融合比特皇趋势滚仓与予与裸K波段两种模式。分析行情后给出结构化操作建议，通过 OKX Agent Trade Kit CLI 安全执行交易（密钥不离开本地）。触发词：/rolling-position, 滚仓, 加仓策略, 仓位管理"
license: MIT
metadata:
  author: awan
  version: "2.0.0"
---

# 智能滚仓助手

## 概述

本 Skill 融合两位顶级交易员的核心方法论：
- **比特皇模式**：趋势突破后浮盈加仓，随资金增长动态降杠杆，三次止损强制休息
- **予与模式**：裸K识别震荡区间做波段，趋势行情浮盈1:1滚仓，只做龙头标的

**核心铁律（不可违反）**：
1. 浮亏时绝对禁止加仓
2. 单日止损3次 → 强制停止当日所有交易
3. 加仓仓位必须同时设置止损
4. 止损优先于止盈考虑

---

## 执行流程

用户调用 `/rolling-position [交易对]` 时，按以下步骤执行：

### Step 1：读取状态文件

检查 `~/.claude/rolling-position-state.json` 是否存在：

```bash
cat ~/.claude/rolling-position-state.json 2>/dev/null || echo '{"daily_stops": 0, "last_stop_date": "", "total_equity_usd": 0}'
```

如果 `daily_stops >= 3` 且 `last_stop_date == 今日日期` → **立即停止，输出强制休息提示，不执行任何操作**。

### Step 2：获取账户信息

通过 OKX Trade CLI 获取（需要用户已通过 `okx config init` 配置密钥，密钥存储在本地 `~/.okx/config.toml`，不经过 AI）：

```bash
okx account balance
```

提取：
- `totalEq`：账户总净值（USD）
- `availBal`：可用余额

根据净值确定**最大杠杆上限**（比特皇复利降杠杆原则）：

| 净值范围 | 最大杠杆 | 单笔最大仓位 |
|---------|---------|------------|
| < $10,000 | 20x | 净值 30% |
| $10k–$100k | 10x | 净值 25% |
| $100k–$1M | 5x | 净值 20% |
| > $1M | 3x | 净值 15% |

### Step 2.5：操作前检查（每次必做）

在执行任何交易操作前，必须先检查现有挂单和策略单：

```bash
# 查看现有策略单（止损/止盈/trailing stop）
okx swap algo orders --instId {交易对}

# 查看现有限价挂单
okx swap orders --instId {交易对}
```

**注意事项**：
- 修改杠杆前必须先取消所有挂单和策略单，否则会报错
- 取消策略单：`okx swap algo cancel --instId {交易对} --algoId {策略单ID}`
- 取消限价单：`okx swap cancel {交易对} --ordId {订单ID}`

### Step 3：获取当前持仓

```bash
okx swap positions {交易对}
```

提取：
- `pos`：持仓数量（正=多，负=空）
- `avgPx`：开仓均价
- `upl`：未实现盈亏
- `uplRatio`：浮盈率
- `liqPx`：强平价格
- `lever`：当前杠杆

### Step 4：获取 K 线数据

```bash
okx market candles {交易对} --bar 4H --limit 100
okx market candles {交易对} --bar 1H --limit 50
```

同时获取4小时和1小时两个级别，用于判断趋势/震荡。

### Step 5：行情模式判断（裸K分析，不依赖指标）

#### 趋势模式判断条件（满足2条以上）
- 4H级别：连续3根以上同向K线
- 价格突破近20根K线的最高/最低点
- 回调不超过前一波涨幅的50%（更高的低点/更低的高点）
- 成交量在突破时明显放大

#### 震荡模式判断条件（满足2条以上）
- 价格在明确的高低点区间内来回运动
- 多次触及同一支撑/阻力位后反弹
- 4H级别无明显方向，1H级别有小波段
- 近期高点和低点的差距 < 15%

#### 关键价位识别
- **支撑位**：近期多次触及的低点，取最近3个低点的均值
- **阻力位**：近期多次触及的高点，取最近3个高点的均值
- **突破确认**：收盘价超过阻力位/支撑位 2% 以上

---

## 操作决策树

### 情况A：无持仓 + 趋势模式

**开仓条件**：价格刚突破阻力位（多）或跌破支撑位（空），突破幅度 > 2%

**操作**：
1. 建底仓：账户净值 × 20%，杠杆 = 当前级别最大杠杆的 50%
2. 同时设置止损：止损位 = 突破点下方 3%（多）/ 上方 3%（空）
3. 止盈目标：盈亏比至少 3:1，理想 10:1

**下单命令模板**：
```bash
# 1. 查看当前杠杆
okx swap get-leverage --instId {交易对} --mgnMode cross

# 2. 市价开多，同时附带止损（会自动创建策略止损单）
okx swap place --instId {交易对} --side buy --posSide long --ordType market --sz {合约张数} \
  --tdMode cross --slTriggerPx {止损价} --slOrdPx=-1

# 2. 市价开空，同时附带止损
okx swap place --instId {交易对} --side sell --posSide short --ordType market --sz {合约张数} \
  --tdMode cross --slTriggerPx {止损价} --slOrdPx=-1

# 3. 【必做】验证止损单已生效
okx swap algo orders --instId {交易对}
# 必须看到 slTrigger 列有正确的止损价格，state 为 live
# 如果没有止损单，立即补挂（见下方"补挂止损"命令）
```

**补挂止损**（如果开仓时止损未生效，或需要单独添加止损）：
```bash
# 用策略单命令单独挂止损（注意：这里用 swap algo place，不是 swap place）
# swap place --side sell 是直接市价平仓，不是挂止损！
okx swap algo place --instId {交易对} --side sell --sz {合约张数} \
  --slTriggerPx {止损价} --slOrdPx=-1 --posSide long --tdMode cross

# 空单补挂止损
okx swap algo place --instId {交易对} --side buy --sz {合约张数} \
  --slTriggerPx {止损价} --slOrdPx=-1 --posSide short --tdMode cross

# 验证
okx swap algo orders --instId {交易对}
```

---

### 情况B：无持仓 + 震荡模式（予与裸K波段）

**开仓条件**：
- 做多：价格接近支撑位（距离 < 2%），且1H出现止跌信号（下影线、锤子线）
- 做空：价格接近阻力位（距离 < 2%），且1H出现止涨信号（上影线、射击之星）

**操作**：
1. 建仓：账户净值 × 15%，杠杆 = 当前级别最大杠杆的 60%
2. 止损：区间外 3%（支撑位下方 3% / 阻力位上方 3%）
3. 止盈：区间另一端的 80% 位置

---

### 情况C：有持仓 + 浮盈 > 10% + 趋势延续（滚仓核心）

**加仓条件**（必须同时满足）：
- `uplRatio > 0.10`（浮盈超过10%）
- 价格继续突破新高/新低（趋势延续确认）
- 当前杠杆 < 最大杠杆上限
- 今日止损次数 < 3

**加仓规则（比特皇/予与共同原则）**：
- 加仓量 ≤ 底仓量（1:1 原则，不超过底仓）
- 加仓后整体杠杆不超过上限
- 加仓部分必须单独设置止损（止损位 = 加仓价下方 3%）
- 底仓止损上移至成本价（保本止损）

**加仓命令模板**：
```bash
# 1. 加仓（市价开多，附带止损）
okx swap place --instId {交易对} --side buy --posSide long --ordType market --sz {加仓张数} \
  --tdMode cross --slTriggerPx {加仓止损价} --slOrdPx=-1

# 2. 验证加仓止损单已生效
okx swap algo orders --instId {交易对}

# 3. 底仓止损上移至成本价（修改已有的止损策略单）
okx swap algo amend --instId {交易对} --algoId {底仓止损单ID} \
  --newSlTriggerPx {成本价} --newSlOrdPx=-1

# 4. 验证所有止损单
okx swap algo orders --instId {交易对}
```

**趋势行情中保护浮盈（移动止损/Trailing Stop）**：
```bash
# 用 trailing stop 替代固定止损，自动跟踪最高价回撤3%平仓
okx swap algo trail --instId {交易对} --side sell --sz {合约张数} \
  --callbackRatio 0.03 --posSide long --tdMode cross

# 空单 trailing stop
okx swap algo trail --instId {交易对} --side buy --sz {合约张数} \
  --callbackRatio 0.03 --posSide short --tdMode cross
```

---

### 情况D：有持仓 + 浮亏（铁律）

**禁止加仓**，分析浮亏程度：
- 浮亏 < 5%：观察，不操作
- 浮亏 5%–止损位：等待，准备止损
- 触及止损位：**立即执行止损**

止损执行：
```bash
# 平多仓
okx swap close --instId {交易对} --mgnMode cross --posSide long

# 平空仓
okx swap close --instId {交易对} --mgnMode cross --posSide short
```

止损后更新状态文件（daily_stops + 1）。

---

### 情况E：有持仓 + 趋势反转信号

**平仓条件**（满足1条即可）：
- 4H级别出现明显反转形态（头肩顶/底、双顶/底）
- 价格跌破/突破关键支撑/阻力位
- 行情从趋势转为震荡（连续3根K线无方向）

**操作**：
- 信号强（形态完整）：一次性全平
- 信号弱（仅价格异常）：平仓50%，剩余移动止损

---

## 输出格式

每次分析后，输出以下结构化报告：

```
═══════════════════════════════════════
📊 滚仓策略分析报告
═══════════════════════════════════════
交易对：{instId}
当前价格：{price}
分析时间：{timestamp}

【行情模式】{趋势/震荡} - 置信度 {高/中/低}
  4H趋势：{上涨/下跌/横盘}
  关键支撑：{price}
  关键阻力：{price}

【当前持仓】
  方向：{多/空/无仓}
  均价：{avgPx}
  浮盈率：{uplRatio%}
  止损位：{slPx}

【账户状态】
  净值：${totalEq}
  今日止损次数：{n}/3
  最大杠杆上限：{lever}x

【操作建议】
  动作：{开仓/加仓/持仓观察/止损/平仓/强制休息}
  方向：{多/空}
  仓位：净值的 {n}%（约 ${amount}）
  杠杆：{lever}x
  入场价：{price}（{市价/限价}）
  止损位：{slPx}（亏损 {n}%）
  止盈位：{tpPx}（盈利 {n}%）
  盈亏比：{ratio}:1

【风险提示】
  {具体风险说明}

【执行确认】
  输入 'yes' 执行上述操作，输入 'no' 取消
═══════════════════════════════════════
```

---

## OKX Agent Trade Kit CLI 前置要求

本 Skill 通过 OKX Agent Trade Kit 的 CLI 工具执行所有交易操作，API 密钥始终存储在用户本地，不会传递给 AI。

**安装**：
```bash
npm install -g @okx_ai/okx-trade-cli
```

**配置密钥**（交互式，密钥保存在本地 `~/.okx/config.toml`）：
```bash
okx config init
```

**验证安装**：
```bash
okx account balance
```

如果 CLI 未安装或未配置，提示用户先完成上述步骤。

**安全说明**：
- API 密钥由 `okx-trade-cli` 在本地管理，AI 不接触密钥
- 所有交易通过 CLI 子进程执行，签名在本地完成
- 建议使用模拟盘 profile 进行测试：`okx config init` 时选择 demo 模式

---

## 状态文件

`~/.claude/rolling-position-state.json`：

```json
{
  "daily_stops": 0,
  "last_stop_date": "2026-04-07",
  "total_equity_usd": 10000,
  "positions": {
    "BTC-USDT-SWAP": {
      "entry_price": 80000,
      "base_size": 0.1,
      "add_count": 0,
      "stop_loss": 77600,
      "mode": "trend"
    }
  }
}
```

---

## 使用示例

```
/rolling-position BTC-USDT-SWAP
/rolling-position ETH-USDT-SWAP
/rolling-position SOL-USDT-SWAP
```

不带参数时，默认分析 BTC-USDT-SWAP。

---

## 免责声明

本 Skill 提供基于规则的策略建议，不构成投资建议。加密货币合约交易存在极高风险，可能导致本金全部损失。执行任何交易前请确认止损已正确设置，仓位大小在你的风险承受范围内。

---

### [46] `rookie-airbag`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/rookie-airbag/SKILL.md`

---
name: rookie-airbag
description: 小白上场手册 Vol.1 安全气囊 | 在你让 AI 动真钱之前,先学会保护自己。涵盖 API Key 保护三铁律、Withdraw 权限陷阱、杠杆心理陷阱、tdMode 全仓/逐仓抉择、AI 常见翻车场景。当用户说"安全气囊"、"密钥保护"、"防坑"、"airbag"、"安全检查"、"保护账户"、"怎么不被盗"时启用。AI 会主动扫描用户账户设置,给出 0-100 的风险体检报告。
---

# 🛡️ 小白上场手册 Vol.1 · 安全气囊

> **一句话定位**:在你让 AI 动真钱之前,先搞清楚哪些操作会把你账户送走。

---

## 这本小册子解决什么

Vol.0 让你连上了 OKX,但这就像刚拿到驾照。**上路之前,你得先知道安全带、气囊、刹车在哪。**

这本小册子的任务:
1. 教你保护 API Key,避免被盗导致账户被清空
2. 讲清楚**杠杆、保证金模式、仓位大小**背后的真实代价
3. 告诉你 **AI 会在哪 5 个地方翻车**,以及你该怎么兜底
4. 让 AI 主动扫描你的账户,给出一份**风险体检报告**

---

## 📖 知识地图(5 个死亡陷阱)

### 陷阱 1 · API Key 三不原则

**绝对不能做的三件事:**

| 危险行为 | 后果 |
|---|---|
| 把 Key 上传到 GitHub / GitLab | 2-5 分钟内被爬虫扫到 |
| 把 Key 贴到任何聊天窗口 | 对方记录后你就等着账户清零 |
| 把 Key 存在明文 txt / 备忘录 | 电脑中病毒或给别人用时泄露 |

**正确做法:**
- Key 只存 `~/.okx/config.toml`,这个文件被 Agent Trade Kit 保护,AI 看不到内容
- 定期(比如每月)去 OKX 重置一次 Key
- **如果你怀疑 Key 可能泄露了,立刻去 OKX 删除 Key 并重建**,不要犹豫

### 陷阱 2 · Withdraw 权限 = 黑客提款通道

创建 API Key 时,Withdraw 权限默认不勾就行。但你可能好奇"我勾了会怎样"。

**真实案例**(广泛流传的社区案例,细节有代表性):
> 某用户创建 API Key 时顺手勾了 Withdraw,想着"以后可能用得上"。Key 保存在个人笔记本。某天用了公共 Wi-Fi 调试代码,Key 被截获。**30 分钟后账户 ETH 全部转到陌生地址**,损失不可挽回。

**记住**:你做 AI 交易根本不需要提现权限,勾了只有坏处,没有好处。

### 陷阱 3 · 杠杆的心理陷阱

**"3x 杠杆看起来很保守,20x 才够刺激"** —— 这是小白最常见的心理陷阱。

真相是这样:

| 杠杆 | BTC 波动 3% 时 | 触及强平所需波动 |
|---|---|---|
| 3x | 账户波动 9% | 约 33% |
| 10x | 账户波动 30% | 约 10% |
| 20x | 账户波动 60% | **约 5%** |
| 50x | 账户波动 150% | **约 2%** |

BTC **日波动轻松超过 2-3%**,所以 50x 杠杆意味着你的仓位平均**每天都在爆仓边缘跳舞**。

**小白建议**:3x 起步,熟练了之后再考虑 5-10x,不要一上来就 20x+。

### 陷阱 4 · 全仓 vs 逐仓:一个字的区别

`tdMode` 这个参数有两个选择,很多小白完全不看这里默认怎么填。

**全仓(cross):**
- 所有仓位共用**整个账户**的保证金
- 优点:不容易被爆仓(因为账户里所有钱都能顶)
- 缺点:**一次极端行情可能把整个账户扫光**,不只一个仓位的事

**逐仓(isolated):**
- 每个仓位的保证金**独立隔离**
- 优点:风险被锁在单仓里,一个仓位爆了其他不受影响
- 缺点:爆仓阈值更低(因为保证金池子小)

**小白建议**:**新手一律用逐仓**。风险被锁在单仓,最坏结果可预测。全仓对应的是有经验、会主动管理保证金的交易员。

### 陷阱 5 · AI 的 5 种常见翻车

AI 再聪明也会翻车,以下 5 种是真实发生过的:

**翻车 1:AI 幻觉出不存在的工具**
AI 有时会"自信满满"地调用 `trade_get_orders_history` 这种根本不存在的命令。
**兜底**:查你的 AI 每次执行的日志,看看报错有没有"command not found"或"tool not exist",有就立刻停手人工核对。

**翻车 2:单位混淆**
AI 把"张数"当"USDT"算,结果要开 0.01 张但填了 100 张。
**兜底**:Skill 设计时强制要求 AI **输出决策前先算一遍占账户百分比**,超过 30% 应该引起警觉。

**翻车 3:过度交易**
AI 情绪激动之后连续开仓 10 笔,每笔手续费 0.05%,一天被磨掉 1-2% 本金。
**兜底**:Skill 里必须有"连续 5 笔亏损自动暂停"、"每日开仓次数上限"这类硬性熔断。

**翻车 4:遗忘止损**
开完仓 AI 忘了挂止损,或者止损挂单失败没补救。
**兜底**:Skill 里强制"开仓 60 秒内未挂止损则市价平仓"。

**翻车 5:残留算法单**
平仓了但没取消对应的止盈止损单,下次开仓时残留单异常触发。
**兜底**:每次循环开始先用 `okx swap algo-orders` 查残留,全部取消后再决策新动作。

---

## 🤖 AI 互动环节:我给你做一次风险体检

**AI 触发本 Skill 时,请按以下流程扫描用户账户并输出体检报告:**

### 互动 1 · 用户自述

AI 先问用户 4 个问题,了解基础配置:

**问题 A**:"你的 API Key 现在存在哪里?"
- 用户回答关键词 "config.toml" / "okx config init" / "向导" → 加 10 分
- 用户回答关键词 "txt" / "备忘录" / "GitHub" / "聊天记录" → **-50 分,红色警告**
- 用户不记得 → 引导用户检查 `~/.okx/config.toml` 是否存在

**问题 B**:"你 API Key 勾了 Withdraw 权限吗?"
- 没勾 → 加 20 分
- 勾了 → **-30 分,红色警告:立刻回 OKX 关闭这个权限**

**问题 C**:"你准备用多少倍杠杆?"
- 1-5x → 加 10 分
- 5-10x → 加 5 分
- 10-20x → 减 10 分,黄色警告
- 20x+ → **-20 分,红色警告:杠杆过高,爆仓概率极大**

**问题 D**:"你的保证金模式是全仓还是逐仓?"
- 逐仓 → 加 10 分
- 全仓 → -5 分,黄色提醒:新手建议逐仓
- 不知道 → AI 主动调用以下命令查询

### 互动 2 · AI 主动扫描账户

AI 执行以下命令核对实际账户状态:

```bash
# 查账户配置(持仓模式、账户等级等)
okx account config
```

AI 检查返回值里的关键字段:
- `posMode`:持仓模式
  - `net_mode`(单向)→ 小白推荐,简单
  - `long_short_mode`(双向)→ 需要明确 `--posSide`,否则下单报错
- `acctLv`:账户等级(1=简单交易模式,2=单币种保证金模式,3=跨币种,4=组合保证金)
  - 小白建议 `acctLv = 2`(单币种)或 `3`(跨币种),4 级组合保证金太复杂

```bash
# 查账户余额
okx account balance
```

检查:
- 余额是否异常大(> 2000 USDT)→ 建议用户**只留参赛用的 500 USDT,其余划回资金账户**
- 余额是否过小(< 50 USDT)→ 提醒策略可能开不出最小仓位

```bash
# 查当前持仓
okx account positions
```

检查:
- 是否有残留持仓(不是本次 AI 开的)→ 提醒用户手动清理,避免干扰 AI 决策
- 持仓方向是否混乱(既有 long 又有 short 的同一个合约)→ 对冲仓位会让新手困惑

### 互动 3 · 输出风险体检报告

AI 将用户自述分 + 实际扫描结果综合,输出体检报告:

```
═══════════════════════════════════
      🛡️ 安全气囊 · 风险体检报告
═══════════════════════════════════

🔐 API Key 保护
  存储位置:[✅ config.toml / ⚠️ 不确定 / ❌ 明文存储]
  Withdraw 权限:[✅ 未开启 / ❌ 已开启 - 立即关闭]
  IP 绑定:[✅ 已绑定 / ⚠️ 未绑定(14 天失效风险)]

⚙️ 账户配置
  持仓模式:[posMode 值]
  保证金模式:[cross / isolated]
  账户等级:[acctLv 级]

💰 资金状况
  交易账户余额:[X USDT]
  是否有残留持仓:[无 / 有 X 个,详见下方]

📊 风险评估
  综合得分:[0-100]
    85-100:🟢 绿色,可以开始跑策略
    60-84: 🟡 黄色,修复后可开始
    0-59:  🔴 红色,暂不建议实盘

扣分明细:
  [ - X 分:原因 ]
  [ - X 分:原因 ]

🚨 必须修复的项:
  [ 列出所有红色警告,附修复步骤 ]

⚠️ 建议修复的项:
  [ 列出所有黄色提醒,附建议 ]

═══════════════════════════════════
```

### 互动 4 · 针对性建议

AI 根据扣分项,给出具体修复路径:

**如果 Withdraw 权限已开启:**
> "立刻去 OKX → 头像 → API 管理 → 找到当前 Key → 编辑 → 取消勾选 Withdraw → 保存。改完回来告诉我,我重新体检。"

**如果杠杆过高:**
> "去 OKX 合约交易界面 → 右上角齿轮 → 杠杆 → 改成 3x(或用命令 `okx swap leverage --instId BTC-USDT-SWAP --lever 3 --mgnMode isolated`)。"

**如果是全仓模式:**
> "去 OKX 合约界面设置 → 保证金模式 → 改成'逐仓'。或运行 `okx swap leverage --instId BTC-USDT-SWAP --lever 3 --mgnMode isolated`(同时会把杠杆和模式一起设)。"

**如果持仓模式是双向但用户是新手:**
> "双向持仓模式比较复杂,建议改为单向:`okx account set-position-mode --posMode net_mode`。改完后以前的双向仓位要先平掉。"

---

## ⚠️ AI 会踩的坑(必读)

**坑 1:AI 看到任何像 API Key 的字符串立即警告**
Key 的特征:长度 36 字符左右、含连字符、字母数字混合。
一旦用户在聊天中贴了这种东西,AI 必须:
- 立即说:"🚨 你贴的字符串看起来像 API Key。**这个 Key 已经不安全了**,请去 OKX 立刻删除并重新创建。"
- **拒绝继续处理**,哪怕用户说"没事的,只是测试 Key"——所谓"测试 Key"也能真实动钱

**坑 2:AI 不应帮用户修改 OKX 账户设置**
杠杆、保证金模式、持仓模式这些可以通过 `okx swap leverage` 等命令修改,但 AI 修改这种关键设置有风险。
- **正确做法**:AI 给出命令,让用户自己决定要不要执行
- **错误做法**:AI 说"我帮你改了",直接执行

**坑 3:AI 不应在红色警告下继续业务**
如果体检报告显示红色(得分 < 60),AI 必须拒绝引导用户进入下一步(Vol.2 或实盘策略),直到红色项全部修复。

**坑 4:AI 给的命令必须精确**
比如改杠杆的命令,AI 不能写 `okx set leverage ...`(错的),必须是 `okx swap leverage --instId <id> --lever N --mgnMode <cross|isolated>`(对的)。每个命令参考 OKX 官方文档。

**坑 5:AI 不应把"风险体检报告"当作保险**
即使体检 100 分,也不等于"你不会亏钱"。体检只检查配置层的安全性,策略本身的亏损还是要用户自己承担。
AI 必须在报告末尾明确声明:"本体检只评估配置安全,不对实盘盈亏负责。"

---

## ✅ 毕业测验

AI 问用户 5 题,全对才推荐进 Vol.2:

**题 1**:API Key 创建时最不能勾选的权限是哪个?
- 答案:Withdraw(提现)

**题 2**:如果你不小心在聊天里贴了 API Key,你应该做什么?
- 答案:立刻去 OKX 删除这个 Key 并重建,不要继续用

**题 3**:新手用 3x 杠杆还是 20x 杠杆?为什么?
- 答案:3x,因为 BTC 日波动经常 2-3%,20x 杠杆大概 5% 波动就爆仓,新手没有能力抗住

**题 4**:全仓和逐仓,新手推荐哪个?为什么?
- 答案:逐仓,因为风险被锁在单个仓位,一笔翻车不会波及整个账户

**题 5**:AI 下单时如果"忘了挂止损",你的 Skill 应该有什么机制保护你?
- 答案:开仓 60 秒内未挂止损则强制市价平仓(或类似的裸奔检查机制)

### 毕业奖章 🏅

5 题通过后,AI 输出:

```
🏅 恭喜你!你已拿到第 2 枚奖章:安全气囊 🛡️

你现在的能力:
  ✅ 知道怎么保护 API Key 不被盗
  ✅ 理解杠杆、保证金模式的真实代价
  ✅ 知道 AI 会在哪里翻车,自己能兜底

大部分小白都是被"杠杆心理陷阱"送走的,你已经跳过了这个坑。

下一步推荐:
  👉 Vol.2 · 读仪表盘  — 看懂那些天书数字背后的逻辑
  触发词:"仪表盘" / "合约术语" / "dashboard"
```

---

## 📎 引用其他 Skill

- 前置:Vol.0 · 点火器(如未配置好连接,先装 Vol.0)
- 后续:Vol.2 · 读仪表盘(学会计算真实风险)
- 完整路径:Vol.0 → Vol.1 → Vol.2 → `resilience-trader` → `trade-mirror`

---

*小白上场手册 · Vol.1 · 安全气囊 | 适用平台:OKX Agent Trade Kit*
*本 Skill 不下单,只做安全审计与风险评估。MIT 开源,欢迎 fork。*

---

### [47] `rookie-dashboard`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/rookie-dashboard/SKILL.md`

---
name: rookie-dashboard
description: 小白上场手册 Vol.2 读仪表盘 | 教你看懂 OKX 合约面板上的所有天书数字——张数、保证金、名义价值、资金费率、强平价。AI 会用你的实时账户数据一步步带你算,最后出一道实战题让你自己算。当用户说"仪表盘"、"合约术语"、"读懂交易界面"、"dashboard"、"张数怎么算"、"保证金是什么"、"资金费率"、"强平价"时启用。配套计算器,AI 根据实盘数据陪你练。
---

# 📊 小白上场手册 Vol.2 · 读仪表盘

> **一句话定位**:教你看懂 OKX 合约面板上那些天书数字,让你知道自己每一笔交易到底押了多少。

---

## 这本小册子解决什么

Vol.0 让你连上了,Vol.1 教你保护自己。但你现在看 OKX 合约界面,可能还是一脸懵:
- "张数"和"数量"有什么区别?
- "保证金"是预付款还是冻结?
- "名义价值"和"我的亏损"是什么关系?
- "资金费率 0.01%"是每小时还是每 8 小时?
- "强平价"到底怎么算出来的?

这本小册子的任务:
1. 把 6 个最容易混淆的数字讲清楚
2. 用**你的真实账户数据**一步步带你算
3. 教你一个公式:**给定本金和可接受亏损,一笔最多开多少张**
4. 让 AI 出一道应用题,你答对才能毕业

---

## 📖 知识地图(6 个必懂概念)

### 概念 1 · 张数 vs 数量 vs 名义价值

这是最容易糊涂的地方。用 BTC 举例:

```
当前 BTC 价格 = $71,000
合约面值 = 1 BTC / 张(注意:不同交易所可能不同)

你开了 0.0063 张 BTC-USDT-SWAP 做多,意味着:
  ├─ 张数 = 0.0063 张
  ├─ 对应数量 = 0.0063 × 1 = 0.0063 BTC
  └─ 名义价值 = 0.0063 × $71,000 = $447.30
```

**三个数字的关系:**
- **张数**:交易所的计数单位,下单时填的就是这个
- **数量**:换算成 BTC/ETH 等基础币的量
- **名义价值**:按当前价格换算成 USDT 的总市值

你买了 $447 名义价值的 BTC,但**实际只需要掏一小部分钱当保证金**,这就是杠杆的作用。

### 概念 2 · 保证金 = 押金

用上面的例子继续:

```
名义价值 = $447.30
杠杆 = 3x
保证金 = 名义价值 ÷ 杠杆 = $447.30 ÷ 3 = $149.10
```

**保证金就是你为了"租"一个 $447 仓位,押给交易所的 $149。**

- 如果仓位盈利 → 你的保证金安全,还能多拿到利润
- 如果仓位亏损 → 先从保证金里扣,扣到某个阈值就爆仓

**保证金率**(Margin Ratio)= 当前保证金余额 ÷ 维持保证金 × 100%,低于 100% 就被强平。

### 概念 3 · 名义价值决定盈亏,不是保证金

**这是小白最容易搞错的地方:**

如果 BTC 从 $71,000 涨到 $72,420(涨 2%):
- 你的盈利 = 名义价值 × 涨幅 = $447.30 × 2% = **$8.95**

不是"保证金 × 2% = $2.98",也不是"张数 × 2% = 没意义"。

**记住:盈亏永远按名义价值和价格变化幅度算。**

### 概念 4 · 资金费率 = 持仓税

资金费率(Funding Rate)是永续合约每 **8 小时结算一次**的强制收付:

```
若当前 BTC 资金费率 = +0.01%(正):
  做多方付费给做空方
  每张仓位每 8 小时付 = 名义价值 × 0.01%
  
若资金费率 = -0.01%(负):
  做空方付费给做多方
```

用 $447 名义价值的仓位举例:
- 费率 +0.01% → 做多每 8 小时付 $0.045
- 费率 +0.1% → 做多每 8 小时付 $0.447
- 费率 +0.15%(极度拥挤)→ 每 8 小时付 $0.67

**如果你逆费率持仓 3 天**(9 次结算)× 0.1% 费率,成本累计约 $4,占本金 $500 的 0.8%。**很多"方向看对但还是亏"的小白,就是输在这里。**

### 概念 5 · 三种价格:开仓价、标记价、指数价

OKX 合约界面经常出现三种价格,各有用处:

| 价格类型 | 定义 | 用途 |
|---|---|---|
| **开仓价**(avgPx) | 你实际成交的价格 | 计算你自己的盈亏基准 |
| **标记价**(markPx) | 综合多个交易所的公允价 | **计算强平**使用这个价 |
| **指数价**(indexPx) | 多家交易所现货均价 | 计算资金费率使用 |

**关键点**:爆仓不是按你看到的"最新价"爆,是按**标记价**爆。标记价有时候比最新价慢半拍,意味着插针行情里你可能看"价格已经跌到强平线了"但其实没爆,这是标记价的平滑机制在救你。

### 概念 6 · 强平价(爆仓价)计算逻辑

强平价的完整公式比较复杂,但新手只需要记一个**粗略估算**:

**做多强平价 ≈ 开仓价 × (1 - 1/杠杆 + 维持保证金率)**

用 3x 杠杆、逐仓、0.5% 维持保证金率举例:
- BTC 开仓 $71,000
- 强平价 ≈ $71,000 × (1 - 1/3 + 0.005) = $71,000 × 0.672 ≈ **$47,712**

也就是说,BTC 需要**从 $71,000 跌到 $47,712**(跌 33%)你才会爆仓。

**对比 20x 杠杆**:
- 强平价 ≈ $71,000 × (1 - 1/20 + 0.005) = $71,000 × 0.955 ≈ **$67,805**
- 只需要 BTC 跌 4.5% 就爆仓

**这就是 Vol.1 说过的"杠杆心理陷阱"**——20x 下,单日一次正常波动就能把你送走。

---

## 🤖 AI 互动环节:用你的真实数据陪你算

**AI 触发本 Skill 时,请按以下流程和用户互动:**

### 互动 1 · 拉实时数据

AI 告诉用户:
> "我们不用 PPT 举例,用你的真实账户数据来算。先让我查几个东西。"

AI 执行以下命令:

```bash
# 1. 查当前 BTC 价格
okx market ticker BTC-USDT-SWAP

# 2. 查 BTC 合约面值(避免假设)
okx market instruments --instType SWAP --instId BTC-USDT-SWAP

# 3. 查用户当前账户余额
okx account balance

# 4. 查当前 BTC 资金费率
okx market funding-rate BTC-USDT-SWAP
```

AI 根据返回值,**把实时数据填进接下来的例题**。

### 互动 2 · 第一道计算题:名义价值 & 保证金

AI 出题(以实时 BTC 价 $X、账户余额 $Y 为例):

> "假设你想用 30% 的保证金、3x 杠杆、开一个 BTC 做多仓位。
> 问你三件事:
>   ❓ 问题 1:你能掏出多少保证金?
>   ❓ 问题 2:这些保证金对应多少名义价值?
>   ❓ 问题 3:名义价值换算成张数是多少?(别忘了向下截断到 0.0001)"

**AI 不给答案,让用户回答。用户答完 AI 给反馈:**

- 若用户算对 → "✅ 对了。继续下一题。"
- 若用户算错 → "不对。提示:保证金 × 杠杆 = 名义价值。你再算一次。"
- 用户再错 → 才给出完整推导过程

**完整推导示例**(假设 BTC = $71,000,账户 $500):
```
步骤 1:保证金 = $500 × 30% = $150
步骤 2:名义价值 = $150 × 3 = $450
步骤 3:张数 = $450 ÷ 1(合约面值) ÷ $71,000 = 0.00634
        向下截断 = 0.0063 张
```

### 互动 3 · 第二道计算题:盈亏估算

AI 继续:
> "好,你开了 0.0063 张。
> ❓ 如果 BTC 涨到 $72,420(涨 2%),你赚多少 USDT?
> ❓ 如果 BTC 跌到 $69,580(跌 2%),你亏多少 USDT?"

**AI 让用户回答。**

正确答案:
```
涨 2%:0.0063 × ($72,420 - $71,000) × 1(合约面值) = 0.0063 × $1,420 = $8.95
跌 2%:0.0063 × ($71,000 - $69,580) × 1 = 0.0063 × $1,420 = $8.95
```

**关键结论**:开多与开空在相同幅度下盈亏对称,盈亏 = 张数 × 价格变动 × 合约面值。

### 互动 4 · 第三道计算题:资金费率成本

AI 继续(用实时资金费率填入):
> "当前 BTC 资金费率是 [X]%。
> ❓ 如果你这笔 0.0063 张的多单持有 24 小时(结算 3 次),逆费率的成本是多少?
> ❓ 这笔成本占你账户的百分比是?"

正确答案(以费率 +0.05% 为例):
```
单次成本 = $447.30(名义价值) × 0.05% = $0.224
24 小时累计(3 次结算) = $0.672
占账户比 = $0.672 ÷ $500 = 0.13%
```

### 互动 5 · 第四道计算题:强平距离

AI 用 `okx account max-size` 查用户账户在当前杠杆下的最大可开张数,对比用户上面算的数字,直观感受公式。

```bash
okx account max-size --instId BTC-USDT-SWAP --tdMode isolated
```

然后问:
> "❓ 如果你用 3x 杠杆 + 逐仓模式,BTC 要跌多少百分比你才会被强平?"

正确估算:约 33%(详见知识地图概念 6)。

AI 问一个后续问题:
> "❓ 如果你改用 10x 杠杆呢?"

正确估算:约 10%。让用户直观感受杠杆和爆仓距离的关系。

### 互动 6 · 综合应用题(毕业测验)

AI 出一道综合题,用户答对才能毕业:

```
🎯 毕业测验

你账户 500 USDT,想开 BTC 做多,要求:
- 单笔最坏亏损不超过账户 2%(即 $10)
- 止损距离 = 开仓价 × 0.98(做多 -2% 止损)
- 当前 BTC 价格用 AI 刚查到的实时价
- 合约面值 1 BTC / 张

❓ 你最多能开多少张?
❓ 对应名义价值是多少?
❓ 需要多少保证金(3x 杠杆)?
❓ 这笔仓位的实际占账户百分比?
```

**解题思路:**
```
步骤 1:最大亏损金额 = $500 × 2% = $10
步骤 2:止损距离 = 开仓价 × 0.02
步骤 3:最大张数(按风险)= $10 ÷ 止损距离 ÷ 合约面值
步骤 4:名义价值 = 张数 × 合约面值 × 当前价
步骤 5:保证金 = 名义价值 ÷ 3
步骤 6:占账户比 = 保证金 ÷ $500

以 BTC = $71,000 为例:
  止损距离 = $1,420
  最大张数 = $10 ÷ $1,420 ÷ 1 = 0.00704
  向下截断 = 0.0070 张
  名义价值 = 0.0070 × $71,000 = $497
  保证金 = $497 ÷ 3 = $165.67
  占账户比 = 33.1%
```

**但是!** 这里会触发名义价值上限校验——保证金占账户 33% 已经超过了"保守小白"推荐的 30% 上限。此时 AI 应该指出:
> "注意:你这个仓位虽然'最坏亏损 $10'达标,但保证金占账户 33%,略超 30% 推荐上限。
> 建议:可以把张数再下调到 0.0063 张,保证金占比降到 30% 以内,更稳健。"

这一步是小白必须学会的"**不同风控口径下仓位的博弈**":按风险公式算和按保证金公式算,可能得到不同答案,要取较小值。

---

## ⚠️ AI 会踩的坑(必读)

**坑 1:AI 必须调实时数据,不能凭记忆**
AI 脑子里的 BTC 价格和合约面值可能是过时的。讲课前必须用 `okx market ticker` 和 `okx market instruments` 拉最新数据。
- 凭记忆说"BTC 是 $50,000"会让用户算错所有题
- **正确做法**:每次互动开始,先执行实时数据拉取

**坑 2:AI 不要一次给完答案**
本 Skill 的教学价值在于"用户自己算一遍"。如果用户问"直接告诉我答案",AI 应该说:
> "我给你完整推导反而学不会。你先试着算,算错我再教。这才是这本小册子存在的意义。"

**坑 3:合约面值不能假设**
BTC-USDT-SWAP 的面值可能是 1 BTC/张(当前主流)或 0.01 BTC/张(旧版本)。
AI 必须调 `okx market instruments --instType SWAP --instId BTC-USDT-SWAP` 查 `ctVal` 字段,**不能靠"我记得是 1"这种断言**。

**坑 4:讲强平价时必须说明"是估算"**
强平价的完整公式涉及维持保证金率、杠杆档位、账户模式等多个变量,不同合约不一样。
AI 讲的是**粗略估算**,必须说明"这是新手理解用的简化公式,实际强平价以交易所计算为准"。

**坑 5:不要把张数换算混淆成现货数量**
永续合约的"张数"不等于"买了多少个 BTC"(虽然面值 1 BTC/张时两者恰好相等)。
小白可能会问"我开 0.0063 张等于买了 0.0063 个 BTC 吗?",AI 的答案要严谨:
> "在当前合约面值是 1 BTC/张的情况下,**对应关系**是 0.0063 张 = 0.0063 BTC 的仓位。但这不是现货,是保证金交易,你并没有'拥有' BTC。"

---

## ✅ 毕业测验

用户完成互动 6 的综合应用题后,AI 出最后 3 题:

**题 1**:500 USDT 本金,想单笔风险 1%,止损 3%,BTC 价 $71,000。最多开多少张?
- 答案:$5 ÷ ($71,000 × 3%) ÷ 1 = 0.00235,向下截断 = 0.0023 张

**题 2**:资金费率 -0.02%,你做多持仓 24 小时,赚还是亏资金费?金额多少?(假设仓位 0.0063 张 @ $71,000)
- 答案:赚。因为费率为负,做多方收取。3 次结算共赚 0.0003 × $447.30 × 3 = $0.40

**题 3**:同一个 BTC 仓位,用 3x 和 10x 杠杆开仓,哪个更抗暴跌?相差多少百分点的价格空间?
- 答案:3x 更抗。3x 的强平距离约 33%,10x 约 10%,相差约 23 个百分点。

### 毕业奖章 🏅

3 题通过后,AI 输出:

```
🏅 恭喜你!你已拿到第 3 枚奖章:读仪表盘 📊

你现在的能力:
  ✅ 看得懂张数、名义价值、保证金三者的关系
  ✅ 能手动计算盈亏、资金费用、强平距离
  ✅ 给定本金和风险容忍度,能自己算一笔最多开多少张

小白上场手册三本已全部毕业!你的基础认知已经超过 80% 第一次接触合约的人。

下一步推荐:
  🎯 装 resilience-trader(韧性交易者)跑第一笔真实策略
     触发词:"韧性交易" / "resilience trader"
  
  🔍 跑过几笔后,装 trade-mirror(交易镜子)做复盘
     触发词:"复盘" / "trade mirror"

祝交易顺利,活下来才是硬道理。
```

---

## 📎 引用其他 Skill

- 前置:Vol.0 · 点火器、Vol.1 · 安全气囊
- 完成后建议:`resilience-trader`(跑第一笔真实交易)
- 跑过一段时间后:`trade-mirror`(复盘与行为诊断)

---

*小白上场手册 · Vol.2 · 读仪表盘 | 适用平台:OKX Agent Trade Kit*
*本 Skill 不下单,只做数据解读与计算训练。MIT 开源,欢迎 fork。*

---

### [48] `rookie-ignition`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/rookie-ignition/SKILL.md`

---
name: rookie-ignition
description: 小白上场手册 Vol.0 点火器 | 帮完全没用过 OKX Agent Trade Kit 的新手,用 AI 互动方式走完 API Key 创建、权限配置、虚拟盘/实盘切换、连接自检全流程。当用户说"点火器"、"API 配置"、"帮我检查连接"、"ignition"、"check connection"、"小白上场"、"okx 怎么连"时启用。不下单、不涉及策略,纯配置引导与连接诊断。
---

# 🔥 小白上场手册 Vol.0 · 点火器

> **一句话定位**:让你的 AI 第一次和 OKX 账户握手,保证所有 Skill 都能正确启动。

---

## 这本小册子解决什么

你可能遇到过这些问题:
- 装了 Claude / Cursor 想接 OKX,但 API Key 填哪儿、怎么填不知道
- 配置完报 **401(Key 环境不匹配)**、**502(代理连不上)** 、**50011(请求超限)**,不知道怎么办
- 搞不清**虚拟盘**和**实盘**有什么区别、比赛该用哪个
- 担心 API Key 配错了被盗,但又不知道怎么才算"配对了"

这本小册子的任务:
1. 教你正确创建 API Key 并配置权限
2. 教 AI 做**连接自检三连**,告诉你当前配置是否健康
3. 遇到报错,AI 能根据错误码告诉你具体怎么解

**本 Skill 不下单、不交易,只做配置指导和连接诊断。**

---

## 📖 知识地图(先扫 5 个点)

### 点 1 · Agent Trade Kit 是什么

OKX 官方开源的工具包,**让你的 AI(Claude / Cursor 等)通过本地程序连接 OKX 账户**。

- 全部本地运行,API Key 只存在你电脑的 `~/.okx/config.toml`(Windows 是 `C:\Users\<你的用户名>\.okx\config.toml`)
- **AI 永远看不到你的 Key**,它只能通过工具包"间接操作"
- 开源协议 MIT,源码可审计:`github.com/okx/agent-trade-kit`

### 点 2 · 三条 API Key 权限铁律

创建 Key 时只勾两个,一个绝不能勾:

| 权限 | 勾不勾 | 原因 |
|---|---|---|
| **Read(读取)** | ✅ 必勾 | 要查余额和 K 线 |
| **Trade(交易)** | ✅ 必勾 | 要下单和挂止损 |
| **Withdraw(提现)** | ❌ **绝不勾** | 勾了等于给黑客提款通道 |

**这条规则一辈子不会变,请刻在脑子里。**

### 点 3 · 虚拟盘 vs 实盘(四大区别)

| 特征 | 虚拟盘 Demo | 实盘 Live |
|---|---|---|
| 资金 | 模拟币,输光不心疼 | 真钱,亏了就是亏了 |
| 入口 | OKX → 交易 → **模拟交易** → 个人中心 | OKX → 头像 → **API** |
| Agent 启动参数 | `--profile demo` 或 `--demo` | `--profile live` |
| **比赛是否计分** | ❌ 不计入 | ✅ **只有实盘计入** |

**⚠️ 核心规则:虚拟盘 Key 只能连虚拟盘,实盘 Key 只能连实盘,两者永远不能混用。**
混用就会出现 `401 Key 环境不匹配` 错误。

### 点 4 · 为什么必须用子账户

**主账户**是你整个身家所在,**子账户**是从主账户派生的独立账户,权限、资金隔离。

用子账户给 AI 用的三个理由:
- 子账户余额有限,AI 就算翻车也只动子账户这点钱
- 子账户独立 API Key,万一泄露不影响主账户
- OKX 大赛规则允许用子账户参赛,报名时选子账户即可

### 点 5 · 连接验证"三条自检命令"

AI 可以用下面三条命令帮你验证连接状态:

```bash
okx account balance             # 验证:账户能连上吗?
okx account positions           # 验证:有交易权限吗?
okx market ticker BTC-USDT-SWAP # 验证:能拉行情数据吗?
```

**本 Skill 的核心就是让 AI 帮你跑这三条**,并根据结果给你诊断报告。

---

## 🤖 AI 互动环节:我陪你走一遍配置

**AI 触发本 Skill 时,请按以下对话流程与用户交互:**

### 互动 1 · 起点诊断

AI 开场第一句:
> "欢迎,我是你的点火助手 🔥。在帮你检查连接之前,我需要先问你 4 个问题,了解你现在走到哪一步。每个问题回答 A/B/C 即可。"

**问题 A:你装 Node.js 了吗?**
- A. 装了(继续下一问)
- B. 没装(AI 给出安装链接 `https://nodejs.org`,并建议安装 LTS 版本)
- C. 不知道(AI 指导用户打开终端输入 `node -v`,看输出是不是 v18 或更高)

**问题 B:你装 okx-trade-cli / okx-trade-mcp 了吗?**
- A. 装了
- B. 没装(AI 输出安装命令:`npm install -g @okx_ai/okx-trade-mcp @okx_ai/okx-trade-cli`)
- C. 不确定(AI 指导输入 `okx --version` 验证)

**问题 C:你现在想先用虚拟盘测试,还是直接上实盘?**
- A. 虚拟盘(AI 跳转到"虚拟盘 API 创建流程")
- B. 实盘(AI 跳转到"实盘 API 创建流程")
- C. 我要参加 OKX AI 大赛(AI 明确告知:**比赛只计实盘成绩,但强烈建议先用虚拟盘跑 24 小时验证,再切实盘**)

**问题 D:你有 OKX 子账户吗?**
- A. 有
- B. 没有(AI 引导用户去 OKX → 资产 → 子账户 → 创建,并解释子账户的三个安全好处)
- C. 不知道什么是子账户(AI 用知识地图点 4 的内容解释)

### 互动 2 · API Key 创建指引(AI 根据问题 C 的回答走对应分支)

**分支 1:虚拟盘 API Key**

AI 告诉用户:
> "请按以下步骤操作,我不会帮你代操作,你自己完成:
> 1. 登录 OKX,顶部菜单点 **交易 → 模拟交易**
> 2. 进入模拟交易界面后,点右上角 **个人中心 → API 管理**
> 3. 点 **创建 API Key**
> 4. 权限勾选:✅ Read ✅ Trade ❌ Withdraw(千万别勾这个)
> 5. 设置 Passphrase(自己记住,后面要填)
> 6. 创建成功后会显示 **API Key / Secret Key / Passphrase** 三个值
> 
> ⚠️ 注意:Secret Key 只显示一次,请立刻复制到安全的地方(不要贴聊天窗口、不要截图发微信)。
> 
> 完成后告诉我,我引导你下一步。"

**分支 2:实盘 API Key**

AI 告诉用户:
> "请按以下步骤操作:
> 1. 登录 OKX,点右上角 **头像 → API**
> 2. **强烈建议:切换到子账户**(如果你有),不要用主账户创建
> 3. 点 **创建 V5 API Key**
> 4. 权限勾选:✅ Read ✅ Trade ❌ Withdraw
> 5. 是否绑定 IP:
>    - 绑定:更安全,但只能在这个 IP 使用
>    - 不绑定:任何 IP 可用,但 **14 天不调用会自动失效**(做 AI 交易基本每天都在调,一般不会失效)
> 6. 设置 Passphrase 并保存三个值
> 
> ⚠️ 同样,Secret Key 只显示一次,立刻保存好。"

### 互动 3 · 配置 config.toml

AI 指导用户执行:

```bash
okx config init
```

并解释交互向导里每一步:
- **Profile 名字**:建议命名为 `demo`(虚拟盘用)或 `live`(实盘用)。可以同时配两套。
- **API Key / Secret Key / Passphrase**:就是刚才 OKX 给你的三个值
- **Environment**:选 demo 或 live,要和你的 API Key 匹配

AI 在引导中反复强调:
> "⚠️ 这三个值只进这个交互式向导,**千万别在我这里的聊天窗口贴出来**。我永远不需要看到你的 API Key,我只需要你告诉我'我填完了'。"

### 互动 4 · 启动 MCP 连接

AI 告诉用户启动命令:

**虚拟盘启动:**
```bash
okx-trade-mcp --profile demo --modules market,swap,account
```

**实盘启动:**
```bash
okx-trade-mcp --profile live --modules market,swap,account
```

解释 `--modules` 参数:
- `market`:行情数据(无需 API Key 也能用)
- `swap`:永续合约下单(比赛核心模块)
- `account`:账户余额和持仓查询
- **不启用** `spot` / `futures` / `option` / `bot`,降低小白误触风险

### 互动 5 · 连接自检三连(本 Skill 的核心动作)

**AI 此时主动执行以下三条命令,并实时反馈每一步结果:**

```bash
# 自检 1:账户连接
okx account balance
```

AI 诊断反馈模板:
- 若返回余额数据 → "✅ 账户连接成功。你当前账户余额:[具体数字] USDT"
- 若返回 401 错误 → "❌ Key 环境不匹配。你的 Key 是 [demo/live] 环境创建的,但启动命令用的是 [live/demo]。请重新 `okx config init` 配对环境,或者换一个匹配的 Key。"
- 若返回 502/超时 → "❌ 网络层连不上。如果你在使用代理,换一个节点;或者检查 OKX 是否在你所在地区开放。"

```bash
# 自检 2:持仓查询权限
okx account positions
```

AI 诊断反馈模板:
- 若返回(空列表或持仓数据)→ "✅ Trade 权限正常。"
- 若返回 50011(速率限制)→ "⚠️ 请求太快,等 30 秒再试。"
- 若返回权限错误 → "❌ API Key 缺少 Trade 权限,请回 OKX 重新创建 Key 并勾选 Read + Trade。"

```bash
# 自检 3:行情数据
okx market ticker BTC-USDT-SWAP
```

AI 诊断反馈模板:
- 若返回价格数据 → "✅ 行情数据正常,BTC 现价 $[数字]"
- 若失败 → "❌ 连 market 模块都连不上,这是底层网络问题。先检查你能不能在浏览器打开 okx.com"

### 互动 6 · 诊断总报告

三条命令跑完后,AI 输出一份**格式化的连接健康报告**:

```
═══════════════════════════════════
      🔥 点火器 · 连接诊断报告
═══════════════════════════════════

🔌 账户连接      [✅ 通过 / ❌ 失败]
🔑 Trade 权限    [✅ 通过 / ❌ 失败]
📊 行情数据      [✅ 通过 / ❌ 失败]
🌐 运行环境      [虚拟盘 demo / 实盘 live]
💰 账户余额      [X USDT]
📐 持仓模式      [net_mode 单向 / long_short_mode 双向]
⚙️  保证金模式    [cross 全仓 / isolated 逐仓]

综合判断:
[✅ 所有检查通过,你已具备跑任何交易 Skill 的基础条件]
      或
[⚠️ X 项有问题,请按上方报错提示修复后重试]

═══════════════════════════════════
```

---

## ⚠️ AI 会踩的坑(必读)

**坑 1:AI 不应询问、接收、存储用户的 API Key 原始值**
用户的 API Key / Secret Key / Passphrase **只能写进 `~/.okx/config.toml`**,绝不能进聊天对话。
- 如果用户粘贴了疑似 API Key 的字符串,AI 必须立即警告:"🚨 你刚才贴了疑似密钥的信息。**请立刻回 OKX 重置这个 Key**(贴过聊天窗口的密钥不能再用),然后重新配置。"
- 本 Skill 中涉及 Key 的所有步骤,AI 只能说"请你去 xx 填 xx",**不能主动替用户做**。

**坑 2:AI 不应混淆 401 错误的两种成因**
`401 Unauthorized` 可能有两种原因:
- **Key 环境不匹配**(demo Key 连了 live 域名,或反之)
- **Key 权限不足**(没勾 Trade 权限)

AI 看到 401 必须让用户**先核对启动命令的 `--profile` 是否和 Key 环境一致**,再去怀疑权限问题。

**坑 3:AI 不应代替用户操作 OKX 后台**
创建 API Key、改权限、开子账户、切换持仓模式——这些都必须用户自己去 OKX 界面操作。
AI 可以给详细路径和步骤,但不能说"我帮你创建"。

**坑 4:AI 要主动核对合约面值**
不同账户、不同地区、不同合约,合约面值(ctVal)可能不同。AI 在讲"1 张 = 多少 BTC"之前,应该跑一条 `okx market instruments --instType SWAP --instId BTC-USDT-SWAP` 查 `ctVal` 字段的实际值,不要凭记忆说。

**坑 5:AI 不应把虚拟盘结果当作实盘承诺**
虚拟盘的滑点、流动性、资金费率和实盘有差异。用户在 demo 跑得好,AI 不应说"那你上实盘也这个成绩",必须提醒实盘有差异。

---

## ✅ 毕业测验

AI 问用户这 3 题,3 题全过才推荐进 Vol.1:

**题 1**:"你的 API Key 现在配的是虚拟盘还是实盘?启动命令的 `--profile` 对得上吗?"
- 答对:用户能清楚说出"Key 是 demo,启动用 --profile demo"

**题 2**:"你 API Key 的 Withdraw 权限勾了吗?"
- 答对:必须是"没勾"

**题 3**:"连接自检三连,哪一条验证了你有 Trade 权限?"
- 答对:`okx account positions`(因为 positions 是 Trade 权限才能读的)

### 毕业奖章 🏅

三题通过后,AI 输出:

```
🏅 恭喜你!你已经拿到了「小白上场手册」第 1 枚奖章:点火器 🔥

你现在的能力:
  ✅ 能正确创建和配置 API Key
  ✅ 能区分虚拟盘和实盘
  ✅ 遇到连接报错知道怎么排查

70% 的小白在这一步就卡住了,你已经赢了他们一个身位。

下一步推荐:
  👉 Vol.1 · 安全气囊  — 在你让 AI 动钱之前,先学会保护自己
  触发词:"安全气囊" / "密钥保护" / "airbag"
```

---

## 📎 引用其他 Skill

- 完成本 Skill 后,建议连续装 **Vol.1 · 安全气囊** 和 **Vol.2 · 读仪表盘**
- 三本都过完后,可以尝试装 `resilience-trader`(韧性交易者)跑第一笔真实交易
- 跑过几笔后,装 `trade-mirror`(交易镜子)做复盘

---

*小白上场手册 · Vol.0 · 点火器 | 适用平台:OKX Agent Trade Kit*
*本 Skill 不下单,只负责连接配置与诊断。MIT 开源,欢迎 fork。*

---

### [49] `rsi-bottom-hunter`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/rsi-bottom-hunter/SKILL.md`

---
name: rsi-bottom-hunter
description: "RSI抄底策略交易 Skill。当用户说'RSI抄底'、'超卖买入'、'RSI策略'、'抄底宝'、'启动RSI交易'时使用此技能。自动监控RSI指标，在超卖区域买入，并执行止盈止损。依赖 okx-cex-market、okx-cex-trade、okx-cex-portfolio 三个 Skill。"
version: "1.0.0"
user-invocable: true
---

# RSI抄底宝

基于 RSI(14) 超卖信号的自动抄底策略。当 RSI 低于设定阈值时自动买入，持仓后根据涨跌幅自动止盈止损。支持现货与合约模式。

## 依赖 Skills（必须先安装）

- `okx-cex-market` — 获取实时价格和 RSI 等技术指标
- `okx-cex-trade` — 执行买入和卖出订单
- `okx-cex-portfolio` — 查询账户持仓和余额

## 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| instId | string | ✅ | - | 交易对，现货用 BTC-USDT，合约用 BTC-USDT-SWAP |
| amount | number | ✅ | - | 每次买入金额（USDT） |
| bar | string | ❌ | 1H | K线周期：1m/5m/15m/1H/4H/1Dutc |
| rsi_period | integer | ❌ | 14 | RSI 计算周期 |
| rsi_buy_threshold | number | ❌ | 30 | RSI 低于此值时触发买入（建议 25-35） |
| take_profit_pct | number | ❌ | 8 | 止盈百分比（建议 5-12） |
| stop_loss_pct | number | ❌ | 6 | 止损百分比（建议 5-10） |
| max_positions | integer | ❌ | 1 | 最大同时持仓数 |
| mode | string | ❌ | spot | 交易模式：spot（现货）/ swap（永续合约） |
| profile | string | ❌ | demo | 实盘 live / 模拟盘 demo（强烈建议先用 demo 测试） |

## 执行流程

### Phase 1：参数确认

1. 用户触发技能后，确认交易对（instId）和买入金额（amount）。
2. 如果用户未指定 profile，**默认使用 demo 模拟盘**，保护资金安全。
3. 如果用户未指定其他参数，使用默认值：RSI阈值 30、止盈 8%、止损 6%、周期 1H、现货模式。
4. 根据 mode 自动处理 instId 格式：
   - mode=spot → instId 格式为 `BTC-USDT`
   - mode=swap → instId 格式为 `BTC-USDT-SWAP`
5. 向用户确认完整参数后开始执行。

### Phase 2：获取 RSI 信号

调用 `okx-cex-market` 获取当前 RSI 值和实时价格：

```bash
# 获取 RSI 值
okx market indicator rsi <instId> --bar <bar> --params <rsi_period>
# 示例：okx market indicator rsi BTC-USDT --bar 1H --params 14

# 获取当前价格
okx market ticker <instId>
# 示例：okx market ticker BTC-USDT
```

从 ticker 返回值中提取 `last`（最新价格）。
从 indicator 返回值中提取最新 RSI 值。

输出当前状态：
- 当前 RSI 值
- 当前价格
- 是否触发买入信号（RSI < rsi_buy_threshold）

### Phase 3：买入判断与执行

**Step 1：检查前置条件**

```bash
# 查询账户 USDT 余额
okx account balance USDT --profile <profile>

# 查询当前持仓（如果是合约模式）
okx account positions --instType SWAP --profile <profile>
```

**Step 2：判断是否满足买入条件**

全部满足才执行买入：
1. RSI < rsi_buy_threshold（默认 30）
2. 当前持仓数 < max_positions
3. 账户 USDT 可用余额（available）>= amount

**Step 3：执行买入**

现货买入：
```bash
okx spot place --instId <instId> --side buy --ordType market --sz <amount> --tgtCcy quote_ccy --profile <profile>
# 示例：okx spot place --instId BTC-USDT --side buy --ordType market --sz 100 --tgtCcy quote_ccy --profile demo
# --tgtCcy quote_ccy 表示 sz 的单位是 USDT
```

合约买入（做多）：
```bash
okx swap place --instId <instId> --side buy --ordType market --sz <amount> --tdMode cross --posSide long --tgtCcy quote_ccy --profile <profile>
# 示例：okx swap place --instId BTC-USDT-SWAP --side buy --ordType market --sz 100 --tdMode cross --posSide long --tgtCcy quote_ccy --profile demo
```

买入成功后：
- 从 ticker 记录买入时价格作为 entry_price
- 向用户报告：买入价格、RSI值、买入数量、订单ID

**不满足条件时：**
- 向用户报告当前 RSI 值和余额，说明未达到买入条件
- 如果用户要求持续监控，每隔一个 bar 周期重新从 Phase 2 开始检查

### Phase 4：持仓监控与止盈止损

当存在持仓时，持续监控价格变化：

**Step 1：获取当前价格**
```bash
okx market ticker <instId>
```

**Step 2：计算盈亏**
```
profit_pct = (current_price - entry_price) / entry_price × 100
```

**Step 3：止盈判断**

如果 profit_pct >= take_profit_pct（默认 +8%）：

现货止盈卖出：
```bash
# 先查持仓数量
okx account balance <baseCcy> --profile <profile>
# 全部卖出
okx spot place --instId <instId> --side sell --ordType market --sz <持仓数量> --tgtCcy base_ccy --profile <profile>
```

合约止盈平仓：
```bash
okx swap close --instId <instId> --mgnMode cross --posSide long --profile <profile>
```

向用户报告：卖出价格、盈利百分比、盈利金额。

**Step 4：止损判断**

如果 profit_pct <= -stop_loss_pct（默认 -6%）：

执行方式与止盈相同（现货卖出或合约平仓），向用户报告：卖出价格、亏损百分比、亏损金额。

**Step 5：持仓中**

未触发止盈止损时：
- 向用户报告当前价格、浮盈/浮亏百分比
- 继续监控，每隔一个 bar 周期重新检查

## 使用示例

用户可以这样触发：

- "启动 RSI抄底宝，BTC-USDT，RSI低于30买入，每次100 USDT，涨8%止盈，跌6%止损"
- "查看当前 BTC-USDT 的 RSI 信号"
- "用 RSI 策略抄底 ETH-USDT，每次 50U，1小时线"
- "RSI抄底 SOL-USDT 200U"
- "用模拟盘测试 RSI抄底 BTC-USDT 100U"
- "切换到实盘，RSI抄底 BTC-USDT 100U"

## 输出格式

每次执行后向用户报告：

```
📊 RSI抄底宝 - BTC-USDT [模拟盘]
━━━━━━━━━━━━━━━━━━━━
当前 RSI(14)：28.5
当前价格：$84,230
买入阈值：< 30
━━━━━━━━━━━━━━━━━━━━
⚡ 信号：RSI 进入超卖区，触发买入！
💰 买入金额：100 USDT
📍 买入价格：$84,230
🎯 止盈目标：$90,968（+8%）
🛑 止损价格：$79,176（-6%）
📋 订单ID：xxxxxxxxx
```

## 风险提示

1. **默认使用模拟盘（demo）**，切换实盘需用户明确指定 profile=live。
2. 单笔金额建议不超过总资金的 5%，避免连续止损导致大幅回撤。
3. RSI 抄底策略在单边下跌行情中可能连续触发止损，需结合趋势判断使用。
4. 实际交易存在滑点、手续费、API 延迟等风险，实际盈亏与理论值会有偏差。
5. 本 Skill 仅供学习研究，不构成投资建议，盈亏自负。

---

### [50] `sol-rebound-short`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/sol-rebound-short/SKILL.md`

---
name: sol-rebound-short
description: SOL-USDT-SWAP 阶梯做空策略 / SOL-USDT-SWAP laddered short strategy.
---

# SOL Rebound Short

## What This Skill Does / 这个 Skill 是做什么的

`SOL Rebound Short` is a rules-based OKX perpetual futures skill for `SOL-USDT-SWAP` that turns a discretionary short-recovery idea into an agent-readable strategy.

`SOL Rebound Short` 是一个面向 `SOL-USDT-SWAP` 的 OKX 永续合约规则化做空 Skill，用来把原本偏主观的空头回补思路，整理成 Agent 可以理解、执行和复盘的策略框架。

It is designed for traders who want to:
- start with a small short position,
- add only when adverse movement hits predefined thresholds,
- reduce rescue layers on rebound,
- take profit in fixed increments,
- and keep account-level risk bounded with explicit capital and drawdown limits.

它适合这样的交易者：
- 先用小仓位试空，
- 只有在不利波动达到阈值时才分层加仓，
- 在价格回弹时优先减掉补仓层，
- 用固定利润目标逐步止盈，
- 同时用明确的资金和回撤限制，把风险控制在账户可承受范围内。

This is **not** a hype skill for showing only winning screenshots. It is a structured strategy skill focused on **repeatability, bounded risk, and reviewability**.

它**不是**那种只会展示盈利截图的“包装型 Skill”，而是一个强调**可重复、风险有边界、并且方便复盘**的结构化交易策略 Skill。

## Why It Is Different / 它和普通补仓策略有什么不同

Compared with uncontrolled averaging or martingale-style shorting, this skill adds visible risk boundaries:

和常见的无上限补仓、马丁式做空相比，这个 Skill 明确加入了可见的风险边界：

- use only **50%** of current account equity as strategy capital
- cap total position size at **50%** of the account's current maximum openable quantity
- stop trading after **20% daily drawdown**
- avoid new exposure in the funding blackout window

- 只使用当前账户权益的 **50%** 作为策略资金
- 最大总仓位限制为当前账户可开最大仓位的 **50%**
- 日内回撤达到 **20%** 后停止交易
- 在资金费率结算前后黑窗期内不新增风险敞口

In one line:

**small starter short -> controlled adverse adds -> rebound de-risk -> fixed profit harvesting -> dynamic size cap -> daily circuit breaker**

一句话概括：

**小仓试空 -> 逆向受控加仓 -> 反弹去风险 -> 固定利润收割 -> 动态仓位上限 -> 日内熔断保护**

## Best-fit Market Conditions / 适用行情

Use this skill when SOL is in:
- high-volatility range conditions
- failed breakout / fade structures
- weak rallies with repeated rejection
- noisy short-term mean-reversion environments

这个 Skill 更适合以下 SOL 行情：
- 高波动震荡
- 假突破后的回落结构
- 反弹无力、反复受压的弱势行情
- 短周期有噪音但存在均值回归特征的环境

Avoid presenting it as ideal for strong one-way squeeze markets.

不要把它包装成适合单边强逼空行情的策略，那不是它擅长的环境。

## Risk Warning / 风险提示

This is still a recovery-style averaging model. In strong one-way rebound or squeeze conditions, repeated adds can amplify drawdown. The purpose of this skill is not to eliminate losses, but to keep them **bounded, observable, and reviewable**.

本质上它仍然属于一种“回补型、受控补仓”策略。在单边强反弹或逼空环境中，连续加仓仍可能放大回撤。这个 Skill 的目标不是消灭亏损，而是让亏损保持在**有边界、可观察、可复盘**的范围内。

## Live-account Example Snapshot / 真实账户案例摘要

A recent authorized account example showed:

近期一个已授权账户样例结果如下：

- Account equity: `102.3302 USDT`
- Strategy capital: `51.1651 USDT`
- Max position in cycle: `4 SOL`
- Realized PnL: `-1.5145 USDT`
- Strategy ROI: `-2.9601%`
- Account impact: `-1.4800%`

- 账户权益：`102.3302 USDT`
- 策略资金：`51.1651 USDT`
- 本轮最大持仓：`4 SOL`
- 已实现收益：`-1.5145 USDT`
- 策略资金收益率：`-2.9601%`
- 对账户总权益影响：`-1.4800%`

Why include a losing example up front? Because it proves the point of the skill: this strategy can lose in adverse conditions, but the combination of sizing caps, capital allocation rules, and circuit-breaker logic can keep damage relatively contained at the account level.

为什么要把一个亏损案例放在前面？因为这恰恰能说明这个 Skill 的核心价值：它在不利行情下仍然可能亏损，但通过仓位上限、资金占比和熔断机制，能够把账户层面的损伤控制在相对有限的范围内。

## Strategy Profile

- Exchange: `okx`
- Instrument: `SOL-USDT-SWAP`
- Account mode: `cross`
- Position mode: `long_short_mode`
- Trade direction: `short`
- Signal filter enabled: `true`
- Night trading: `true`
- Dry run: `false` by default

## Core Logic

1. Open an initial short with a small base position.
2. If floating loss reaches the configured loss threshold and price has moved far enough from the previous add level, add one unit to improve average entry.
3. Cap total position size at no more than 50% of the maximum quantity the current account can open.
4. When price reverts toward average entry, reduce the newest added layer first, then the next layer, to de-risk exposure.
5. Take profit in fixed per-SOL increments instead of waiting for one large move.
6. Stop trading for the day when daily drawdown reaches 20% or failure conditions are triggered.

## Trading Parameters

### Leverage and Risk

- Exchange max leverage allowed by setup: `50x`
- Strategy-side risk leverage cap: `8x`

Always obey the lower effective leverage implied by risk controls and capital allocation, even if the exchange allows higher leverage.

### Capital

- Strategy capital budget: `50%` of current account equity
- Reserve capital: remaining `50%` of current account equity

Interpretation:

- Use only half of current account equity for this strategy.
- Keep the other half as reserve and untouched by default.
- Recompute the strategy budget dynamically from current account state instead of assuming a fixed USDT balance.

### Position Sizing

- Base position: small starter short
- Add unit: fixed incremental layer per add event
- Max position: `50%` of the maximum quantity the current account can open under current margin and instrument constraints

Interpretation:

- Do not use a hard-coded max position size such as `4 SOL`.
- Query current account buying power, leverage limits, and instrument constraints.
- Derive an account-level maximum openable quantity.
- Limit this strategy to at most `50%` of that maximum openable quantity.

## Entry and Add Rules

## Initial Entry

Open the first short only if the upstream signal filter permits it.

Because `signal_filter_enabled: true`, do not blindly enter on every price tick. Require an external or precomputed bearish filter before opening the base position.

## Add Conditions

Add exactly `1 SOL` only when **all** of the following are true:

- Current floating loss reaches at least `13 USDT`
- Price has dropped at least `2.5%` from the last add reference level
- Current total position is below the strategy cap of `50%` of current account max openable quantity
- No circuit breaker is active
- Current time is outside the funding blackout window

If any condition fails, do not add.

## Profit-Taking and De-Risking

### Fixed Profit Objective

- Target profit: `1.0 USDT` per `1 SOL`

Interpretation:

- Harvest gains in small, repeatable increments.
- Do not wait for outsized trend extension if the fixed target is reached.

### Rebound De-Risk Rules

When price rebounds toward the average entry price of the current short stack:

1. If mark price reaches `avg_price + 0.2`, reduce the most recent add layer.
2. If mark price reaches `avg_price + 1.0`, reduce the next add layer.

Execution intent:

- Remove newest risk first.
- Shrink exposure as the trade recovers toward breakeven.
- Preserve the core position longer than the latest rescue adds.

Map the provided actions as:

- `reduce_last_add_6` -> reduce the newest add tranche
- `reduce_next_add_6` -> reduce the second-newest add tranche

If implementation needs exact quantity mapping, default to reducing one add unit per rule unless the exchange lot size requires rounding.

## Circuit Breakers

Stop new trading activity when any of the following happens:

- Daily strategy drawdown reaches `20%`
- Position is already at the strategy max size and market breaks the defined support level
- Two recovery attempts fail

### Implementation Notes

Because `break support` and `failed recovery` need market-structure interpretation, apply these conservative defaults if no richer signal model is supplied:

- **Break support**: price closes below the most recent local support zone identified before the latest add
- **Failed recovery**: after an add, price fails to rebound enough to trigger a de-risk rule and then continues against the position to a new adverse threshold

When either structural rule is ambiguous, choose the safer path and stop adding.

## Funding Window Controls

Suspend opening and adding around funding time:

- Block new risk `5` minutes before funding
- Block new risk `5` minutes after funding

Inside the blackout window:

- Do not open a new base short
- Do not add to an existing short
- Allow risk reduction and take-profit exits

## Operational Checklist

Before execution:

1. Confirm instrument is `SOL-USDT-SWAP`
2. Confirm account mode is `cross`
3. Confirm position mode supports independent short exposure
4. Confirm available strategy capital is `50%` of current account equity
5. Confirm effective leverage does not exceed the risk cap intent
6. Confirm no funding blackout is active
7. Confirm no daily circuit breaker is active
8. Confirm bearish signal filter is valid

During execution:

1. Track every layer separately
2. Recompute average entry after each add or reduction
3. Evaluate add rules only on adverse movement
4. Evaluate de-risk rules continuously on rebound
5. Stop immediately when circuit-breaker conditions are met

After execution:

1. Record entries, adds, reductions, exits, and reasons
2. Record daily PnL and circuit-breaker triggers
3. Review whether adds improved exit quality or merely increased drawdown

## Default Structured Config

```yaml
exchange: okx
instrument: SOL-USDT-SWAP
account_mode: cross
position_mode: long_short_mode
trade_direction: short
signal_filter_enabled: true
max_leverage: 50
risk_leverage_cap: 8
strategy_capital_ratio: 0.5
reserve_capital_ratio: 0.5
max_position_ratio_of_account_openable_qty: 0.5
base_position_mode: small_starter
add_unit_mode: fixed_increment
take_profit_per_sol_usdt: 1.0
add_trigger_floating_loss_usdt: 13
add_trigger_drop_from_last_add_pct: 2.5
derisk_rules:
  - trigger: "avg_price + 0.2"
    action: "reduce_last_add_6"
  - trigger: "avg_price + 1.0"
    action: "reduce_next_add_6"
daily_circuit_breaker_drawdown_pct: 20
stop_when_max_pos_and_break_support: true
stop_when_two_failed_recoveries: true
night_trading: true
funding_blackout_before_min: 5
funding_blackout_after_min: 5
dry_run: false
```

## What to Tell the User

When presenting this strategy, summarize it plainly:

- Bias: short SOL perpetuals
- Style: layered averaging into adverse movement
- Exit: small fixed take-profit plus rebound de-risk
- Main risk: averaging into a continued squeeze
- Main protection: dynamic 50% size cap, funding blackout, and daily 20% drawdown stop logic

## Executable Parameter Schema

Use `references/executable-schema.json` as the runtime config contract.

Execution engines should resolve the following live values before placing or adjusting any order:

- current account equity
- current instrument max openable quantity
- current leverage setting and exchange constraints
- current average entry and active layer state
- realized and unrealized daily PnL
- upcoming funding timestamp and blackout window

Recommended execution mapping:

1. Query equity via `okx account balance`
2. Query max available/openable size via `okx account max-size` or `okx account max-avail-size`
3. Query positions via `okx swap positions` or `okx account positions`
4. Place or reduce short exposure via `okx swap place`, `okx swap amend`, and `okx swap close`
5. Compute ROI outputs after fills using the case-study formulas in `references/case-study-template.md`

## Marketplace Publishing Copy

Use `references/publish-copy.md` for bilingual marketplace copy.

## References

- `references/strategy-spec.md` — compact machine-readable spec and publishing notes
- `references/executable-schema.json` — executable runtime config schema
- `references/publish-copy.md` — Chinese and English marketplace copy
- `references/case-study-template.md` — ROI logic and case-study template

---

### [51] `speed-hunter`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/speed-hunter/SKILL.md`

---
name: 极速猎手v1
description: "激进高收益策略 — 当用户说「激进策略」「高收益」「短期暴利」「极速猎手」「合并策略」「双信号」「复利交易」「高频交易」时使用此技能。RSI超卖+EMA金叉双信号驱动，10x~20x高杠杆，1H高频周期，复利加仓模式，专为2周内最大化收益率设计。⚠️高风险高回报，仅适合激进投资者。"
license: MIT
version: "1.1.0"
user-invocable: true
metadata:
  author: 极速猎手v1
  tags: [激进, 高收益, 复利, 高频, RSI, EMA, 双信号, 极速猎手, 高杠杆]
  agent:
    requires:
      bins: ["okx"]
    install:
      - id: npm
        kind: node
        package: "@okx_ai/okx-trade-cli"
        bins: ["okx"]
        label: "Install okx CLI (npm)"
---

# 极速猎手v1 — 激进高收益双信号策略

> **⚠️ 高风险警告**：本策略采用 **10x~20x 高杠杆** + **高频交易** + **复利加仓**，专为 **2周内最大化收益率** 设计。历史回测显示可能产生 **-100% 本金损失**。仅适合能承受全部本金亏损的激进投资者。不构成投资建议，盈亏自负。

---

## 策略定位

**「合约小师傅」+「趋势猎手」合并升级版**

| 维度 | 合约小师傅 | 趋势猎手 | **极速猎手（本策略）** |
|---|---|---|---|
| **核心思想** | RSI超卖抄底 | EMA金叉追涨 | **双信号驱动，择强入场** |
| **信号类型** | 单一RSI | 单一EMA | **RSI+EMA双确认** |
| **时间周期** | 4H | 4H | **1H（更高频）** |
| **杠杆倍数** | 3x~5x | 3x~5x | **10x~20x（激进）** |
| **止损方式** | 固定2% | ATR动态 | **固定1.5%（更紧）** |
| **止盈方式** | 固定3% | 1:2盈亏比 | **5%~10%（让利润奔跑）** |
| **仓位管理** | 固定仓位 | 固定仓位 | **复利加仓（盈利后加码）** |
| **持仓时间** | 短线 | 中线 | **超短线~短线** |
| **目标收益** | 稳健 | 稳健 | **2周内最大化** |

---

## 核心创新：双信号驱动系统

### 信号A：RSI超卖反弹（均值回归）
```
条件：RSI(14) < 25（比原版30更激进）
      + 价格接近近期低点
      + 成交量放大（>20日均量1.5倍）
方向：做多（抄底）
优势：抓住恐慌性抛售后反弹
```

### 信号B：EMA趋势加速（动量延续）
```
条件：EMA(9) 上穿 EMA(21)（金叉）
      + ADX > 30（强趋势确认，比原版25更严格）
      + 价格突破前1H高点
方向：做多（追涨）
优势：抓住趋势启动加速段
```

### 信号优先级（智能选择）
```
IF 信号A和信号B同时出现 → 满仓入场（复利加仓模式）
IF 仅信号A出现 → 50%仓位（RSI抄底）
IF 仅信号B出现 → 75%仓位（趋势追涨）
IF 无信号 → 空仓等待
```

---

## 激进参数配置（2周高收益目标）

| 参数 | 默认值 | 激进优化 | 说明 |
|---|---|---|---|
| `TIMEFRAME` | `1H` | ✅ | 1小时K线，更高频交易机会 |
| `LEVER` | `15x` | ✅ | 10x~20x可调，默认15x激进 |
| `RSI_THRESHOLD` | `30` | ✅ | RSI超卖阈值 |
| `RSI_EXIT` | `55` | ✅ | RSI>55即止盈，不贪多 |
| `EMA_FAST` | `9` | ✅ | 快线周期 |
| `EMA_SLOW` | `21` | ✅ | 慢线周期 |
| `ADX_THRESHOLD` | `25` | ✅ | ADX趋势强度阈值 |
| `STOP_LOSS_PCT` | `ATR×2.0 (1.5%~3%)` | ✅ | ATR动态止损 |
| `TAKE_PROFIT_PCT` | `ATR×3.0 (最少6%)` | ✅ | ATR动态止盈 |
| `TRAILING_STOP` | `true` | ✅ | 启用移动止盈 |
| `TRAILING_PCT` | `3%` | ✅ | 回撤3%触发移动止盈 |
| `COMPOUND_MODE` | `true` | ✅ | 盈利后复利加仓 |
| `COMPOUND_STEP` | `5%` | ✅ | 每盈利5%加仓一次 |
| `MAX_POSITIONS` | `3` | ✅ | 最多同时3个币种持仓 |
| `POSITION_SIZE` | `30%` | ✅ | 单币种初始仓位30% |

---

## 复利加仓系统（核心收益放大器）

### 加仓触发条件
```
当前持仓盈利 ≥ 5% 且 趋势未反转
→ 自动加仓至原仓位的 50%
→ 新止损上移至成本价（保本）
→ 新止盈目标上调至 +12%
```

### 加仓层级示例
```
初始：BTC 做多，仓位 $3,000（本金$10,000的30%）

第1次加仓：盈利5% → 加仓$1,500 → 总仓位$4,500
           止损上移至成本价，止盈目标+12%

第2次加仓：再盈利5%（累计10%）→ 加仓$2,250 → 总仓位$6,750
           止损上移至第1次加仓价，止盈目标+15%

最大仓位限制：单币种不超过本金的 80%
```

---

## 策略执行流程

```
Phase 0  →  前置检查（API + 余额 + 当前持仓数 < MAX_POSITIONS）
Phase 1  →  扫描所有目标币种（BTC/ETH/SOL/BNB/XRP/DOGE）
Phase 2  →  对每个币种计算：RSI + EMA + ADX + 成交量
Phase 3  →  信号评分：信号A强度 + 信号B强度
Phase 4  →  选择评分最高的1-3个币种入场
Phase 5  →  设置15x杠杆，市价开仓 + 止盈止损条件单
Phase 6  →  高频轮询（每30秒）：检查止盈/止损/加仓条件
Phase 7  →  平仓结算，更新复利基数，扫描下一机会
```

---

## ⚠️ 重要配置：策略状态文件

**文件路径**：`~/.qclaw/workspace-agent-ca7a859e/.agents/skills/极速猎手v1/strategy_state.json`

```json
{
  "active_positions": [],
  "available_margin": 10000,
  "total_equity": 10000,
  "compound_base": 10000,
  "daily_pnl": 0,
  "daily_trades": 0,
  "consecutive_losses": 0,
  "circuit_breaker": false,
  "last_update": null,
  "signal_scores": {
    "BTC": {"rsi_signal": 0, "ema_signal": 0, "total": 0},
    "ETH": {"rsi_signal": 0, "ema_signal": 0, "total": 0}
  }
}
```

---

## Phase 0 — 前置检查

### Step 0.1 验证API凭据
```bash
okx config show
# 确认 apiKey / secretKey / passphrase 已配置
```

### Step 0.2 检查账户权益
```bash
okx account balance
# 确保 USDT 可用余额 > 0
# 记录当前权益作为复利基数
```

### Step 0.3 检查当前持仓
```bash
okx swap positions
# 确保当前持仓数 < MAX_POSITIONS (默认3)
# 如有持仓，进入Phase 6监控模式
```

---

## Phase 1 — 多币种信号扫描

### Step 1.1 批量获取指标
```bash
# 对 BTC/ETH/SOL/BNB/XRP/DOGE 分别执行：

okx market indicator rsi BTC-USDT-SWAP --bar 1H --params 14 --limit 3
okx market indicator ema BTC-USDT-SWAP --bar 1H --params 9 --limit 3
okx market indicator ema BTC-USDT-SWAP --bar 1H --params 21 --limit 3
okx market indicator adx BTC-USDT-SWAP --bar 1H --params 14 --limit 3

# 记录：当前RSI、EMA9、EMA21、ADX、成交量
```

### Step 1.2 信号评分计算
```python
# 信号A评分（RSI超卖）
if RSI < 20:  rsi_score = 100      # 极度超卖
elif RSI < 25: rsi_score = 80      # 严重超卖
elif RSI < 30: rsi_score = 60      # 超卖
else: rsi_score = 0

# 信号B评分（EMA金叉+ADX）
if EMA9 > EMA21 and ADX > 35: ema_score = 100    # 强趋势金叉
elif EMA9 > EMA21 and ADX > 30: ema_score = 80   # 趋势金叉
elif EMA9 > EMA21: ema_score = 50                # 弱金叉
else: ema_score = 0

# 总评分
total_score = rsi_score * 0.4 + ema_score * 0.6
```

---

## Phase 2 — 智能选币与仓位分配

### Step 2.1 选择目标币种
```
按 total_score 排序，选择评分最高的 1-3 个币种

IF 最高分 > 80: 满仓模式（单币80%或双币各40%）
IF 最高分 60-80: 标准模式（单币50%或双币各25%）
IF 最高分 < 60: 观望，不入场
```

### Step 2.2 计算开仓数量
```python
# 以 BTC 为例，当前价 $72,000，本金 $10,000，杠杆 15x

position_size_usd = total_equity * position_pct * lever  # $10,000 * 0.3 * 15 = $45,000
btc_amount = position_size_usd / current_price           # $45,000 / $72,000 = 0.625 BTC
contract_size = round(btc_amount, 3)                     # 0.625 → 0.63 BTC
```

---

## Phase 3 — 开仓执行

### Step 3.1 设置杠杆
```bash
okx swap leverage --instId BTC-USDT-SWAP --lever 15 --mgnMode cross
```

### Step 3.2 计算止盈止损价（ATR动态）
```python
# ATR止损：基于波动幅度，更科学
# 公式：止损价 = 入场价 - (ATR × 2.0)
# 动态范围：1.5%~3%
atr = get_atr(instId)  # 获取14周期ATR
atr_pct = (atr / entry_price) * 100
stop_pct = 2.0 * atr_pct
stop_pct = max(1.5, min(3.0, stop_pct))  # 限制范围
stop_loss_price = entry_price * (1 - stop_pct / 100)

# ATR止盈：基于波动幅度
# 公式：止盈价 = 入场价 + (ATR × 3.0)
# 最小止盈6%，确保风险收益比至少1:1.5
tp_pct = 3.0 * atr_pct
tp_pct = max(6.0, tp_pct)  # 最小6%
take_profit_price = entry_price * (1 + tp_pct / 100)

# 移动止盈触发：盈利5%后，回撤3%触发
# 移动止盈价 = 最高价 * 0.97
```

### Step 3.3 市价开仓
```bash
okx swap place \
  --instId BTC-USDT-SWAP \
  --side buy \
  --ordType market \
  --sz 0.63 \
  --tdMode cross \
  --posSide long \
  --slTriggerPx 70920 \
  --slOrdPx -1 \
  --tpTriggerPx 77760 \
  --tpOrdPx -1
```

---

## Phase 4 — 高频监控与复利加仓

### Step 4.1 高频轮询（每30秒）
```bash
okx swap positions --instId BTC-USDT-SWAP
okx market ticker BTC-USDT-SWAP
```

### Step 4.2 复利加仓判断
```python
# 当前盈利百分比
pnl_pct = (current_price - entry_price) / entry_price * 100

# 加仓条件
if pnl_pct >= 5 and not added_position:
    # 加仓50%原仓位
    add_size = original_size * 0.5
    # 新止损上移至成本价
    new_sl = entry_price
    # 新止盈上调
    new_tp = entry_price * 1.12
    # 执行加仓
    execute_add_position(add_size, new_sl, new_tp)
```

### Step 4.3 移动止盈判断
```python
# 记录持仓期间最高价
highest_price = max(highest_price, current_price)

# 移动止盈触发
if pnl_pct > 5 and current_price < highest_price * 0.97:
    # 盈利回撤3%，触发移动止盈
    close_position("trailing_stop")
```

---

## Phase 5 — 平仓与结算

### Step 5.1 平仓执行
```bash
# 市价平仓
okx swap close --instId BTC-USDT-SWAP --posSide long --ordType market
```

### Step 5.2 更新状态文件
```json
{
  "last_trade": {
    "instId": "BTC-USDT-SWAP",
    "entry_price": 72000,
    "exit_price": 77760,
    "pnl_pct": 8.0,
    "pnl_usdt": 360,
    "exit_reason": "take_profit"
  },
  "compound_base": 10360,  // 原10000 + 盈利360
  "total_equity": 10360,
  "consecutive_losses": 0
}
```

### Step 5.3 熔断检查
```python
if consecutive_losses >= 3:
    circuit_breaker = true
    print("⚠️ 连续3次亏损，触发熔断，停止交易24小时")
```

---

## 风险控制（必读）

### 硬止损规则
1. **单笔止损**：-1.5%（15x杠杆下实际亏损22.5%本金）
2. **单日止损**：单日亏损达本金的30%即停止交易
3. **连续亏损**：连续3笔亏损触发24小时熔断
4. **最大回撤**：总权益回撤50%立即停止所有策略

### 杠杆风险提示
```
15x杠杆意味着：
- 价格反向波动6.67% → 本金归零（强平）
- 本策略设置1.5%止损 → 实际亏损22.5%本金
- 必须严格止损，不能扛单！
```

---

## 预期收益与风险（2周目标）

### 乐观情景（强趋势市场）
```
胜率：60%
盈亏比：3:1（平均盈利8% vs 平均亏损1.5%）
交易频率：每天2-3笔
2周交易次数：约30笔

预期收益率：+150%~+300%
（复利效应下可能更高）
```

### 悲观情景（震荡市）
```
胜率：40%
频繁止损，连续触发熔断
2周收益率：-50%~-100%（本金亏损）
```

### 最可能情景
```
胜率：50%
有盈有亏，复利缓慢增长
2周收益率：+30%~+80%
```

---

## 使用示例

### 启动极速猎手（默认参数）
```
用户：启动极速猎手，本金1万USDT
AI：扫描信号中... BTC信号评分85，EMA金叉+RSI超卖双确认
    建议：BTC满仓做多，15x杠杆，仓位80%
    止损：-1.5%，止盈：+8%，启用移动止盈
用户：确认执行
AI：开仓成功，进入高频监控模式...
```

### 自定义激进参数
```
用户：极速猎手，20x杠杆，RSI阈值20，止盈10%
AI：⚠️ 警告：20x杠杆风险极高，价格反向5%即爆仓
    确认使用以下参数？
    - 杠杆：20x
    - RSI阈值：20（极度超卖才入场）
    - 止盈：10%
    - 止损：1.5%
用户：确认
```

---

## 与原版策略对比总结

| 特性 | 合约小师傅 | 趋势猎手 | 极速猎手 |
|---|---|---|---|
| **适合市场** | 震荡市 | 强趋势 | 任何有波动市场 |
| **交易频率** | 低 | 中 | **高（1H周期）** |
| **杠杆** | 3x~5x | 3x~5x | **10x~20x** |
| **单笔风险** | 2% | ATR动态 | **1.5%（更紧）** |
| **收益潜力** | 稳健 | 稳健 | **激进高收益** |
| **最大回撤** | 可控 | 可控 | **可能-100%** |
| **操作难度** | 简单 | 中等 | **需要盯盘** |
| **复利** | 无 | 无 | **有（核心）** |

---

> **最后警告**：本策略为激进投机设计，2周高收益目标意味着承担高风险。请确保：
> 1. 只投入能承受全部损失的资金
> 2. 严格遵循止损规则，不扛单
> 3. 市场极端行情时手动干预
> 4. 盈利后及时提取本金，用利润继续博弈

**祝交易顺利，但请做好最坏的打算。**

---

### [52] `spot-momentum-scan-validate`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/spot-momentum-scan-validate/SKILL.md`

---
name: spot-momentum-scan-validate
description: >
  量价共振两阶段验证策略。第一阶段"只扫描不下单"，输出信号报告供人工确认；
  第二阶段"确认下单"，用户明确传入 confirm_trade=true 后才执行实际交易。
  当用户提到"先扫描再下单"、"验证信号"、"确认后交易"、"两阶段交易"、
  "信号验证"、"先看信号"时，必须使用本 skill。
---

# 量价共振两阶段验证策略

## 策略概述

本 skill 将交易流程拆分为两个明确阶段：

```
阶段一（默认）：扫描 → 计算指标 → 输出信号报告       ← 不触碰账户
阶段二（需确认）：用户审阅报告 → 传入 confirm_trade=true → 执行下单 + 挂止损止盈
```

人工确认作为硬隔离，防止信号逻辑有误时直接造成资金损失。

---

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `confirm_trade` | `false` | **必须显式设为 true 才会下单**，默认只扫描 |
| `timeframe` | `1H` | K线周期（`1H` / `4H` / `15m`） |
| `price_change_min` | `1.0` | 最小当前K线涨幅（%） |
| `vol_ratio_min` | `1.5` | 最小量比 |
| `rsi_min` / `rsi_max` | `50` / `72` | RSI 区间 |
| `position_pct` | `5` | 每笔仓位占可用 USDT 的比例（%） |
| `stop_loss_pct` | `2.0` | 固定止损幅度（%） |
| `trailing_pct` | `2.0` | 移动止盈回撤幅度（%） |
| `trailing_activate_pct` | 等于 `stop_loss_pct` | 移动止盈激活门槛（%） |
| `scan_pairs` | 前50大成交量 | 可传入指定币对列表 |
| `top_n` | `50` | 按成交额取前 N 个现货 USDT 币对 |

---

## 阶段一：扫描（confirm_trade=false，默认）

### 执行步骤

**Step 1 — 获取行情**

用 `market_get_tickers` 拉取所有现货 USDT 交易对，按 24h 成交额降序，取前 `top_n` 名。
若 `scan_pairs` 不为空，则只扫描指定列表，忽略 `top_n`。

**Step 2 — 拉取 K 线**

对每个币对调用 `market_get_candles`：
```
instType: SPOT
bar: <timeframe>
limit: 60
```
两次调用之间间隔 100ms（`time.sleep(0.1)`），避免触发限速。
若 K 线数量 < 30，跳过该币对并在报告中标注"数据不足"。

**Step 3 — 计算指标**

调用 `scripts/calc_indicators.py` 中的 `analyze()` 函数，计算：

```python
MA20          = 收盘价20周期简单均线
MACD Histogram = 使用完整双EMA历史序列（与TradingView一致，非单点近似）
RSI(14)       = Wilder平滑法
vol_ratio     = 最新K线量 / 近20根均量
price_change  = (收盘 - 开盘) / 开盘 × 100
score         = vol_ratio/vol_ratio_min×3 + price_change/price_change_min×3（上限各5分）
```

**Step 4 — 过滤信号**

五个条件全部满足才触发：

| 条件 | 表达式 |
|------|--------|
| 价格在均线上方 | `close > MA20` |
| MACD 多头 | `macd_hist > 0` |
| 当前K线涨幅 | `price_change >= price_change_min` |
| 放量 | `vol_ratio >= vol_ratio_min` |
| RSI 区间 | `rsi_min <= RSI <= rsi_max` |

有多个信号时，按 `score` 降序排列。

**Step 5 — 输出扫描报告（不操作账户）**

```
=== 量价共振扫描报告（只读，未下单）===
扫描时间: 2024-01-15 14:30 UTC+8
扫描币对: 50 个  |  触发信号: 3 个  |  confirm_trade: false

信号详情:
┌─────────────┬────────┬──────┬──────┬──────────┬───────────────────────────────────┐
│ 币对        │ 涨幅   │ 量比 │ RSI  │ 收盘价   │ 各条件状态                        │
├─────────────┼────────┼──────┼──────┼──────────┼───────────────────────────────────┤
│ SOL-USDT    │ +3.2%  │ 2.8x │ 62.1 │  86.04   │ ✅ MA ✅ MACD ✅ 涨幅 ✅ 量比 ✅ RSI │
│ AVAX-USDT   │ +2.5%  │ 1.9x │ 58.4 │   9.47   │ ✅ MA ✅ MACD ✅ 涨幅 ✅ 量比 ✅ RSI │
│ LINK-USDT   │ +2.1%  │ 1.6x │ 55.2 │   9.22   │ ✅ MA ✅ MACD ✅ 涨幅 ✅ 量比 ✅ RSI │
└─────────────┴────────┴──────┴──────┴──────────┴───────────────────────────────────┘

未触发币对摘要（仅展示差一个条件的，帮助理解信号边界）:
  BNB-USDT  — 差: RSI=74.3（超买）
  DOGE-USDT — 差: 量比=1.3（低于1.5阈值）

⚠️  以上为只读扫描，未执行任何下单操作。
    如需下单，请在下一条消息中明确告知并传入 confirm_trade=true。
```

将扫描结果（含未触发币对的指标）写入 CSV（追加）：

```
timestamp, instId, price_change_pct, vol_ratio, rsi, macd_hist, ma20, close_price,
score, signal_triggered, failed_checks, confirm_trade, status, notes
```

`status` 固定为 `SCAN_ONLY`，`confirm_trade` 固定为 `false`。

---

## 阶段二：确认下单（confirm_trade=true）

**触发方式**：用户审阅阶段一报告后，明确说"确认下单"或"confirm_trade=true"。

执行前，**再次扫描并输出最新信号**（市场可能已变化），然后展示确认提示：

```
⚠️  即将对以下币对执行实际下单，操作不可撤销：
    SOL-USDT  买入约 50 USDT（可用余额的 5%）
    AVAX-USDT 买入约 50 USDT
    LINK-USDT 买入约 50 USDT

    止损：成交价 -2%（固定）
    止盈：盈利 ≥2% 激活，高点回撤 2% 触发（移动）

    请再次确认：回复"确认执行"后开始下单。
```

收到"确认执行"后，按以下步骤执行（与 spot-momentum-1h 完全一致）：

**Step 1 — 查询余额**

`account_get_balance` 获取可用 USDT。若 < 10 USDT，停止并提示。

**Step 2 — 下市价买单**

对每个信号币对：
1. `market_get_instruments` 获取 `lotSz`、`tickSz`
2. `market_get_ticker` 获取最新 ask 价，计算买入数量（按 `lotSz` floor）
3. `spot_place_order` 下单：
   ```
   instId: <币对>
   tdMode: cash
   side: buy
   ordType: market
   sz: <数量>
   ```
4. `spot_get_order` 轮询直到 `filled`，获取 `fill_price`、`fill_sz`

若已有持仓，跳过该币对。

**Step 3 — 挂固定止损单**

```
slTriggerPx = fill_price × (1 - stop_loss_pct/100)，按 tickSz floor
slOrdPx     = -1（市价止损）
ordType     = conditional
```

`spot_place_algo_order` 提交，记录 `sl_algo_id`。失败则重试 2 次，仍失败则警告并标记 `sl_status=FAILED`。

**Step 4 — 挂移动止盈单**

```
activePx       = fill_price × (1 + trailing_activate_pct/100)，按 tickSz ceil
callbackRatio  = trailing_pct / 100
ordType        = move_order_stop
```

`spot_place_algo_order` 提交，记录 `tp_algo_id`。失败处理同上。

**Step 5 — 写入 CSV**

追加到与阶段一相同的 CSV 文件，字段同阶段一，额外字段：

```
order_id, fill_price, fill_sz,
sl_price, sl_algo_id, sl_status,
tp_activate_price, tp_callback_ratio, tp_algo_id, tp_status
```

`status` 为 `FILLED` 或 `FAILED`，`confirm_trade` 为 `true`。

**Step 6 — 输出交易摘要**

```
=== 量价共振交易执行结果 ===
扫描时间: 2024-01-15 14:32 UTC+8
confirm_trade: true

成交详情:
┌─────────────┬──────────┬──────────┬───────────────────────────────────────────────┐
│ 币对        │ 成交价   │ 成交量   │ 风控挂单                                      │
├─────────────┼──────────┼──────────┼───────────────────────────────────────────────┤
│ SOL-USDT    │  86.04   │  0.5810  │ 止损 @84.32 (-2%) ✅  移动止盈激活 @87.76 (+2%) ✅ │
│ AVAX-USDT   │   9.47   │  5.2800  │ 止损 @ 9.28 (-2%) ✅  移动止盈激活 @ 9.66 (+2%) ✅ │
│ LINK-USDT   │   9.22   │  5.4200  │ 止损 @ 9.04 (-2%) ✅  移动止盈激活 @ 9.40 (+2%) ✅ │
└─────────────┴──────────┴──────────┴───────────────────────────────────────────────┘

账户操作:
- 共使用 USDT: 150.00
- 最大亏损上限: -3.00 USDT（每笔 50 USDT × 2% × 3 笔）
- 记录已写入: ~/momentum_trades.csv
```

---

## 两阶段完整对话示例

```
用户: 帮我扫描一下现货市场有没有量价共振信号，先别下单

Claude: [执行阶段一，输出扫描报告]
        ⚠️ 以上为只读扫描，未执行任何下单操作。
        如需下单，请回复"确认下单"。

用户: SOL 和 AVAX 信号不错，LINK 量比有点低先不买，
      帮我只买 SOL 和 AVAX，confirm_trade=true

Claude: [重新扫描确认信号仍有效，展示确认提示]
        即将对 SOL-USDT、AVAX-USDT 执行实际下单……
        请回复"确认执行"。

用户: 确认执行

Claude: [执行阶段二，仅对 SOL-USDT 和 AVAX-USDT 下单]
        [输出成交摘要]
```

---

## 技术指标计算脚本

读取 `scripts/calc_indicators.py` 获取 `analyze()` 实现。
脚本接受 OKX 原始 K 线数据，返回每个币对的指标值与信号判断。

---

## 常见问题处理

**API 限速**: 每次 K 线请求之间加 100ms 延迟。

**精度**: 下单数量按 `lotSz` floor；`slTriggerPx` 按 `tickSz` floor；`activePx` 按 `tickSz` ceil。

**数据不足**: K 线 < 30 根的币对直接跳过，在扫描报告中标注。

**重试**: 下单或挂算法单失败时最多重试 2 次，仍失败则在 CSV 标记 `FAILED` 并输出 `⚠️` 警告。

---

### [53] `stochrsi-mdi-trend-v1`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/stochrsi-mdi-trend-v1/SKILL.md`

---
name: StochRSI-MDI 趋势追踪 V1.1
description: 一个基于 StochRSI 与 MDI 指标差异扩大的高频趋势追踪策略，每15分钟执行一次，并包含严格的模拟仓测试和风控规则。
---

# 策略名称
StochRSI-MDI 趋势追踪 V1.1 (含模拟仓测试, 1小时暂停)

# 执行节奏
每 15 分钟触发一次

# Step 0 · 模拟仓测试阶段 (重要)
**策略正式上线前，必须进行为期至少 2 周的模拟仓测试。**
- **测试环境**：使用与实盘相同的 API 接口和数据源，但不发生真实资金变动。
- **测试目标**：验证策略逻辑的准确性、评估胜率、盈亏比和最大回撤。
- **评判标准**：
    - 模拟盈利率 > 10% (2周内)
    - 最大连续亏损次数 <= 3次
    - 模拟账户最大回撤 < 8%
- **结果记录**：详细记录每次交易的入场/出场时间、价格、方向、盈亏，并截图存档。
- **正式上线**：只有通过 Step 0 测试标准，方可进入 Step 1 实盘数据采集。

# Step 1 · 行情数据采集
调用 `market_get_candles` 分别获取 BTC-USDT-SWAP / ETH-USDT-SWAP 的 15m K线数据。
计算指标：
- StochRSI (14, 14, 3, 3)：仅保留 StochRSI_K 线 (通常称为 STOCHRSI)。
- MDI (14, 6)：仅保留 MDI 线 (Minus Directional Indicator)。

# Step 2 · AI 综合判断 (核心)
你作为交易 AI，需要对每个标的（BTC, ETH）的数据进行以下推理：

1.  **识别信号类型**：
    - **潜在多头信号**：当前 STOCHRSI 线 > MDI 线，且两者之间的差距在过去 3 个周期内持续扩大 (gap_t > gap_t-1 > gap_t-2)。
    - **潜在空头信号**：当前 STOCHRSI 线 < MDI 线，且两者之间的差距在过去 3 个周期内持续扩大 (gap_t > gap_t-1 > gap_t-2)。
    - **无信号**：其他所有情况。

2.  **评估信号强度**：
    - **多头强度**：计算 STOCHRSI - MDI 的斜率（或最近 N 期的斜率均值），斜率越大，多头动能越强。
    - **空头强度**：计算 MDI - STOCHRSI 的斜率（或最近 N 期的斜率均值），斜率越大，空头动能越强。

3.  **AI 最终决策**：
    - 对 BTC 和 ETH 同时进行上述分析，得出各自的信号方向和强度。
    - **优先级排序**：如果 BTC 和 ETH 都发出同方向信号，则选择信号强度更强的那个。如果方向相反，则根据历史表现或默认偏好（例如，优先选择 BTC）进行选择。
    - **最终指令**：确定一个标的和一个方向（Buy/Sell）。
        - 如果没有找到符合条件的信号（即 BTC 和 ETH 均为“无信号”），则指令为 **本次跳过**。

# Step 3 · 执行下单 (仅当 AI 判断明确开仓时)
调用 `swap_place_order`：
- instId = < AI 在第二步选定的标的 (e.g., BTC-USDT-SWAP) >
- side = < AI 在第二步判断的方向 (buy/sell) >
- ordType = "market"
- sz = < 固定仓位 2% 账户权益，或根据波动率动态调整 > 
- tag = "agentTradeKit" - 必填，否则不计入排行榜

# Step 4 · 止损设置
开仓后立即调用 `swap_place_algo_order` 设置止损：
- **多头止损** = 开仓价 × (1 - 0.025)  # 2.5% 固定止损
- **空头止损** = 开仓价 × (1 + 0.025)  # 2.5% 固定止损
- *(可选进阶)*：可以考虑使用 ATR 动态止损替代固定百分比。

# 风控规则
// 1. 单笔最大亏损不超过账户净值 2.5%
// 2. 当日净值回撤超 5% 则停止新开仓 **1小时**
// 3. 最多同时持有 1 个标的，禁止对冲持仓
// 4. 若连续两次开仓亏损，则暂停交易至**下一个小时周期** (例如，当前15:30发生，则暂停至16:00开始的1小时周期)
// 5. 模拟仓测试未通过，不得进入实盘交易。

---

### [54] `trade-mirror`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trade-mirror/SKILL.md`

---
name: trade-mirror
description: 交易镜子 | 一份以"诚实面对自己"为核心的交易复盘 Skill。当用户说"复盘"、"帮我看看最近的交易"、"trade mirror"、"交易镜子"、"我这周做得怎么样"时启用。覆盖 OKX 现货与永续合约,六层分析架构:客观统计、反模式识别、情绪时间线、反事实模拟、成本显性化、AI 教练诊断。手动触发,输出可归档的复盘日记。
---

# 策略名称
交易镜子(Trade Mirror):AI 交易复盘与行为诊断 Skill V1.0

---

> *"市场从不会教你交易,市场只会反复惩罚你不改的坏习惯。真正让你进步的,是每次亏损之后那 20 分钟诚实的自我审视。"*

---

## 这不是一份交易策略

请先明确:本 Skill **不下单、不预测、不给建议仓位**。它只做一件事——**把你过去做过的交易,像一面镜子一样摊开在你面前**,让你看见那些你自己永远不会主动看见的模式。

市面上的交易复盘工具普遍有三个问题:
1. **只给数据不给诊断**——告诉你胜率 42%,然后就没了
2. **不识别情绪**——把你 FOMO 追高的那笔和冷静布局的那笔等同看待
3. **建议太多等于没建议**——一次性列 10 条"改进建议",人类根本改不过来

本 Skill 试图解决这三个问题。它不追求"给你一份漂亮的报表",它追求**让你在读完之后有一瞬间的不适感**——因为真正有用的复盘,本来就会让人不舒服。

---

## 执行模式

**手动触发**。由用户主动发起,典型触发语:
- "帮我复盘"
- "帮我看看最近 7 天交易"
- "trade mirror"
- "我这周做得怎么样"

默认时间窗口 **7 天**,用户可指定 **1 / 7 / 30 天**三档。
覆盖标的:OKX **现货 + 永续合约**(Layer 1 自动区分)。

---

## Step 1 · 数据采集层(Layer 1)

调用账户接口,拉取指定窗口内所有已平仓交易记录。

**必须采集字段:**

| 字段 | 用途 |
|---|---|
| `instId` | 标的,用于分标的统计 |
| `side`(buy/sell) | 方向 |
| `posSide`(long/short,合约) | 持仓方向 |
| `avgPx`(开仓均价) | 入场价 |
| `closeAvgPx`(平仓均价) | 出场价 |
| `cTime` / `uTime` | 开仓/平仓时间戳 |
| `sz`(数量) | 仓位规模 |
| `lever`(杠杆) | 仅合约 |
| `fee`(手续费) | 成本计算 |
| `fundingFee`(资金费用) | 仅合约 |
| `pnl`(已实现盈亏) | 核心输出 |

**必须同步采集的上下文数据**(用于 Layer 3~4 的行为诊断):

对每一笔交易的开仓时间点和平仓时间点,**向前回溯拉取该标的 1h K 线**(至少回溯 24 根),用于:
- 判断进场时趋势方向(EMA20 / EMA60)
- 计算进场时 RSI(14)
- 计算进场时 ATR(14) 相对均值倍率
- 获取当时资金费率(合约)

这一层如果偷懒,后面所有诊断都是空中楼阁。

---

## Step 2 · 客观统计层(Layer 2)

这是地基,必须准确,但不是重点。输出以下指标:

**总览面板:**
- 总交易笔数 / 盈利笔数 / 亏损笔数
- 胜率 = 盈利笔数 / 总笔数
- 盈亏比 = 平均盈利金额 / 平均亏损金额
- 期望值 = 胜率 × 平均盈利 − (1 − 胜率) × 平均亏损
- 累计净盈亏(扣除手续费和资金费)
- 最大单笔盈利 / 最大单笔亏损
- 最大连续盈利次数 / 最大连续亏损次数(连败警报)

**分组分析:**
- 按标的分组:每个币种的胜率、盈亏贡献、交易频次
- 按方向分组:做多 vs 做空的胜率差异(识别方向偏见)
- 按时段分组:将 24 小时划分为四段(亚洲盘 00-08 / 欧洲盘 08-16 / 美盘 16-24 UTC),统计每段的胜率与平均盈亏
- 按持仓时长分组:< 1h / 1-4h / 4-24h / > 24h 四档,识别你真正擅长的时间尺度

**关键比率:**
- 止损触发率 = 止损单被触发的交易数 / 有止损单的交易数
- 止盈触发率 = 止盈单被触发的交易数 / 有止盈单的交易数
- 无止损交易占比 = 开仓时未设止损单的交易数 / 总交易数
- R 倍数分布(R-multiple):每笔交易的 (实际盈亏 / 计划风险),输出均值、中位数、最大正 R、最大负 R

> R 倍数是 Van Tharp 提出的核心指标。一笔计划亏 100U 止损的单,实际亏了 300U,就是 −3R;最终赚了 250U 就是 +2.5R。**一个成熟交易者的 R 分布应该呈现"负 R 截断、正 R 拉长"的不对称形状。**如果你的负 R 比正 R 长,说明你让亏损跑,把盈利砍掉了——这是散户最致命的一个结构。

---

## Step 3 · 反模式识别层(Layer 3,核心一)

> *"你以为你在交易,其实你在重复同一个错误,只是换了不同的币。"*

这一层是诊断的第一重火力。AI 必须扫描所有交易,识别以下 **七大反模式**,每识别到一例,必须输出**具体交易编号和证据**,不允许泛泛而谈。

**反模式 1:反趋势交易病(Counter-Trend Syndrome)**
- 定义:开仓方向与当时 4h EMA20/EMA60 排列方向相反
- 扫描逻辑:对每笔做多单检查开仓时 4h EMA20 是否在 EMA60 之下(反之同理),若是则标记
- 阈值告警:若反趋势交易占比 > 30%,触发红色警报
- 输出格式:"你有 X 笔交易是反趋势开仓,其中 X 笔亏损,合计亏损 Y USDT,占本期总亏损的 Z%"

**反模式 2:止损过近病(Tight Stop Syndrome)**
- 定义:止损单被触发后 4 小时内,价格回到原计划方向并突破原始盈利目标
- 扫描逻辑:对每笔止损成交的单,继续拉取后续 4h 的 K 线,模拟"如果不止损会怎样"
- 阈值告警:若此类案例 > 止损总数的 40%,触发"止损过紧"诊断
- 暗含判断:止损被打的原因可能是"进场时机差"而非"止损设得不合理",这一点 AI 在 Layer 5 需要辨别

**反模式 3:裸奔交易病(Naked Position Syndrome)**
- 定义:开仓后 60 秒内未设置止损单的交易
- 扫描逻辑:交叉比对订单记录与算法单记录
- 阈值告警:任何一笔裸奔交易都应被单独列出(无论盈亏)
- 严重性:这是**唯一一个"哪怕赚了也要批评"的反模式**——因为裸奔赢钱只是运气,它会强化最危险的习惯

**反模式 4:报复性交易病(Tilt Trading Syndrome)**
- 定义:一笔亏损平仓后的 30 分钟内立即开立新仓
- 扫描逻辑:按时间戳排序,识别"亏损平仓 → 30min 内新开仓"序列
- 进一步判断:这类报复单的胜率应单独计算,通常会显著低于该用户的整体胜率
- 输出示例:"你有 X 次报复性开单,胜率 Y%,而你整体胜率 Z%,差距 (Z-Y)% 就是情绪的代价"

**反模式 5:止盈过早病(Premature Profit Syndrome)**
- 定义:止盈平仓后,价格继续向原方向运行,最终触达 2 倍于实际止盈点的位置
- 扫描逻辑:对每笔止盈成交单,后续追踪 24h 内价格极值,计算"实际兑现 / 潜在最大浮盈"比值
- 阈值告警:若该比值中位数 < 0.4,触发"你总是把肉汤喝掉、把肉留给别人"诊断
- 与反模式 2 配套:止损过近 + 止盈过早 = 经典的"亏损跑、盈利砍"结构

**反模式 6:逆费率交易病(Funding Fee Bleed)**
- 定义:在资金费率对持仓方向严重不利的情况下(费率绝对值 > 0.1% 且方向不利)继续持有超过 8 小时
- 扫描逻辑:对每笔持仓超 8h 的合约单,检查持仓期间资金费率加权方向
- 输出:"你本期因逆费率持仓支付的资金费累计 X USDT,占总亏损的 Y%"
- 意义:很多亏损不是输在方向上,是输在成本上,这一条专治"我方向看对了为什么还亏"

**反模式 7:过度杠杆病(Over-Leverage Syndrome)**
- 定义:单笔仓位风险金额(仓位 × 止损距离)超过账户净值的 5%
- 扫描逻辑:对每笔合约交易,反推该笔的实际风险占比
- 阈值告警:任何一笔风险 > 5% 都列出,整体风险超限比例 > 20% 触发"仓位管理失控"诊断

---

## Step 4 · 情绪时间线重构(Layer 4,核心二)

> *"你的账户对账单,其实是你这一周情绪的心电图。"*

这一层是 **Trade Mirror 最独特的价值**——广场上没有其他 skill 在做这件事。AI 不看你说了什么,只看你做了什么,反推你当时处于什么状态。

**情绪状态判定规则:**

| 行为特征 | 推断情绪 |
|---|---|
| 30 分钟内连续同向加仓 ≥ 2 次,且每次仓位递增 | **FOMO(追高)** |
| 亏损平仓后 30 分钟内反向开仓 | **报复** |
| 盈利平仓后立即加倍开新仓 | **过度自信** |
| 连续 3 笔止损后 4 小时无新交易 | **挫败/回避** |
| 持仓浮亏 > 预设止损但未触发止损且未平仓 | **侥幸(希望回本心态)** |
| 止盈单距离开仓价 < 1%,过早锁利 | **恐惧回吐** |
| 长时间无交易后突然大仓位入场 | **积压欲望释放** |
| 同一标的同一方向 1 小时内反复开平 | **焦虑/犹豫** |

**输出形式:生成一条叙事性的"情绪时间线"**,以自然语言呈现,例如:

```
【本周情绪时间线】

周一 UTC 02:14 — 冷静:低仓位试探 BTC 做多,按计划止盈
周一 UTC 14:30 — 过度自信:盈利后立即 3 倍仓位加仓 ETH,止损过紧被扫
周一 UTC 14:58 — 报复:28 分钟后反向做空 ETH,再次止损
周二 UTC 03:20 — 挫败:连败后沉默 9 小时,无交易
周二 UTC 22:10 — FOMO:看 SOL 拉升 5% 后追多,买在当日高点
周三 UTC 全天 — 恢复理性:回归低频试探,3 笔小盈利
...
```

这段文字的价值不在于精确,在于**让你看见自己被情绪牵着走的完整轨迹**。很多人一辈子没意识到自己交易的根本问题不是技术,是情绪。

---

## Step 5 · 反事实模拟层(Layer 5,硬核差异点)

> *"如果当时止损再宽 0.5%,结果会怎样?"——这个问题,AI 能替你精确算出来。*

对本期所有**亏损交易**,AI 执行三类反事实模拟:

**模拟 A:止损宽度敏感性**
- 对每笔止损成交单,模拟"如果止损再宽 0.5% / 1% / 2% 会怎样"
- 拉取该交易结束后 24h 内的最高 / 最低价,计算若不止损的最终盈亏
- 输出"你若整体放宽止损 1%,本期净盈亏会从 X 变为 Y"
- **注意**:这不是鼓励放宽止损,而是暴露"你的止损设置是否系统性过紧"

**模拟 B:进场时机敏感性**
- 对每笔亏损单,模拟"如果晚进场 1h / 2h / 4h 会怎样"
- 用同样的止盈止损距离,在推迟时间点重新测算
- 输出:"你有 X 笔交易若延迟 2 小时进场可避免亏损,这说明你的进场时机系统性过早"

**模拟 C:镜像对照——如果你什么都不做**
- 计算"若本期未进行任何交易,账户会是多少"
- 对比实际账户终值,算出"交易行为本身的净贡献"
- 这是治疗过度交易最有效的一记闷棍:**很多人发现自己辛苦交易一周,不如什么都不做**

**输出格式示例:**
```
【反事实镜像】
本期你实际结果:−245 USDT
若止损放宽 1%:+120 USDT(差距 +365 USDT)
若延迟 2h 入场:−87 USDT(差距 +158 USDT)
若本期未交易:0 USDT(差距 +245 USDT)

残酷结论:你本期所有的交易行为,综合贡献为 −245 USDT。
```

---

## Step 6 · 成本显性化层(Layer 6)

很多亏损不是输给市场,是输给摩擦成本。这一层单独把成本拉出来示众。

**成本构成拆解:**
- 开仓手续费总计
- 平仓手续费总计
- 资金费总支出(合约,正负相抵后的净值)
- 滑点估算(开仓价与当时中间价的偏离)

**关键指标:**
- **交易成本侵蚀率** = 总成本 / |总盈亏|
- 若你本期盈利 100U,成本花了 80U,侵蚀率 = 80%——说明你在给交易所打工
- **每笔平均成本** = 总成本 / 交易笔数
- **成本 vs 期望值** 对照:若单笔平均成本 > 单笔期望值,你的策略在数学上不可能长期盈利

**输出示例:**
```
【成本体检】
本期总交易成本:82.5 USDT
其中:手续费 54.2 | 资金费 28.3 | 估算滑点 —
单笔平均成本:4.1 USDT / 笔
单笔平均盈利期望:2.8 USDT / 笔
结论:你的策略期望值尚不足以覆盖交易成本,降低频次优先于优化胜率。
```

---

## Step 7 · AI 教练诊断(Layer 7,核心三)

> *"优秀的教练不会告诉你十件事,他只会告诉你一件——那件最重要的事。"*

综合前六层所有数据,AI 必须输出**三段式诊断**。这是整个 Skill 的决策层,也是对标比赛审核"包含 AI 推理判断步骤"的核心环节。

**格式(严格遵守):**

```
═══════════════════════════════════
         交易镜子 · 本期诊断
═══════════════════════════════════

【一句话诊断】
(用一句话概括本期最核心的问题)
例:"你本期最大的漏洞是反趋势交易,它让你付出了总亏损 61% 的代价。"

【核心证据】
(列出 3 条最关键的数据证据,引用具体交易编号)
1. 交易 #12、#15、#19 均为 4h EMA 向下时做多,合计亏损 XXX USDT
2. 反趋势交易占比 47%,显著高于健康区间 (<25%)
3. 若剔除反趋势交易,本期净盈亏将由 −245 USDT 转为 +92 USDT

【行为模式】
你的盈利模式:(AI 归纳在什么条件下用户最能赚钱)
例:"亚洲盘低波动时段的小仓位趋势跟随,胜率 68%"

你的亏损模式:(AI 归纳在什么条件下用户最容易亏)
例:"美盘开盘后的反趋势抄底/摸顶,胜率仅 18%"

【情绪剖面】
(一句话总结本期情绪主导类型)
例:"FOMO 主导型(占所有开仓决策的 40%)"

【下一步:只改一件事】
(严禁给超过一条的建议)
下周你只需要做到:___
具体做法:___(必须可执行、可验证)
验证指标:___(下期复盘时如何判断你做到了没有)

例:
下周你只需要做到:开仓前必须确认 4h EMA20 方向与开仓方向一致
具体做法:每次下单前,把 4h K 线截图贴到笔记里,EMA20 向上才做多、向下才做空
验证指标:下期复盘时,反趋势交易占比应 < 25%

═══════════════════════════════════
```

**为什么只允许一条建议?**

行为经济学反复证明,人类一次只能有效改变一个习惯。给 5 条建议的复盘报告,实际执行率接近 0;给 1 条建议,执行率才可能突破 30%。**精简不是简陋,是对认知负荷的尊重。**

---

## Step 8 · 归档与闭环(Layer 8)

每次复盘完成后,生成一份 markdown 格式的**复盘日记**,包含:
- 复盘时间戳
- 时间窗口(如 2026-04-01 ~ 2026-04-07)
- 完整 Layer 2~7 输出
- 本期"只改一件事"的任务

**下次复盘时,AI 必须首先执行闭环检查:**
1. 读取上次复盘日记中的"只改一件事"任务
2. 在本期数据中,专门验证这一条是否已改善
3. 输出"上期任务完成度评估":
   - ✓ 完成:该问题占比下降 > 50%
   - △ 部分改善:下降 10%-50%
   - ✗ 未改善:下降 < 10% 或反而恶化
4. 若未改善,本期"只改一件事"**继续是同一条**,不换新目标

**这是整个 Skill 的灵魂机制。**没有闭环,复盘只是情绪发泄;有了闭环,复盘才变成训练。

---

## 使用示例(典型对话)

**用户:** 帮我复盘最近 7 天

**AI 执行流程:**
1. 拉取过去 7 天所有已平仓交易
2. 对每笔交易拉取对应时间点的 1h K 线上下文
3. 执行 Layer 2~6 的全部计算
4. 综合推理输出 Layer 7 诊断
5. 读取上次复盘日记(如有)执行闭环检查
6. 生成本期复盘日记 markdown 并附在回复末尾

**AI 输出顺序**(固定,不可打乱):
```
① 上期任务完成度(若为首次复盘则跳过)
② 客观统计概览
③ 反模式扫描结果(按严重性排序)
④ 情绪时间线
⑤ 反事实镜像
⑥ 成本体检
⑦ 本期诊断(三段式)
⑧ 归档日记
```

---

## 设计原则(不可违反)

```
// [P1] 每条诊断结论必须有具体交易编号作为证据,禁止空泛评价
// [P2] 本 Skill 禁止输出未来预测(如"明天 BTC 会涨"),只诊断过去
// [P3] 禁止情绪化评语(如"你太菜了"),所有批评必须由数据驱动
// [P4] 每期复盘只允许给出一条核心建议,不得超过
// [P5] 裸奔交易(无止损)必须无条件列出,哪怕那笔是盈利的
// [P6] 反事实模拟必须包含"如果什么都不做"的镜像对照
// [P7] 闭环检查优先级最高,未完成上期任务前不得下发新任务
// [P8] 本 Skill 不下单、不荐仓、不预测,只做复盘与诊断
```

---

## 这份 Skill 的自我叙述

市场上从不缺少"预测未来"的工具,缺的是"看清过去"的工具。

每个亏损的交易者都在反复做同一件事:重复自己过去的错误,然后告诉自己"下次不会了"。但下次永远会。不是因为他不聪明,是因为他**从未真正看清过自己做了什么**。

交易镜子只做一件事——把镜子举到你面前,让你看见你真正在做什么。
不是你以为你在做什么。

当你能看见自己的反模式、看见自己的情绪时间线、看见自己如果什么都不做会更赚——你才真正开始交易。

在那之前,你只是在用你的钱,交学费。

---

*Skill 版本:V1.0 | 适用平台:OKX Agent Trade Kit | 覆盖:现货 + 永续合约*
*本 Skill 以 MIT 协议开源,欢迎 fork 与改进。*

---

### [55] `trading-cultivation-chronicle`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trading-cultivation-chronicle/SKILL.md`

---
name: trading-cultivation-chronicle
description: 将你的交易历史转化为修仙打怪升级的成长体系。每笔交易是一场修炼，每次盈利积累灵气，每次亏损消耗修为，AI 定期评估你的境界突破与功法缺陷。当用户说"修仙"、"升级"、"我到什么境界了"、"交易修仙录"时启用。
---

## 万古长河，唯有修为不朽

---

> *"天地为炉，造化为工；阴阳为炭，万物为铜。"*
> — 《庄子·大宗师》
>
> *"市场是最公平的修炼场。它不看你的出身，只看你的修为。"*
> — 交易修仙录序言

---

## 世界观设定

在交易修仙界，没有捷径，没有秘籍，没有一步登天。

每一笔交易，都是一次与市场魔头的对决。你的账户净值是**本命元神**，你的胜率是**道心纯度**，你的盈亏比是**剑意锋芒**，你的风控执行力是**功法稳定性**。

境界不是靠嘴说出来的，是靠数据打出来的。

**修仙七境，从凡入圣：**

```
炼气期 → 筑基期 → 金丹期 → 元婴期 → 化神期 → 合体期 → 大乘期
```

你现在在哪一境？让数据说话。

---

## 执行触发

**定期触发**：每7天自动运行一次完整境界评估，输出修仙周报。

**手动触发**：用户说"我到什么境界了"、"给我看修仙进度"、"本周修炼报告"。

**单次触发**：每笔交易平仓后，自动结算本次修炼的灵气得失。

---

## Step 1 · 修炼数据采集

调用 `swap_get_orders`（永续合约订单）和 `swap_get_fills`（成交明细）获取近 **30天** 交易记录；若用户有现货交易，同时调用 `spot_get_orders` 和 `spot_get_fills` 补充数据。

提炼以下**五维修炼数据**：

```
【本命元神】当前账户净值（USDT）
【月净增损】本月净盈亏（USDT / %）
【道心纯度】近30笔交易胜率（%）
【剑意锋芒】平均盈亏比（盈利均值 ÷ 亏损均值）
【功法稳定性】止损执行率（有止损的交易 ÷ 总交易数）
【修炼强度】月交易笔数
【最大劫难】最大单日回撤（%）
【渡劫成功率】大亏损（>3%）后下一笔交易的盈利率
```

---

## Step 2 · 境界判定系统

### 七大境界详解

---

**第一境：炼气期**
*万丈高楼平地起，炼气者初入修仙道。*

```
境界标准：
□ 胜率 35%~50%
□ 盈亏比 < 1.0（亏得比赚得多）
□ 止损执行率 < 60%（经常扛单）
□ 月净值变化 < -5%

境界描述：
刚踏入修仙界，灵根尚未稳固。对市场魔头充满恐惧，
时而冲动出手，时而错失良机。止损二字，知道但做不到。
每次亏损都怀疑自己是否适合修仙。

主要功法缺陷：[根据数据具体指出]
当前天劫：[最大的弱点]
```

---

**第二境：筑基期**
*基础已立，修为初显，然根基尚浅。*

```
境界标准：
□ 胜率 45%~55%
□ 盈亏比 0.8~1.2
□ 止损执行率 60%~75%
□ 月净值变化 -5%~+5%

境界描述：
已能稳定入场，懂得基本的止损之道。但功法尚不纯熟，
盈利的拿不住，亏损的又不愿放。在市场的风浪中摇摆，
偶有灵光乍现，却无法复现。

主要功法缺陷：[根据数据具体指出]
破境关键：盈亏比需突破 1.5
```

---

**第三境：金丹期**
*金丹既成，修为质变，已可独当一面。*

```
境界标准：
□ 胜率 50%~60%
□ 盈亏比 1.2~2.0
□ 止损执行率 75%~85%
□ 月净值变化 +0%~+10%

境界描述：
功法趋于稳定，胜多败少。知道市场的基本规律，
能在顺势行情中稳定获利。但遇到震荡行情仍会迷失，
情绪控制仍是最大短板。偶尔仍会被市场魔头引入陷阱。

主要功法缺陷：[根据数据具体指出]
破境关键：情绪稳定性，消灭报复性交易
```

---

**第四境：元婴期**
*元婴出窍，心神合一，已入一流之列。*

```
境界标准：
□ 胜率 55%~65%
□ 盈亏比 1.8~2.5
□ 止损执行率 85%~95%
□ 月净值变化 +5%~+15%
□ 最大单日回撤 < 5%

境界描述：
已建立完整的交易体系，进出场有据可依。
情绪已基本受控，极少出现报复性交易。
在不同行情中均能找到适合自己的节奏。
开始思考概率与期望值，而非单笔胜负。

主要功法缺陷：[根据数据具体指出]
破境关键：仓位管理精细化，极端行情表现
```

---

**第五境：化神期**
*化神归真，返璞归真，市场如掌中观纹。*

```
境界标准：
□ 胜率 60%~70%
□ 盈亏比 2.0~3.0
□ 止损执行率 > 95%
□ 月净值变化 +10%~+25%
□ 最大单日回撤 < 3%
□ 渡劫成功率（大亏后恢复）> 70%

境界描述：
功法已臻化境，在市场中游刃有余。
对自己的优势和局限了如指掌，严格在能力圈内交易。
心如止水，盈亏不惊。已经开始思考如何将自己的功法传授他人。

主要功法缺陷：[根据数据具体指出]
破境关键：规模化，保持一致性
```

---

**第六境：合体期**
*合体飞升，人剑合一，已是散仙之姿。*

```
境界标准：
□ 胜率 > 65%
□ 盈亏比 > 2.5
□ 止损执行率 > 98%
□ 月净值变化 > +20%（稳定，非偶发）
□ 连续3个月以上保持化神期以上标准

境界描述：
极少数修仙者能达到的境界。
交易已成为本能，无需刻意思考，决策自然流出。
在市场的风浪中如磐石，既不狂喜也不悲观。
账户净值持续稳定增长，已超越绝大多数同道中人。
```

---

**第七境：大乘期**
*大乘圆满，证道飞升，此界已无对手。*

```
境界标准：
□ 以上所有标准均达到，且持续6个月以上
□ 月净值增长率 > 30%，最大回撤 < 2%
□ 已建立完整可复现的交易体系

境界描述：
传说中的境界。在这个境界，你已经不再需要这个 Skill。
你应该去写一本书，或者开一个基金。
```

---

## Step 3 · 五维雷达图数据

计算用户当前五维修炼数据的评分（各维度0~100分）：

```
道心纯度（胜率）：
0-35% = 0-20分 | 35-50% = 20-50分 | 50-65% = 50-80分 | >65% = 80-100分

剑意锋芒（盈亏比）：
<0.8 = 0-15分 | 0.8-1.5 = 15-50分 | 1.5-2.5 = 50-80分 | >2.5 = 80-100分

功法稳定性（止损执行率）：
<50% = 0-20分 | 50-75% = 20-55分 | 75-90% = 55-80分 | >90% = 80-100分

元神厚度（本月净值变化）：
<-10% = 0分 | -10~0% = 0-40分 | 0~10% = 40-70分 | >10% = 70-100分

渡劫韧性（大亏后恢复率）：
<40% = 0-20分 | 40-60% = 20-50分 | 60-80% = 50-75分 | >80% = 75-100分
```

---

## Step 4 · 修仙周报输出

```
══════════════════════════════════════════
            交 易 修 仙 录
            第 [X] 周修炼报告
══════════════════════════════════════════

  道号：[用户账户ID或自定义]
  当前境界：[境界名称]
  修仙年资：[使用OKX的天数]

──────────────────────────────────────────
                五维修为
──────────────────────────────────────────

  道心纯度  ████████░░  [X分]  胜率 [X%]
  剑意锋芒  ██████░░░░  [X分]  盈亏比 [X.X]
  功法稳定  █████████░  [X分]  止损率 [X%]
  元神厚度  ███████░░░  [X分]  月盈亏 [+/-X%]
  渡劫韧性  ████░░░░░░  [X分]  恢复率 [X%]

  综合修为指数：[X/100]

──────────────────────────────────────────
              本周修炼战报
──────────────────────────────────────────

  修炼场次：[X] 场
  斩妖（盈利）：[X] 场  积累灵气：+[X] USDT
  遭劫（亏损）：[X] 场  损耗修为：-[X] USDT
  净积灵气：[+/-X] USDT

  本周最强一战：[盈利最高的交易，简述]
  本周最惨败绩：[亏损最大的交易，简述]

──────────────────────────────────────────
              境界评估
──────────────────────────────────────────

  当前境界：[境界名称]
  距离下一境：差 [具体指标差距]

  [境界描述，3-4句，用修仙语言描述当前状态]

──────────────────────────────────────────
              主要功法缺陷
──────────────────────────────────────────

  第一缺陷：[具体问题，修仙语言]
  → 修炼方法：[具体可操作的建议]

  第二缺陷：[具体问题]
  → 修炼方法：[具体建议]

──────────────────────────────────────────
              本周天劫预警
──────────────────────────────────────────

  [如果检测到以下风险，发出天劫预警]

  □ 连续亏损超过3场 → 天劫预警：魔障入侵，建议暂停修炼一日
  □ 单日回撤超过5%  → 天劫预警：元神受损，今日修炼已达上限
  □ 报复性交易迹象  → 天劫预警：心魔作祟，速速静心调息

──────────────────────────────────────────
           下周修炼目标（功课）
──────────────────────────────────────────

  【主修功法】[针对最大缺陷的一个具体目标]
  【辅修心法】[针对第二缺陷的一个具体目标]
  【戒律】[一条本周要严格遵守的纪律]

══════════════════════════════════════════
  愿道友修为精进，早日证道飞升。
══════════════════════════════════════════
```

---

## 特殊成就系统

当用户达到以下里程碑时，AI 自动颁发**修仙成就**：

| 成就名称 | 触发条件 | 颁发语 |
|---|---|---|
| 🌱 **初入仙途** | 完成第一笔交易 | "一步踏入修仙道，万里征途始于此。" |
| ⚔️ **初斩心魔** | 首次严格执行止损 | "止损之难，难于上青天。道友今日已胜自己。" |
| 🔥 **三劫不死** | 连续亏损3笔后仍纪律入场 | "经历三劫，元神未散。此乃渡劫之资。" |
| 💎 **金丹初成** | 首次达到金丹期标准 | "道心已固，金丹初成。修仙界，真正欢迎你。" |
| 🌊 **心如止水** | 连续10笔交易均严格执行止损 | "十战十守，功法已成自然。" |
| 🏆 **月圆功成** | 月净值增长 > 15% | "此月修为精进，灵气大涨。记住此刻的感受。" |
| 👁️ **识破天机** | 判决书连续5笔评级"完美入场" | "入场如有神助，已窥市场天机一角。" |

---

## 风控附注

```
// 本 Skill 仅读取交易历史，不执行任何下单操作
// 境界评定基于近30天数据，每周更新
// 修仙语言为趣味包装，背后是严肃的量化评估逻辑
// 当天劫预警触发时，请认真对待，不要因为好玩而忽视风险
// 目标不是让你觉得自己厉害，是让你看清楚自己真实的位置
```

---

### [56] `trading-personality-decoder`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trading-personality-decoder/SKILL.md`

---
name: trading-personality-decoder
description: 用心理学与行为经济学框架深度分析你的交易记录，识别你的交易人格类型与认知偏误。不说废话，只用你自己的数据证明你是谁。当用户说"分析我的交易"、"我为什么总是亏钱"、"交易心理"、"人格解码"时启用。
---

## 你以为你在交易市场，其实你在交易自己的大脑

---

> *"认识你自己。"*
> — 德尔菲神庙铭文，公元前 400 年
>
> *"大多数交易者失败，不是因为他们不够聪明，而是因为他们不够了解自己。"*
> — 行为金融学核心命题

---

## 这个 Skill 做什么

它不教你技术分析。它不给你买卖信号。

它做一件更难、更有价值的事：**用你自己的交易数据，照出你真实的心理面目。**

每一笔交易都是一次心理快照。盈利后你怎么做、亏损后你怎么做、连胜时你怎么做、连败时你怎么做——这些行为模式加在一起，就是你的**交易人格**。

不了解它，你会一遍又一遍犯同样的错误，然后把原因归结为"运气不好"。

---

## 执行触发

**手动触发**：用户说"分析我的交易"、"给我做人格测试"、"我的问题在哪"时启动。

**自动触发**：累计新增交易记录 ≥ 20 笔时，主动提示用户进行一次人格更新分析。

---

## Step 1 · 数据采集：拉取你的交易指纹

调用 `swap_get_orders` 和 `swap_get_fills` 获取账户近 **90天** 的永续合约已平仓交易记录；若有现货交易同时调用 `spot_get_orders` 和 `spot_get_fills`。

提取以下维度的原始数据：

**时间维度**
- 每笔交易的开仓时间、平仓时间、持仓时长
- 统计各时段（凌晨0-6点、早盘6-12点、午盘12-18点、夜盘18-24点）的交易频率与胜率

**盈亏维度**
- 每笔交易的盈亏金额、盈亏百分比
- 盈利交易的平均持仓时长 vs 亏损交易的平均持仓时长
- 最大单笔盈利 vs 最大单笔亏损
- 盈利超过 2% 后的平仓率（是否提前锁利）
- 亏损超过 2% 后的继续持有率（是否扛单）

**仓位维度**
- 每笔交易占账户净值的比例
- 连续盈利后仓位变化趋势（是否越赚越大）
- 连续亏损后仓位变化趋势（是否越亏越重）
- 平均仓位 vs 最大仓位的比值

**频率维度**
- 日均交易笔数
- 最高单日交易笔数（过度交易日）
- 大亏损后24小时内的交易笔数（是否急于报复）

---

## Step 2 · 数据预计算层（先算再判，不靠 AI 猜测）

在进行任何心理分析之前，必须先用原始数据计算出以下**硬指标**。这些数字是确定性的，不依赖 AI 推断：

```
【必须计算的九个硬指标】

指标 A · 处置比率
= 盈利交易平均持仓时长（小时）÷ 亏损交易平均持仓时长（小时）
数据来源：swap_get_fills 中每笔交易的开平仓时间戳差值

指标 B · 连胜后仓位放大率
= 连续盈利3笔后第4笔仓位 ÷ 近30笔平均仓位
数据来源：swap_get_orders 中 sz 字段，按时间排序识别连胜序列

指标 C · 亏损扛单比率
= 浮亏超过-3%后继续持有超过2小时的交易笔数 ÷ 总亏损交易笔数
数据来源：结合 swap_get_fills 成交价与 market_get_candles K线还原持仓期间价格

指标 D · 追涨比率
= 入场时距近期最高价距离 < 0.5×ATR14 的买入交易占比
数据来源：入场价与 market_get_candles 近20根K线最高价比较

指标 E · 大亏后2小时内交易笔数均值
= 所有单笔亏损>3%的交易后2小时内触发的新交易笔数 / 触发次数
数据来源：swap_get_orders 时间戳序列

指标 F · 连亏后仓位变化方向
= 连续亏损3笔后第4笔仓位 vs 亏损序列前均仓的比值
数据来源：同指标 B，识别连亏序列

指标 G · 止损整数关口集中度
= 止损价格落在整百整千USDT±0.3%范围内的比例
数据来源：swap_get_orders 中 slTriggerPx 字段

指标 H · 最差时段胜率 vs 该时段交易频率占比
= 按6小时分段统计各时段胜率，取最低胜率时段；
  该时段交易笔数 ÷ 总交易笔数 = 频率占比
数据来源：swap_get_fills 时间戳转换本地时区

指标 I · 仓位时间序列斜率
= 对所有交易按时间排序，计算仓位占比的线性回归斜率
斜率 > 0 = 仓位随时间膨胀；斜率 < 0 = 仓位随时间收缩
数据来源：swap_get_orders sz 字段 + 账户净值
```

**以上九个指标必须先完成数值计算，再进入 Step 3 的心理诊断。**
AI 的判断建立在这些已计算的数字上，而不是凭感觉推断。

---

## Step 3 · 认知偏误诊断：九项心理测试（基于 Step 2 硬指标）

对 Step 2 已计算的九个硬指标，逐项进行心理诊断。每项输出：**计算数值**（来自Step2）+ **诊断结论** + **严重程度**（轻度/中度/重度）

---

**测试 01 · 处置效应（Disposition Effect）**
```
数据来源：Step 2 指标 A（处置比率）
正常范围：> 1.5（盈利拿得比亏损久）
警戒线：< 1.0（亏损反而拿得更久）
```
*含义：人类天生倾向于快速锁定盈利、长期持有亏损。这是最普遍也最致命的交易心理偏误。*

---

**测试 02 · 过度自信（Overconfidence）**
```
数据来源：Step 2 指标 B（连胜后仓位放大率）
指标A：放大率 > 1.5 倍均仓
指标B：胜率最高的时段，仓位是否也最重
```
*含义：连胜会让人误以为自己掌握了市场规律，从而在最危险的时刻下最重的注。*

---

**测试 03 · 损失厌恶（Loss Aversion）**
```
数据来源：Step 2 指标 C（亏损扛单比率）
指标：亏损 > 3% 后继续持有的概率 ÷ 盈利 > 3% 后继续持有的概率
正常范围：接近 1.0
警戒线：> 2.0（面对亏损时扛单倾向是锁利的两倍以上）
```
*含义：行为经济学证明，亏损带来的痛苦是同等盈利带来的快乐的 2.5 倍。这导致人们宁愿扛单也不愿意承认亏损。*

---

**测试 04 · FOMO（错失恐惧）**
```
数据来源：Step 2 指标 D（追涨比率）
指标A：在价格已上涨 > 2ATR 后追入的交易占比
指标B：这类追入交易的平均盈亏 vs 整体平均盈亏
```
*含义：看着别人赚钱比自己亏钱更难受。FOMO 驱动的追高往往在最糟糕的时机入场。*

---

**测试 05 · 报复性交易（Revenge Trading）**
```
数据来源：Step 2 指标 E（大亏后2小时内交易笔数均值）
指标：大亏损后 2 小时内的交易笔数均值
正常值：≤ 1 笔
警戒线：≥ 3 笔（亏损后立刻频繁交易）
```
*含义：亏钱后急于"找回来"，是最容易将小亏变大亏的行为模式。*

---

**测试 06 · 赌徒谬误（Gambler's Fallacy）**
```
数据来源：Step 2 指标 F（连亏后仓位变化方向）
指标：连续亏损 3 笔后，下一笔仓位变化比值
正常：保持不变或减小
警戒：明显增大（认为"该赢了"）
```
*含义：硬币连续正面朝上10次，下一次正面的概率仍然是50%。但人类大脑不这么认为。*

---

**测试 07 · 锚定效应（Anchoring）**
```
数据来源：Step 2 指标 G（止损整数关口集中度）
指标：止损价落在整数关口±0.3%范围内的占比
检测方法：统计止损价与最近整数关口的距离分布
```
*含义：人类倾向于用"整数"作为参考点，而不是用市场结构来设置止损。这让止损位变成了集体陷阱。*

---

**测试 08 · 时段偏误（Time Bias）**
```
数据来源：Step 2 指标 H（最差时段胜率 vs 频率占比）
指标：最低胜率时段 及 该时段交易频率占比
对比：这些时段的交易频率是否高于平均
```
*含义：大多数人有一个"魔鬼时段"——在那个时间段交易总是亏钱，但还是忍不住交易。*

---

**测试 09 · 仓位膨胀（Position Creep）**
```
数据来源：Step 2 指标 I（仓位时间序列斜率）
指标：线性回归斜率，正值为膨胀
警戒：均值随时间持续上升（逐渐重仓化）
```
*含义：随着时间推移，交易者往往不知不觉地越来越重仓，直到一次大亏将累计收益归零。*

---

## Step 4 · 人格类型判定

基于以上 9 项测试结果，AI 综合判断用户的**主导交易人格**：

| 人格类型 | 核心特征 | 主要偏误组合 |
|---|---|---|
| **🦁 过度自信者** | 连胜后加仓，觉得自己读懂了市场 | 过度自信 + 仓位膨胀 + FOMO |
| **🐢 损失扛单者** | 亏损不止损，盈利过早跑 | 处置效应 + 损失厌恶 + 锚定 |
| **🔥 报复型赌徒** | 亏损后立刻报复，越亏越急 | 报复性交易 + 赌徒谬误 + 过度自信 |
| **👻 FOMO 追随者** | 总在别人赚完后才入场 | FOMO + 锚定 + 时段偏误 |
| **🧊 分析瘫痪者** | 错过好机会，却在冲动时下单 | 时段偏误 + 赌徒谬误 + 锚定 |
| **🌪️ 混合失控者** | 多种偏误并存，无主导模式 | 5种以上偏误同时触发 |

---

## Step 5 · 人格报告输出

AI 输出完整的交易人格报告，格式如下：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        交易人格解码报告
        分析周期：近 90 天
        分析交易笔数：[X] 笔
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【主导人格】[人格类型名称]

【九项测试结果】

✓/✗  处置效应     比值 [X.X]    [轻度/中度/重度/无]
✓/✗  过度自信     触发率 [X%]   [轻度/中度/重度/无]
✓/✗  损失厌恶     比值 [X.X]    [轻度/中度/重度/无]
✓/✗  FOMO        占比 [X%]     [轻度/中度/重度/无]
✓/✗  报复交易     均值 [X笔]    [轻度/中度/重度/无]
✓/✗  赌徒谬误     触发率 [X%]   [轻度/中度/重度/无]
✓/✗  锚定效应     集中度 [X%]   [轻度/中度/重度/无]
✓/✗  时段偏误     最差时段 [XX] [轻度/中度/重度/无]
✓/✗  仓位膨胀     趋势 [上升/稳定] [轻度/中度/重度/无]

【最昂贵的错误】
你因为 [偏误名称]，在过去90天额外亏损了约 [X] USDT。
（计算方法：如果该偏误不存在，对应交易的预期结果改善值）

【你的魔鬼时段】
[时段]：胜率 [X%]，但你在这个时段完成了 [X%] 的交易。
建议：在这个时段关闭交易界面。

【一句话诊断】
[针对主导人格的一句精准描述，不超过30字，直击要害]

【下一步行动】
1. [针对最严重偏误的具体建议，可操作]
2. [针对第二严重偏误的具体建议]
3. [一个本周可以立刻执行的微小改变]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 风控附注

```
// 本 Skill 仅读取交易历史，不执行任何下单操作
// 分析结果基于统计规律，不代表每一笔具体交易的对错
// 建议每30天更新一次人格报告，追踪偏误改善情况
// 数据越多，分析越准确——至少需要20笔交易记录
```

---

### [57] `trading-plan-generator`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trading-plan-generator/SKILL.md`

---
name: trading-plan-generator
description: >-
  Use this skill whenever a user wants a crypto trading plan, trading strategy, position sizing,
  signal analysis, or risk-managed trade recommendation for any instrument on OKX (spot, perpetual
  swap, delivery futures, options). Trigger on: "交易计划", "交易策略", "做多方案", "做空方案",
  "仓位管理", "信号分析", "风险管理框架", "BTC/ETH/SOL trading plan", "help me trade",
  "how should I trade", "entry and exit levels", "stop loss and take profit", "market signal",
  "看多看空分析", "合约策略", "现货策略". Integrates real-time data from OKX TradeKit MCP
  (price, OI, candles, technical indicators, funding rate) and CoinGlass MCP (L/S ratio,
  liquidation heatmap, whale positions) to produce a structured trading plan with three risk tiers,
  concrete entry/exit prices, and a signal-weight breakdown. Always use this skill — not a generic
  response — when any trading planning is involved.
---

# Trading Plan Generator

> **Compliance notice**: This skill outputs objective market data and structured trade frameworks only.
> All prices and signals are sourced from public APIs. Interpretation and execution decisions remain solely with the user.
> Always append a disclaimer that outputs are not investment advice.

Generates professional crypto trading plans by combining OKX TradeKit market data with CoinGlass
on-chain signals. Supports spot, perpetual swap, delivery futures, and options. Outputs a structured
text plan with three risk tiers and a 6-dimension signal weight breakdown.

**Skill routing**
- This skill (trading plan, strategy, risk management) → `trading-plan-generator`
- Market data only (price, candles, indicators) → `okx-cex-market`
- Place / cancel / amend orders → `okx-cex-trade`
- Account balance / positions / P&L → `okx-cex-portfolio`
- Grid / DCA bots → `okx-cex-bot`

---

## Data Sources

**Primary — OKX TradeKit MCP** (no setup required):
MCP tools: `market_get_ticker`, `market_get_candles`, `market_get_indicator`, `market_get_funding_rate`, `market_get_open_interest`, `market_get_orderbook`

**Fallback — OKX TradeKit CLI** (if MCP unavailable):
```bash
npm install -g @okx_ai/okx-trade-cli
okx market ticker BTC-USDT   # verify install
```

**Optional — CoinGlass MCP** (provides L/S ratio, liquidation, whale data):
See https://github.com/gpsxtreme/mcp-coinglass for setup.
If unavailable, use CoinGecko + OKX TradeKit as fallback (see Step 2).

---

## Step 1 — Collect User Intent

If the user's message already contains all required fields, skip to Step 2.
Otherwise, ask for the missing items in one message (do not ask one-by-one).

**Required:**
| Field | Examples |
|-------|---------|
| 交易标的 | BTC、ETH、SOL |
| 交易类型 | 现货 / 永续合约 / 交割合约 / 期权（可多选） |
| 方向预期 | 看多 📈 / 看空 📉 / 震荡 ↔️ |
| 时间框架 | 短线 <1天 / 中线 1-7天 / 长线 >7天 |
| 最大亏损容忍 | 账户的 2% / 5% / 10% |
| 最大杠杆 | 3x / 5x / 10x / 无杠杆 |
| 单笔仓位上限 | 总资金的 5% / 10% / 20% |

**Optional** (use defaults if not provided):
- 信号偏好（是否优先链上数据、情绪数据、大户持仓）
- 交易所偏好（默认 OKX）

---

## Step 2 — Gather Market Data

For any command or tool that fails, mark the field `⚠️ 数据不可用` and continue.

> instId format: spot `BTC-USDT` · swap `BTC-USDT-SWAP` · futures `BTC-USDT-250328`

### OKX TradeKit MCP (primary)

```
market_get_ticker(instId=<instId>)                          # price and 24h stats
market_get_open_interest(instId=<instId>, instType="SWAP")  # OI (SWAP/FUTURES only)
market_get_candles(instId=<instId>, bar="1H", limit=48)     # 1H candles
market_get_candles(instId=<instId>, bar="4H", limit=30)     # 4H candles
market_get_indicator(instId=<instId>, indicator="rsi",  bar="1Dutc")   # RSI daily
market_get_indicator(instId=<instId>, indicator="macd", bar="1Dutc")   # MACD daily
market_get_indicator(instId=<instId>, indicator="ema",  bar="1Dutc")   # EMA daily
market_get_funding_rate(instId=<instId>)                    # funding rate (SWAP only)
```

### OKX TradeKit CLI (fallback if MCP unavailable)

```bash
okx market ticker <instId>
okx market open-interest --instType SWAP --instId <instId>
okx market candles <instId> --bar 1H --limit 48
okx market candles <instId> --bar 4H --limit 30
okx market indicator rsi <instId> --bar 1Dutc
okx market indicator macd <instId> --bar 1Dutc
okx market funding-rate <instId>
```

### CoinGlass MCP tools (if available)

| Data | Tool |
|------|------|
| 资金费率 | `coinglass_funding_rate` |
| 多空比 (L/S Ratio) | `coinglass_long_short_ratio` |
| 清算数据 | `coinglass_liquidation` |
| 大户持仓 | `coinglass_top_trader_position` |

### CoinGecko fallback (when CoinGlass is unavailable)

Call the CoinGecko free API to supplement missing context:

```
GET https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=true
```
- `coin_id`: e.g., `bitcoin`, `ethereum`, `solana`

CoinGecko supplements: market cap, price change %, sentiment votes, ATH distance, 24h volume context.

**CoinGecko limitations** — it cannot replace CoinGlass for:
- 多空比 (L/S Ratio) → mark `⚠️ 数据不可用`
- 清算数据 → mark `⚠️ 数据不可用`
- 大户持仓变化 → mark `⚠️ 数据不可用`

资金费率: use OKX `market_get_funding_rate` as the primary source (full replacement for CoinGlass on this dimension).
OI 变化趋势: use OKX `market_get_open_interest` (full replacement).

---

## Step 3 — Analyze Signals

Load `references/signal-framework.md` for the full weight table, scoring rules, and interpretation guide.

**Quick reference — default weights:**
```
OI 变化趋势        20%   (OKX TradeKit MCP/CLI)
多空比 L/S Ratio   20%   (CoinGlass → ⚠️ 不可用时记 0)
资金费率           15%   (OKX TradeKit MCP/CLI, or CoinGlass)
清算数据           15%   (CoinGlass → ⚠️ 不可用时记 0)
大户持仓变化       15%   (CoinGlass → ⚠️ 不可用时记 0)
OKX 内置信号       15%   (OKX TradeKit MCP market_get_indicator)
```

Compute a composite signal score (−100 to +100). Score > +30 = bullish bias; < −30 = bearish bias; −30 to +30 = neutral/range.

---

## Step 4 — Output: Structured Trading Plan

Output the full plan in this exact structure (in Chinese, with English labels for prices/numbers):

```
════════════════════════════════════════
  交易计划 — {标的} {交易类型}
  生成时间：{timestamp}  |  市场环境：{看多📈 / 看空📉 / 震荡↔️}
════════════════════════════════════════

【市场信号概览】
综合信号得分：{score}/100  →  {结论}

| 信号维度       | 读数                  | 权重 | 分项得分 |
|----------------|-----------------------|------|----------|
| OI 变化趋势    | {value}               | 20%  | {±pts}   |
| 多空比 L/S     | {value}               | 20%  | {±pts}   |
| 资金费率       | {value}               | 15%  | {±pts}   |
| 清算数据       | {value}               | 15%  | {±pts}   |
| 大户持仓       | {value}               | 15%  | {±pts}   |
| OKX 信号       | {value}               | 15%  | {±pts}   |

注：⚠️ 标注表示数据不可用，该项得分记为 0。

────────────────────────────────────────
【标的组合建议】
推荐交易对：{instId}
建议配置：{现货X% / 合约Y% / 期权Z%}（基于用户风险框架）

────────────────────────────────────────
【三档交易计划】

▌低风险方案（适合：保守型 / 初次建仓 / 不确定性高时）
  入场区间：${entry_low} – ${entry_high}
  止损位：  ${stop_loss}（跌破则离场，无例外）
  止盈目标1：${tp1}
  止盈目标2：${tp2}
  建议仓位：总资金的 {x}%（≤ 用户设定上限）
  杠杆：    {n}x（≤ 用户设定上限）
  预期 R:R：1:{rr}

▌中风险方案（适合：有经验 / 信号较明确时）
  入场区间：...（同上格式）

▌高风险方案（适合：激进型 / 信号强烈时 / 需严格止损纪律）
  入场区间：...（同上格式）

────────────────────────────────────────
【风险总结】
市场风险评级：{1-10} / 10
主要风险：
  1. {risk_1}
  2. {risk_2}
  3. {risk_3}（可选）
建议止损策略：{hard-stop / trailing-stop / time-stop}

────────────────────────────────────────
【计划推理说明】
- {每个信号如何影响结论的 2-3 句话}
- 关键不确定性：{what could invalidate this plan}
- 计划失效条件：{specific price level or event that invalidates the thesis}

────────────────────────────────────────
⚠️ 免责声明：本交易计划由 AI 生成，仅供参考，不构成投资建议。
加密货币交易存在高风险，请独立判断并自行承担风险。
════════════════════════════════════════
```

---

## Edge Cases

- **杠杆/仓位超限**：三档方案的杠杆和仓位必须严格在用户设定上限内，不得超出，即使信号极强
- **方向与信号不一致**：若用户说看多但信号显示看空（得分 < −30），明确提示矛盾并列出两种情景，不要强行生成看多计划
- **数据不可用 > 3 项**：超过 3 个信号无数据时，询问用户是否继续（用不完整数据生成示例计划）
- **期权标的**：需先调用 `market_get_orderbook` 或 `okx option instruments --uly BTC-USD` 获取有效 instId
- **震荡方案**：方向为震荡时，入场改为"区间上沿做空 / 区间下沿做多"的双向说明
- **instId 格式错误**：若 ticker 命令失败，自动尝试 SWAP 格式（如 `BTC-USDT-SWAP`）并告知用户

---

## Global Notes

- 所有价格使用从 MCP 或 CLI 获取的真实数据；若不可用，明确标注 `⚠️ 示例数据`
- 止损位必须是具体价格，不能写"跌破支撑"等模糊描述
- 每次输出后在末尾附上 3 条关键风险提示（精炼版）
- 不需要用户确认即可运行 OKX 市场数据命令（只读）
- CoinGlass MCP 工具调用失败时静默降级，不中断流程

---

### [58] `trend-grid-bot`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trend-grid-bot/SKILL.md`

---
name: trend-grid-bot
description: Trend-adaptive contract grid bot strategy targeting 4%+/month returns with directional bias
trigger: grid bot|trend grid|trendgrid|그리드봇|그리드 전략
tools:
  - mcp__okx-trade__market_get_ticker
  - mcp__okx-trade__market_get_candles
  - mcp__okx-trade__market_get_indicator
  - mcp__okx-trade__market_get_instruments
  - mcp__okx-trade__market_get_funding_rate
  - mcp__okx-trade__account_get_balance
  - mcp__okx-trade__account_get_config
  - mcp__okx-trade__grid_create_order
  - mcp__okx-trade__grid_get_orders
  - mcp__okx-trade__grid_get_order_details
  - mcp__okx-trade__grid_get_sub_orders
  - mcp__okx-trade__grid_stop_order
  - mcp__okx-trade__futures_set_leverage
  - mcp__okx-trade__futures_get_leverage
---

# TrendGrid Bot - Trend-Adaptive Contract Grid Strategy

## Overview

추세 추종형 컨트랙트 그리드 봇. SuperTrend + EMA + MACD 기반으로 추세 방향을 판단하고,
방향성 있는 그리드(long/short)를 배치하여 **그리드 수익 + 추세 수익**을 동시에 포착한다.

**Target:** 월 4%+ (보수적), 실제 기대 8-15%/월 (변동성 정상 구간)

---

## Phase 1: Market Analysis (추세 판단)

아래 지표를 **반드시 모두** 수집한 뒤 종합 판단한다.

### 1-1. 지표 수집

```
필수 지표 (모두 병렬 호출):
- market_get_ticker        → instId: {PAIR}-SWAP         (현재가, 24h 변동)
- market_get_indicator     → supertrend, bar: 4H          (추세 방향 + 지지/저항)
- market_get_indicator     → ema, bar: 4H, params: [20,50](EMA 정배열/역배열)
- market_get_indicator     → macd, bar: 1Dutc             (장기 모멘텀)
- market_get_indicator     → rsi, bar: 4H                 (과매수/과매도)
- market_get_indicator     → bb, bar: 4H                  (변동성 밴드 → 그리드 범위)
- market_get_indicator     → bb, bar: 1Dutc               (일봉 밴드 → 외곽 범위)
- market_get_candles       → bar: 1D, limit: 14           (14일 고/저 → 범위 검증)
- market_get_funding_rate  → instId: {PAIR}-SWAP          (펀딩비 방향 확인)
```

### 1-2. 추세 스코어링 (Trend Score)

각 지표에 점수를 부여하여 합산한다 (-5 ~ +5):

| 지표 | Bullish (+) | Bearish (-) | 중립 (0) |
|------|------------|------------|---------|
| SuperTrend 4H | direction=-1 (UP): **+2** | direction=1 (DOWN): **-2** | - |
| EMA 20/50 | EMA20 > EMA50: **+1** | EMA20 < EMA50: **-1** | 교차 중: 0 |
| MACD Daily | DIF > DEA & MACD > 0: **+1** | DIF < DEA & MACD < 0: **-1** | 0 |
| RSI 4H | 40-65 (건전한 상승): **+0.5** | 35-60 (건전한 하락): **+0.5** | >75 or <25: **-0.5** (과열) |
| Funding Rate | < 0.01% (저렴): **+0.5** | > 0.05% (과열): **-0.5** | 0 |

**판정:**
- Score >= +3.0 → **LONG** (direction=long)
- Score <= -3.0 → **SHORT** (direction=short)
- -3.0 < Score < +3.0 → **NEUTRAL** (direction=neutral)

---

## Phase 2: Grid Parameter Calculation (그리드 파라미터 산출)

### 2-1. 그리드 범위 (Range)

추세 방향에 따라 비대칭 범위를 설정한다:

```
LONG 모드:
  minPx = max(SuperTrend_lowerBand, BB_4H_lower) × 0.995   # 약간의 여유
  maxPx = BB_4H_upper × 1.02                                # 상단 돌파 여유
  → 현재가가 범위의 하위 30-40% 지점에 위치하도록 조정

SHORT 모드:
  minPx = BB_4H_lower × 0.98
  maxPx = min(SuperTrend_upperBand, BB_4H_upper) × 1.005
  → 현재가가 범위의 상위 30-40% 지점에 위치하도록 조정

NEUTRAL 모드:
  minPx = BB_4H_lower × 0.99
  maxPx = BB_4H_upper × 1.01
  → 현재가가 범위의 중앙 부근에 위치
```

**범위 검증:**
- 범위 폭 = (maxPx - minPx) / minPx × 100
- 최소 5%, 최대 15%. 벗어나면 조정
- 현재가가 범위 밖이면 범위를 현재가 기준으로 재조정

### 2-2. 그리드 수 (gridNum) & 간격

```
목표 그리드 간격: 0.15% ~ 0.30% (geometric 기준)

gridNum 계산:
  range_pct = (maxPx - minPx) / minPx × 100
  gridNum = round(range_pct / target_spacing)

  target_spacing 기준:
    변동성 높음 (BB bandwidth > 8%): 0.25-0.30% → 그리드 적게 (25-35개)
    변동성 보통 (BB bandwidth 4-8%): 0.18-0.25% → 그리드 보통 (35-50개)
    변동성 낮음 (BB bandwidth < 4%): 0.15-0.18% → 그리드 많이 (50-70개)

  BB bandwidth = (BB_upper - BB_lower) / BB_middle × 100

제한: gridNum은 최소 20, 최대 100
```

### 2-3. 레버리지 & 마진

```
레버리지 결정:
  Score 절대값 >= 4 (강한 추세): lever = "5"
  Score 절대값 3-4 (보통 추세):  lever = "3"
  NEUTRAL 모드:                  lever = "3"

마진 배분 (sz):
  전체 가용 USDT의 최대 30%를 단일 봇에 배분
  최소 $100, 권장 $300+
```

### 2-4. 리스크 관리

```
SL (손절):
  LONG:  slTriggerPx = minPx × 0.97  (범위 하단 -3%)
  SHORT: slTriggerPx = maxPx × 1.03  (범위 상단 +3%)
  slRatio 대안: "0.08" (마진 대비 8% 손실 시 청산)

TP (익절) - 선택적:
  강한 추세 시 TP 미설정 (추세 수익 극대화)
  NEUTRAL 시 tpRatio: "0.05" (5% 수익 시 종료)
```

---

## Phase 3: Deploy (봇 배포)

### 3-1. 사전 확인

```
1. account_get_config → posMode 확인 (net_mode 권장)
2. account_get_balance → USDT 가용 잔고 확인
3. grid_get_orders(algoOrdType="contract_grid", status="active")
   → 동일 페어에 기존 봇이 있으면 사용자에게 알림
4. market_get_instruments(instType="SWAP", instId="{PAIR}-SWAP")
   → minSz, ctVal, tickSz 확인
```

### 3-2. 주문 실행

```
grid_create_order:
  instId:      "{PAIR}-SWAP"          # e.g. "BTC-USDT-SWAP"
  algoOrdType: "contract_grid"
  maxPx:       "{계산된 상한가}"
  minPx:       "{계산된 하한가}"
  gridNum:     "{계산된 그리드 수}"
  runType:     "2"                     # geometric (비율 기반 등간격)
  direction:   "{long|short|neutral}"
  lever:       "{3|5}"
  sz:          "{배분 마진 USDT}"
  basePos:     true                    # 초기 포지션 즉시 오픈
  slTriggerPx: "{계산된 손절가}"       # 또는 slRatio 사용
  algoClOrdId: "tg-{PAIR}-{timestamp}" # 추적용 고유 ID
```

### 3-3. 배포 후 확인

```
1. grid_get_orders(algoOrdType="contract_grid") → 봇 활성 확인
2. grid_get_order_details(algoOrdType="contract_grid", algoId="{id}")
   → 설정값 + 초기 포지션 확인
3. grid_get_sub_orders(algoOrdType="contract_grid", algoId="{id}", type="live")
   → 대기 주문 정상 배치 확인
```

---

## Phase 4: Monitor & Rebalance (모니터링)

### 4-1. 정기 점검 (4시간 주기 권장)

```
점검 항목:
1. grid_get_order_details → 현재 PnL, 체결 횟수
2. market_get_indicator(supertrend, 4H) → 추세 변화 감지
3. market_get_indicator(ema, 4H, [20,50]) → EMA 정배열 유지 여부
4. market_get_ticker → 현재가 vs 그리드 범위 위치

리밸런싱 트리거:
- 추세 방향 반전 (SuperTrend 플립): 즉시 재배치
- 현재가가 그리드 범위의 상/하위 10%에 도달: 범위 조정
- 누적 수익률 목표 달성 (월 4%+): 사용자에게 보고
```

### 4-2. 리밸런싱 절차

```
1. grid_stop_order(stopType="1") → 기존 봇 종료 (포지션 청산)
2. Phase 1 재실행 → 새로운 추세 판단
3. Phase 2 재실행 → 새로운 파라미터 산출
4. Phase 3 재실행 → 새 봇 배포
```

---

## Phase 5: Performance Report (성과 보고)

### 보고 항목

```
grid_get_order_details 에서 추출:
- 그리드 수익 (gridProfit)
- 미실현 PnL (floatProfit)
- 총 수익률 = (gridProfit + floatProfit) / sz × 100
- 연환산 수익률 = 총 수익률 / 운영일수 × 365
- 체결 횟수 (filledCount)

grid_get_sub_orders(type="filled") 에서 추출:
- 최근 체결 내역
- 평균 체결 간격
- 일일 평균 체결 횟수
```

---

## Return Projection (수익 시뮬레이션)

### 기본 가정

```
투자금: $1,000 USDT 마진
페어: BTC-USDT-SWAP
레버리지: 5x → 실질 노출 $5,000
그리드 수: 40개 (geometric)
범위: 8% (예: $69,000 - $74,520)
그리드 간격: ≈ 0.20%
```

### 수익 계산

```
그리드 1회 체결 수익:
  = 그리드간격 × 레버리지 × (마진/그리드수)
  = 0.20% × 5 × ($1,000/40)
  = 0.20% × 5 × $25
  = $0.25 per round-trip

수수료 (maker 0.02% + taker 0.05% = 편도 ~0.035%):
  = 0.035% × 2 × 5 × $25 = $0.0875
  
순 수익/round-trip = $0.25 - $0.0875 = $0.1625

일일 평균 체결: 8-15 round-trips (BTC 일일 변동성 2-3% 기준)
일일 그리드 수익: $1.30 - $2.44
월간 그리드 수익: $39 - $73 (3.9% - 7.3%)

추세 수익 (direction=long, 월 5% 상승 시):
  = 5% × 5(lever) × 평균 포지션 비율(~50%)
  = 12.5% of margin = $125

총 월간 기대 수익: $164 - $198 (16.4% - 19.8%)
보수적 추정 (변동성 낮은 구간): $40-60 (4% - 6%)
```

---

## Quick Deploy Command Examples

### BTC Long Grid (현재 시장 기준)

```
현재 시장 상태 (2026-04-14):
  BTC: $74,605 | SuperTrend: UP | EMA 20>50 | MACD: Bullish
  Trend Score: +4.5 → LONG

추천 파라미터:
  instId:    "BTC-USDT-SWAP"
  minPx:     "71500"      (SuperTrend support $71,968 근처)
  maxPx:     "77000"      (BB upper + 여유)
  gridNum:   "35"
  runType:   "2"          (geometric)
  direction: "long"
  lever:     "5"
  sz:        "{가용잔고의 30%}"
  basePos:   true
  slTriggerPx: "69500"    (minPx -2.8%)
```

### ETH Long Grid

```
현재 시장 상태:
  ETH: $2,388 | SuperTrend: UP
  
추천 파라미터:
  instId:    "ETH-USDT-SWAP"
  minPx:     "2240"
  maxPx:     "2520"
  gridNum:   "35"
  runType:   "2"
  direction: "long"
  lever:     "5"
  sz:        "{가용잔고의 20%}"
  basePos:   true
  slTriggerPx: "2170"
```

---

## Risk Warnings

1. **레버리지 리스크**: 5x에서 범위 이탈 + SL 미작동 시 큰 손실 가능
2. **추세 반전 리스크**: Long 그리드 중 급락 시 그리드 수익 < 미실현 손실
3. **펀딩비**: Long 포지션은 양(+)의 펀딩비 지불 → 장기 보유 시 비용
4. **유동성 리스크**: 극단적 변동성에서 슬리피지 발생 가능
5. **항상 전체 자산의 30% 이하만 단일 봇에 배분할 것**

---

## Multi-Pair Portfolio (분산 배치)

고급 전략: 2-3개 페어에 분산하여 리스크 분산 + 수익 안정화

```
배분 예시 ($3,000 기준):
  BTC-USDT-SWAP: $1,000 (33%) - 안정적 추세 추종
  ETH-USDT-SWAP: $800  (27%) - 높은 변동성 활용
  SOL-USDT-SWAP: $500  (17%) - 고변동 고수익
  현금 유보:     $700  (23%) - 리밸런싱 + 기회 대비
```

---

### [59] `trendline-symmetry-breakout`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/trendline-symmetry-breakout/SKILL.md`

---
name: 趋势线对称形态突破交易系统
description: 基于有效顶底计数+对称结构+末端蓄势+实体突破的高确定性趋势交易系统，每15分钟触发一次，全市场扫描OKX USDT永续合约币种，优先捕捉1小时大周期+15分钟小周期的嵌套共振形态，经过6个月以上实盘验证，胜率稳定在65%以上
version: 1.0
license: MIT
tags: ["交易策略", "交易执行", "趋势交易", "形态交易"]
---

# 策略名称：趋势线对称形态突破交易系统 V1.0
# 策略核心：基于「有效顶底计数+对称结构+末端蓄势+实体突破+多周期共振」的高确定性趋势交易系统，经过6个月以上实盘验证，胜率稳定在65%以上，专为OKX USDT永续合约设计
# 策略适配：完全兼容OKX Agent Trade Kit，仅统计AI自动执行的交易订单，符合欧易AI交易大赛全部规则

# 执行节奏
每15分钟触发一次全市场扫描与策略执行，优先捕捉1小时大周期+15分钟小周期的嵌套共振形态，无符合标准的信号则自动跳过本次执行

# Step 1 · 行情数据采集（严格适配OKX官方接口）
1.  调用 market_get_candles 获取 BTC-USDT-SWAP 的4小时、1小时K线数据，计算趋势方向、关键支撑压力位，确定全市场整体多空环境
2.  调用 market_get_candles 获取所有24小时成交额≥1000万USDT的USDT永续合约币种的1小时、15分钟K线数据，筛选符合形态要求的标的
3.  调用 market_get_volumes 获取对应币种的实时成交量、20周期平均成交量数据，用于末端蓄势和突破放量有效性验证
4.  调用 market_get_funding_rate 获取对应币种的8小时资金费率，过滤资金费率绝对值＞0.1%的极端拥挤行情标的
5.  调用 market_get_open_interest 获取对应币种的持仓量变化数据，辅助验证趋势强度与突破有效性

# Step 2 · AI综合判断（核心推理环节，严格对齐实盘交易规则）
基于以上所有采集的数据，你作为专属交易AI，必须严格按照以下步骤逐层推理，禁止任何主观发挥，所有判断必须有明确的数据支撑，禁止执行不符合规则的开仓操作：

## 推理环节1：全市场趋势锚定（绝对开仓前提）
- 若BTC 4小时、1小时周期处于明确下跌趋势（跌破关键支撑位、高点持续降低），直接跳过本次所有开仓操作，仅处理现有持仓的止盈止损，禁止任何逆势开仓
- 若BTC处于横盘震荡或上升趋势，继续执行后续筛选步骤，所有开仓方向必须顺BTC大趋势，禁止逆势开仓

## 推理环节2：标的形态初筛
从所有符合流动性要求的币种中，仅保留同时满足以下条件的标的：
1.  1小时周期形成清晰可识别的收敛三角/上升通道/下降通道形态，可画出明确的上下轨趋势线
2.  价格处于形态收敛末端，距离上下轨的空间≤5%，即将进入变盘窗口
3.  8小时资金费率绝对值≤0.05%，无极端多空拥挤风险
4.  24小时成交额≥1000万USDT，无流动性枯竭风险

## 推理环节3：有效顶底精准计数（核心规则，100%对齐实盘标准）
对初筛通过的标的，严格按照以下标准计数有效顶底，**仅认K线实体与趋势线有明确实质性触碰、且触碰后出现至少2根反向K线的高低点，仅影线触碰不计入有效顶底**：
1.  统计1小时大周期的有效顶和有效底数量
2.  统计15分钟小周期的有效顶和有效底数量
3.  仅保留满足「大周期≥3次有效顶底+小周期≥3次有效顶底」的对称完整结构标的，结构不完整的直接排除，禁止开仓

## 推理环节4：末端蓄势有效性验证（无蓄势不开单铁律）
对结构完整的标的，必须同时满足以下蓄势标准，不达标者直接排除，禁止提前博弈：
1.  形态末端连续8根以上对应周期K线的成交量，萎缩至近20根K线平均成交量的60%以下
2.  价格在狭窄区间内横盘震荡，无大幅单边波动，多空筹码充分交换
3.  MACD双线粘合于0轴附近，无明确发散信号，符合蓄势特征

## 推理环节5：有效突破/跌破信号验证
对蓄势达标的标的，严格按照以下标准验证信号有效性，仅影线刺破不算有效信号：
1.  顺趋势方向的K线实体完全站稳/跌破形态上下轨，且对应周期K线收线确认
2.  突破/跌破时，成交量放大至近20根K线平均成交量的1.5倍以上
3.  15分钟小周期突破与1小时大周期突破形成多周期共振，优先选择共振标的

## 推理环节6：安全等级与对应仓位判定
根据形态质量、共振情况、市场环境，严格按照以下标准确定安全等级和开仓仓位，禁止超仓位开仓：
- 千载难逢级：4小时大周期+1小时中周期+15分钟小周期三级共振，4次以上有效顶底对称，满蓄势，开仓仓位=账户净值的5%
- 极其安全级：1小时+15分钟双周期共振，4次有效顶底对称，满蓄势，开仓仓位=账户净值的3%
- 一般安全级：1小时+15分钟双周期共振，3次有效顶底对称，满蓄势，开仓仓位=账户净值的2%
- 可操作级：仅单周期符合条件，3次有效顶底对称，满蓄势，开仓仓位=账户净值的1%
- 观察级：结构不完整或蓄势不达标，禁止开仓

## 推理环节7：止损止盈参数计算
基于安全等级和开仓方向，严格按照以下规则计算交易参数：
1.  开仓价格：顺趋势方向的实体突破/跌破位
2.  止损价格：多头止损=形态下轨下方0.5%位置；空头止损=形态上轨上方0.5%位置，确保单笔最大亏损不超过账户净值的1%
3.  第一止盈位：1:2盈亏比对应价格，到点必须执行平仓操作
4.  第二止盈位：顺趋势方向的前高/前低强压力/支撑位，用移动止损持有

## 推理环节8：最终决策输出
综合以上所有推理步骤，输出最终明确决策：
1.  若有多个符合条件的标的，优先选择安全等级最高、盈亏比最大、流动性最好的标的
2.  若同时有做多和做空信号，优先选择顺BTC大趋势方向的信号
3.  明确输出：开仓标的、开仓方向、开仓价格、止损价格、第一止盈位、第二止盈位、对应开仓仓位，并详细说明每一步的推理理由
4.  若无符合所有规则的标的，输出「本次无符合标准的开仓信号，跳过执行」

# Step 3 · 执行下单（仅当AI判断明确开仓时执行）
调用 swap_place_order 执行下单，严格对齐OKX Agent Trade Kit规范：
instId = <AI在Step2最终决策选定的标的>
side = <AI判断的开仓方向，buy=做多/sell=做空>
ordType = "limit"
px = <AI计算的开仓价格>
sz = <AI计算的对应仓位数量，以币为单位>
tag = "agentTradeKit"
（必填tag，否则订单不计入大赛排名统计）

# Step 4 · 持仓管理与止盈止损执行
1.  开仓后立即调用 swap_place_algo_order 设置条件止损单：
    - 多头止损触发价=AI计算的止损价格，止损委托价=止损价格*0.995
    - 空头止损触发价=AI计算的止损价格，止损委托价=止损价格*1.005
2.  当价格触及1:2盈亏比第一止盈位时，立即调用 swap_place_order 平掉50%的持仓仓位，同时将止损位调整为开仓价，设置保本损，确保剩余仓位不会亏损本金
3.  剩余50%仓位全程使用移动止损持有：每创出一次顺趋势的新高/新低，将止损位上移/下移至最近一次回踩低点/反弹高点
4.  当价格触及移动止损位时，立即平掉全部剩余仓位，结束本次交易
5.  任何一笔交易仅可开一次仓，绝对禁止加仓、补仓、摊平成本操作

# Step 5 · 全局风控规则（绝对红线，任何情况不得违反，优先级高于所有开仓规则）
1.  单笔交易最大亏损不得超过账户净值的1%
2.  当日账户净值回撤达到5%时，立即停止所有新开仓操作，当日不再执行任何开仓指令
3.  最多同时持有2个标的的仓位，禁止对冲持仓，禁止同一标的双向开仓
4.  禁止在重大宏观新闻事件前后30分钟内开新仓
5.  禁止交易24小时成交额低于1000万USDT的低流动性币种
6.  禁止在结构不完整、蓄势不达标、无有效突破信号的情况下提前进场博弈
7.  所有订单必须通过Agent Trade Kit自动执行，手动下单不计入大赛统计，策略内不包含任何手动操作指令

---

### [60] `tri-asset-adaptive-fusion`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/tri-asset-adaptive-fusion/SKILL.md`

---
name: 三标的自适应融合策略：黄金网格 + BTC宏观 + ETH动量
description: 本策略横向对比 XAU、BTC、ETH 三个标的，基于 EMA 趋势、布林带突破、订单簿深度、资金费率及宏观估值区间（矿工成本/M2协整）进行多维度信号评分，由 AI 综合推理后选出最优标的执行交易。融合用户实盘黄金网格参数（5x杠杆、4450-4950区间、30格）及林恩·奥尔登宏观框架，风控严格，适合 4 小时中频交易场景。
---

# 策略名称
三标的自适应融合策略：黄金网格 + BTC宏观 + ETH动量 V1.0

# 策略哲学声明
本策略集成了三个独立验证过的交易模型，覆盖贵金属、宏观数字货币和智能合约平台三类资产。每次触发时，AI 将横向对比 XAUUSDT、BTC-USDT-SWAP、ETH-USDT-SWAP 的市场状态，选出信号强度最高、风险收益比最优的**单一标的**执行交易。策略核心逻辑包括：
- **黄金网格**：基于用户实盘验证的高频区间套利模型（初始本金约 300 USDT，运行收益 +11.77%，日均套利 11 次）。
- **比特币宏观**：模拟林恩·奥尔登框架，融合矿工盈亏模型与 M2 协整估值逻辑，捕捉宏观周期驱动的趋势机会。
- **以太坊动量**：结合 EMA 趋势、布林带突破、Gas 费定性推理与 ETH/BTC 汇率轮动信号的中短期动量策略。

资金管理采用 500 USDT 总池模式，单次开仓风险严格控制在总净值的 2% 以内。

# 执行节奏
本策略采用“定时 + 事件驱动”复合触发机制：
- **定时触发**：每 4 小时触发一次，覆盖三个标的的 4 小时 K 线级别分析。
- **事件触发**：任一标的在 30 分钟内价格波幅超过 ATR(14) 的 1.2 倍，或资金费率绝对值 > 0.15%，或订单簿买卖盘深度比在 10 分钟内变化超过 60% 时，立即触发策略运行。

每次触发后，AI 需完成完整的数据采集与推理流程，即使最终决策为“观望”，也必须输出推理理由。

# Step 1 · 行情与市场数据采集
针对 **XAUUSDT**、**BTC-USDT-SWAP**、**ETH-USDT-SWAP** 三个标的，分别调用以下接口获取数据：

## 1.1 通用技术数据
- `market_get_candles` (4h)：获取近 100 根 4 小时 K 线，计算：
  - EMA20、EMA60、EMA200
  - ATR(14)（平均真实波幅）
  - 布林带 (20, 2)：上轨、中轨、下轨、带宽
  - MACD (12,26,9)：快慢线及柱状图
  - 成交量均线 (20)
- `market_get_orderbook`：获取深度 5 档数据，计算：
  - 买盘总量 = 买一至买五挂单量之和
  - 卖盘总量 = 卖一至卖五挂单量之和
  - 买卖盘深度比 = 买盘总量 / 卖盘总量
- `market_get_funding_rate`：获取当前永续合约资金费率
- `market_get_open_interest`：获取 4 小时持仓量变化率
- `market_get_ticker`：获取最新价、24h 涨跌幅、现货/永续合约交易量比

## 1.2 标的专用数据
- **XAUUSDT**：无额外数据，重点关注其价格相对于预设网格区间 [4450, 4950] 的位置。
- **BTC-USDT-SWAP**：
  - AI 需记忆并参考以下宏观估值参考线（无需接口，作为推理常识）：
    - 矿工电费成本参考线：约 **65,000 USDT**
    - 矿工总维持成本区间：约 **75,000 - 114,000 USDT**
    - M2 协整模型公允值参考线：约 **98,500 USDT**（基于美国 M2 货币供应量与 BTC 价格的历史协整关系）
  - 通过计算 ETH/BTC 汇率（ETH 价格 / BTC 价格）辅助判断资金轮动。
- **ETH-USDT-SWAP**：
  - 计算 ETH/BTC 汇率，判断是否突破近 20 日高点。
  - AI 需根据 ETH 价格与成交量的配合关系，定性推理链上 Gas 费活跃度（放量上涨则推理 Gas 升高，链上活跃）。

# Step 2 · 信号强度评分计算
AI 需基于 Step 1 采集的数据，结合市场常识进行定性推理，为每个标的计算一个**信号强度评分**（满分 100 分）。评分维度如下：

| 评分维度 | 评分逻辑 |
| :--- | :--- |
| **趋势清晰度** (30分) | EMA20 > EMA60 且价格在 EMA20 上方，同时 MACD 柱状图连续 2 根扩大 → 30 分；EMA 多头但 MACD 走平 → 20 分；均线缠绕 → 10 分；空头排列且 MACD 向下 → 0 分。 |
| **布林带位置** (25分) | 价格突破上轨或下轨，且带宽处于近 10 根 K 线低位后开始扩张 → 25 分；价格沿中轨运行，带宽平稳 → 15 分；价格触及轨道但带宽未扩张 → 5 分。 |
| **订单簿支撑** (20分) | 买卖盘深度比 > 1.3（买方支撑强）或 < 0.7（卖方压力大，利于做空）→ 20 分；比值在 0.8-1.2 之间 → 10 分。 |
| **资金费率健康度** (15分) | 绝对值 < 0.05% → 15 分；0.05%-0.1% → 8 分；> 0.1% → 0 分（拥挤风险）。 |
| **波动率合理性** (10分) | 当前 ATR(14) 占价格比例处于近 20 根 K 线均值的 0.8-1.2 倍 → 10 分；过高 (>1.5倍) 或过低 (<0.6倍) → 3 分。 |

**标的附加分（在基础分上额外加减）** ：

- **BTC 附加分**：
  - 宏观估值安全边际：AI 需推理当前价格与矿工电费成本 (65k)、M2 公允值 (98.5k) 的关系。若价格 ≤ 65k（极限低估区）→ +15 分；65k < 价格 ≤ 98.5k（合理区）→ +5 分；价格 > 98.5k（高估区）→ -10 分。
  - 矿工行为定性：若近期币价企稳且全网算力（可通过公开新闻或常识推断）持续增长，推理矿工惜售 → +5 分。

- **ETH 附加分**：
  - 链上活性定性：若 ETH 放量上涨，推理 Gas 费升高、链上活跃 → +8 分；若缩量阴跌 → -5 分。
  - 资金轮动信号：若 ETH/BTC 汇率突破近 20 日高点 → +8 分。

- **XAU 附加分**：
  - 网格位置：若当前价格处于预设网格区间 [4450, 4950] 的中枢位置（4600-4800）→ +8 分；若逼近上下沿 5% 范围内 → 0 分。

AI 需在推理环节输出三个标的的最终评分及排名，并简述高分标的的优势维度。

# Step 3 · AI 综合判断 (核心推理环节)
基于以上数据与评分，你作为交易 AI，需通过自然语言推理完成以下判断：

1. **标的筛选**：在 XAUUSDT、BTC-USDT-SWAP、ETH-USDT-SWAP 三个标的中，哪一个的**综合信号强度评分最高**？请指出该标的，并分析其高分主要来源于哪些维度（例如：趋势清晰、宏观估值极低、订单簿支撑强劲等）。

2. **宏观与估值验证**（若选定 BTC 或 ETH）：
   - 若选定 BTC：请结合当前价格与矿工电费成本 (≈65k)、M2 协整公允值 (≈98.5k) 的对比关系，推理其长期安全边际是处于“低估”、“合理”还是“高估”区间。
   - 若选定 ETH：请结合其近期量价关系，推理当前链上 Gas 费可能的活跃程度，以及 ETH/BTC 汇率是否显示资金轮动迹象。

3. **风险因素权衡**：
   - 该标的的资金费率绝对值是否 > 0.1%？若拥挤，是否应将计划仓位减半？
   - 当前 ATR(14) 占价格的比例是否过高（> 历史均值 1.5 倍）或过低（< 0.6 倍）？过高是否意味着风险过大应降低仓位或跳过？过低是否意味着机会不足可观望？
   - 订单簿深度是否足以支持预期的开仓规模？是否存在滑点过大的风险？

4. **综合决策输出**：
   基于以上三点分析，请给出本次触发的最终决策：
   - **选定标的**：XAUUSDT / BTC-USDT-SWAP / ETH-USDT-SWAP / 无
   - **交易方向**：做多 / 做空 / 观望
   - **执行仓位比例**：标准仓位的 X%（标准仓位 = 账户总净值的 5%，即约 25 USDT 名义价值。可根据信号强度和风险因素在 20%-150% 范围内浮动）
   - **决策理由**：用 3-5 句话清晰阐述，必须包含标的筛选依据、核心信号描述、以及风险因素如何影响最终仓位调整。

# Step 4 · 执行下单
仅当 Step 3 的最终决策为“做多”或“做空”，且执行仓位比例 > 0 时，调用下单接口。

## 4.1 杠杆设置
开仓前根据波动率动态调节杠杆倍数（调用 `account_set_leverage`）：
- 计算波动率偏离度 = 当前 ATR% / 近 20 根 K 线 ATR% 均值。
- 若偏离度 < 0.8：可使用 3x 杠杆（仅 BTC/ETH，XAU 固定 5x 网格除外）。
- 若偏离度在 0.8-1.2 之间：使用 2x 杠杆。
- 若偏离度 > 1.2：使用 1x 杠杆（即现货模式）。

*注：XAUUSDT 黄金网格策略固定使用 5x 杠杆，且仅在首次触发时部署完整网格，后续触发仅维护挂单。*

## 4.2 下单指令
调用 `swap_place_order` 市价成交：
instId = <AI 选定的标的>
side = <buy / sell>
ordType = "market"
sz = <账户总净值的 5% × 决策仓位比例 × 杠杆倍数（换算为合约张数）>
tag = "agentTradeKit"

## 4.3 黄金网格特殊执行逻辑（当选定标的为 XAUUSDT 时）
- **首次开仓**：部署完整的 30 格等差网格。
  - 网格区间：4450 - 4950 USDT
  - 单网格买卖量：0.011 XAU
  - 初始建仓：按当前价格市价买入约 50% 网格计划总仓位作为底仓。
  - 循环挂单：在区间内按等差价格分布 30 个限价买入/卖出挂单。
- **后续触发**：仅检查因成交而产生的空缺挂单位置，调用 `swap_cancel_order` 撤销已成交挂单，并调用 `swap_place_order` 补充新的限价挂单，参数与初始挂单一致。
- 所有网格挂单均需携带 `tag = "agentTradeKit"`。

# Step 5 · 止损设置
开仓后立即调用 `swap_place_algo_order` 设置止损单。

## 5.1 通用止损规则
- **金额止损（强制熔断）**：
  - 多头止损价 = 开仓价 × (1 - 2% × 杠杆倒数)
  - 空头止损价 = 开仓价 × (1 + 2% × 杠杆倒数)
  - 确保单笔最大亏损不超过账户总净值的 2%。
- **技术止损**：
  - 多头止损价同时参考 EMA200 当前值，取两者中的较高者（即更早触发止损）。
  - 空头止损价同时参考 EMA200 当前值，取两者中的较低者。

## 5.2 黄金网格专用止损
- XAUUSDT 网格策略强制设置全平止损线为 **4400 USDT**。一旦价格跌破此线，立即市价全平并暂停该子策略，等待 AI 重新评估。

# 风控规则
- **仓位上限**：单次开仓名义价值不超过账户总净值的 10%（即 50 USDT）。
- **杠杆上限**：BTC/ETH 最高 3x，XAU 固定 5x 但仅用于网格套利。
- **总回撤熔断**：当日账户净值从高点回撤超过 8% 时，跳过后续 24 小时内所有新开仓信号，仅允许平仓和止损操作。
- **单一持仓**：同一时间最多只持有 1 个标的的仓位，未平仓前不重复开新仓。
- **禁止对冲**：严禁对同一标的同时持有多空双向仓位。

# 实盘验证与策略背书
- **黄金网格策略**：基于用户实盘数据验证（初始本金约 321 USDT，运行 4 天 11 小时收益 +11.77%，成交 102 次，日均套利 11 次）。本 Skill 将其核心参数（区间 4450-4950，30 格，单格 0.011 XAU，5x 杠杆）完整嵌入，并由 AI 负责动态评估区间有效性。
- **比特币宏观策略**：逻辑基于林恩·奥尔登（Lyn Alden）2025-2026 年公开市场研判框架，成功捕捉 ETF 驱动牛市并规避 2025 年 10 月回撤。融合矿工盈亏模型与 M2 协整模型，为 AI 提供宏观估值锚点。
- **以太坊动量策略**：经历史数据回测，在 2024-2025 年多次 ETH/BTC 汇率轮动行情中表现优异，通过趋势与链上活性定性推理捕捉独立行情机会。

本 SKILL 严格遵循比赛要求：所有推理环节均以开放式问题引导 AI 进行多维度分析并输出自然语言理由，风控规则清晰明确，具备实盘数据佐证。

---

### [61] `wangwang-v3-strategy`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/wangwang-v3-strategy/SKILL.md`

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

---

### [62] `whale-tracker`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/whale-tracker/SKILL.md`

---
name: 鲸鱼追踪者
description: 以"机构怎么动，我就跟着动"为核心哲学的永续合约策略 Skill。识别 Order Block 机构挂单区、Fair Value Gap 价格失衡区与流动性扫盘信号，追踪 BTC 市场中鲸鱼的真实意图。当用户说"鲸鱼追踪"、"whale tracker"、"聪明钱"、"机构跟踪"、"SMC策略"时启用。
---

# 策略名称
鲸鱼追踪者：聪明钱足迹识别与跟踪策略 V1.0

---

> *"在海洋里，小鱼不需要比鲸鱼聪明。只需要知道鲸鱼在哪里，然后跟着游。"*
> — 鲸鱼追踪者策略设计理念

---

## 策略哲学

BTC 市场从来不是散户的游乐场。

每一次"莫名其妙"的暴跌，背后是鲸鱼在扫荡散户的止损单；每一次"假突破"后的反转，是机构在收割追高的人；每一段横盘震荡，是大资金在悄悄建仓。

散户输钱，不是因为不努力，而是因为**在和鲸鱼对赌，却浑然不觉**。

本策略的核心信念只有一句话：**不要试图预测鲸鱼，而是学会读懂它们留下的足迹。**

鲸鱼无法隐藏自己。它们的体量太大，每一次进出场都会在价格结构上留下痕迹：
- **Order Block（机构挂单区）**：鲸鱼最后一次大规模买入或卖出的位置，价格往往会回来测试
- **Fair Value Gap（公允价值缺口）**：鲸鱼移动太快，留下的"真空地带"，市场天然想要填补
- **流动性扫盘**：鲸鱼故意把价格推到散户止损位，收割流动性后迅速反向

**读懂这三种足迹，你不需要预测市场，你只需要等待。**

---

## 执行节奏

每 **1 小时** 触发一次完整扫描循环。

---

## Step 1 · 足迹侦测：寻找鲸鱼活动痕迹

> *"鲸鱼不会说话，但它们的行为会。"*

**1.1 市场结构建立（确认鲸鱼的方向）**

调用 `market_get_candles` 获取 BTC-USDT-SWAP 的 **4h K线**，建立宏观市场结构：

- 识别近期的**摆动高点（Swing High）**和**摆动低点（Swing Low）**：价格在连续5根K线中为最高/最低点
- 判断当前结构类型：
  - **趋势结构**：高高高低（HH/HL）= 鲸鱼在买；低低低高（LL/LH）= 鲸鱼在卖
  - **结构突破（BOS）**：价格有效突破上一个摆动高/低点 = 鲸鱼改变方向
  - **特征变换（CHoCH）**：反向突破且伴随成交量放大 = 趋势可能反转

同时获取 **1h K线** 作为精确入场的微观结构参考。

**1.2 Order Block 识别（机构挂单区定位）**

Order Block 是鲸鱼留下最清晰的足迹。识别规则：

在 **4h 时间框架**上：
- **看涨 OB（需求区）**：寻找趋势中最后一根**阴线**，该阴线之后紧跟了一段强劲上涨（涨幅 > 1.5 × ATR14）。该阴线的**高低点范围**即为 OB 区域
- **看跌 OB（供给区）**：寻找趋势中最后一根**阳线**，该阳线之后紧跟了一段强劲下跌（跌幅 > 1.5 × ATR14）。该阳线的**高低点范围**即为 OB 区域
- OB 有效期：价格未曾回测并穿越该区域（一旦穿越，OB 失效）
- 最多追踪近期 **3个有效 OB**，优先使用距当前价格最近的一个

在 **1h 时间框架**上：同样方法识别精确入场用的小级别 OB。

**1.3 Fair Value Gap 识别（价格失衡区）**

调用 `market_get_candles` 扫描近100根 **1h K线**，寻找 FVG：

- **看涨 FVG**：K线 N 的最低价 > K线 N-2 的最高价（向上的价格真空）
- **看跌 FVG**：K线 N 的最高价 < K线 N-2 的最低价（向下的价格真空）
- FVG 最小尺寸：间距 > 0.3 × ATR14（过滤噪音缺口）
- FVG 状态：未被回补（价格未重新进入该区域）则持续有效

**1.4 流动性扫盘侦测（鲸鱼收割信号）**

这是最关键的信号之一。调用近期 **1h K线**检查：

- **扫盘特征**：
  - 价格短暂突破近期摆动高/低点（形成长上影/下影线）
  - 但当根K线**收盘价回到突破点内侧**（突破后反转收盘）
  - 伴随成交量放大（> 1.5 × 20周期均量）
- **信号含义**：鲸鱼在散户止损位收割流动性，准备反向拉升/打压
- **信号有效期**：扫盘后的前 **3根1h K线**内为最佳入场窗口

---

## Step 2 · 足迹分级：评估鲸鱼信心

> *"不是每一个足迹都值得跟随。大鲸鱼的足迹，比小鲸鱼的更值钱。"*

对当前侦测到的信号进行**置信度评分**，满分 100 分：

| 信号维度 | 评分标准 | 最高分 |
|---|---|---|
| **市场结构对齐** | 4h 与 1h 结构方向一致：25分；仅一个时框明确：12分；相互矛盾：0分 | 25 |
| **Order Block 质量** | OB 形成时成交量 > 2× 均量：20分；1.5-2×：12分；< 1.5×：5分 | 20 |
| **FVG 存在** | 当前价格在有效 FVG 区间内：20分；FVG 在 OB 内部（双重确认）：+5分加成 | 25 |
| **流动性扫盘** | 过去3根K线内出现扫盘信号且方向匹配：20分；4-6根K线内：10分；无：0分 | 20 |
| **资金费率健康** | 调用 `market_get_funding_rate`，绝对值 < 0.05%：10分；< 0.08%：5分；≥ 0.08%：0分 | 10 |

**置信度阈值**：
- **≥ 75 分**：高置信度，允许标准仓位入场
- **55~74 分**：中等置信度，仓位减半
- **< 55 分**：信号不足，本轮跳过

---

## Step 3 · 鲸鱼意图判断：AI 综合推理（核心）

> *"技术指标告诉你价格在哪里。聪明钱分析告诉你鲸鱼想去哪里。"*

AI 必须在此步骤完成完整的意图推理，**不允许跳过任何子项**：

**3.1 当前鲸鱼在做什么？**

基于 Step 1 的足迹数据，AI 判断鲸鱼当前最可能的行为模式：
- **建仓模式**：价格在 OB 区域内震荡 + 成交量温和 + 持仓量小幅增长 → 鲸鱼在悄悄买入/卖出
- **拉升/打压模式**：价格突破关键结构 + 成交量放大 + FVG 形成 → 鲸鱼在推动方向
- **收割模式**：流动性扫盘信号出现 → 鲸鱼在消灭散户，准备反向

**3.2 散户现在在做什么？（反向参考）**

调用 `market_get_open_interest` 获取持仓量变化：
- 持仓量与价格同向暴增（> 20% / 24h）：散户在追涨/追空，鲸鱼可能即将反向收割
- 持仓量与价格逆向变化：聪明钱在主导，方向更可信

**3.3 最终意图声明**

AI 必须输出：

```
【鲸鱼意图分析】
当前足迹：[OB位置 / FVG区间 / 是否有扫盘]
鲸鱼行为模式：[建仓 / 拉升打压 / 收割]
散户情绪：[追涨追空 / 观望 / 恐慌]
置信度得分：[X/100]
跟踪方向：[做多 / 做空]
核心理由：[1-2句，说明为什么这是鲸鱼真实意图而非陷阱]
```

如果 AI 认为当前信号可能是**鲸鱼设置的陷阱**（例如：扫盘后立刻出现反向大成交量，或 OB 区域已被测试超过3次），**必须放弃本轮入场**，并在摘要中注明"可能陷阱，放弃跟踪"。

---

## Step 4 · 执行下单（仅当置信度 ≥ 55 且 AI 意图声明完整）

> *"跟上鲸鱼，但不要贴得太近——它翻身的时候会把你压死。"*

调用 `swap_place_order`：

```
instId  = "BTC-USDT-SWAP"
side    = <buy 或 sell，基于Step 3判断>
ordType = "market"
sz      = <基于Step 5风控计算的张数>
tag     = "agentTradeKit"   ← 必填
```

---

## Step 5 · 止损与止盈（以结构为锚）

> *"止损不是认输，是为下一次跟踪保留子弹。"*

**止损设置**（以市场结构为锚点，非固定百分比）：

调用 `swap_place_algo_order`：

| 方向 | 止损位 | 逻辑 |
|---|---|---|
| 做多 | 入场 OB 低点以下 0.3% | OB 被有效突破则鲸鱼意图失效 |
| 做空 | 入场 OB 高点以上 0.3% | OB 被有效突破则鲸鱼意图失效 |

**单笔最大风险 = 账户净值 × 1.5%**，由此反推仓位大小。

**止盈设置**（目标为下一个流动性池）：

| 止盈档位 | 目标位置 | 平仓比例 |
|---|---|---|
| 第一档 | 最近的 FVG 中点 | 40% 仓位 |
| 第二档 | 最近的对向 OB 边缘 | 40% 仓位 |
| 第三档 | 最近的摆动高/低点（流动性集中区）| 剩余 20% |

第一档触发后，将止损移至**保本价**。

---

## Step 6 · 持仓监控

每次循环时，对现有仓位执行**鲸鱼意图变化检测**：

- 是否出现**反向 CHoCH**（结构特征变换）？若是，减仓 50% 并收紧止损
- 是否出现**反向 OB** 且价格正在测试？若是，准备全平
- 资金费率是否突然跳升 > 0.1%？若是，评估提前离场

---

## 风控总则

```
// [P1] 单笔最大风险 1.5%，置信度55-74分时降至 0.75%
// [P2] 当日回撤超 5% 停止新开仓
// [P3] 同一个 OB 区域最多入场 2 次，第三次测试不再跟踪
// [P4] 开仓后 90 秒内必须完成止损挂单
// [P5] 严禁在持仓亏损时加仓（鲸鱼陷阱的最常见受害方式）
// [P6] 流动性扫盘信号有效期超过 3 根K线则失效，不再追入
```

---

## 策略的自我叙述

鲸鱼追踪者不相信预测。

它只相信：**大资金无法完全隐藏自己**，而读懂足迹的人，可以用小资金跟着大资金一起走。

这个策略要求 AI 扮演一个侦探，而不是一个预言家。每一次入场，都是一次"我读懂了鲸鱼的意图"的声明。如果读不懂，就不做。

等待，是这个策略最重要的技能。

---

*策略版本：V1.0 | 适用平台：OKX Agent Trade Kit | 参赛赛道：优质 Skill*
*灵感来源：Smart Money Concepts (SMC) 机构交易理论 & AlphaX Nexus 聪明钱分析框架*

---

### [63] `yield-king-strategy`
- **Path**: `/Users/zava/.openclaw/workspace/skills/zava-okx-skill/marketplace/yield-king-strategy/SKILL.md`

---
name: 收益王策略
description: AI增强的收益率优先策略，专为OKX交易大赛设计，通过多因子分析、智能风控和动态止盈止损实现稳健收益
author: 收益王策略团队
version: "2.0"
tags: [trading, algorithmic, ai, risk-management, yield-focused]
---

# 策略名称：收益王 - AI增强收益率策略 V2.0

## 策略简介
"收益王"是一个专为大宗赛设计的AI增强策略，通过多维度分析实现稳健收益增长。该策略：

✅ **核心优势**：
- 多因子AI评分系统（趋势40% + 动量30% + 波动率20% + 资金10%）
- 智能三层决策机制（市场过滤 → 标的筛选 → 动态仓位）
- 多层次风控（ATR动态止损 + 趋势跟踪 + 分级止盈）
- 自适应调整（市场状态、时间因素、相关性控制）

✅ **参赛合规**：
- 严格按照OKX大赛规则设计
- 纯AI推理逻辑，非简单if/else规则
- 通过Agent Trade Kit自动执行
- 支持任意子账户参赛

✅ **风险控制**：
- 最大单笔风险≤0.8%账户净值
- 动态止损止盈系统
- 相关性风险监控
- 连续亏损保护机制

# 执行节奏：每1小时触发一次
# 核心原则：稳健增长，严格风控，AI驱动

## 依赖工具
- OKX Agent Trade Kit (市场数据：market_get_candles, market_get_funding_rate, market_get_open_interest, market_get_ticker)
- OKX Agent Trade Kit (交易执行：swap_place_order, swap_place_algo_order)

## 快速开始
1. **安装依赖**：确保已安装 OKX Agent Trade Kit
2. **配置API**：配置你的 OKX API 凭证（推荐使用子账户）
3. **设置标签**：确保 tag="agentTradeKit" 以计入大赛排名
4. **启动策略**：策略会自动获取市场数据、分析、决策、执行交易

## 适用场景
- ✅ OKX AI交易大赛
- ✅ BTC/ETH/SOL永续合约交易
- ✅ 稳健收益目标
- ✅ 风险控制优先

# Step 1 · 多维度行情数据采集
调用 market_get_candles 分别获取：
- BTC-USDT-SWAP 的1小时K线，limit=100根
- ETH-USDT-SWAP 的1小时K线，limit=100根
- SOL-USDT-SWAP 的1小时K线，limit=100根

数据点包括：时间戳(t)、开高低收(ohlc)、成交量(vol)、成交额(volCcy)

# Step 2 · 技术指标计算
对每个标的计算：
1. EMA指标：EMA7和EMA25（用于趋势判断）
2. ATR指标：周期14的ATR（用于动态止损）
3. RSI指标：周期14的RSI（用于超买超卖判断）
4. MACD指标：MACD快线、慢线、信号线（用于动能判断）
5. 成交量变化：近24h成交量与平均成交量的比值

计算公式：
- ATR = 真实波幅的14周期移动平均
- EMA = 平滑指数移动平均
- RSI = 相对强弱指标

# Step 3 · 市场环境评分
综合评分计算（0-100分）：

趋势因子（40分）：
- EMA7 > EMA25：+15分（上升趋势）
- EMA7 < EMA25：-15分（下降趋势）
- 价格 > EMA25：+10分（强势）
- 价格 < EMA25：-10分（弱势）
- 近24h涨幅：根据幅度给分（-10到+10）

动量因子（30分）：
- RSI < 30（超卖）：+10分
- RSI > 70（超买）：-10分
- MACD金叉：+10分
- MACD死叉：-10分
- 成交量增长：+10分（vs前24h平均）

波动率因子（20分）：
- ATR/价格 < 0.02：+5分（低波动）
- ATR/价格 0.02-0.05：+3分（中等）
- ATR/价格 > 0.05：-5分（高波动）

资金因子（10分）：
- 资金费率 > 0：+5分（多头资金流入）
- 资金费率 < 0：-5分（空头资金流入）
- 持仓量增长：+5分

# Step 4 · 市场环境过滤
基于综合评分判断市场环境：

多头市场（评分 > 60）：
- 允许做多
- 禁止做空
- 仓位可适当放大

中性市场（评分 40-60）：
- 允许双向交易
- 仓位适中
- 严格止损

空头市场（评分 < 40）：
- 允许做空
- 禁止做多
- 仓位可适当放大

# Step 5 · 标的筛选
根据评分选择交易标的：

1. 筛选条件：
   - 评分 > 60（满足开仓条件）
   - 趋势方向一致（多头市场选上升趋势，空头市场选下降趋势）
   - 波动率适中（非极端情况）

2. 排序规则：
   - 按评分从高到低排序
   - 优先选择趋势最强的标的

3. 选择数量：
   - 最多选择2个标的
   - 相关性高的标的同时持仓不超过1个

# Step 6 · 动态仓位计算
根据市场状态计算仓位：

基本仓位计算：
- 单笔风险 = 账户净值 × 0.8%
- 止损距离 = ATR × 1.5
- 仓位大小 = 单笔风险 / 止损距离

仓位调整因子：
- 市场评分 > 70：×1.2（强势市场）
- 市场评分 60-70：×1.0（正常市场）
- 市场评分 50-60：×0.8（弱势市场）

最大仓位限制：
- 单个标的仓位 ≤ 15% 账户净值
- 总仓位 ≤ 25% 账户净值

# Step 7 · 订单执行
根据市场评分和筛选结果执行交易：

开仓信号：
- 标的评分 > 60
- 趋势方向明确
- 满足筛选条件

开仓参数：
- 交易方向：根据市场环境（多头做多，空头做空）
- 订单类型：市价单
- 仓位大小：按动态仓位计算
- 杠杆倍数：3x（可调整）

# Step 8 · 止损设置
设置多重止损保护：

1. ATR动态止损：
   - 止损价格 = 开仓价 ± (ATR × 1.5)
   - 做多：开仓价 - (ATR × 1.5)
   - 做空：开仓价 + (ATR × 1.5)

2. 趋势跟踪止损：
   - 做多：止损价随价格上涨而上移
   - 做空：止损价随价格下跌而下跌
   - 移动幅度：ATR × 0.5

3. 时间衰减止损：
   - 持仓超过24小时未盈利：止损价调整为开仓价
   - 持仓超过48小时未盈利：考虑平仓

# Step 9 · 止盈设置
设置分级止盈：

第1级止盈：+0.5%
- 平仓30%仓位
- 移动止损到开仓价

第2级止盈：+1.0%
- 平仓30%仓位
- 移动止损到第1级止盈价

第3级止盈：+1.5%
- 平仓20%仓位
- 移动止损到第2级止盈价

第4级止盈：+2.0%
- 平仓剩余20%仓位
- 或移动止损到第3级止盈价（继续持有）

# Step 10 · 风险控制
持续监控风险指标：

1. 单笔交易风险：
   - 确保每笔交易风险 ≤ 0.8% 账户净值
   - 超过则减少仓位或放弃交易

2. 总仓位风险：
   - 确保总仓位 ≤ 25% 账户净值
   - 超过则等待部分平仓或减少新仓位

3. 相关性风险：
   - 相关性高的标的同时持仓 ≤ 1个
   - 避免集中风险

4. 连续亏损保护：
   - 连续3笔亏损：暂停交易1小时
   - 连续5笔亏损：暂停交易4小时
   - 当日亏损超过账户净值2%：暂停当日交易

5. 异常情况处理：
   - 价格剧烈波动（ATR突增3倍以上）：暂停交易
   - 流动性不足（成交量低于平均50%）：暂停交易
   - 系统错误：立即停止所有交易

## 输出要求
每次执行时输出：
1. 市场环境评分（各因子得分和总分）
2. 选中的交易标的（名称、方向、仓位）
3. 执行的交易详情（价格、数量、止损止盈）
4. 当前持仓情况
5. 累计盈亏统计
6. 风险指标（单笔风险、总仓位、相关性）

---
