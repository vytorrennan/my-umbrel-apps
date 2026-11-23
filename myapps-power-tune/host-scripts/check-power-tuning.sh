#!/bin/bash

GREEN="\e[32m"
YELLOW="\e[33m"
RED="\e[31m"
NC="\e[0m"

ok()    { echo -e "${GREEN}[ OK ]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

echo "===== Power Optimization Check ====="
echo

#
# CPU Governor
#
govs=$(cat /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor 2>/dev/null | sort -u | tr '\n' ' ' | sed 's/ $//')

if [[ "$govs" == "schedutil" ]]; then
    ok "CPU governor: $govs (all CPUs)"
else
    fail "CPU governor: ${govs:-unknown} (expected schedutil)"
fi

#
# CPU Max Frequency Limit
#
capped_cpus=0
for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
    smax=$(cat "$cpu/scaling_max_freq" 2>/dev/null)
    hwmax=$(cat "$cpu/cpuinfo_max_freq" 2>/dev/null)
    if [[ -n "$smax" && -n "$hwmax" && "$smax" -lt "$hwmax" ]]; then
        capped_cpus=$((capped_cpus + 1))
    fi
done

if [[ "$capped_cpus" -eq 0 ]]; then
    ok "CPU scaling_max_freq: uncapped on all CPUs"
else
    warn "CPU scaling_max_freq: $capped_cpus CPU(s) capped below hardware max"
fi

#
# Intel Turbo Boost
#
if [[ -r /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
    no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo)
    if [[ "$no_turbo" == "1" ]]; then
        ok "Intel Turbo Boost: disabled (no_turbo=1)"
    else
        warn "Intel Turbo Boost: enabled (no_turbo=$no_turbo)"
    fi
fi

#
# Display Backlight & DPMS
#
for bl in /sys/class/backlight/*; do
    [[ -d "$bl" ]] || continue
    bright=$(cat "$bl/brightness" 2>/dev/null)
    if [[ "$bright" == "0" ]]; then
        ok "Backlight ($(basename "$bl")): off (0)"
    else
        warn "Backlight ($(basename "$bl")): brightness=$bright"
    fi
done

if [[ -r /sys/class/drm/card0-LVDS-1/dpms ]]; then
    lvds_dpms=$(cat /sys/class/drm/card0-LVDS-1/dpms 2>/dev/null)
    if [[ "$lvds_dpms" == "Off" ]]; then
        ok "LVDS-1 display DPMS: Off"
    else
        warn "LVDS-1 display DPMS: $lvds_dpms"
    fi
fi

#
# Unused PCI Devices (Wi-Fi, Audio, SD Card Reader)
#
for entry in "0000:03:00.0|Wi-Fi (BCM4313)" "0000:00:1b.0|HD Audio" "0000:02:00.1|SD Card Reader"; do
    dev="${entry%%|*}"
    label="${entry#*|}"
    if [[ -r "/sys/bus/pci/devices/$dev/power/runtime_status" ]]; then
        rstat=$(cat "/sys/bus/pci/devices/$dev/power/runtime_status")
        if [[ "$rstat" == "suspended" ]]; then
            ok "PCI $label ($dev): suspended"
        else
            warn "PCI $label ($dev): $rstat"
        fi
    fi
done

#
# Optical Drive (sr0) Runtime PM
#
if [[ -r /sys/block/sr0/device/power/control ]]; then
    sr0_ctrl=$(cat /sys/block/sr0/device/power/control 2>/dev/null)
    sr0_stat=$(cat /sys/block/sr0/device/power/runtime_status 2>/dev/null)
    if [[ "$sr0_ctrl" == "auto" ]]; then
        ok "Optical drive (sr0) runtime PM: auto ($sr0_stat)"
    else
        warn "Optical drive (sr0) runtime PM: $sr0_ctrl ($sr0_stat)"
    fi
fi

#
# Unused Host Services
#
for svc in ModemManager.service wpa_supplicant.service; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        warn "Service $svc: running"
    else
        ok "Service $svc: stopped"
    fi
done

#
# SATA ALPM (check populated SATA ports; empty AHCI ports stay keep_firmware_settings)
#
sata_active=0
sata_low=0
for hostdir in /sys/class/scsi_host/host*; do
    policy="$hostdir/link_power_management_policy"
    [[ -r "$policy" ]] || continue
    # Only count hosts that have a target/device attached
    hostnum=$(basename "$hostdir" | sed 's/host//')
    if compgen -G "/sys/class/scsi_device/${hostnum}:*" >/dev/null; then
        sata_active=$((sata_active + 1))
        val=$(cat "$policy" 2>/dev/null)
        if [[ "$val" == "med_power_with_dipm" || "$val" == "min_power" ]]; then
            sata_low=$((sata_low + 1))
        fi
    fi
done
if [[ "$sata_active" -gt 0 ]]; then
    if [[ "$sata_low" -eq "$sata_active" ]]; then
        ok "SATA ALPM: low-power on all $sata_active populated port(s)"
    else
        warn "SATA ALPM: low-power on $sata_low/$sata_active populated port(s)"
    fi
fi

#
# PCIe ASPM
#
aspm_lines=$(lspci -vv 2>/dev/null | grep "LnkCtl:")

if [[ -z "$aspm_lines" ]]; then
    warn "PCIe ASPM: unable to read link states (needs root)"
else
    aspm_total=$(echo "$aspm_lines" | wc -l)
    aspm_disabled=$(echo "$aspm_lines" | grep -c "ASPM Disabled")
    aspm_enabled=$((aspm_total - aspm_disabled))

    if [[ "$aspm_disabled" -eq 0 ]]; then
        ok "PCIe ASPM: enabled on all $aspm_total link(s)"
    elif [[ "$aspm_enabled" -eq 0 ]]; then
        warn "PCIe ASPM: disabled on all $aspm_total link(s)"
    else
        warn "PCIe ASPM: enabled on $aspm_enabled/$aspm_total link(s)"
    fi
fi

#
# Wi-Fi
#
if command -v rfkill >/dev/null; then
    wifi_status=$(rfkill list wifi 2>/dev/null)
    if [[ -z "$wifi_status" ]] || ! echo "$wifi_status" | grep -q "Soft blocked: no"; then
        ok "Wi-Fi blocked/unloaded"
    else
        warn "Wi-Fi enabled"
    fi
fi

#
# Bluetooth
#
if command -v rfkill >/dev/null; then
    bt_status=$(rfkill list bluetooth 2>/dev/null)

    if [[ -z "$bt_status" ]]; then
        ok "No Bluetooth device present"
    elif echo "$bt_status" | grep -q "Soft blocked: yes"; then
        ok "Bluetooth blocked"
    else
        warn "Bluetooth enabled"
    fi
fi

#
# Powertop tunables
#
if command -v powertop >/dev/null; then
    echo
    echo "PowerTOP Tunables:"
    sudo powertop --time=1 --html=/tmp/powertop.html >/dev/null 2>&1
    echo "Generated: /tmp/powertop.html"
fi

#
# CPU Frequency (informational)
#
freq=$(awk '/cpu MHz/ {sum+=$4;n++} END{printf "%.0f",sum/n}' /proc/cpuinfo)
echo
ok "Current average CPU frequency: ${freq} MHz"

#
# Lid configuration
#
echo

for item in HandleLidSwitch HandleLidSwitchExternalPower HandleLidSwitchDocked
do
    if grep -q "^$item=ignore" /etc/systemd/logind.conf 2>/dev/null; then
        ok "$item=ignore"
    else
        warn "$item not configured"
    fi
done

#
# Current C-state residency
#
echo
if command -v turbostat >/dev/null; then
    echo "Current C-State summary:"
    sudo turbostat --quiet --show Busy%,Bzy_MHz,CPU%c1,CPU%c3,CPU%c6,CPU%c7,Pkg%pc2,Pkg%pc3,Pkg%pc6,Pkg%pc7,PkgWatt --interval 5 --num_iterations 1
fi

echo
echo "===== Finished ====="
