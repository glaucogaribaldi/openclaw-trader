#!/usr/bin/env python3
"""
Nemotron AI Co-Auditor Client for VPS
Queries Nemotron (nemotron-3.5-lightning:latest) running on AI VPS (100.125.189.103:11434).
"""
import urllib.request
import json
import sys

OLLAMA_URL = "http://100.125.189.103:11434/api/generate"
MODEL_NAME = "nemotron-3.5-lightning:latest"

def query_nemotron(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(OLLAMA_URL, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            response_text = res_json.get("response", "")
            return {
                "status": "success",
                "model": f"Nemotron VPS ({MODEL_NAME})",
                "response": response_text.strip()
            }
    except Exception as e:
        return {
            "status": "error",
            "model": MODEL_NAME,
            "error": str(e)
        }

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "Esegui un audit del sistema TRE OS v5.6."
    res = query_nemotron(p)
    print(json.dumps(res, indent=2, ensure_ascii=False))
