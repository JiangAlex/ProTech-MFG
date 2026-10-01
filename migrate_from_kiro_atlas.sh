#!/usr/bin/env bash
#
# migrate_from_kiro_atlas.sh — copy UNCHANGED files from kiro-ATLAS into
# this ProTech-MFG repo. Files that were modified for pure-MFG are written
# by Kiro directly (do NOT copy those from kiro-ATLAS):
#   Kiro-written (pure MFG): src/web/app.py, src/web/runner.py,
#     src/mfg/__init__.py, src/mfg/console.py, src/mfg/device_profile.py
#   Kiro-written (pure MFG frontend, pending): src/web/static/blocks.js,
#     generators.js, index.html
#
# Run from the ProTech-MFG repo root:  bash migrate_from_kiro_atlas.sh
set -euo pipefail
SRC="${1:-$HOME/projects/kiro-ATLAS}"
echo "Copying UNCHANGED files from $SRC"

mkdir -p src/mfg src/web/static scripts/MFG config/test_node config/profiles \
         config/console tools docs/logfiles tftp

# --- Backend (unchanged) ---
cp "$SRC/src/mfg/power_controller.py"     src/mfg/
cp "$SRC/src/mfg/manufacturing_script.py" src/mfg/

# --- GUI unchanged Python ---
cp "$SRC/src/web/models.py"          src/web/
cp "$SRC/src/web/db.py"              src/web/
cp "$SRC/src/web/script_parser.py"   src/web/
cp "$SRC/src/web/console_stream.py"  src/web/
cp "$SRC/src/web/scheduler.py"       src/web/
cp "$SRC/src/web/static/style.css"   src/web/static/
# DO NOT copy: device_monitor.py, static/{plan,dashboard,editor,console}.html,
#              static/topology.js  (Switch/AP — not used by pure MFG)

# --- MFG scripts (into scripts/MFG; skip old generated/) ---
cp -r "$SRC/scripts/MFG/"* scripts/MFG/ 2>/dev/null || true
mkdir -p scripts/MFG/generated   # GUI writes generated .py here now

# --- Config: MFG testbeds + profiles + ser2net console cfg ---
for f in eap111_testbed oap101_testbed pi7a_testbed; do
  cp "$SRC/config/test_node/$f.yaml" config/test_node/ 2>/dev/null || true
done
for f in EAP111 OAP101 Pi7a; do
  cp "$SRC/config/profiles/$f.yaml" config/profiles/ 2>/dev/null || true
done
cp -r "$SRC/config/console/"* config/console/ 2>/dev/null || true

# --- Tools ---
cp "$SRC/tools/setup_ft232h_gpio.sh"    tools/ 2>/dev/null || true
cp "$SRC/tools/ft232h_polarity_test.py" tools/ 2>/dev/null || true

touch tftp/.gitkeep

echo "Done copying unchanged files."
echo "Still needed (see docs/kiro-memory.md):"
echo "  - src/web/static/{blocks.js,generators.js,index.html}  (pure-MFG, Kiro to write)"
echo "  - conftest.py, pytest.ini, requirements.txt, .gitignore"
echo "  - IMPORTANT: MFG scripts still import generated into scripts/MFG/generated;"
echo "    generated .py files import 'from mfg.manufacturing_script import ...'."
