#!/usr/bin/env bash
# Verify the ser2net console server (方案 B) is reachable and responsive.
#
#   ./config/console/verify_console.sh [host] [port] [prompt]
#
# Defaults: 127.0.0.1 5001 "MT7981>"
set -u

HOST="${1:-127.0.0.1}"
PORT="${2:-5001}"
PROMPT="${3:-MT7981>}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "== 1. ser2net service =="
if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active --quiet ser2net \
        && echo "  ser2net active" \
        || echo "  WARN: ser2net not active (systemctl is-active ser2net)"
fi

echo "== 2. TCP port ${HOST}:${PORT} =="
# Prefer bash /dev/tcp; fall back to nc.
if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
    exec 3>&- 3<&-
    echo "  TCP ${HOST}:${PORT} open"
elif command -v nc >/dev/null 2>&1 && nc -z -w2 "${HOST}" "${PORT}"; then
    echo "  TCP ${HOST}:${PORT} open (nc)"
else
    fail "cannot connect to ${HOST}:${PORT} — is ser2net running? (sudo systemctl status ser2net)"
fi

echo "== 3. Console prompt check =="
# Use pexpect (already a project dependency) to send Enter and look for prompt.
python3 - "$HOST" "$PORT" "$PROMPT" <<'PY'
import sys
try:
    import pexpect
except ImportError:
    print("  SKIP: pexpect not installed (pip install pexpect); TCP check already passed")
    sys.exit(0)

host, port, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
child = pexpect.spawn(f"telnet {host} {port}", encoding="utf-8", timeout=8)
child.sendline("")
idx = child.expect([prompt, pexpect.TIMEOUT, pexpect.EOF])
if idx == 0:
    print(f"  OK: got prompt {prompt!r}")
    sys.exit(0)
else:
    print(f"  WARN: no {prompt!r} within timeout. DUT may be powered off "
          f"or not at U-Boot. TCP path itself is OK.")
    sys.exit(0)
PY

echo "DONE: console server reachable at ${HOST}:${PORT}"
