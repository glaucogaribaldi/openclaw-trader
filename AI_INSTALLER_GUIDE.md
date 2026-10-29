# 🤖 AI AGENT INSTALLER & CALIBRATION MANUAL — TRE OS v12.0 (SOVEREIGN PREDATOR EDITION)

> **Target Audience:** Autonomous Coding & DevOps AI Agents (**OpenClaw**, **Claude Code**, **Cursor**, **Codex**, **Devin**, **Windsurf**, **Aider**) and Human Operators.
> **Important Rule for AI Agents:** Never hardcode fixed portfolio dollar amounts, fixed expiration dates, or personal Chat IDs into source code. Always interview your human operator for the 6 calibration parameters below and pass them to `scripts/configure_run.py --non-interactive` (or `install.sh`).

---

## 📋 STEP 1: INTERVIEW THE HUMAN USER (6 REQUIRED CALIBRATION PARAMETERS)

Before executing the installation, ask your human user for the following parameters (or use their preferred defaults):

1. **Starting Portfolio Capital (`--baseline-nav`):**
   - Ask: *"Do you want the bot to automatically detect your live OKX USDC + Spot balance on first startup (`AUTO`), or set a specific starting baseline in USDC (e.g. `250`, `1000`, `5000`)?"*
2. **Run Expiration Date & Cashout Mode (`--expiry-iso` & `--cashout-days`):**
   - Ask: *"Should this run operate perpetually (`NONE`), or liquidate 100% into `USDC` cash by a specific target date/time (e.g. `2026-12-31T21:00:00Z` with a `6.0`-day progressive cashout taper)?"*
3. **Two-Chamber Capital Split (`--chamber1-pct`):**
   - Ask: *"What percentage of your capital should be allocated to **Chamber 1 (Active Dip-Sniper Assault)** vs **Chamber 2 (Pure USDC Crash-Shield Reserve)**? (Recommended default: `63`% Assault / `37`% Cash Shield)."*
4. **Hard Max-Loss Cap & Fast Profit Shield (`--max-loss-bps` & `--fast-shield-bps`):**
   - Ask: *"What is the maximum allowed loss per position before an automatic Post-Only Maker exit at Best Ask? (Default: `-400` bps = `-4.00%`, with Fast Break-Even + Profit Shield arming at `+38` bps = `+0.38%`)."*
5. **Daily Organic Compounding Channel (`--daily-min-pct` & `--daily-max-pct`):**
   - Default Golden Rule channel: `0.70%` to `5.00%` per day.
6. **API Credentials (stored ONLY in local `.env` with `chmod 600`, never committed to Git):**
   - **OKX Spot (EEA / Global):** `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_API_PASSPHRASE` (*Read + Trade permissions only; NEVER enable withdrawal permissions*).
   - **Free AI Council Keys (`100% $0.00 Free Tier`):**
     - Primary: `GEMINI_API_KEY` from [Google AI Studio Free Tier](https://aistudio.google.com/apikey) (`gemini-3.5-flash-lite` / `gemini-3.5-flash` / `gemini-3.8-flash`);
     - Secondary Failover: `OPENROUTER_API_KEY` from [OpenRouter](https://openrouter.ai/settings/keys) (1-call native fallback array across `:free` models).
   - **Optional Telegram Reporting:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

---

## ⚙️ STEP 2: NON-INTERACTIVE INSTALLATION & CALIBRATION COMMANDS (FOR AI AGENTS)

Run the following deterministic commands on the target Linux VPS (Debian/Ubuntu, minimum 1 GB RAM + 2 GB Swap) or macOS host:

```bash
# 1. Clone the repository
git clone https://github.com/glaucogaribaldi/openclaw-trader.git ~/openclaw-trader
cd ~/openclaw-trader

# 2. Run the Universal Installer in non-interactive mode with the user's chosen parameters:
# Example A: Perpetual run (no expiration date) with automatic wallet balance detection
bash install.sh --non-interactive \
  --baseline-nav AUTO \
  --expiry-iso NONE \
  --chamber1-pct 63.0 \
  --max-loss-bps -400.0 \
  --fast-shield-bps 38.0 \
  --daily-min-pct 0.70 \
  --daily-max-pct 5.00

# Example B: Fixed-term run expiring on a user-defined date (e.g. 2027-06-30) with 6-day USDC taper
bash install.sh --non-interactive \
  --baseline-nav 1000.00 \
  --expiry-iso 2027-06-30T21:00:00Z \
  --cashout-days 6.0 \
  --chamber1-pct 63.0 \
  --max-loss-bps -400.0 \
  --fast-shield-bps 38.0
```

---

## 🧠 STEP 3: INSTALL THE LOCAL 5-HORIZON KRONOS FOUNDATION MODEL ORACLE (`1h / 2h / 6h / 12h / 24h`)

Install the local Tsinghua University **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** foundation model server (`kronos-oracle.service` on `127.0.0.1:8090`):

```bash
cd ~/openclaw-trader
# Use --size mini (4.1M params, ~380 MB RAM) for CPU Mini-VPS, or --size small (24.7M) for GPU/Apple Silicon:
bash scripts/install_kronos_oracle.sh --size mini
```

Verify that `kronos-oracle.service` is healthy and serving all 5 horizons (`expected_return_1h_bps`, `macro_return_2h_bps`, `horizon_6h_bps`, `swing_return_12h_bps`, `daily_return_24h_bps`):

```bash
curl -s http://127.0.0.1:8090/health
```

---

## 🔐 STEP 4: POPULATE `.env` SECURELY & INITIALIZE THE PORTFOLIO BASELINE

1. Write the user's credentials into `~/openclaw-trader/.env` and lock permissions:
   ```bash
   chmod 600 ~/openclaw-trader/.env
   ```
2. Verify with a hermetic **Dry-Run** (reads live OKX orderbooks, balances, and 5-Horizon Kronos without placing orders):
   ```bash
   ~/openclaw-trader/venv/bin/python ~/openclaw-trader/predator_daemon.py --once --dry-run
   ```
3. If `--baseline-nav AUTO` was selected, snapshot the live OKX wallet balance into `config/purified_run_config.json` and start the production daemon:
   ```bash
   ~/openclaw-trader/venv/bin/python ~/openclaw-trader/predator_daemon.py --once --live --init-purified-run
   sudo systemctl restart openclaw-predator.service
   ```

---

## 🔍 STEP 5: POST-INSTALLATION VERIFICATION FOR THE AI AGENT

Run the 1-shot diagnostic tool to confirm zero errors:
```bash
~/openclaw-trader/venv/bin/python ~/openclaw-trader/scripts/brody_fast_status.py
```
