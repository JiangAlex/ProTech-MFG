#!/usr/bin/env bash
#
# install.sh — one-shot ProTech-MFG fixture setup for a Raspberry Pi 4
#              (Raspberry Pi OS 64-bit / arm64).
#
# What it does (idempotent — safe to re-run):
#   1. Install OS packages (python venv, ser2net, libusb for pyftdi).
#   2. Create the project venv and install Python deps (requirements.txt).
#   3. Install udev rules: FT232H GPIO release + stable /dev/mfg-* symlinks.
#   4. Write a VERSION file (git short hash if available) for OTA bookkeeping.
#   5. Install + enable the systemd service (GUI on :8020, auto-start on boot).
#
# It does NOT flash any DUT or assume specific hardware is attached; it only
# prepares this Pi4 to serve as a fixture host.
#
# Usage (run from the project root as the fixture user, NOT root):
#   bash deploy/install.sh
#
# The script re-invokes sudo only for the steps that need root (apt, udev,
# systemd). The venv and VERSION are created as the invoking user.

set -euo pipefail

# --- locate project root (parent of this deploy/ dir) --------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

RUN_USER="${SUDO_USER:-$(id -un)}"
VENV="${PROJECT_ROOT}/.venv"
PORT="${MFG_PORT:-8020}"
SERVICE_NAME="protech-mfg"

echo "==> ProTech-MFG fixture install"
echo "    project root : ${PROJECT_ROOT}"
echo "    run user     : ${RUN_USER}"
echo "    GUI port     : ${PORT}"

if [[ "${EUID}" -eq 0 ]]; then
    echo "ERROR: run as the fixture user (not root). The script sudo's where needed." >&2
    exit 1
fi

# --- 1) OS packages ------------------------------------------------------
echo "==> [1/5] Installing OS packages (apt)"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    ser2net \
    libusb-1.0-0 \
    git

# --- 2) venv + Python deps ----------------------------------------------
echo "==> [2/5] Creating venv + installing Python deps"
if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip -q
"${VENV}/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt" -q
echo "    venv ready: ${VENV}"

# --- 3) udev rules: FT232H GPIO + stable serial symlinks -----------------
echo "==> [3/5] Installing udev rules (FT232H GPIO release + /dev/mfg-* names)"
# FT232H: unbind ftdi_sio so pyftdi can drive the power relay.
sudo bash "${PROJECT_ROOT}/tools/setup_ft232h_gpio.sh"
# Stable device symlinks (DUT console -> /dev/mfg-console, FT232H -> /dev/mfg-power).
sudo cp "${PROJECT_ROOT}/config/console/99-mfg-serial.rules" \
        /etc/udev/rules.d/99-mfg-serial.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
# Ensure the fixture user can access libusb devices (plugdev) for pyftdi.
sudo usermod -aG plugdev "${RUN_USER}" || true

# --- 4) VERSION file (OTA bookkeeping) -----------------------------------
echo "==> [4/5] Writing VERSION"
if git -C "${PROJECT_ROOT}" rev-parse --short HEAD >/dev/null 2>&1; then
    VER="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
else
    VER="unknown-$(date +%Y%m%d)"
fi
echo "${VER}" > "${PROJECT_ROOT}/VERSION"
echo "    VERSION = ${VER}"

# --- 5) systemd service --------------------------------------------------
echo "==> [5/5] Installing systemd service: ${SERVICE_NAME}"
TMP_UNIT="$(mktemp)"
sed -e "s|@PROJECT_ROOT@|${PROJECT_ROOT}|g" \
    -e "s|@RUN_USER@|${RUN_USER}|g" \
    -e "s|@PORT@|${PORT}|g" \
    "${PROJECT_ROOT}/deploy/${SERVICE_NAME}.service" > "${TMP_UNIT}"
sudo cp "${TMP_UNIT}" "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "${TMP_UNIT}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo
echo "==> Done. Service '${SERVICE_NAME}' enabled and started."
echo "    Status : sudo systemctl status ${SERVICE_NAME}"
echo "    Logs   : journalctl -u ${SERVICE_NAME} -f"
echo "    GUI    : http://$(hostname -I | awk '{print $1}'):${PORT}"
echo
echo "    NOTE: you were added to the 'plugdev' group for FT232H access."
echo "          If pyftdi can't open the device, log out/in (or reboot) once."
