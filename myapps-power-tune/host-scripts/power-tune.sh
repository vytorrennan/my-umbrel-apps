#!/bin/bash

# Install tools only if missing (prefer offline .deb cache under /home/umbrel/umbrel/power-tune/debs)
POWER_TUNE_DEBS="/home/umbrel/umbrel/power-tune/debs"
missing_tools=0
for cmd in cpupower powertop ethtool lspci rfkill; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_tools=1
    break
  fi
done

if [ "$missing_tools" -eq 1 ]; then
  if [ -d "$POWER_TUNE_DEBS" ] && compgen -G "$POWER_TUNE_DEBS/*.deb" >/dev/null; then
    DEBIAN_FRONTEND=noninteractive dpkg -i "$POWER_TUNE_DEBS"/*.deb >/dev/null 2>&1 || true
  fi

  still_missing=0
  for cmd in cpupower powertop ethtool lspci rfkill; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      still_missing=1
      break
    fi
  done

  if [ "$still_missing" -eq 1 ]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y linux-cpupower powertop ethtool pciutils rfkill
  fi
fi

# Reset scaling_max_freq on all CPUs (clears any stale per-core cap)
for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
  if [ -r "$cpu/cpuinfo_max_freq" ] && [ -w "$cpu/scaling_max_freq" ]; then
    cat "$cpu/cpuinfo_max_freq" > "$cpu/scaling_max_freq" 2>/dev/null || true
  fi
done

# Dynamic CPU governor (scales down to 1.2 GHz at idle, boosts under load)
cpupower frequency-set -g schedutil

# Disable Intel Turbo Boost (caps i5-3230M at 2.60 GHz base to limit peak power, heat, and fan noise)
if [ -w /sys/devices/system/cpu/intel_pstate/no_turbo ]; then
  echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo
fi

# PowerTOP tuning (SATA ALPM, PCI/USB runtime PM, audio PM, NMI watchdog off)
powertop --auto-tune

# Put all SATA hosts (including empty ports) into low-power ALPM
for policy in /sys/class/scsi_host/host*/link_power_management_policy; do
  [ -w "$policy" ] || continue
  cur=$(cat "$policy" 2>/dev/null)
  if [ "$cur" = "keep_firmware_settings" ] || [ "$cur" = "max_performance" ]; then
    echo med_power_with_dipm > "$policy" 2>/dev/null || echo min_power > "$policy" 2>/dev/null || true
  fi
done

# Turn off laptop display backlight and power down the LVDS display pipeline
for bl in /sys/class/backlight/*/brightness; do
  [ -w "$bl" ] && echo 0 > "$bl" 2>/dev/null || true
done
if [ -c /dev/tty1 ] && command -v setterm >/dev/null 2>&1; then
  setterm --term linux --blank 1 --powerdown 1 >/dev/tty1 </dev/tty1 2>/dev/null || true
fi
if [ -w /sys/class/graphics/fb0/blank ]; then
  echo 4 > /sys/class/graphics/fb0/blank 2>/dev/null || true
fi

# Disable WiFi/Bluetooth
rfkill block wifi
rfkill block bluetooth

# Unbind/unload drivers for unused PCI devices so they can enter runtime suspend
# (Broadcom BCM4313 Wi-Fi, Intel HD Audio, Broadcom SD card reader)
if [ -e /sys/bus/pci/drivers/bcma-pci-bridge/0000:03:00.0 ]; then
  echo 0000:03:00.0 > /sys/bus/pci/drivers/bcma-pci-bridge/unbind 2>/dev/null || true
fi
for mod in brcmsmac bcma snd_hda_intel sdhci_pci; do
  if lsmod | grep -q "^${mod} "; then
    modprobe -r "$mod" 2>/dev/null || true
  fi
done
# Fallback if snd_hda_intel stayed loaded
if [ -w /sys/module/snd_hda_intel/parameters/power_save_controller ]; then
  echo Y > /sys/module/snd_hda_intel/parameters/power_save_controller 2>/dev/null || true
fi
# Ensure PCI runtime PM is auto after unbinding drivers
for dev in 0000:03:00.0 0000:00:1b.0 0000:02:00.1; do
  [ -w "/sys/bus/pci/devices/${dev}/power/control" ] && echo auto > "/sys/bus/pci/devices/${dev}/power/control" 2>/dev/null || true
done

# Optical drive (DVD) runtime PM
if [ -w /sys/block/sr0/device/power/control ]; then
  echo auto > /sys/block/sr0/device/power/control 2>/dev/null || true
fi

# Ethernet power settings
ethtool -s enp2s0f0 wol d

# PCIe ASPM (harmless fallback if BIOS/kernel allows runtime changes)
echo powersave > /sys/module/pcie_aspm/parameters/policy 2>/dev/null || true

# Lid switch behavior (ignore so closing the lid doesn't suspend/shutdown the server)
logind_changed=0
for setting in HandleLidSwitch HandleLidSwitchExternalPower HandleLidSwitchDocked; do
  if grep -q "^${setting}=ignore$" /etc/systemd/logind.conf 2>/dev/null; then
    continue
  elif grep -q "^${setting}=" /etc/systemd/logind.conf 2>/dev/null; then
    sed -i "s/^${setting}=.*/${setting}=ignore/" /etc/systemd/logind.conf
    logind_changed=1
  elif grep -q "^#${setting}=" /etc/systemd/logind.conf 2>/dev/null; then
    sed -i "s/^#${setting}=.*/${setting}=ignore/" /etc/systemd/logind.conf
    logind_changed=1
  else
    echo "${setting}=ignore" >> /etc/systemd/logind.conf
    logind_changed=1
  fi
done

if [ "$logind_changed" -eq 1 ]; then
  systemctl restart systemd-logind
fi

# Disable unused host services (no BT, no cellular modem, Wi-Fi unloaded)
for svc in bluetooth.service ModemManager.service wpa_supplicant.service; do
  systemctl disable --now "$svc" 2>/dev/null || true
  systemctl mask "$svc" 2>/dev/null || true
done
