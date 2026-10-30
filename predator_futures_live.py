#!/usr/bin/env python3
"""
TRE OS v14.0 — Sovereign Perpetual Futures 2.5x Isolated Live Production Entrypoint (predator_futures_live.py)
Promoted production daemon for OKX Europe Regulated Perpetual Futures (*-USD_UM_XPERP-*).
"""
import os
os.environ["FUTURES_LIVE_EXECUTION"] = "true"
from predator_futures_demo import main

if __name__ == "__main__":
    main()
