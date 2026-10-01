#!/usr/bin/env bash
#
# setup_ft232h_gpio.sh
#
# Purpose:
#   Make the FT232H (VID:PID 0403:6014) usable for GPIO/MPSSE via pyftdi/libusb
#   by permanently preventing the kernel ftdi_sio (UART) driver from claiming it.
#
#   The kernel ftdi_sio driver binds FT232H as a serial /dev/ttyUSBx by default.
#   That is mutually exclusive with pyftdi's GPIO mode: while ftdi_sio holds the
#   chip, pyftdi cannot drive the pins (pins float at ~1-2.3V, relays won't switch).
#
#   This script installs a udev rule that:
#     1. Grants libusb access (MODE=0666, GROUP=plugdev) to 0403:6014.
#     2. Automatically unbinds ftdi_sio whenever this FT232H is added, so the
#        chip is always free for pyftdi -- survives replug and reboot.
#   It also immediately unbinds any currently-bound FT232H interface so you
#   don't have to replug right now.
#
# Usage:
#   sudo ./tools/setup_ft232h_gpio.sh
#
# Idempotent: safe to run multiple times.

set -euo pipefail

VID="0403"
PID="6014"
RULE_FILE="/etc/udev/rules.d/99-ft232h-gpio.rules"
OLD_RULE_FILE="/etc/udev/rules.d/11-ftdi-ft232h.rules"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use: sudo $0)" >&2
    exit 1
fi

echo "==> Installing udev rule: ${RULE_FILE}"
cat > "${RULE_FILE}" <<RULE
# FT232H (${VID}:${PID}) for pyftdi GPIO/MPSSE.
# Grant libusb access to non-root users in the plugdev group.
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="${VID}", ATTR{idProduct}=="${PID}", MODE="0666", GROUP="plugdev"
# Auto-unbind the kernel ftdi_sio UART driver so pyftdi can own the chip.
ACTION=="add", SUBSYSTEM=="usb", DRIVERS=="ftdi_sio", ATTRS{idVendor}=="${VID}", ATTRS{idProduct}=="${PID}", RUN+="/bin/sh -c 'echo \$kernel > /sys/bus/usb/drivers/ftdi_sio/unbind'"
RULE

# Remove the older permission-only rule to avoid confusion / duplication.
if [[ -f "${OLD_RULE_FILE}" ]]; then
    echo "==> Removing obsolete rule: ${OLD_RULE_FILE}"
    rm -f "${OLD_RULE_FILE}"
fi

echo "==> Reloading udev rules"
udevadm control --reload-rules
udevadm trigger

# Immediately release any currently-bound FT232H interface(s).
DRV_DIR="/sys/bus/usb/drivers/ftdi_sio"
echo "==> Unbinding any currently-bound FT232H interface(s)"
unbound_any=0
if [[ -d "${DRV_DIR}" ]]; then
    for iface in "${DRV_DIR}"/*:*; do
        [[ -e "${iface}" ]] || continue
        ifname="$(basename "${iface}")"
        # Confirm this interface belongs to our FT232H by checking its device idVendor/idProduct.
        devpath="${iface%:*}"          # strip ":1.0" -> USB device path
        vid_file="${devpath}/idVendor"
        pid_file="${devpath}/idProduct"
        if [[ -r "${vid_file}" && -r "${pid_file}" ]]; then
            dev_vid="$(cat "${vid_file}")"
            dev_pid="$(cat "${pid_file}")"
            if [[ "${dev_vid}" == "${VID}" && "${dev_pid}" == "${PID}" ]]; then
                echo "    unbinding ${ifname}"
                echo "${ifname}" > "${DRV_DIR}/unbind" || true
                unbound_any=1
            fi
        else
            # Fallback: unbind regardless (only reached if idVendor unreadable).
            echo "    unbinding ${ifname} (vendor unverified)"
            echo "${ifname}" > "${DRV_DIR}/unbind" || true
            unbound_any=1
        fi
    done
fi
[[ "${unbound_any}" -eq 0 ]] && echo "    (nothing bound -- already free)"

# Verify result.
echo
echo "==> Verification"
if ls "${DRV_DIR}"/*:* >/dev/null 2>&1; then
    still="$(ls "${DRV_DIR}" | grep -E '^[0-9]' || true)"
    if [[ -n "${still}" ]]; then
        echo "    WARNING: ftdi_sio still has bound interfaces: ${still}" >&2
    fi
else
    echo "    ftdi_sio: no bound interfaces (good)"
fi
if ls /dev/ttyUSB* >/dev/null 2>&1; then
    echo "    NOTE: /dev/ttyUSB* still present:"
    ls -l /dev/ttyUSB* 2>/dev/null | sed 's/^/      /'
    echo "    (If one of these was the FT232H it should now be gone; ttyUSB for other"
    echo "     serial devices is fine.)"
else
    echo "    /dev/ttyUSB*: none (FT232H released)"
fi

echo
echo "==> Done. FT232H should now be controllable by pyftdi."
echo "    Verify with:"
echo "      ~/projects/kiro-ATLAS/.venv/bin/python3 -c \"from pyftdi.gpio import GpioController as G; g=G(); g.configure('ftdi://ftdi:232h/1', direction=0x03); g.write(0x00); print('readback', hex(g.read())); g.close()\""
echo "    Expect readback = 0xfc (low 2 bits driven low). If 0xff/floating, re-run this script."
