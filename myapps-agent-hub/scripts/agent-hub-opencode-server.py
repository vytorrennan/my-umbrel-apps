#!/usr/bin/env python3
"""Keep the shared OpenCode server aligned with CLI updates."""
import argparse
import os
import re
import shutil
import signal
import subprocess
import time


def fingerprint(executable):
    path = shutil.which(executable)
    if not path:
        return None
    try:
        resolved = os.path.realpath(path)
        stat = os.stat(resolved)
        return resolved, stat.st_ino, stat.st_size, stat.st_mtime_ns
    except OSError:
        return None


def version(executable):
    try:
        result = subprocess.run([executable, "--version"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, timeout=5)
        match = re.search(r"(?m)^opencode v?(\d+\.\d+\.\d+[^\s]*)", result.stdout)
        return match[1] if result.returncode == 0 and match else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def stop(process, timeout):
    # Include any descendants left behind by a CLI launcher.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--settle-seconds", type=float, default=0.5)
    parser.add_argument("--stop-timeout", type=float, default=10)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a server command is required")
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    current = version(command[0])
    if current is None:
        print("[opencode-server] CLI is not ready", flush=True)
        return 1
    baseline = fingerprint(command[0])
    process = subprocess.Popen(command, start_new_session=True)
    candidate, changed_at = None, 0
    try:
        while not stopping:
            if process.poll() is not None:
                return process.returncode or 1
            observed = fingerprint(command[0])
            if observed is not None and observed != baseline:
                if observed != candidate:
                    candidate, changed_at = observed, time.monotonic()
                elif time.monotonic() - changed_at >= args.settle_seconds:
                    updated = version(command[0])
                    # A failing/incomplete replacement must not stop the server.
                    if updated is not None and fingerprint(command[0]) == observed:
                        if updated != current and not stopping:
                            print(f"[opencode-server] CLI changed {current} -> {updated}; restarting server", flush=True)
                            stop(process, args.stop_timeout)
                            if stopping:
                                break
                            process = subprocess.Popen(command, start_new_session=True)
                            current = updated
                        baseline, candidate = observed, None
            else:
                candidate = None
            time.sleep(args.poll_interval)
        return 0
    finally:
        stop(process, args.stop_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
