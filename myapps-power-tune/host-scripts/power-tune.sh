#!/bin/bash

# Install tools
apt-get update
apt-get install -y linux-cpupower powertop ethtool pciutils rfkill

# CPU governor
cpupower frequency-set -g powersave

# PowerTOP tuning
powertop --auto-tune

# Disable WiFi/Bluetooth if desired
rfkill block wifi
rfkill block bluetooth

# Ethernet power settings
ethtool -s enp2s0f0 wol d

# PCIe ASPM
echo powersave > /sys/module/pcie_aspm/parameters/policy 2>/dev/null || true

# Lid switch behavior (ignore so closing the lid doesn't suspend/shutdown the server)
for setting in HandleLidSwitch HandleLidSwitchExternalPower HandleLidSwitchDocked; do
  if grep -q "^${setting}=" /etc/systemd/logind.conf; then
    sed -i "s/^${setting}=.*/${setting}=ignore/" /etc/systemd/logind.conf
  elif grep -q "^#${setting}=" /etc/systemd/logind.conf; then
    sed -i "s/^#${setting}=.*/${setting}=ignore/" /etc/systemd/logind.conf
  else
    echo "${setting}=ignore" >> /etc/systemd/logind.conf
  fi
done

systemctl restart systemd-logind

# Disable Bluetooth service (no BT radio on this hardware, but keep it off in case one's ever added)
systemctl disable --now bluetooth.service 2>/dev/null || true
systemctl mask bluetooth.service 2>/dev/null || true
