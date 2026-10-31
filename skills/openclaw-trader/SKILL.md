---
name: openclaw-trader
description: Operate, audit, and self-optimize TRE OS v18.2 (Autonomous OKX EEA XPERP Perpetual Futures Engine with 60s Gemini Free Co-Pilot, 3-Strategy Auto-Switcher, and Hourly Guardian).
---

# OpenClaw Trader — TRE OS v18.2 Skill

- **Primary Daemon:** `predator_futures_demo.py` (`openclaw-futures-demo.service` on `brody`).
- **Instant Status:** `./venv/bin/python scripts/brody_fast_status.py`
- **Full Stress & Audit Suite:** `./venv/bin/python scripts/full_vps_stress_and_audit.py`
- **48h Empirical Replay:** `./venv/bin/python scripts/replay_last_48h_disaster.py`
- **Hourly Autonomous Guardian & Telegram Push:** `./venv/bin/python scripts/hourly_autonomous_guardian.py`