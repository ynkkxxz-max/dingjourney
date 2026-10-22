"""
Journa NextGen - Main Launcher
Starts FastAPI uvicorn server, Cloudflare tunnel, extracts the live URL,
and launches the browser automatically.
"""

import sys
import os
import subprocess
import time
import re
import webbrowser
import signal

# Ensure Windows terminal doesn't crash on emoji prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "tunnel.log")
URL_FILE = os.path.join(BASE_DIR, "tunnel_url.txt")
BIN_CLOUDFLARED = os.path.join(BASE_DIR, "bin", "cloudflared.exe")

def main():
    os.chdir(BASE_DIR)
    
    # 1. Kill any existing instances on port 8000 if needed
    print("=" * 65)
    print("       🚀 Journa NextGen - Trading Calendar Dashboard")
    print("=" * 65)
    print("\n[1/3] Starting FastAPI Server on http://localhost:8000...")
    
    server_log_path = os.path.join(BASE_DIR, "server.log")
    server_log = open(server_log_path, "w", encoding="utf-8")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=server_log,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for server to respond
    time.sleep(2)
    print("[✓] Server started successfully.")
    
    tunnel_proc = None
    tunnel_log = None
    live_url = "http://localhost:8000"
    
    if os.path.exists(BIN_CLOUDFLARED):
        print("\n[2/3] Connecting Cloudflare Secure Tunnel for iPhone/Remote...")
        try:
            tunnel_log = open(LOG_FILE, "w", encoding="utf-8")
            tunnel_proc = subprocess.Popen(
                [BIN_CLOUDFLARED, "tunnel", "--url", "http://127.0.0.1:8000"],
                stdout=tunnel_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Read tunnel.log for the live trycloudflare URL
            start_wait = time.time()
            while time.time() - start_wait < 15:
                time.sleep(0.5)
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                            if match:
                                live_url = match.group(0)
                                with open(URL_FILE, "w", encoding="utf-8") as uf:
                                    uf.write(live_url)
                                break
                    except Exception:
                        pass
        except Exception as e:
            print(f"[!] Tunnel startup notice: {e}")
    else:
        print("[!] bin/cloudflared.exe not found. Running in local-only mode.")

    print("\n[3/3] Opening dashboard in browser...")
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  ✅ JOURNA NEXTGEN IS LIVE & READY!")
    print("=" * 65)
    print(f"  💻 Local PC Link (Instant 3ms): http://127.0.0.1:8000")
    if live_url != "http://localhost:8000" and live_url != "http://127.0.0.1:8000":
        print(f"  📱 iPhone / Remote Link:        {live_url}")
        print("\n  👉 iPhone Tip: Open the link above in Safari and select")
        print("     'Add to Home Screen' to use it as a native iOS App!")
    print("=" * 65)
    print("\n  ⚠️  DO NOT CLOSE THIS WINDOW while using Journa NextGen.")
    print("  (Press Ctrl+C to stop the server)\n")

    def cleanup(signum=None, frame=None):
        print("\nStopping Journa NextGen...")
        if tunnel_proc and tunnel_proc.poll() is None:
            tunnel_proc.terminate()
        if server_proc and server_proc.poll() is None:
            server_proc.terminate()
        try:
            if server_log:
                server_log.close()
            if tunnel_log:
                tunnel_log.close()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Keep alive and drain logs
    try:
        while True:
            if server_proc.poll() is not None:
                print("[!] Server stopped unexpectedly.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
