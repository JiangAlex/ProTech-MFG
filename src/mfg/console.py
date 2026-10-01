"""Console adapter — serial/telnet connection for uboot interaction."""

import logging
import re
import time

import pexpect

log = logging.getLogger(__name__)

# ANSI/VT100 escape sequences: CSI (ESC[ ... final-byte) plus a few common
# non-CSI escapes. Used to clean colorized firmware output before logging /
# pattern matching.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]|\x1b[=>]")


class _SerialExpect:
    """Minimal pexpect-compatible wrapper over a pyserial object.

    Why: pyserial's RFC2217 client (``rfc2217://host:port``) is a socket-backed
    object with NO real ``fileno()``, so ``pexpect.fdpexpect.fdspawn`` cannot
    wrap it (raises ``io.UnsupportedOperation: fileno``). We only rely on a
    small pexpect surface (sendline / expect(pattern|list) / before / after),
    so we reimplement just that on top of pyserial read()/write(). This keeps
    RFC2217's per-connection baudrate negotiation (one ser2net port serving
    EAP111 @115200 and Pi7a @2000000) while preserving the Console interface.

    Bytes are decoded as UTF-8 with errors='replace' (the DUT emits non-UTF-8
    bytes during early boot), matching the picocom pexpect path's behavior.
    """

    def __init__(self, ser, logfile_read=None, timeout=30):
        self._ser = ser
        self._buf = ""            # decoded, not-yet-matched text
        self.before = ""
        self.after = ""
        self.timeout = timeout
        self.logfile_read = logfile_read

    def _read_some(self):
        """Read whatever bytes are pending; return decoded text ('' if none)."""
        try:
            n = self._ser.in_waiting
        except Exception:
            n = 0
        data = self._ser.read(n or 1)  # read(1) blocks up to serial timeout
        if not data:
            return ""
        text = data.decode("utf-8", errors="replace")
        # Strip ANSI escape sequences (the QCC74x firmware colorizes its prompt,
        # e.g. ESC[36m qcc74x /> ESC[0m). They are terminal display noise: our
        # expect() patterns are plain-text prompts, so removing the escapes
        # keeps matching intact while making the buffer/log readable.
        text = _ANSI_RE.sub("", text)
        if self.logfile_read is not None:
            try:
                self.logfile_read.write(text)
            except Exception:
                pass
        return text

    def sendline(self, s=""):
        self._ser.write((s + "\r\n").encode("utf-8", errors="replace"))
        try:
            self._ser.flush()
        except Exception:
            pass

    def sendcontrol(self, char):
        # Ctrl-<char>: map letter to control code (a->1, x->24, etc.)
        c = ord(char.lower()) - ord("a") + 1
        self._ser.write(bytes([c]))

    def expect(self, pattern, timeout=None):
        """Wait until one of ``pattern`` (str/regex or list) is found.

        Returns the matched index (pexpect semantics) and sets .before/.after.
        Raises pexpect.TIMEOUT on timeout so callers can treat it like pexpect.
        """
        if timeout is None:
            timeout = self.timeout
        patterns = pattern if isinstance(pattern, (list, tuple)) else [pattern]
        compiled = [re.compile(p, re.DOTALL) if isinstance(p, str) else p
                    for p in patterns]
        deadline = time.time() + timeout
        while True:
            for idx, rx in enumerate(compiled):
                m = rx.search(self._buf)
                if m:
                    self.before = self._buf[:m.start()]
                    self.after = self._buf[m.start():m.end()]
                    self._buf = self._buf[m.end():]
                    return idx
            if time.time() >= deadline:
                self.before = self._buf
                self.after = ""
                raise pexpect.TIMEOUT(
                    f"Timeout waiting for {patterns!r} after {timeout}s")
            chunk = self._read_some()
            if chunk:
                self._buf += chunk
            else:
                time.sleep(0.02)

    def close(self):
        try:
            self._ser.close()
        except Exception:
            pass


