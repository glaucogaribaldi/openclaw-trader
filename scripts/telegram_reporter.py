#!/usr/bin/env python3
"""
TRE OS v14.0 — Sovereign Perpetual Futures 2.5x Isolated Telegram Executive Reporter (telegram_reporter.py)
Reads config/futures_demo_snapshot.json and sends a brutally honest live executive report to Telegram.
"""
import json, os, ssl, sys, urllib.request
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from predator_daemon import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

def send_telegram_report() -> None:
    snap_p = os.path.join(BASE_DIR, "config", "futures_demo_snapshot.json")
    if not os.path.exists(snap_p):
        print("[!] Missing futures_demo_snapshot.json")
        return
    s = json.load(open(snap_p, encoding="utf-8"))
    nav = float(s.get("current_nav_usd") or 0.0)
    base = float(s.get("baseline_nav_usd") or 268.95)
    free_mgn = float(s.get("free_margin_usd") or 0.0)
    locked_mgn = float(s.get("locked_margin_usd") or 0.0)
    rpnl = float(s.get("realized_pnl_usd") or 0.0)
    upnl = float(s.get("unrealized_pnl_usd") or 0.0)
    fees = float(s.get("total_fees_usd") or 0.0)
    fdrag = float(s.get("fee_drag_ratio_pct") or 0.0)
    wins, shields, stops = int(s.get("wins_count") or 0), int(s.get("shield_locks_count") or 0), int(s.get("stops_count") or 0)
    delta_base = nav - base
    delta_pct = (delta_base / base * 100.0) if base > 0 else 0.0
    pos_lines = []
    for p in s.get("open_positions", []):
        pos_lines.append(f"• {p['direction']} 2.5x {p['inst_id'].split('-')[0]}: Mgn=$${p['margin_usd']} | Entry=$${p['entry_px']} -> $${p['current_px']} | Peak={p['peak_move_bps']:+.1f}bps Shield={p['shield_armed']}")
    pos_txt = "\n".join(pos_lines) if pos_lines else "• Nessuna posizione aperta (100% Margine USDC liquido)"
    msg = (
        f"⚡ *TRE OS v14.0 — LIVE XPERP FUTURES 2.5X ISOLATED*\n"
        f"🕒 `{s.get('timestamp')}`\n\n"
        f"💰 *NAV Conto Trading OKX:* `$${nav:.2f} USDC` (`{delta_base:+.2f} USDC` / `{delta_pct:+.2f}%` da switch $${base:.2f})\n"
        f"🛡️ *Camera 2 (Free Margin USDC):* `$${free_mgn:.2f} USDC`\n"
        f"⚔️ *Camera 1 (Locked Margin 2.5x):* `$${locked_mgn:.2f} USDC`\n"
        f"📊 *Realized PnL:* `$${rpnl:+.4f}` | *Unr PnL:* `$${upnl:+.3f}`\n"
        f"🧾 *Fees (2 bps Maker):* `$${fees:.4f}` (`Fee-Drag: {fdrag:.1f}%`)\n"
        f"🏆 *Esiti:* `Wins={wins} | Shields={shields} | Stops={stops}`\n"
        f"🧠 *Auditor:* `{s.get('auditor_model')}`\n\n"
        f"*Posizioni Attive (Max 4 x 12.5% NAV):*\n{pos_txt}"
    )
    print(msg)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    cid = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tok and cid:
        try:
            u = f"https://api.telegram.org/bot{tok}/sendMessage"
            data = json.dumps({"chat_id": cid, "text": msg, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(u, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8, context=ssl.create_default_context())
        except Exception as e:
            print(f"[!] Telegram send warning: {e}")

if __name__ == "__main__":
    send_telegram_report()
