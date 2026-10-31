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
