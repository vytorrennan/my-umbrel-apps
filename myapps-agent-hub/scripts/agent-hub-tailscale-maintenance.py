#!/usr/bin/env python3
"""Update stable Tailscale daily and reconcile Supervisor's running executable."""
import os
import subprocess
import time

def reconcile():
    result = subprocess.run(["/usr/bin/supervisorctl", "pid", "tailscaled"], capture_output=True, text=True)
    try:
        pid = int(result.stdout.strip())
        if pid > 0 and not os.path.samefile(f"/proc/{pid}/exe", "/usr/sbin/tailscaled"):
            subprocess.run(["/usr/bin/supervisorctl", "restart", "tailscaled"], check=True, timeout=60)
    except (ValueError, FileNotFoundError):
        pass

def main():
    next_update = 0
    while True:
        try:
            reconcile()
            if time.monotonic() >= next_update:
                result = subprocess.run(["/usr/bin/tailscale", "update", "--yes", "--track=stable"], timeout=900)
                next_update = time.monotonic() + (86400 if result.returncode == 0 else 3600)
                reconcile()
        except Exception as error:
            print(f"Tailscale maintenance: {error}", flush=True)
            next_update = time.monotonic() + 3600
        time.sleep(60)

if __name__ == "__main__":
    main()
