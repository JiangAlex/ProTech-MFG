"""Live console log streaming for the WLAN Test GUI.

Tails the ser2net `trace-read` log file (the physical DUT console output) and
pushes new content to WebSocket clients. This is strictly READ-ONLY: it never
opens the serial device nor sends any keystroke, so it cannot interfere with a
running test session that is attached to ser2net (127.0.0.1:5001).

The trace log path is configured in config/console/ser2net.yaml as:
    trace-read: /var/log/ser2net/ttyUSB0.log
A fixed filename is used (ser2net date escapes are not zero-padded); rotate
with logrotate if needed.
"""
import asyncio
import os
import re
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

# ANSI/VT100 escape sequences emitted by the DUT firmware (the QCC74x colorizes
# its prompt and even echoes each typed char wrapped in ESC[0m). Strip them so
# the GUI live console shows clean text instead of "␛[0m" noise. Mirrors the
# filter in src/mfg/console.py (_ANSI_RE). Plain-text only; keeps newlines.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]|\x1b[=>]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

# Directory + filename pattern must match config/console/ser2net.yaml (trace-read).
CONSOLE_LOG_DIR = Path(os.environ.get("ATLAS_CONSOLE_LOG_DIR", "/var/log/ser2net"))
CONSOLE_LOG_PREFIX = os.environ.get("ATLAS_CONSOLE_LOG_PREFIX", "ttyUSB0")

# ser2net endpoint that the keepalive connection attaches to. Opening this
# connection makes ser2net open the serial device, which activates `trace-read`
# so the log file exists even before any test runs.
SER2NET_HOST = os.environ.get("ATLAS_SER2NET_HOST", "127.0.0.1")
SER2NET_PORT = int(os.environ.get("ATLAS_SER2NET_PORT", "5001"))
# Set ATLAS_CONSOLE_KEEPALIVE=0 to disable (e.g. in tests / no ser2net).
KEEPALIVE_ENABLED = os.environ.get("ATLAS_CONSOLE_KEEPALIVE", "1") != "0"

# How many bytes from the end of the file to send as initial backlog.
_TAIL_BACKLOG_BYTES = 16 * 1024
# Poll interval when waiting for new data / file rotation (seconds).
_POLL_INTERVAL = 0.5
# Reconnect delay for the keepalive connection (seconds).
_KEEPALIVE_RETRY = 5.0


def _fixed_log_path() -> Path:
    """Primary log path: fixed filename written by ser2net trace-read."""
    return CONSOLE_LOG_DIR / f"{CONSOLE_LOG_PREFIX}.log"


def latest_log_path() -> Path | None:
    """Return the fixed log if present, else the most recently modified match.

    Prefers the fixed `<prefix>.log` written by ser2net. Falls back to a glob
    (`<prefix>*.log`) so rotated files (e.g. logrotate `.log.1`) or legacy
    date-suffixed files are still picked up.
    """
    fixed = _fixed_log_path()
    if fixed.exists():
        return fixed
    if not CONSOLE_LOG_DIR.is_dir():
        return None
    candidates = sorted(
        CONSOLE_LOG_DIR.glob(f"{CONSOLE_LOG_PREFIX}*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


async def ws_console_handler(websocket: WebSocket):
    """Stream the ser2net trace log to a WebSocket client (read-only tail -f).

    Handles three edge cases:
      * log file does not exist yet (ser2net not started / no output today)
      * daily file rotation (date rolls over -> switch to the new file)
      * file truncation/rotation (inode/size shrinks -> reopen from start)
    """
    await websocket.accept()

    async def send(msg: str) -> bool:
        try:
            await websocket.send_text(msg)
            return True
        except Exception:
            return False

    # Announce which file we are watching (or that we are waiting for one).
    path = latest_log_path()
    if path is None:
        await send(
            f"[console] waiting for log in {CONSOLE_LOG_DIR}/ "
            f"{CONSOLE_LOG_PREFIX}*.log — is ser2net running?\n"
        )

    fh = None
    cur_path: Path | None = None
    last_ino = None

    async def _keepalive():
        """Drain incoming frames so the socket stays open; ignore client input."""
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass

    ka_task = asyncio.create_task(_keepalive())

    try:
        while True:
            target = latest_log_path() or _fixed_log_path()

            # (Re)open when the target file changes or first becomes available.
            if fh is None or target != cur_path:
                if not target.exists():
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                if fh:
                    fh.close()
                    fh = None
                try:
                    fh = open(target, "r", encoding="utf-8", errors="replace")
                except PermissionError:
                    await send(
                        f"[console] permission denied reading {target} — "
                        f"the log is not readable by this user. Fix with e.g. "
                        f"'sudo chgrp adm {target} && sudo chmod 640 {target}' "
                        f"(this user is in the 'adm' group), then reconnect.\n"
                    )
                    break
                except OSError as e:
                    await send(f"[console] cannot open {target}: {e}\n")
                    break
                cur_path = target
                last_ino = os.fstat(fh.fileno()).st_ino
                # Seek to show a bounded backlog rather than the whole file.
                size = fh.seek(0, os.SEEK_END)
                fh.seek(max(0, size - _TAIL_BACKLOG_BYTES))
                if size > 0:
                    backlog = fh.read()
                    # Drop a possibly partial first line from the backlog window.
                    if size > _TAIL_BACKLOG_BYTES and "\n" in backlog:
                        backlog = backlog.split("\n", 1)[1]
                    if backlog and not await send(_strip_ansi(backlog)):
                        break
                await send(f"\n[console] --- tailing {cur_path.name} ---\n")

            # Detect rotation/truncation of the current file.
            try:
                st = os.stat(cur_path)
                if st.st_ino != last_ino or st.st_size < fh.tell():
                    fh.close()
                    fh = None
                    continue
            except FileNotFoundError:
                fh.close()
                fh = None
                continue

            chunk = fh.read()
            if chunk:
                if not await send(_strip_ansi(chunk)):
                    break
            else:
                await asyncio.sleep(_POLL_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        ka_task.cancel()
        if fh:
            fh.close()


async def console_keepalive():
    """Maintain a read-only connection to ser2net so trace-read stays active.

    Opening a connection to ser2net (127.0.0.1:5001) causes it to open the
    serial device, which activates the `trace-read` log file. Without any
    client attached, the log file is never created and the GUI would show
    "waiting for log" forever.

    This task is strictly READ-ONLY: it drains and discards incoming bytes
    (including telnet negotiation) and NEVER writes to the connection, so it
    cannot inject keystrokes into the DUT console or disturb a running test.
    It occupies one of ser2net's `max-connections` slots. Reconnects forever
    with a backoff until the app shuts down (task cancellation).
    """
    if not KEEPALIVE_ENABLED:
        return

    while True:
        writer = None
        try:
            reader, writer = await asyncio.open_connection(SER2NET_HOST, SER2NET_PORT)
            # Read-only: continuously drain and discard. Do NOT write anything.
            while True:
                data = await reader.read(4096)
                if not data:  # ser2net closed the connection (EOF)
                    break
        except asyncio.CancelledError:
            # App shutdown: close cleanly and stop.
            if writer is not None:
                writer.close()
            raise
        except Exception:
            # ser2net not up yet / connection dropped: retry after a delay.
            pass
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

        try:
            await asyncio.sleep(_KEEPALIVE_RETRY)
        except asyncio.CancelledError:
            raise
