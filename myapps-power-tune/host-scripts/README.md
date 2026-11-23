These are backup copies of the scripts that run on the host at
/home/umbrel/umbrel/. They are NOT used during the Docker build or referenced
by the container. If you restore this setup on a fresh Umbrel install, copy
these back to /home/umbrel/umbrel/ manually and chmod +x them.

To run the check directly on the host:
`sudo /home/umbrel/umbrel/check-power-tuning.sh`

Or via the container (if installed as an Umbrel app):
`sudo docker exec power-tune nsenter --target 1 --mount --uts --ipc --net --pid -- /home/umbrel/umbrel/check-power-tuning.sh`
