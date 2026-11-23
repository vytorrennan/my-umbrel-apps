#!/bin/sh

MAX_APPLY_RETRIES="${MAX_APPLY_RETRIES:-5}"
RETRY_DELAY="${RETRY_DELAY:-15}"

run_on_host() {
  nsenter --target 1 --mount --uts --ipc --net --pid -- "$@"
}

echo "[power-tune] applying power tuning on host..."
attempt=1
until run_on_host /home/umbrel/umbrel/power-tune.sh; do
  if [ "$attempt" -ge "$MAX_APPLY_RETRIES" ]; then
    echo "[power-tune] power-tune.sh failed after ${attempt} attempts"
    break
  fi
  echo "[power-tune] power-tune.sh failed (attempt ${attempt}/${MAX_APPLY_RETRIES}), retrying in ${RETRY_DELAY}s"
  attempt=$((attempt + 1))
  sleep "$RETRY_DELAY"
done

echo "[power-tune] applied. sleeping idle (run check-power-tuning.sh manually when needed)."
exec tail -f /dev/null
