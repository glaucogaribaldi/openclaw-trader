#!/usr/bin/env python3
"""
TRE OS v5.6 SRE Log Management & Storage Maintenance Helper
Truncates log files in memory/*.log if they exceed 5MB to preserve VPS disk space.
"""
import os, sys, glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "memory")
MAX_BYTES = 5 * 1024 * 1024 # 5 MB threshold

def rotate_logs():
    rotated = []
    if not os.path.exists(LOG_DIR):
        return rotated
    
    for log_path in glob.glob(os.path.join(LOG_DIR, "*.log")):
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > MAX_BYTES:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                # Keep last 5000 lines
                keep_lines = lines[-5000:]
                with open(log_path, "w", encoding="utf-8") as f:
                    f.writelines(keep_lines)
                rotated.append((os.path.basename(log_path), len(keep_lines)))
        except Exception as e:
            print(f"Error rotating {log_path}: {e}")
            
    return rotated

if __name__ == "__main__":
    res = rotate_logs()
    print("=== SRE LOG ROTATION CHECK ===")
    if res:
        for fname, count in res:
            print(f"[ROTATED] {fname} truncated to last {count} lines")
    else:
        print("[OK] All log files under 5MB threshold. Disk space optimal.")
