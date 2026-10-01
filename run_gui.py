#!/usr/bin/env python3
"""Launch the ProTech-MFG GUI from the project root.

Usage:
    python run_gui.py [port]      # default port 8020

Handles sys.path so app.py's implicit imports (db / models / runner) and the
`mfg` package both resolve, without needing to `cd src/web` first.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
WEB = SRC / "web"

# src/ for `import mfg`; src/web/ for app.py's `import db` / `from models ...`.
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(WEB))

import uvicorn
from app import app  # noqa: E402  (path set above)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8020
    uvicorn.run(app, host="0.0.0.0", port=port)