class Console:
    """Interact with DUT uboot/Linux via serial or telnet (ser2net)."""

    def __init__(self, config: dict):
        self.type = config.get("type", "serial")
        self.port = config.get("port", "/dev/ttyUSB0")
        self.baudrate = config.get("baudrate", 115200)
        self.prompt = config.get("prompt", "MT7981>")
        self._child = None
        self._serial = None  # pyserial rfc2217 object (telnet mode)

    def connect(self):
        """Establish serial or telnet connection.

        telnet mode: connect to ser2net via pyserial's RFC2217 client
        (rfc2217://host:port). RFC2217 negotiates the serial line settings
        (baudrate) with ser2net at connect time, so ONE ser2net port can serve
        DUTs with different baud rates (e.g. EAP111 115200, Pi7a 2000000) — the
        rate is taken from this testbed's ap.console.baudrate. Because the
        rfc2217 pyserial object has no real fileno(), it cannot be wrapped by
        pexpect.fdspawn; we use _SerialExpect (a small pexpect-compatible shim)
        instead. serial mode: direct picocom via pexpect.spawn as before.
        """
        if self.type == "telnet":
            import serial
            host, port = self.port.split(":")
            url = f"rfc2217://{host}:{port}"
            log.info(f"Console connect: {url} @ {self.baudrate} (rfc2217)")
            # timeout: per-read block cap; expect() enforces the real deadline.
            self._serial = serial.serial_for_url(
                url, baudrate=int(self.baudrate), timeout=0.1
            )
            self._child = _SerialExpect(self._serial,
                                        logfile_read=LogWriter(log), timeout=30)
        else:
            cmd = f"picocom -b {self.baudrate} {self.port} --noreset --noinit"
            log.info(f"Console connect: {cmd}")
            # codec_errors='replace': the DUT emits non-UTF-8 bytes during early
            # boot / power-on (e.g. 0xf1); without this, pexpect raises
            # UnicodeDecodeError and the console dies. Replace keeps the stream
            # alive (bad bytes -> U+FFFD), which is fine for pattern matching.
            self._child = pexpect.spawn(cmd, encoding="utf-8",
                                        codec_errors="replace", timeout=30)
            self._child.logfile_read = LogWriter(log)
        # Drain any stale data left in the buffer from a previous session
        # (e.g. a leftover partial command echoed by the device) so it does
        # not pollute the next expect().
        self.drain()
        # Send enter to get prompt
        self._child.sendline("")
        return self

    def drain(self, quiet=0.5):
        """Read and discard any pending output until the line goes quiet.

        Used to clear stale buffer content (old prompts, partial commands)
        before starting a fresh interaction. Non-fatal on error.
        """
        if not self._child:
            return
        try:
            while True:
                self._child.expect(r'.+', timeout=quiet)
        except Exception:
            # TIMEOUT/EOF => nothing more to read; buffer is drained.
            pass

    def send(self, cmd: str):
        """Send command without waiting."""
        log.info(f">>> {cmd}")
        self._child.sendline(cmd)

    def expect(self, pattern=None, timeout=30):
        """Wait for pattern. Returns matched output (before+after)."""
        pat = pattern or self.prompt
        self._child.expect(pat, timeout=timeout)
        return self._child.before + self._child.after

    def expect_index(self, patterns, timeout=30):
        """Wait for one of several patterns; return the matched INDEX.

        ``patterns`` is a list; the return value is the integer index of the
        pattern that matched (pexpect semantics). Use this for multi-way
        branching (e.g. login: password vs shell prompt), because expect()
        returns matched text and cannot be compared to an index.
        """
        return self._child.expect(patterns, timeout=timeout)

    def send_and_expect(self, cmd: str, pattern=None, timeout=30):
        """Send command and wait for expected pattern. Returns output."""
        self.send(cmd)
        return self.expect(pattern, timeout)

    def close(self):
        """Close connection."""
        if self._child:
            if self.type != "telnet":
                # picocom exit sequence (Ctrl-A Ctrl-X). Not applicable to the
                # rfc2217/fdspawn telnet path (would inject bytes to the DUT).
                try:
                    self._child.sendcontrol("a")
                    self._child.sendcontrol("x")
                except Exception:
                    pass
            try:
                self._child.close()
            except Exception:
                pass
            self._child = None
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        log.info("Console closed")

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()


class LogWriter:
    """Redirect pexpect output to logger."""

    def __init__(self, logger):
        self._log = logger

    def write(self, data):
        for line in data.strip().splitlines():
            if line.strip():
                self._log.debug(f"[console] {line}")

    def flush(self):
        pass
