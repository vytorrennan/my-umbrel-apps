#!/usr/bin/env bash
# codex-ssd-guard
#
# Protects the SSD from Codex CLI's runaway diagnostic logging.
# Codex writes diagnostics to ~/.codex/logs_2.sqlite (SQLite WAL). In affected
# (pre-0.142) builds this ran at TRACE level and ignored RUST_LOG, causing
# massive write amplification (~640 TB/year extrapolated, and a crash once the
# DB exceeds ~200 MB). The upstream fix shipped in 0.142.x/0.143.x, but this
# guard adds a belt-and-braces layer that survives any version:
#
#   1. Redirect the log DB to /dev/shm (RAM-backed tmpfs) so no log writes
#      ever hit the SSD, even if a future regression returns.
#   2. Apply a SQLite BEFORE INSERT trigger that discards all rows written to
#      the `logs` table, eliminating write amplification at the source.
#
# The log DB holds only diagnostics (no conversations/credentials), so losing
# it on reboot is harmless. /dev/shm is wiped on reboot, but this script
# re-applies the symlink (and the trigger once Codex has recreated the logs
# table) on every shell/login.
#
# Idempotent: safe to run repeatedly.

set -euo pipefail

CODEX_DIR="$HOME/.codex"
LOG_DB="$CODEX_DIR/logs_2.sqlite"
RAM_DIR="/dev/shm"
RAM_DB="$RAM_DIR/codex_logs_2.sqlite"

[ -d "$CODEX_DIR" ] || mkdir -p "$CODEX_DIR"

# Only redirect if /dev/shm is RAM-backed tmpfs.
if ! df -t tmpfs /dev/shm >/dev/null 2>&1; then
  echo "codex-ssd-guard: /dev/shm is not a tmpfs mount; skipping RAM redirect." >&2
  exit 0
fi

# 1. Point ~/.codex/logs_2.sqlite at the RAM-backed file.
if ! [ -L "$LOG_DB" ] || [ "$(readlink "$LOG_DB")" != "$RAM_DB" ]; then
  rm -f "$LOG_DB" "$LOG_DB-wal" "$LOG_DB-shm"
  ln -s "$RAM_DB" "$LOG_DB"
fi

# 2. Apply the blocking trigger, but only once Codex has actually created the
#    `logs` schema (a bare trigger on a missing table cannot be created). Until
#    then the RAM redirect alone already keeps writes off the SSD; the trigger
#    is applied idempotently on the first later shell once the table exists.
if [ -f "$RAM_DB" ] && command -v sqlite3 >/dev/null 2>&1; then
  if sqlite3 "$RAM_DB" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='logs';" 2>/dev/null | grep -q 1; then
    sqlite3 "$RAM_DB" \
      "CREATE TRIGGER IF NOT EXISTS block_log_inserts BEFORE INSERT ON logs BEGIN SELECT RAISE(IGNORE); END;" \
      2>/dev/null || true
  fi
fi
