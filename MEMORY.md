# MEMORY.md

## Stable Lessons

- Lehman Brody should move bulk files with null-safe or `find ... -exec` patterns, not brittle `xargs` pipelines.
- When Giacomo asks for an internal system task, Lehman Brody should execute it directly, verify it, and only then report back.
- OpenClaw runs locally on Giacomo's Mac through the local gateway; Ollama is remote on the VPS.
- OpenClaw's browser profile is `chromium`; Google Chrome and the `chrome` profile are excluded.
- Chromium has its own profile. GCloud, Tailscale, and GitHub may need one-time interactive login in Chromium.
- Money-related actions are never performed. A successful report requires post-action evidence, not an intention or drafted command.
- For internet work, Lehman Brody uses web_search for discovery, web_fetch for readable sources, and the OpenClaw Chromium profile for dynamic or authenticated pages; it records sources and verifies every browser action.
- The workspace skill web-research is the standard procedure for current research, source comparison, prompt-injection resistance, and post-action verification.

## 📈 OKX Algorithmic Trading Architecture (Stable Lessons & Setup)

- **Cloud Infrastructure & Pairing Synergy (`openclaw pair`)**:
  - The primary execution, monitoring, and database layers for 24/7 autonomous trading are hosted on the Google Cloud VM `openclaw-trader-box` (Tesla T4 GPU, 16GB VRAM, local Ollama with `qwen2.5-coder:7b` for 100% private, zero-cost, local-intelligence orchestration). <!-- project: path:/Users/zava/.openclaw/workspace -->
  - The Mac operates as the Master/Client console. Both environments are paired securely over Tailscale using `openclaw pair`. This allows Giacomo to turn off his Mac while the cloud node trades h24. <!-- project: path:/Users/zava/.openclaw/workspace -->
  
- **Telegram & Mobile Monitoring**:
  - The Telegram channel `@beato_zava` is paired and integrated into OpenClaw. Giacomo can send `/report` from his smartphone to get real-time portfolio balance, bot profits, and open order statistics from the cloud VM node instantly. <!-- project: path:/Users/zava/.openclaw/workspace -->

- **Two-Tiered Risk Management System**:
  - **Tier 1 (Conservative Alarm at -15% drawdown / $314.50)**: Pauses the SOL Grid Bot, locks new scalping buy orders, and keeps existing Limit Sells on the book to exit on a rebound. <!-- project: path:/Users/zava/.openclaw/workspace -->
  - **Tier 2 (Hard Kill-Switch at -20% drawdown / $296.00)**: Stops all bots, cancels all open orders, and executes Market Sell orders on 100% of holdings (BTC, ETH, SOL) back into USDC cash to freeze the account. <!-- project: path:/Users/zava/.openclaw/workspace -->

- **Time-Aware Soft Close & Autoclose Execution (Session Sizing)**:
  - For time-bound trading sessions (e.g. 12h), the system must enforce a progressive close timeline:
    - **T-2h (Soft Close)**: Disable new scalping buy entries, set the Grid Bot to *Reduce-Only* to prevent locking up capital on a sudden end-of-session dip. <!-- project: path:/Users/zava/.openclaw/workspace -->
    - **T-1h (Tapering)**: Automatically adjust and lower existing Limit Sell targets (e.g. to +0.10% or breakeven) to maximize the probability of filling on the book. <!-- project: path:/Users/zava/.openclaw/workspace -->
    - **T-0h (Hard Close)**: Automatically stops all bots, cancels open orders, and liquidates any remaining assets at market back to USDC cash. <!-- project: path:/Users/zava/.openclaw/workspace -->
