#!/bin/sh

INTERVAL="${CHECK_INTERVAL:-300}"
MAX_APPLY_RETRIES="${MAX_APPLY_RETRIES:-5}"
RETRY_DELAY="${RETRY_DELAY:-15}"

run_on_host() {
  nsenter --target 1 --mount --uts --ipc --net --pid -- "$@"
}

echo "[power-tune] applying power tuning on host..."
attempt=1
until run_on_host /home/umbrel/umbrel/power-tune.sh; do
  if [ "$attempt" -ge "$MAX_APPLY_RETRIES" ]; then
    echo "[power-tune] power-tune.sh failed after ${attempt} attempts (likely apt/network) - moving on to monitor loop anyway"
    break
  fi
  echo "[power-tune] power-tune.sh failed (attempt ${attempt}/${MAX_APPLY_RETRIES}), retrying in ${RETRY_DELAY}s"
  attempt=$((attempt + 1))
  sleep "$RETRY_DELAY"
done

echo "[power-tune] entering monitor loop (every ${INTERVAL}s)"
while true; do
  sleep "$INTERVAL"
  echo "[power-tune] running check-power-tuning.sh"
  run_on_host /home/umbrel/umbrel/check-power-tuning.sh || true
done
