import sqlite3
import urllib.request
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RENDER_URL = "https://dingjourney.onrender.com"
DB_PATH = os.path.join(os.path.dirname(__file__), "app", "dingjourney.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    trades = [dict(r) for r in conn.execute("SELECT * FROM trades").fetchall()]
    config_rows = conn.execute("SELECT * FROM config").fetchall()
    config = {r["key"]: r["value"] for r in config_rows}
    conn.close()

    print(f"[*] Found {len(trades)} local trades.")

    # 1. Clear old demo trades on Render
    try:
        req = urllib.request.Request(f"{RENDER_URL}/api/trades/clear", data=b"", method="POST")
        with urllib.request.urlopen(req) as resp:
            print("[✓] Cleared old trades on Render:", resp.read().decode("utf-8"))
    except Exception as e:
        print("[!] Error clearing trades:", e)

    # 2. Insert real trades
    for t in trades:
        try:
            payload = json.dumps(t).encode("utf-8")
            req = urllib.request.Request(
                f"{RENDER_URL}/api/trades",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                print(f"[✓] Synced real trade {t.get('ticket')}")
        except Exception as e:
            print(f"[!] Error syncing trade {t.get('ticket')}:", e)

    # 3. Sync config
    try:
        cfg_payload = {
            "starting_capital": float(config.get("starting_capital", 10000.0)),
            "sync_pin": config.get("sync_pin", "77778888"),
            "account_type": config.get("account_type", "REAL"),
            "account_name": config.get("account_name", "Base Account"),
            "currency": config.get("currency", "$")
        }
        req = urllib.request.Request(
            f"{RENDER_URL}/api/config",
            data=json.dumps(cfg_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            print("[✓] Synced config on Render:", resp.read().decode("utf-8"))
    except Exception as e:
        print("[!] Error syncing config:", e)

    print("\n[✓] Render Cloud Sync Complete!")

if __name__ == "__main__":
    main()
