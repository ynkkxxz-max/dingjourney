"""
Journa NextGen - Tunnel Manager
Keeps the Cloudflare tunnel persistently active and writes the live public URL to tunnel_url.txt.
"""

import subprocess
import time
import re
import os

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel.log")
URL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_url.txt")
BIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "cloudflared.exe")

def run_tunnel():
    while True:
        if not os.path.exists(BIN_PATH):
            time.sleep(5)
            continue
            
        print("Starting cloudflared tunnel...")
        try:
            proc = subprocess.Popen(
                [BIN_PATH, "tunnel", "--protocol", "http2", "--edge-ip-version", "4", "--url", "http://127.0.0.1:8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
            
            for line in proc.stdout:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line)
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    url = match.group(0)
                    print("FOUND LIVE URL:", url, flush=True)
                    with open(URL_FILE, "w", encoding="utf-8") as f:
                        f.write(url)
                        
            proc.wait()
        except Exception as e:
            print("Tunnel loop error:", e, flush=True)
        print("Tunnel process ended, restarting in 3s...", flush=True)
        time.sleep(3)

if __name__ == "__main__":
    run_tunnel()
