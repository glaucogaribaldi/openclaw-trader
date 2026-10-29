# 📘 SYSTEM BLUEPRINT & ARCHITECTURE SPECIFICATION
## Project: OKX Sovereign Self-Improving Algorithmic Trader (TRE-OS)
> **Author:** Lehman Brody (TRE Quant OS) // **Owner:** Giacomo
> **Source Repository:** `https://github.com/glaucogaribaldi/openclaw-trader.git`
> **Active Environment:** OKX Live Spot (EEA European Regulated Region) // **Real Capital:** $325.03 USDC

---

## 📑 1. EXECUTIVE SUMMARY & CORE MISSION
The **TRE-OS** is a non-custodial, local-first, self-improving algorithmic trading system designed to operate 24/7 on OKX Spot markets. It aims to generate consistent yield through highly optimized, non-correlated scalping loops and dynamic grid market-making, while maintaining complete privacy, sovereign hardware execution, and exactly $0.00 in commercial LLM API costs.

---

## 📐 2. SYSTEM ARCHITECTURE & NETWORK TOPOLOGY
The system operates on a **Dual-Node Hybrid Infrastructure** paired securely over an encrypted private network:

```
[ LOCAL MASTER CONSOLE (MacBook Air) ]
          │
          ├── (Control UI & Native Chromium Profile // Session Saving)
          ├── (Secure Local Git Repository)
          │
          ├── [ Tailscale VPN Encrypted Tunnel (100.x.x.x) ]
          │
          ▼
[ REMOTE CLOUD NODE VPS (openclaw-trader-box) ]
          │
          ├── Host: Google Compute Engine (n1-standard-4, us-central1-a)
          ├── Hardware: NVIDIA Tesla T4 GPU (16GB VRAM) // CUDA 12.8
          ├── Driver: NVIDIA Stable Proprietario 580.178.04
          │
          ├── [ LOCAL AI CORE (Ollama qwen2.5-coder:7b in VRAM) ]
          │
          └───► [ OKX API Spot Engine ] // [ Telegram Bot API (@beato_zava) ]
```

---

## 📊 3. PORTFOLIO ALLOCATION & ACTIVE STRATEGIES
The baseline real-money capital of **`$325.03 USDC`** is mathematically allocated across two independent yield-generation engines:

### A. SOL-USDC Market-Making Grid Bot (Allocated: `$125.03` USDC)
*   **Execution Location:** Native OKX Cloud Bot Engine (0% VPS latency impact).
*   **Grid Style:** Arithmetic, 12 levels, optimized range: **`$113.90 - $134.10`**.
*   **Purpose:** Captures micro-arbitrage on SOL volatility, accumulating stablecoin cash during lateral ranges.

### B. Multi-Correlated Spot Scalping (Allocated: `$200.00` USDC)
*   **Asset Division:** 4 high-beta and blue-chip tokens allocated at **`$50.00` USDC each**:
    1.  `BTC-USDC`: Target Profit `+0.55%` (Low volatility, high security)
    2.  `ETH-USDC`: Target Profit `+0.70%` (Medium volatility)
    3.  `NEAR-USDC`: Target Profit `+0.85%` (High-beta, high volatility)
    4.  `LINK-USDC`: Target Profit `+0.65%` (Chainlink oracle blue-chip)
*   **Tactical Execution Style (Anti-FOMO / Maker-Only):**
    *   **Round 1:** Triggered at market.
    *   **Round 2 and beyond:** The system never FOMO-buys at market peaks. It places **Limit Buy orders at a discount** (typically `-0.80%` below current price) on the book, securing excellent entry prices on corrections, and instantly places the **Limit Sell TP** upon fill.

---

## ⚙️ 4. THE AUTOMATION DAEMON FLEET (SCRIPTS SPECIFICATION)
The background autonomous orchestration is divided among 4 specialized Python scripts running on the GCP VPS:

### 1. `retro_analyzer.py` (Scheduled: Cron every 12 hours)
*   **Purpose:** The Self-Improving Logic Engine.
*   **Workflow:** Ingests recent 24h OKX fills and price data -> Formulates a dense context JSON -> Queries the **local Ollama Qwen-7B** -> Receives optimized targets -> Validates against `protected.json` -> Rewrites `strategy_playbook.json` -> Commits and pushes to GitHub.

