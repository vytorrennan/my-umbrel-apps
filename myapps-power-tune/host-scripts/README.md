These are backup copies of the scripts that actually run on the host at
/home/umbrel/umbrel/. They are NOT used during the Docker build or referenced
by the container — the power-tune app calls the live host copies directly
via nsenter. If you restore this app on a fresh Umbrel install, copy these
back to /home/umbrel/umbrel/ manually and chmod +x them.


To run the check:
`sudo docker exec power-tune nsenter --target 1 --mount --uts --ipc --net --pid -- /home/umbrel/umbrel/check-power-tuning.sh`
