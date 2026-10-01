#!/usr/bin/env bash
# Copy the two static JS files verbatim (blocks.js, generators.js).
# index.html is written separately by Kiro as a pure-MFG version.
set -euo pipefail
SRC="${1:-$HOME/projects/kiro-ATLAS}"
mkdir -p src/web/static
cp "$SRC/src/web/static/blocks.js"     src/web/static/
cp "$SRC/src/web/static/generators.js" src/web/static/
echo "Copied blocks.js + generators.js. index.html is provided by Kiro (pure MFG)."