### 2. `watcher_daemon.py` (Scheduled: Cron every 5 minutes)
*   **Purpose:** The Instant Capital Recycler.
*   **Workflow:** Compares current live balances against open spot orders. 
    *   If a **Limit Sell** is filled (available balance of that coin goes to 0 and no open orders), it instantly places the next **Limit Buy at a discount**, recycling the capital.
    *   If a **Limit Buy** is filled (available balance goes > 0 and no open orders), it instantly calculates and places the **Limit Sell TP order** on the book, capturing the profit.

### 3. `telegram_reporter.py` (Scheduled: Cron every 5 hours)
*   **Purpose:** Telemetry Push Notifications.
*   **Workflow:** Queries OKX live balance and active orders, formats a clean Markdown summary, and pushes it directly to Giacomo's Telegram via the `@beato_zava` bot.

### 4. `telegram_interactor.py` (Running: Infinite Python Background Loop)
*   **Purpose:** Mobile Control Plane (Interactive Polling).
*   **Workflow:** Polls Telegram `getUpdates` for messages from Giacomo's Chat ID (`655481675`).
    *   `/status` -> Instantly replies with a live balance and order status report.
    *   `/close` -> *Emergency Break-Glass Kill Switch*. Instantly stops the SOL Grid, cancels all open spot orders, and sells all spot crypto at market, liquidating the entire account back to 100% USDC cash.

---

## 🛡️ 5. TWO-TIERED SAFETY & DRAWDOWN LIMITS
To safeguard real-money capital under extreme market conditions, the system enforces a strict programmatic risk policy defined in `config/protected.json`:
*   **Max Scalp Bet Size:** `$100.00` USDC (hard capped).
*   **Min/Max Scalp Targets:** Capped between `0.20%` and `2.50%`.
*   **Tier 1 Alarm (-15% Drawdown):** Pauses all scalp buying, sets SOL grid to *Reduce-Only*.
*   **Tier 2 Kill-Switch (-20% Drawdown / `$296.00` total equity):** Triggers full market liquidation back to USDC cash.

---

## 🧠 6. COMPREHENSIVE AUDIT INSTRUCTIONS FOR EXTERNAL AI
*(Any external AI model auditing this repository should use the following prompt to conduct a rigorous analysis)*

```
ACT AS AN ELITE PRINCIPAL QUANTITATIVE CRYPTOoperator AND LEAD CYBERSECURITY SRE AUDITOR.
Review this TRE-OS system blueprint and the codebase located in the GitHub repository: https://github.com/glaucogaribaldi/openclaw-trader.git

Your goal is to conduct a multidisciplinary, two-pass, risk-ranked security, code quality, and efficiency audit.

INSPECT THE FOLLOWING AREAS DEEPLY:
1. RACE CONDITIONS & CONCURRENCY:
   Analyze scripts/watcher_daemon.py (running every 5 mins) and the manual/telegram triggers. Is there any scenario where a late API response or rapid fill event causes double-ordering, ghost orders, or API rate-limiting on OKX?
2. CAPITAL EFFICIENCY & RECYCLING:
   Is the 5-minute polling interval in scripts/watcher_daemon.py optimal for a $325.03 USDC account? Does it balance fee drag, latency, and capital utilization rate efficiently?
3. EXCEPTION HANDLING & API RESILIENCE:
   Evaluate how scripts handle network drops, OKX API timeouts (500/502/504 errors), or private rate limits. What happens to the state machine if a partial fill occurs (e.g. only 20% of ETH scalp buy gets filled)?
4. LOCAL INFERENCE LATENCY:
   Is Ollama qwen2.5-coder:7b running on a Tesla T4 VM adequate for generating math-based playbook adjustments without latency issues or JSON parsing failures? Suggest improvements to prompt schema validation.
5. SECURITY & SECRET LEAKS:
   Ensure that config.toml and private keys are properly ignored in .gitignore, and that no environment sentinel expansions leak credentials inside git logs or terminal streams.

PROVIDE A PRIORITIZED REMEDIATION REPORT (HIGH / MEDIUM / LOW severity) with concrete Python/TOML/Bash code fixes.
```
