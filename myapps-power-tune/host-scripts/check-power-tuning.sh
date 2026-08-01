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
gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)

if [[ "$gov" == "powersave" ]]; then
    ok "CPU governor: $gov"
else
    fail "CPU governor: $gov"
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
    if rfkill list wifi 2>/dev/null | grep -q "Soft blocked: yes"; then
        ok "Wi-Fi blocked"
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
# CPU Frequency
#
freq=$(awk '/cpu MHz/ {sum+=$4;n++} END{printf "%.0f",sum/n}' /proc/cpuinfo)

echo

if [[ "$freq" -lt 1500 ]]; then
    ok "Average CPU frequency: ${freq} MHz"
else
    warn "Average CPU frequency: ${freq} MHz"
fi

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
    sudo turbostat --quiet --show CPU%c1,CPU%c3,CPU%c6,CPU%c7,PkgWatt --interval 5 --num_iterations 1
fi

echo
echo "===== Finished ====="
