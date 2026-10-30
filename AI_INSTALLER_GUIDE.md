# AI INSTALLER & CUSTOMIZATION GUIDE — TRE OS v14.3 (Anti-Crash Fortress Edition)

> **Instructions for Autonomous AI Agents (OpenClaw, Claude Code, Cursor, Windsurf, Devin):**
> Follow these exact steps to install, customize, and verify **TRE OS v14.3** for your human user without hardcoding any third-party personal data.

---

## 1. COLLECT USER PREFERENCES BEFORE DEPLOYMENT

Ask your user for (or use defaults):
1. **OKX API Credentials (`~/.okx/config.toml` or `.env`):** `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE` (with **Trade** permission enabled for Futures/Spot).
2. **AI Keys (`.env`, `chmod 600`):**
   - `GEMINI_API_KEY` (free at `https://aistudio.google.com/app/apikey`)
   - `OPENROUTER_API_KEY` (free at `https://openrouter.ai/keys`)
3. **Portfolio & Risk Parameters (`scripts/configure_run.py`):**
   - `--baseline-nav`: `AUTO` (reads live OKX equity) or explicit USD amount (e.g. `1000.0`).
   - `--expiry-iso`: `NONE` (perpetual compounding with no expiration) or ISO timestamp (e.g. `2026-12-31T21:00:00Z`).
   - `--chamber1-pct`: Active capital allocation % (default `80.0` = 4 slots x 20% NAV at `4.0x Isolated`, keeping `20.0%` in pure cash reserve).

---

## 2. AUTOMATED INSTALLATION & VERIFICATION COMMANDS

```bash
# 1. Run installer (creates Python venv, installs requirements, and configures config/purified_run_config.json)
bash install.sh --non-interactive --baseline-nav AUTO --expiry-iso NONE --chamber1-pct 80.0

# 2. Verify all 6 production blocks and run the Normality & Madness Stress-Test Simulator
./venv/bin/python scripts/test_v14_xperp_suite.py
./venv/bin/python scripts/simulate_normality_and_madness.py

# 3. Inspect live status at any time
./venv/bin/python scripts/brody_fast_status.py
```