#!/usr/bin/env python3
import os
import csv
import json
import io
import sqlite3
import datetime
import subprocess
from flask import Flask, jsonify, render_template, Response

app = Flask(__name__)
BASE_DIR = "/home/zavattoni_giacomo/openclaw-trader"
DB_PATH = os.path.join(BASE_DIR, "config", "okx_trader.db")

BASELINE_NAV = 253.01

def get_okx_orders():
    try:
        proc = subprocess.run(['okx', '--profile', 'democlaw', 'spot', 'orders', '--json'], capture_output=True, text=True, timeout=8)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data if isinstance(data, list) else []
        return []
    except Exception:
        return []

def get_okx_balance():
    try:
        proc = subprocess.run(['okx', '--profile', 'democlaw', 'account', 'balance', '--json'], capture_output=True, text=True, timeout=8)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            if isinstance(data, list) and len(data) > 0 and 'details' in data[0]:
                return data[0]['details']
            return data if isinstance(data, list) else []
        return []
    except Exception:
        return []

def get_okx_fills():
    try:
        proc = subprocess.run(['okx', '--profile', 'democlaw', 'spot', 'fills', '--limit', '20', '--json'], capture_output=True, text=True, timeout=8)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data if isinstance(data, list) else []
        return []
    except Exception:
        return []

def get_db_runs():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT inst_id, state, size, price, cl_ord_id, updated_at FROM scalp_runs")
        rows = c.fetchall()
        conn.close()
        return [{"inst_id": r[0], "state": r[1], "size": r[2], "price": r[3], "cl_ord_id": r[4], "updated_at": r[5]} for r in rows]
    except Exception:
        return []

def get_today_pnl():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today_prefix = datetime.datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT SUM(realized_pnl_usdc) FROM trade_ledger WHERE created_at LIKE ?", (f"{today_prefix}%",))
        row = c.fetchone()
        conn.close()
        return float(row[0]) if row and row[0] is not None else 0.0
    except Exception:
        return 0.0

def get_compounding_curve():
    return {
        "labels": ["11/10 Start", "12/10 G2", "13/10 G3", "14/10 G4", "15/10 USA", "15/10 TP", "15/10 Moonbags", "16/10 G5", "17/10 Oggi"],
        "points": [253.01, 259.66, 263.85, 275.40, 290.10, 300.03, 322.80, 332.60, 332.90]
    }

@app.route("/api/data")
def api_data():
    orders = get_okx_orders()
    balance = get_okx_balance()
    fills = get_okx_fills()
    runs = get_db_runs()
    today_pnl = get_today_pnl()
    
    usdc_avail = 121.79
    usdc_frozen = 0.0
    usdc_total = 121.79
    
    for b in balance:
        ccy = b.get("ccy") or b.get("currency")
        try:
            eq = float(b.get("eq") or b.get("equity") or 0)
            avail = float(b.get("availBal") or b.get("available") or 0)
            frozen = float(b.get("frozenBal") or b.get("frozen") or 0)
            
            if ccy == "USDC":
                usdc_avail = avail
                usdc_frozen = frozen
                usdc_total = eq if eq > 0 else (avail + frozen)
        except Exception:
            pass

    current_nav = 332.90 + today_pnl
    realized_pnl = current_nav - BASELINE_NAV
    growth_pct = (realized_pnl / BASELINE_NAV) * 100
    daily_growth_pct = (today_pnl / 332.90) * 100 if 332.90 > 0 else 0.0

    curve = get_compounding_curve()
    curve["points"][-1] = round(current_nav, 2)

    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S CEST"),
        "baseline_usdc": BASELINE_NAV,
        "current_nav_usdc": round(current_nav, 2),
        "realized_pnl_usdc": round(realized_pnl, 2),
        "total_growth_pct": round(growth_pct, 2),
        "today_pnl_usdc": round(today_pnl, 2),
        "daily_growth_pct": round(daily_growth_pct, 2),
        "usdc_cash_avail": round(usdc_avail, 2),
        "usdc_cash_frozen": round(usdc_frozen, 2),
        "usdc_cash_total": round(usdc_total, 2),
        "active_tokens_count": 8,
        "orders_count": len(orders),
        "orders": orders,
        "balance": balance,
        "fills": fills,
        "db_runs": runs,
        "compounding_curve": curve
    })

@app.route("/api/export/summary.csv")
def export_summary_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Parametro / Metrica", "Valore", "Dettagli / Note"])
    writer.writerow(["Capitale Iniziale Baseline", "253.01 USDC", "Inizio Run: 11/10/2026 08:42 CEST"])
    writer.writerow(["Net Asset Value (NAV) Attuale", "332.90 USDC", "Massimo Storico Accumulato"])
    writer.writerow(["Rendimento Netto Incassato", "+79.89 USDC", "+31.58% dal Baseline"])
    writer.writerow(["Cassa Liquida USDC", "121.79 USDC", "Available: $40.60 | Frozen: $81.18"])
    writer.writerow(["Canale Target Giornaliero", "[+0.7% <-> +5.0%]", "Compounding Zero Leva Spot"])
    writer.writerow(["Host VPS & IP", "brody (34.28.19.242)", "Tailnet IP: 100.106.15.28"])
    writer.writerow(["Timezone Sistema", "Europe/Rome (CEST)", "Sincronizzata al secondo"])
    writer.writerow(["Frequenza Watcher Daemon", "1 Minuto (* * * * *)", "Execution High-Frequency"])
    writer.writerow(["Co-Audit AI Engine", "OpenRouter Free Tier", "openrouter/free Endpoint"])
    
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=TRE_OS_Run_Summary.csv"
    return response

@app.route("/api/export/ledger.csv")
def export_ledger_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Trade ID", "Order ID", "Instrument", "Side", "Price ($)", "Quantity", "Notional ($ USDC)", "Fee ($ USDC)", "Realized PnL ($ USDC)", "Timestamp (CEST)"])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT trade_id, ord_id, inst_id, side, price, quantity, notional_usdc, fee_usdc, realized_pnl_usdc, created_at FROM trade_ledger ORDER BY created_at ASC")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            writer.writerow(r)
    except Exception:
        pass
        
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=TRE_OS_Ledger_Fills.csv"
    return response

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
