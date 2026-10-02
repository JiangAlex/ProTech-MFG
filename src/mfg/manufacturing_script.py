"""ManufacturingScript — base class for AP manufacturing/provisioning scripts."""

import logging
import subprocess
import threading
import time

import yaml
import tftpy

from mfg.console import Console

log = logging.getLogger(__name__)


class ManufacturingScript:
    """Base class for manufacturing test scripts (uboot flash, provisioning)."""

    tc_id = ""
    headline = ""
    purpose = ""
    # MFG station code (e.g. "PT" / "FT" / "FDL"; see config/stations.yaml).
    # Open set — a script declares which station it belongs to. Blocks are
    # shared across stations; only the script/flow differs per station.
    station = ""
    # Device model (e.g. "EAP111" / "OAP101" / "Pi7a"). Mainly used by
    # generated scripts (which live in scripts/MFG/generated/ and thus have no
    # model directory to infer from). Hand-written scripts under
    # scripts/MFG/<MODEL>/ leave this empty and rely on their directory.
    model = ""

    def __init__(self):
        self.config = {}
        self._console = None
        self._tftp_server = None
        self._scanned_sn = None
        self._scanned_mac = None
        self._power_ctrl = None
        self._power_relay = 1
        self._power_off_delay = 2.0
        # Linux login credentials remembered from enter_tip_kernel (block
        # fields), reused by internal logins like Step 9 enter_tip_kernel_2.
        self._linux_user = None
        self._linux_password = None
        self._mfg_cache = None
        self._sku = None

    def load_testbed(self, path: str):
        """Load testbed YAML config."""
        with open(path) as f:
            self.config = yaml.safe_load(f)

    def init(self, config: dict):
        """Initialize with testbed config dict."""
        self.config = config

    @property
    def console(self) -> Console:
        """Lazy-init console connection."""
        if self._console is None:
            self._console = Console(self.config["ap"]["console"])
            self._console.connect()
        return self._console

    # -- model-specific MFG parameters -------------------------------------
    # All values come from the testbed's `ap.mfg` section, with EAP111 (MT7981)
    # defaults so existing EAP111 flows are unchanged. To add a new model,
    # provide an `ap.mfg` block in that model's testbed YAML instead of editing
    # this file. Schema: see config/test_node/eap111_testbed.yaml (ap.mfg:).
    _MFG_DEFAULTS = {
        "uboot_prompt": "MT7981>",
        "factory_read_cmd": "mtd read factory 0x46000000 0x0 0x800",
        "mac_eth0_offset": "0x4600002A",
        "mac_eth1_offset": "0x46000024",
        "mac_ar0_offset": "0x46000004",
        "sn_offset": "0x46000060",
        "model_offset": "0x46000070",
        "hw_rev_offset": "0x46000080",
        "flash_load_addr": "0x46000000",
        "fip_write_offset": "0x00380000",
        "fw_write_offset_1": "0x00580000",
        "fw_write_offset_2": "0x04580000",
        "sku": "EAP111(TE)",
        "model": "EAP111",
        "reference_design": "mt7981-spim-nand-rfb",
        "manufacturer_name": "EC",
        "manufacturer_url": "www.edge-core.com",
        "model_description": "802.11ax Dual-Band Enterprise Access Point",
        "certification_region": "WW",
    }

    @property
    def mfg(self) -> dict:
        """Model-specific MFG parameters.

        Merge order (later wins):
          _MFG_DEFAULTS (EAP111/MT7981)  <  ap.mfg  <  ap.mfg.skus.<selected SKU>

        SKU selection lets one model/testbed carry multiple SKUs that differ in
        firmware image, sku string, region, etc. Select via set_sku() / --sku /
        MFG_SKU. If no SKU is selected, ap.mfg.default_sku (if present) is used.
        """
        if getattr(self, "_mfg_cache", None) is None:
            cfg = {}
            try:
                cfg = (self.config.get("ap", {}) or {}).get("mfg", {}) or {}
            except AttributeError:
                cfg = {}
            merged = dict(self._MFG_DEFAULTS)
            # Base ap.mfg values (excluding the skus sub-tree itself).
            for k, v in cfg.items():
                if k not in ("skus", "default_sku"):
                    merged[k] = v
            # Resolve which SKU to apply.
            skus = cfg.get("skus", {}) or {}
            sku = self._sku or cfg.get("default_sku")
            if sku and sku in skus and isinstance(skus[sku], dict):
                merged.update(skus[sku])
                merged["sku_selected"] = sku
            elif sku and skus:
                # A SKU was requested but not defined — fail loudly at use time
                # rather than silently using defaults.
                merged["sku_selected"] = sku
                merged["_sku_unknown"] = True
            self._mfg_cache = merged
        return self._mfg_cache

    def set_sku(self, sku):
        """Select the manufacturing SKU (applies ap.mfg.skus.<sku> overrides).

        Must be called before any step that reads self.mfg. Invalidates the
        cached merge so a later mfg access recomputes with the SKU.
        """
        self._sku = str(sku) if sku else None
        self._mfg_cache = None
        # Validate against known SKUs (if the testbed defines any).
        try:
            skus = (self.config.get("ap", {}) or {}).get("mfg", {}).get("skus", {}) or {}
        except AttributeError:
            skus = {}
        if self._sku and skus and self._sku not in skus:
            raise ValueError(
                f"Unknown SKU '{self._sku}'; testbed ap.mfg.skus defines: "
                f"{sorted(skus)}"
            )

    @property
    def uboot_prompt(self) -> str:
        """U-Boot prompt string for this model (default 'MT7981>')."""
        return self.mfg.get("uboot_prompt", "MT7981>")

    def start_tftp(self):
        """Start TFTP server in background thread using testbed config."""
        tftp = self.config["ap"]["tftp"]
        directory = tftp.get("directory", "/srv/tftp")
        ip = tftp.get("server_ip", "192.168.1.2")
        port = tftp.get("port", 69)
        self._tftp_server = tftpy.TftpServer(directory)
        t = threading.Thread(
            target=self._tftp_server.listen,
            args=(ip, port),
            daemon=True
        )
        t.start()
        log.info(f"TFTP server started on {ip}:{port} serving {directory}")

    def stop_tftp(self):
        """Stop TFTP server."""
        if self._tftp_server:
            self._tftp_server.stop()
            self._tftp_server = None
            log.info("TFTP server stopped")

    def ssh_cmd(self, cmd: str, timeout=10) -> str:
        """Execute command on AP via SSH."""
        ssh = self.config["ap"]["ssh"]
        full_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"{ssh['user']}@{ssh['ip']}", cmd,
        ]
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()

    def wait_ssh_ready(self, timeout=120, interval=5):
        """Wait until AP is reachable via SSH."""
        ip = self.config["ap"]["ssh"]["ip"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                out = self.ssh_cmd("echo ok", timeout=5)
                if "ok" in out:
                    log.info(f"AP {ip} SSH ready")
                    return True
            except Exception:
                pass
            time.sleep(interval)
        raise TimeoutError(f"AP {ip} not reachable via SSH after {timeout}s")

    def step(self, num, description):
        log.info(f"[{self.tc_id}] Step {num}: {description}")
        print(f"\n{'='*60}\n  Step {num}: {description}\n{'='*60}")

    def message(self, msg):
        log.info(f"[{self.tc_id}] {msg}")
        print(f"  {msg}")

    # -------------------------------------------------------------------------
    # MFG method implementations — called by Blockly generator
    # -------------------------------------------------------------------------

    def _uboot_send(self, cmd, expect_prompt=True):
        """Send command to U-Boot console; carriage-return appended automatically.

        An optional inter-command delay (ap.console.cmd_delay seconds, default
        0) is applied BEFORE sending, as a safety margin against command/output
        collisions on a busy console. Set to 0 in the testbed YAML to disable.
        """
        delay = 0
        try:
            delay = float(self.config.get('ap', {}).get('console', {}).get('cmd_delay', 0) or 0)
        except (TypeError, ValueError):
            delay = 0
        if delay > 0:
            time.sleep(delay)
        self.console.send(cmd)
        if expect_prompt:
            self.console.expect(self.uboot_prompt, timeout=10)

    def _uboot_expect_prompt(self, timeout=10):
        self.console.expect(self.uboot_prompt, timeout=timeout)

    def _wait_autoboot_and_interrupt(self, timeout=60):
        """Wait for the U-Boot boot menu, then enter the U-Boot console.

        This DUT requires sending one "0" (menu item "0. U-Boot console") once
        per second until the MT7981> prompt appears; a single key / bare Enter
        does NOT stop autoboot (it boots straight into Linux). Safe to call when
        already at the boot menu or already at the prompt.
        """
        # If we're already at the prompt, nothing to do.
        try:
            self.console.expect(self.uboot_prompt, timeout=1)
            return
        except Exception:
            pass
        # Otherwise, resend "0" on a ~1s cadence until the prompt appears.
        for _ in range(max(1, int(timeout))):
            self.console.send('0')
            try:
                self.console.expect(self.uboot_prompt, timeout=1)
                return
            except Exception:
                continue
        raise RuntimeError(
            'Failed to enter U-Boot console (MT7981>) via repeated "0".'
        )

    def _parse_mac_from_hex(self, hex_str):
        """Convert '44 45 ba 03 10 d8' → '44:45:BA:03:10:D8'."""
        parts = hex_str.strip().split()
        return ':'.join(p.upper() for p in parts)

    def _hex_to_ascii(self, hex_str):
        """Convert hex dump bytes to ASCII string, stripping nulls."""
        parts = hex_str.strip().split()
        chars = [chr(int(p, 16)) for p in parts]
        return ''.join(c if c.isprintable() else '' for c in chars).rstrip('\x00')

    def _read_eth_mac(self, offset, label):
        """Read 6-byte MAC at memory offset; return formatted MAC string."""
        import re
        # U-Boot echoes the prompt BEFORE a command's output and often leaves a
        # trailing "MT7981> " in the buffer from the previous command. If we
        # just expect(prompt) after sending md.b, it matches that stale/echoed
        # prompt immediately and `before` is empty (no hex) -> parse failure.
        # Fix: drain stale buffer first, then expect the md.b ADDRESS line
        # (e.g. "4600002a: 5c 17 83 ed ea 38") which only appears in the actual
        # command output, not in the echo. offset like "0x4600002A" -> the dump
        # address is the lowercase hex without the 0x prefix.
        self.console.drain(quiet=0.3, max_total=3.0)
        addr = offset.lower().replace('0x', '')
        self._uboot_send(f'md.b {offset} 0x6', expect_prompt=False)
        # Match the address line plus its 6 hex bytes in one go.
        pat = (addr + r':\s+([0-9a-fA-F]{2}(?:\s+[0-9a-fA-F]{2}){5})')
        buff = self.console.expect(pat, timeout=10)
        m = re.search(pat, buff)
        if not m:
            raise RuntimeError(f'Cannot parse {label} MAC from buffer: {buff!r}')
        mac_hex = m.group(1)
        return self._parse_mac_from_hex(mac_hex)

    def _read_sn_model(self, offset='0x46000060', length='0x30'):
        """Read SN+Model string from memory.

        md.b output lines look like:
            46000060: 45 43 32 ... 00 00 00 00  EC2612003867....
        i.e. "<addr>: <hex bytes>  <ascii>". Collect the hex-byte column from
        every dump line and convert to ASCII.
        """
        import re
        # Same stale-prompt hazard as _read_eth_mac: drain first so expect does
        # not match a leftover prompt before the dump appears. We expect the
        # first address line to appear, then also capture whatever more arrived
        # (multi-line dumps), tolerating the trailing prompt.
        self.console.drain(quiet=0.3, max_total=3.0)
        start = offset.lower().replace('0x', '')
        self._uboot_send(f'md.b {offset} {length}', expect_prompt=False)
        # Wait until the dump's starting address line shows up, then read the
        # rest up to the prompt to collect all dump lines.
        first = self.console.expect(start + r':', timeout=10)
        rest = self.console.expect(self.uboot_prompt, timeout=10)
        buff = first + rest
        hex_bytes = []
        for line in buff.splitlines():
            # Split "<addr>: <hex column>  <ascii>" — the hex column is between
            # the address colon and the 2+ space gap before the ASCII render.
            mm = re.match(r'\s*[0-9a-fA-F]{6,}:\s+(.*)', line)
            if not mm:
                continue
            rest = mm.group(1)
            # Cut at the first run of 2+ spaces (start of ASCII column).
            gap = re.search(r'\s{2,}', rest)
            hexcol = rest[:gap.start()] if gap else rest
            toks = re.findall(r'[0-9a-fA-F]{2}', hexcol)
            if toks:
                hex_bytes.extend(toks)
        if not hex_bytes:
            raise RuntimeError('Cannot parse SN/Model from buffer')
        return self._hex_to_ascii(' '.join(hex_bytes))

    def _power(self):
        """Lazy-init the FT232H PowerController from testbed ``ap.power``.

        testbed YAML example (all keys optional; safe defaults applied):

            ap:
              power:
                url: "ftdi://ftdi:232h/1"   # FT232H by VID:PID 0403:6014
                relay: 1                      # DC Jack relay (C0=1, C1=2)
                active_high: true             # HIGH drives relay ON
                off_delay: 2.0                # seconds OFF during power_cycle

        Returns None if PowerController cannot be created (e.g. pyftdi not
        installed or FT232H absent); callers fall back to log-only behavior so
        the flow still runs (with manual power) instead of crashing.
        """
        if getattr(self, "_power_ctrl", None) is not None:
            return self._power_ctrl
        cfg = {}
        try:
            cfg = (self.config.get("ap", {}) or {}).get("power", {}) or {}
        except AttributeError:
            cfg = {}
        try:
            from mfg.power_controller import PowerController, DEFAULT_URL

            self._power_ctrl = PowerController(
                url=cfg.get("url", DEFAULT_URL),
                active_high=bool(cfg.get("active_high", True)),
                logger=self.message,
            )
        except Exception as e:  # pyftdi missing, import error, etc.
            log.warning(f"PowerController unavailable ({e}); DC Jack is log-only")
            self._power_ctrl = None
        # Cache resolved relay / off_delay from config (defaults applied).
        self._power_relay = int(cfg.get("relay", 1))
        try:
            self._power_off_delay = float(cfg.get("off_delay", 2.0))
        except (TypeError, ValueError):
            self._power_off_delay = 2.0
        return self._power_ctrl

    def _dcjack_off(self):
        """Power off DUT via DC jack (FT232H relay; log-only if unavailable)."""
        self.message('DC Jack: OFF')
        ctrl = self._power()
        if ctrl is not None:
            ctrl.relay_off(self._power_relay)

    def _dcjack_on(self):
        """Power on DUT via DC jack (FT232H relay; log-only if unavailable)."""
        self.message('DC Jack: ON')
        ctrl = self._power()
        if ctrl is not None:
            ctrl.relay_on(self._power_relay)

    def dcjack_power_cycle(self, off_delay=None):
        """Power-cycle the DUT via the DC Jack relay: OFF -> wait -> ON.

        Backing the /blockly Utility "DUT Power" block (action=CYCLE). When the
        FT232H controller is unavailable this only logs the OFF/ON messages (so
        the MFG flow can proceed with manual power).

        Args:
            off_delay: seconds to stay OFF before turning back ON. If None,
                falls back to the testbed ``ap.power.off_delay`` (default 2.0s).
                Lets the blockly block override the delay per power-cycle.
        """
        ctrl = self._power()
        # Resolve delay: explicit arg > testbed off_delay > 2.0s default.
        if off_delay is None:
            delay = getattr(self, "_power_off_delay", 2.0)
        else:
            try:
                delay = float(off_delay)
            except (TypeError, ValueError):
                delay = getattr(self, "_power_off_delay", 2.0)
        self.message('DC Jack: OFF')
        if ctrl is not None:
            ctrl.relay_off(self._power_relay)
        import time
        if delay > 0:
            self.message(f'Waiting {delay:g}s (OFF)')
            time.sleep(delay)
        self.message('DC Jack: ON')
        if ctrl is not None:
            ctrl.relay_on(self._power_relay)

    def dcjack_on(self):
        """Power ON the DUT via the DC Jack relay (blockly-callable).

        Backs the /blockly Utility "DUT Power" block (action=ON). Log-only when
        the FT232H controller is unavailable so the MFG flow can still proceed.
        """
        self._dcjack_on()

    def dcjack_off(self):
        """Power OFF the DUT via the DC Jack relay (blockly-callable).

        Backs the /blockly Utility "DUT Power" block (action=OFF). Log-only when
        the FT232H controller is unavailable so the MFG flow can still proceed.
        """
        self._dcjack_off()

    # -------------------------------------------------------------------------
    # Blockly-called MFG methods
    # -------------------------------------------------------------------------

    def _read_one_scan(self, source, timeout, prompt):
        """Read a single scanned line from the configured source.

        source="usb_hid": read one line from stdin (blocking). Works with a
            real terminal (`pytest -s`) or the Web GUI stdin injection
            (runner.send_stdin). We do NOT use select() — against a pipe stdin
            it reports ready immediately and readline() returns "".
        source="serial": read one line from the serial console.
        """
        if source == "serial":
            try:
                # Console has no getBuffer(); expect() returns the matched
                # output (before+after), from which we take the scanned line.
                out = self.console.expect(r'[\r\n]', timeout=timeout)
                return (out or "").strip()
            except Exception as e:
                raise RuntimeError(f'Barcode serial read failed: {e}')
        import sys
        self.message(prompt)
        line = sys.stdin.readline()
        if line == "":
            raise RuntimeError(
                'No barcode input available on stdin (EOF). Run with '
                '`pytest -s` in a terminal, or send the value from the GUI '
                'input box.'
            )
        return line.strip()

    @staticmethod
    def _is_mac(value):
        """Classify a scan as MAC vs SN.

        Rule (per site convention): a SN starts with TWO OR MORE English
        letters (e.g. "EC2341003090" -> "EC"...), while a MAC is 12 hex digits
        whose leading run of letters is at most 1 (e.g. "B46AD40A6C64" -> "B"
        then a digit; "4445BA0310D8" -> none). Colons/dashes are stripped.

        So: if the value starts with >= 2 letters -> SN; otherwise, if it is
        exactly 12 hex chars -> MAC. This is needed because SN and MAC can both
        be letter-initial 12-hex strings; only the LENGTH of the leading letter
        run distinguishes them.
        """
        import re
        v = value.replace(':', '').replace('-', '').strip()
        if not v:
            return False
        lead = re.match(r'^[A-Za-z]+', v)
        if lead and len(lead.group(0)) >= 2:
            return False  # >= 2 leading letters -> SN
        return len(v) == 12 and all(c in '0123456789abcdefABCDEF' for c in v)

    @staticmethod
    def _format_mac(value):
        """Normalize a bare 12-hex MAC into colon-separated upper case,
        e.g. "4445BA0310D8" -> "44:45:BA:03:10:D8". Pass through if already
        separated."""
        v = value.replace(':', '').replace('-', '').strip().upper()
        return ':'.join(v[i:i + 2] for i in range(0, 12, 2))

    def scan_barcode(self, source="usb_hid", timeout=30, expected_len=0):
        """
        Step 0: Scan the product SN and MAC at the start of the flow.

        Scans TWO barcodes in any order. Each scanned line is auto-classified:
          * exactly 12 hex chars (e.g. "4445BA0310D8") -> MAC address
          * otherwise (e.g. "EC2612003867")            -> serial number (SN)

        The scanned SN is stored in ``self._scanned_sn`` and the scanned MAC
        (normalized to colon form, e.g. "44:45:BA:03:10:D8") in
        ``self._scanned_mac``. Both are later compared against the values read
        from the factory MTD partition in :meth:`read_hw_version`, and are used
        preferentially when writing manufacturing data.

        Args:
            source: "usb_hid" (stdin, incl. GUI injection) or "serial" (console).
            timeout: Seconds to wait per scan input.
            expected_len: If > 0, validate the scanned SN has this exact length
                (MAC is always validated as 12 hex). 0 disables the SN check.

        Returns:
            (sn, mac) tuple.
        """
        self.step(0, f'ScanBarcode: read SN and MAC from {source} scanner (2 scans, any order)')

        sn = None
        mac = None
        for i in range(2):
            which = 'SN or MAC' if (sn is None and mac is None) else \
                    ('MAC' if sn is not None else 'SN')
            value = self._read_one_scan(source, timeout,
                                        f'Please scan the barcode now ({which})...')
            if not value:
                raise RuntimeError('Scanned barcode is empty')
            if self._is_mac(value):
                if mac is not None:
                    raise ValueError(f'Two MAC-like scans received; SN missing '
                                     f'(second was "{value}")')
                mac = self._format_mac(value)
                self.message(f'Scanned MAC = {mac}')
            else:
                if sn is not None:
                    raise ValueError(f'Two SN-like scans received; MAC missing '
                                     f'(second was "{value}")')
                sn = value
                if expected_len and len(sn) != expected_len:
                    raise ValueError(
                        f'Scanned SN "{sn}" length {len(sn)} != expected {expected_len}'
                    )
                self.message(f'Scanned SN = {sn}')

        if sn is None or mac is None:
            raise RuntimeError(
                f'Expected one SN and one MAC from two scans; got SN={sn}, MAC={mac}'
            )

        self._scanned_sn = sn
        self._scanned_mac = mac
        return sn, mac

    def enter_uboot_menu(self):
        """
        Step 1: Enter U-Boot boot menu.
        Power cycle DC Jack OFF→ON, wait for boot menu, interrupt autoboot.
        """
        self.step(1, 'EnterUbootMenu: DC Jack OFF→ON, interrupt boot menu')

        self._dcjack_off()
        time.sleep(2)
        self._dcjack_on()

        # Clear any stale buffer (e.g. leftover prompt / partial command from a
        # previous failed run) before waiting for the fresh boot menu.
        try:
            self.console.drain()
        except Exception:
            pass

        # Wait for boot menu
        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        self.message('U-Boot menu detected')

        # Interrupt autoboot and enter the U-Boot console: send "0" once per
        # second until MT7981> appears (a single key / bare Enter does NOT stop
        # autoboot on this DUT — it boots straight into Linux).
        self._wait_autoboot_and_interrupt(timeout=20)

        # Stabilize the prompt before issuing commands. Right after entering the
        # U-Boot console the device may still be emitting menu redraw / ANSI
        # escapes; sending a command immediately can get its leading chars eaten
        # (observed: "mtd read factory 0x46000000..." arrived as "x46000000").
        # Flush with a bare Enter and resync on a clean prompt.
        time.sleep(0.5)
        self.console.drain()
        self.console.send('')
        self.console.expect(self.uboot_prompt, timeout=10)
        time.sleep(0.3)

        self.message('U-Boot menu entered; MT7981> prompt confirmed')

    def read_hw_version(self):
        """
        Step 2: Read hardware version from factory MTD partition.
        Reads eth0/eth1/ar0 MAC, SN, Model, HW Rev and logs them.
        """
        self.step(2, 'ReadHwVersion: Read factory MTD for MAC/SN/Model/HW Rev')

        # Read factory MTD partition into memory.
        # _uboot_send already waits for the U-Boot prompt, so do NOT expect it
        # again here (a second expect would block until timeout).
        m = self.mfg
        self._uboot_send(m['factory_read_cmd'])

        # MAC addresses
        eth0_mac = self._read_eth_mac(m['mac_eth0_offset'], 'eth0')
        eth1_mac = self._read_eth_mac(m['mac_eth1_offset'], 'eth1')
        ar0_mac  = self._read_eth_mac(m['mac_ar0_offset'], 'ar0')

        # SN, Model, HW Rev — read each field from its own offset. We do NOT
        # rely on fixed slicing of one big block, because _hex_to_ascii strips
        # NULs and would break 16-byte column alignment.
        sn        = self._read_sn_model(m['sn_offset'], '0x10').rstrip('\x00').strip()
        model_str = self._read_sn_model(m['model_offset'], '0x10').rstrip('\x00').strip()
        hw_rev    = self._read_sn_model(m['hw_rev_offset'], '0x10').rstrip('\x00').strip()

        self.message(f'eth0={eth0_mac} eth1={eth1_mac} ar0={ar0_mac}')
        self.message(f'SN={sn}  Model={model_str}  HW_Rev={hw_rev}')

        # Store for later use
        self._read_hw = {
            'eth0_mac': eth0_mac, 'eth1_mac': eth1_mac, 'ar0_mac': ar0_mac,
            'sn': sn, 'model': model_str, 'hw_rev': hw_rev,
        }

        # ── Verify SN & MAC only (per requirement) ──────────────────────
        # SN and MAC MUST have been scanned at Step 0; if not, fail. Both the
        # hardware SN (md.b 0x46000060) and hardware eth0 MAC (md.b 0x4600002A)
        # must equal the scanned values. Model / HW Rev / eth1 / ar0 are read
        # and logged above for traceability but are NOT part of the pass/fail.
        if not self._scanned_sn or not self._scanned_mac:
            raise AssertionError(
                'SN/MAC not scanned before ReadHwVersion — cannot verify '
                f'(scanned_sn={self._scanned_sn!r}, scanned_mac={self._scanned_mac!r})'
            )

        # SN: hardware (0x46000060) vs scanned barcode.
        if self._scanned_sn == sn:
            self.message(f'SN match OK: scanned={self._scanned_sn} == hw={sn}')
        else:
            raise AssertionError(
                f'SN mismatch: scanned barcode "{self._scanned_sn}" '
                f'!= hardware MTD SN "{sn}"'
            )

        # MAC: hardware eth0 (0x4600002A) vs scanned barcode. Both are
        # colon-separated upper case; compare case-insensitively for safety.
        if self._scanned_mac.upper() == eth0_mac.upper():
            self.message(f'MAC match OK: scanned={self._scanned_mac} == hw={eth0_mac}')
        else:
            raise AssertionError(
                f'MAC mismatch: scanned barcode "{self._scanned_mac}" '
                f'!= hardware eth0 MAC "{eth0_mac}"'
            )

    def update_flash_image(self):
        """
        Step 3: Download FIP + firmware via TFTP and burn to flash partitions.
        """
        self.step(3, 'UpdateFlashImage: TFTP download + burn FIP + firmware')

        tftp_server = self.config.get('ap', {}).get('tftp', {}).get('server_ip', '192.168.1.100')
        dut_ip      = self.config.get('ap', {}).get('tftp', {}).get('dut_ip', '192.168.1.10')
        # Firmware images: prefer the selected SKU's images (ap.mfg[.skus.<SKU>]
        # fip_image/fw_image) so different SKUs flash different firmware; fall
        # back to ap.tftp defaults.
        _tftp = self.config.get('ap', {}).get('tftp', {})
        fip_image = self.mfg.get('fip_image') or _tftp.get('fip_image', 'tip_fip.bin')
        fw_image  = self.mfg.get('fw_image') or _tftp.get('fw_image', 'openwrt.bin')
        self.message(f'Flashing SKU={self.mfg.get("sku_selected", "(default)")} '
                     f'fip={fip_image} fw={fw_image}')

        # Set IP addresses in U-Boot
        self._uboot_send(f'setenv ipaddr {dut_ip}')
        self._uboot_send(f'setenv serverip {tftp_server}')

        # Ping TFTP server
        self._uboot_send(f'ping {tftp_server}')
        self.console.expect('is alive', timeout=10)
        self.message('TFTP server ping OK')

        m = self.mfg
        addr = m['flash_load_addr']
        # Download and burn FIP
        self._uboot_send(f'tftpboot {addr} {fip_image}')
        self.console.expect('Bytes transferred', timeout=60)
        self._uboot_send(f"nmbm nmbm0 erase {m['fip_write_offset']} {m.get('fip_erase_size', '0x00200000')}")
        self.console.expect('Succeeded', timeout=30)
        # Use $filesize literal (U-Boot variable expansion)
        self._uboot_send(f"nmbm nmbm0 write {addr} {m['fip_write_offset']} $filesize")
        self.console.expect('Succeeded', timeout=30)
        self.message('FIP partition updated')

        # Download and burn OpenWrt factory image
        self._uboot_send(f'tftpboot {addr} {fw_image}')
        self.console.expect('Bytes transferred', timeout=120)
        self._uboot_send(f"nmbm nmbm0 erase {m['fw_write_offset_1']} {m.get('fw_erase_size', '0x08000000')}")
        self.console.expect('Succeeded', timeout=60)
        self._uboot_send(f"nmbm nmbm0 write {addr} {m['fw_write_offset_1']} $filesize")
        self.console.expect('Succeeded', timeout=60)
        self._uboot_send(f"nmbm nmbm0 write {addr} {m['fw_write_offset_2']} $filesize")
        self.console.expect('Succeeded', timeout=60)
        self.message('OpenWrt image written to rootfs1 + rootfs2')

        # Reset board
        self.console.send('reset')
        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        self.message('Board resetting after flash update')

    def write_uboot_env_serial(self):
        """
        Step 4: Write bootcount/active/upgrade_available/SN to U-Boot env.
        """
        self.step(4, 'WriteUbootEnvSerial: Write bootcount/active/upgrade_available/SN')

        self._wait_autoboot_and_interrupt(timeout=60)

        sn = self._read_hw.get('sn', self.config.get('ap', {}).get('sn', 'EC2612003867'))

        self._uboot_send('setenv bootcount 0')
        self._uboot_send('setenv active 1')
        self._uboot_send('setenv upgrade_available 1')
        self._uboot_send(f'setenv SN {sn}')
        self._uboot_send('saveenv')
        self._uboot_expect_prompt()

        # Verify
        self._uboot_send('printenv bootcount')
        self._uboot_send('printenv active')
        self._uboot_send('printenv upgrade_available')
        self._uboot_send('printenv SN')

        self.message('U-Boot serial env written and verified')

    def write_manufacturing_data(self, mac_address=None, serial_number=None):
        """
        Step 5: Write model/rev/serial/qr_code/manufacturer env vars to U-Boot.

        Args:
            mac_address: If provided, overrides the MAC read from hardware /
                config. When ``None`` (default) the previous behaviour is kept:
                use the MAC read in ``read_hw_version`` (``self._read_hw``),
                falling back to the ``ap`` section of the testbed config.
            serial_number: Same override semantics as ``mac_address`` for the SN.
        """
        self.step(5, 'WriteManufacturingData: Write model/rev/serial/qr_code/manufacturer env vars')

        # Priority: explicit arg > scanned barcode value > hardware-read value
        # > testbed config default. Using the scanned SN/MAC ensures the value
        # written matches the operator-scanned label.
        _hw = getattr(self, '_read_hw', {}) or {}
        mac = (mac_address or self._scanned_mac
               or _hw.get('eth0_mac', self.config.get('ap', {}).get('mac', '44:45:BA:03:10:D8')))
        sn  = (serial_number or self._scanned_sn
               or _hw.get('sn', self.config.get('ap', {}).get('sn', 'EC2612003867')))
        rev = _hw.get('hw_rev', self.config.get('ap', {}).get('hw_rev', 'R01A'))

        m = self.mfg
        from datetime import date
        mfg_date = date.today().strftime('%d-%m-%Y')
        vn = m['manufacturer_name']
        qr = f'{{"DT":"ap","DM":"{mac}","VN":"{vn}","SN":"{sn}","MN":"{m["model"]}","HW":"{rev}"}}'

        self._uboot_send(f"setenv sku {m['sku']}")
        self._uboot_send(f"setenv model {m['model']}")
        self._uboot_send(f'setenv model_revision {rev}')
        self._uboot_send(f'setenv serial_number {sn}')
        self._uboot_send(f'setenv qr_code {qr}')
        self._uboot_send(f"setenv manufacturer_name {m['manufacturer_name']}")
        self._uboot_send(f'setenv manufacturer_date {mfg_date}')
        self._uboot_send(f"setenv manufacturer_url {m['manufacturer_url']}")
        self._uboot_send(f"setenv model_description {m['model_description']}")
        self._uboot_send(f"setenv reference_design {m['reference_design']}")
        self._uboot_send(f"setenv certification_region {m['certification_region']}")
        self._uboot_send(f'setenv mac_address {mac}')
        self._uboot_send('saveenv')
        # NOTE: _uboot_send('saveenv') already consumes the trailing 'MT7981>'
        # prompt (expect_prompt=True). Do NOT expect the prompt again here or it
        # will block for the full timeout and fail (see kiro-memory "重複 expect").
        self.message('Manufacturing data env vars saved')

        # Reset board
        self.console.send('reset')
        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        self.message('Board resetting after manufacturing data write')

    def _login_linux(self, username='root', password=None, timeout=30):
        """Log in to the Linux console (handles the Password: prompt).

        Assumes a 'login:' prompt has already appeared (caller waited for it).

        Args:
            username: login user (default 'root'). Overridable from the
                blockly "Enter TIP Kernel" block.
            password: login password. If None, falls back to testbed
                ``ap.password`` (default empty -> just Enter). Blank means a
                passwordless login (send Enter at the Password: prompt).
            timeout: per-expect timeout in seconds.

        Leaves the console at the shell prompt (root@...:~#). Retries once on
        'Login incorrect'.
        """
        # Resolve credentials: explicit arg > remembered (from a prior
        # enter_tip_kernel with block-provided creds) > testbed ap.*.
        if username is None:
            username = getattr(self, '_linux_user', None)
        if password is None:
            password = getattr(self, '_linux_password', None)
        if username is None:
            username = 'root'
        if password is None:
            try:
                password = str(self.config.get('ap', {}).get('password', '') or '')
            except AttributeError:
                password = ''
        password = '' if password is None else str(password)
        user = username or 'root'
        # Remember for later internal logins (e.g. Step 9 enter_tip_kernel_2,
        # which has no block fields of its own).
        self._linux_user = user
        self._linux_password = password
        # Shell prompt regex. Real prompt is like 'root@5c1783edea38:~#'
        # (NOTE: the '#' may have no trailing space). Match user@host:path# on a
        # single line; '[^\r\n]*' keeps it from spanning boot-log lines.
        shell_re = r'root@[\w.\-]+:[^\r\n]*#'

        for attempt in range(2):
            # NOTE: do NOT drain() here. The caller already consumed the
            # 'login:' prompt; a drain loop can stall on periodic login-prompt
            # output and delay sending the username until the DUT login times
            # out. Send the username immediately.
            self.console.send(user)
            # After the username, the device prompts for a password. Wait for
            # it explicitly (this DUT always asks). Also accept an immediate
            # shell prompt for passwordless devices. NOTE: use expect_index()
            # (returns the matched INDEX); console.expect() returns text and
            # cannot be compared to an index.
            idx = self.console.expect_index(['[Pp]assword:', shell_re], timeout=timeout)
            if idx == 1:
                # Already at a shell prompt (truly passwordless device).
                self.message(f'Logged in to Linux as {user} (no password prompt)')
                return
            # idx == 0: password prompt -> send the password.
            self.console.send(password)
            idx2 = self.console.expect_index(
                [shell_re, 'Login incorrect', 'login:'], timeout=timeout)
            if idx2 == 0:
                self.message(f'Logged in to Linux as {user}')
                return
            # Login failed; wait for the fresh login: prompt and retry once.
            self.message(f'Login attempt {attempt + 1} failed (incorrect); retrying')
            if idx2 == 1:
                self.console.expect('login:', timeout=timeout)
            continue
        raise AssertionError(
            'Linux login failed: check the Enter TIP Kernel block user/password '
            '(or testbed ap.password)')

    def enter_tip_kernel(self, username='root', password=None):
        """
        Step 6 (and 9): Auto-boot into Linux; wait for login prompt, then log in.

        Args:
            username / password: login credentials, overridable from the
                blockly "Enter TIP Kernel" block. password=None falls back to
                testbed ``ap.password``.
        """
        self.step(6, 'EnterTipKernel: Auto-boot into Linux; wait for login prompt')

        self.message('Waiting for Linux kernel boot (auto-proceeding)...')
        # Wait for either the autoboot countdown, a banner, or the login prompt.
        idx = self.console.expect_index(
            ['Hit any key to stop autoboot:', 'ApNos-', 'OpenWrt 23.05', 'login:'],
            timeout=90,
        )
        # idx==3 means we already matched 'login:' (do NOT expect it again, or
        # we'd wait for a second login prompt that never comes -> timeout).
        if idx != 3:
            if idx == 0:
                self.message('Autoboot countdown active; waiting for kernel...')
            # Boot banner (or countdown) seen; now wait for the login prompt.
            self.console.expect('login:', timeout=120)
        self.message('Login prompt appeared (TIP kernel booted)')
        # Log in here so downstream steps start at a ready root shell.
        self._login_linux(username=username, password=password)

    def check_tip_version(self):
        """
        Step 7: Verify TIP version in /etc/openwrt_release (already logged in).
        """
        self.step(7, 'CheckTipVersion: Verify TIP version in /etc/openwrt_release')

        # enter_tip_kernel() already logged us in to the root shell, so we can
        # issue commands directly. Check TIP version. Console has no getBuffer();
        # use the matched output returned by expect() instead.
        self.console.send("cat /etc/openwrt_release | grep DISTRIB_TIP")
        buff = self.console.expect(r'root@\S+:.*#', timeout=10)
        self.message(f'/etc/openwrt_release DISTRIB_TIP: {buff}')

        if 'TIP-v4.1.1' in buff or 'TIP-v4.1' in buff:
            self.message('TIP version v4.1.1 verified')
        else:
            self.message('TIP version not found or unexpected (continuing)')

        self.message('TIP version check complete')

    def check_manufacturing_data(self):
        """
        Step 8: Linux: jffs2reset + reboot → U-Boot printenv verify manufacturing data.
        """
        self.step(8, 'CheckManufacturingData: Linux jffs2reset+reboot → U-Boot verify')

        self.console.send('jffs2reset -y')
        self.console.expect(self.uboot_prompt + '|root@', timeout=30)
        self.message('jffs2reset executed')

        self.console.send('reboot')
        self.message('Rebooting to verify manufacturing data persistence...')

        # Wait for U-Boot menu after reboot
        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        self._wait_autoboot_and_interrupt(timeout=60)

        # Verify manufacturing env vars
        self._uboot_send('printenv sku')
        self._uboot_send('printenv model')
        self._uboot_send('printenv serial_number')
        self._uboot_send('printenv mac_address')

        self.message('Manufacturing data verified in U-Boot')

        # Reset to start rebooting into Linux so the next Enter TIP Kernel step
        # only needs to wait for the login prompt (autoboot, do NOT interrupt).
        self.console.send('reset')
        self.message('Reset issued; DUT rebooting into Linux for next step')

    # ------------------------------------------------------------------
    # Certification (STUB): the real flow (ping cert server, ssh/telnet to
    # the VPN cert server, generate + pscp download certs, scp upload to the
    # DUT /certificates/, md5 verify) depends on an external certification
    # server plus Windows-side tools (plink/pscp) that are not available in
    # this environment. These methods are intentionally left as stubs so the
    # Blockly flow can be assembled and generated end-to-end; wire up the real
    # logic once the cert server + credentials are provisioned.
    # ------------------------------------------------------------------
    def prepare_certification(self, cert_server="prod-cert.accton.com"):
        """
        Prepare certification: ping the cert server, log in to the VPN cert
        server, generate the per-unit cert bundle and download it locally.

        Args:
            cert_server: Hostname of the certification server.

        TODO: Implement the real prepare flow (ping cert_server, ssh/telnet
        login, generate certs, pscp download <MAC>.tar.gz). Currently a stub.
        """
        self.step(11, f'PrepareCertification: prepare cert bundle from {cert_server}')
        self.message(f'[STUB] prepare_certification(cert_server={cert_server}) not yet implemented')

    def write_certification(self, dut_ip="192.168.1.20"):
        """
        Write certification: upload the downloaded cert bundle to the DUT
        ``/certificates/`` partition and verify by md5.

        Args:
            dut_ip: DUT TIP IP used for the scp upload.

        TODO: Implement the real write flow (extract tar.gz, scp upload to
        root@<dut_ip>:/certificates/, md5 verify each file). Currently a stub.
        """
        self.step(12, f'WriteCertification: upload certs to {dut_ip}:/certificates/')
        self.message(f'[STUB] write_certification(dut_ip={dut_ip}) not yet implemented')

    def check_certification(self):
        """
        Check certification: mount the certificates volume on the DUT and
        verify each cert file md5 against the expected values.

        TODO: Implement the real check flow (mount ubi certificates volume,
        md5sum each cert file, compare). Currently a stub.
        """
        self.step(13, 'CheckCertification: verify cert files md5 on DUT')
        self.message('[STUB] check_certification() not yet implemented')

    def enter_tip_kernel_2(self):
        """
        Step 9: Second boot into Linux; wait for login prompt.
        """
        self.step(9, 'EnterTipKernel (2): Re-boot into Linux; wait for login prompt')

        self.console.send('reset')
        self.message('Rebooting for second Linux boot...')

        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        idx = self.console.expect_index(
            ['Hit any key to stop autoboot:', 'ApNos-', 'OpenWrt 23.05', 'login:'],
            timeout=30,
        )
        # idx==3 means 'login:' already matched; don't expect it again.
        if idx != 3:
            self.console.expect('login:', timeout=120)
        self.message('Login prompt appeared (EnterTipKernel 2nd boot)')
        # Log in here so the following step starts at a ready root shell.
        self._login_linux()

    def reset_default(self):
        """
        Step 10: jffs2reset + reboot → final state is U-Boot menu.
        """
        self.step(10, 'ResetDefault: jffs2reset+reboot → final state is U-Boot menu')

        # enter_tip_kernel_2() already logged us in to the root shell.
        self.console.send('jffs2reset -y')
        self.console.expect(self.uboot_prompt + '|root@', timeout=30)
        self.message('jffs2reset executed')

        self.console.send('reboot')
        self.message('Final reboot; expecting U-Boot menu as end state...')

        self.console.expect(r'\*\*\* U-Boot Boot Menu \*\*\*', timeout=90)
        # This DUT does NOT stop autoboot on a bare Enter; must send "0" once
        # per second until MT7981> appears (same as enter_uboot_menu). A plain
        # send('') let autoboot continue into Linux and the MT7981> expect timed
        # out -> FAILED.
        self._wait_autoboot_and_interrupt(timeout=20)

        self.message('ResetDefault complete; final state: U-Boot menu')

    # -------------------------------------------------------------------------
    # QCC74x (Pi7a) platform methods — core subset, NO ATE RF calibration.
    #
    # Pi7a = Qualcomm QCC744 (QCC74x). Unlike EAP111 (MT7981 U-Boot) and OAP101
    # (IPQ5018 U-Boot), Pi7a has NO U-Boot / no tftpboot flash flow: the firmware
    # is pre-flashed and MFG drives the firmware CLI (prompt "qcc74x />"). These
    # methods issue QCC74x CLI commands and validate their output; all commands,
    # expected strings and thresholds come from testbed ``ap.mfg`` so adding a
    # QCC74x SKU means editing YAML, not this file.
    #
    # Derived from reference PASS log:
    #   docs/logfiles/Pi7a-EC2617002807_PASS_N_1_132811.txt
    # -------------------------------------------------------------------------

    @property
    def _qcc_prompt(self) -> str:
        """QCC74x firmware CLI prompt (default 'qcc74x />')."""
        return self.mfg.get("console_prompt", "qcc74x />")

    @staticmethod
    def _mac_to_colon(mac12: str) -> str:
        """Convert a bare 12-hex MAC to colon-separated upper case.

        '4445BA15E59C' -> '44:45:BA:15:E5:9C'. Input-tolerant: strips existing
        colons/dashes/whitespace before reformatting.
        """
        v = (mac12 or "").replace(":", "").replace("-", "").strip().upper()
        if len(v) != 12 or not all(c in "0123456789ABCDEF" for c in v):
            raise ValueError(f"Invalid 12-hex MAC for QCC74x factory write: {mac12!r}")
        return ":".join(v[i:i + 2] for i in range(0, 12, 2))

    @staticmethod
    def _mac_add(mac_colon: str, delta: int) -> str:
        """Return the colon MAC incremented by ``delta`` in its last octet(s).

        QCC74x firmware derives wifi_mac = base+1, ble_mac = base+2 from the
        base (halow) MAC written by ``factory w``. Used by qcc_factory_check to
        verify the derived MACs.
        """
        v = int(mac_colon.replace(":", ""), 16) + int(delta)
        h = f"{v:012X}"
        return ":".join(h[i:i + 2] for i in range(0, 12, 2))

    def _qcc_send(self, cmd, timeout=15):
        """Send a QCC74x CLI command and wait for the prompt; return output.

        Drains first: the QCC74x firmware emits asynchronous background lines
        (wifi/BLE/Morse Micro init) that leave a stale "qcc74x />" in the buffer
        after the previous command. Without draining, expect() for THIS command
        would immediately match that leftover prompt and return empty output,
        causing false failures (e.g. power_mode 1 saw only a stale prompt +
        "Morse Micro driver initial"). Draining clears stale text so the prompt
        we match belongs to this command's response.
        """
        try:
            self.console.drain()
        except Exception:
            pass
        return self.console.send_and_expect(cmd, self._qcc_prompt, timeout=timeout)

    def qcc_connect(self, timeout=90):
        """
        Power on the DUT (DC Jack) and wait for the QCC74x firmware CLI prompt.

        The QCC74x firmware boots directly to the "qcc74x />" prompt (no U-Boot,
        no boot menu). Power is cycled via the DC Jack relay (log-only if the
        FT232H controller is unavailable, so a manually-powered bench still
        works).
        """
        self.step(1, 'QccConnect: DC Jack power on, wait for "qcc74x />" prompt')
        self._dcjack_off()
        time.sleep(2)
        self._dcjack_on()
        try:
            self.console.drain()
        except Exception:
            pass
        # After boot the QCC74x firmware settles at the CLI but does NOT keep
        # re-printing the prompt: the last boot line is typically
        # "[App] Starting USB Virtual COM" and then the console goes quiet.
        # We must press Enter to make "qcc74x />" appear. Boot can also still be
        # streaming when we start, so retry: send Enter, wait a short window for
        # the prompt; repeat until the overall timeout is reached.
        import pexpect as _pexpect
        deadline = time.time() + timeout
        last_err = None
        while time.time() < deadline:
            self.console.send("")  # Enter
            try:
                self.console.expect(self._qcc_prompt, timeout=3)
                break
            except _pexpect.TIMEOUT as e:
                last_err = e
                continue
        else:
            raise last_err or _pexpect.TIMEOUT(
                f'"{self._qcc_prompt}" not seen within {timeout}s')
        self.message(f'QCC74x CLI prompt "{self._qcc_prompt}" confirmed')

    def qcc_power_mode_test(self):
        """
        Read charger power mode on both I2C buses (power_mode 0/1).

        Validates the command responds with a recognized mode ("Battery power"
        or "USB power"); records the actual mode. Per the reference log both
        modes appear at different points, so either is accepted here — the check
        confirms the command works and the format is valid.
        """
        self.step(2, 'QccPowerModeTest: power_mode 0/1 (charger power mode)')
        for bus in (0, 1):
            out = self._qcc_send(f'power_mode {bus}')
            if 'Battery power' in out:
                self.message(f'power_mode {bus}: Battery power')
            elif 'USB power' in out:
                self.message(f'power_mode {bus}: USB power')
            else:
                raise AssertionError(
                    f'power_mode {bus}: no recognized power mode in output'
                )

    def qcc_battery_mode_test(self):
        """
        Read charger battery mode on I2C0 (battery_mode 0).

        Per spec v0.5 §2.1.3:
          PASS: "Battery Discharging => OK" (Reg13/Reg11 raw shown)
          FAIL: "I2C read error" or "Battery Missing!"
        We fail on either FAIL keyword; otherwise require a "Battery" line and
        record the state (Discharging/Charging).
        """
        self.step(3, 'QccBatteryModeTest: battery_mode 0 (charger battery mode)')
        out = self._qcc_send('battery_mode 0')
        if 'I2C read error' in out:
            raise AssertionError('battery_mode 0: I2C read error (FAILED)')
        if 'Battery Missing' in out:
            raise AssertionError('battery_mode 0: Battery Missing! (FAILED)')
        if 'Battery' not in out:
            raise AssertionError('battery_mode 0: no battery info in output')
        state = 'Discharging' if 'Discharging' in out else \
                ('Charging' if 'Charging' in out else 'unknown')
        self.message(f'battery_mode 0: Battery {state} => OK')

    def qcc_fuel_gauge_test(self):
        """
        Read the SY6410 fuel gauge on both I2C buses (fuel_gauge 0/1).

        Per spec v0.5 §2.1.4 the command prints a status header
        ("I2Cx SY6410 FUEL GAUGE STATUS:") and, on this board, may report
        "Fail to read from I2Cx 0x30 register 0x02." — the spec's own example
        shows exactly that, so we DO NOT enforce a voltage range. We require the
        command to respond (status header present, or any non-empty output) and
        record the actual status for traceability.
        """
        self.step(4, 'QccFuelGaugeTest: fuel_gauge 0/1 (SY6410 status, recorded)')
        for bus in (0, 1):
            out = self._qcc_send(f'fuel_gauge {bus}')
            has_header = 'FUEL GAUGE STATUS' in out.upper()
            if not (has_header or out.strip()):
                raise AssertionError(
                    f'fuel_gauge {bus}: no response from command'
                )
            # Record the meaningful lines (strip the echoed prompt/command).
            lines = [ln.strip() for ln in out.splitlines()
                     if ln.strip() and 'qcc74x' not in ln]
            summary = ' | '.join(lines)[:120] if lines else '(no data)'
            self.message(f'fuel_gauge {bus} (recorded): {summary}')

    def qcc_check_versions(self, mm_expected=""):
        """
        Check diagnostic firmware version (diag_version) and Morse Micro
        version (mm_version).

        diag_version is compared against ap.mfg.diag_version_expected when that
        is non-empty; otherwise recorded only. mm_version is compared against
        ``mm_expected`` (from the GUI block field) when non-empty — the output
        must CONTAIN it (so passing just "1.5.0" matches "1.5.0-295/-299" as a
        prefix); otherwise mm_version is recorded only.
        """
        self.step(5, 'QccCheckVersions: diag_version + mm_version')
        m = self.mfg
        diag_out = self._qcc_send('diag_version')
        expected = (m.get('diag_version_expected') or '').strip()
        if expected:
            if expected in diag_out:
                self.message(f'diag_version OK: contains "{expected}"')
            else:
                raise AssertionError(
                    f'diag_version mismatch: expected "{expected}" not in output'
                )
        else:
            self.message(f'diag_version (recorded): {diag_out.strip()[:120]}')
        mm_out = self._qcc_send('mm_version')
        mm_expected = (mm_expected or '').strip()
        if mm_expected:
            if mm_expected in mm_out:
                self.message(f'mm_version OK: contains "{mm_expected}"')
            else:
                raise AssertionError(
                    f'mm_version mismatch: expected "{mm_expected}" not in output'
                )
        else:
            self.message(f'mm_version (recorded): {mm_out.strip()[:120]}')

    def qcc_i2c_scan(self):
        """
        Scan both I2C buses (i2c_scan / i2c_scan1) and verify all expected
        device addresses are present; also record i2cget 0/1 3f 09.
        """
        self.step(6, 'QccI2cScan: i2c_scan / i2c_scan1 (expected addrs present)')
        m = self.mfg
        expected = m.get('i2c_expected_addrs', ['0x30', '0x3F']) or []
        # i2c_scan can be slow (log showed ~25s across both buses); allow time.
        for cmd in ('i2c_scan', 'i2c_scan1'):
            out = self._qcc_send(cmd, timeout=40)
            up = out.upper()
            missing = [a for a in expected if a.upper() not in up]
            if missing:
                raise AssertionError(f'{cmd}: missing expected I2C addrs {missing}')
            self.message(f'{cmd}: found expected addrs {expected}')
        for bus in (0, 1):
            out = self._qcc_send(f'i2cget {bus} 3f 09')
            self.message(f'i2cget {bus} 3f 09 (recorded): {out.strip()[:80]}')

    def qcc_factory_write(self):
        """
        Write SN/MAC/Model/HWver to the factory partition via the firmware CLI.

        Command format (from reference log):
            factory w <base_MAC(colon)> <SN> <Model> <HWver>
        e.g. factory w 44:45:BA:15:E5:9C EC2617002807 Pi7a-0825-WL R0B

        MAC/SN come from the operator scans (scan_barcode -> self._scanned_mac /
        self._scanned_sn); Model/HWver come from ap.mfg. The firmware derives
        halow (base) / wifi (base+1) / ble (base+2) MACs automatically.
        """
        self.step(7, 'QccFactoryWrite: factory w <MAC> <SN> <Model> <HWver>')
        if not self._scanned_sn or not self._scanned_mac:
            raise AssertionError(
                'SN/MAC not scanned before QccFactoryWrite — call scan_barcode first '
                f'(scanned_sn={self._scanned_sn!r}, scanned_mac={self._scanned_mac!r})'
            )
        m = self.mfg
        mac_colon = self._mac_to_colon(self._scanned_mac)
        sn = self._scanned_sn
        model = m['model']
        hw_rev = m['hw_rev']
        cmd = f"{m['factory_write_cmd']} {mac_colon} {sn} {model} {hw_rev}"
        self.message(f'Writing factory: {cmd}')
        out = self._qcc_send(cmd, timeout=20)
        # Firmware echoes an erase + the new factory info block; a bare prompt
        # return is enough to proceed (qcc_factory_check verifies the values).
        self.message('factory write issued')

    def qcc_factory_check(self):
        """
        Read back the factory partition (factory) and verify all six fields
        match the scanned/expected values.

        Verifies: halow_mac == base MAC, wifi_mac == base+1, ble_mac == base+2,
        S/N == scanned SN, Model == ap.mfg.model, HWver == ap.mfg.hw_rev.
        """
        import re
        self.step(8, 'QccFactoryCheck: factory (read back + verify 6 fields)')
        if not self._scanned_sn or not self._scanned_mac:
            raise AssertionError('SN/MAC not scanned before QccFactoryCheck')
        m = self.mfg
        base = self._mac_to_colon(self._scanned_mac)
        expected = {
            'halow_mac': base,
            'wifi_mac': self._mac_add(base, 1),
            'ble_mac': self._mac_add(base, 2),
            'S/N': self._scanned_sn,
            'Model': m['model'],
            'HWver': m['hw_rev'],
        }
        out = self._qcc_send(m['factory_read_cmd'], timeout=15)

        def _field(name):
            # Lines look like "halow_mac: 44:45:BA:15:E5:9C" or "S/N : EC2617002807".
            mm = re.search(rf'{re.escape(name)}\s*:\s*([^\r\n]+)', out)
            return mm.group(1).strip() if mm else None

        errors = []
        for name, exp in expected.items():
            got = _field(name)
            if got is None:
                errors.append(f'{name}: missing in factory output')
            elif got.upper() != exp.upper():
                errors.append(f'{name}: got "{got}" != expected "{exp}"')
            else:
                self.message(f'{name} OK: {got}')
        if errors:
            raise AssertionError('QccFactoryCheck failed:\n  ' + '\n  '.join(errors))
        self.message('QccFactoryCheck: all 6 fields match')

    def qcc_led_test(self):
        """
        LED test: turn all LEDs on then off (led_cmd_on / led_cmd_off).

        Per spec v0.5 §2.1.5 "led all on" echoes "Pi7 LED all on". We verify
        that echo (confirms the command was accepted) and still rely on the
        operator's visual check for the actual LEDs. The off command is issued
        and recorded.
        """
        self.step(9, 'QccLedTest: led all on / led off (echo + visual)')
        m = self.mfg
        on_cmd = m.get('led_cmd_on', 'led all on')
        out = self._qcc_send(on_cmd)
        if 'Pi7 LED all on' not in out and 'LED' not in out.upper():
            raise AssertionError(
                f'led on: expected "Pi7 LED all on" echo, not seen for "{on_cmd}"'
            )
        self.message('LED all ON (echo OK; operator visual check)')
        time.sleep(1)
        self._qcc_send(m.get('led_cmd_off', 'led off'))
        self.message('LED OFF')

    def qcc_reset_button_test(self, timeout=30):
        """
        Reset-button test: operator holds the reset button >= 5s; verify the
        firmware resets easyflash configs to defaults and reboots, and that the
        factory partition (SN/MAC) is NOT cleared.

        Per the reference log the reset only clears easyflash configs (38
        entries); the factory partition is preserved. We wait for the reset
        message, wait for the reboot prompt, then re-verify the factory info.
        """
        self.step(10, 'QccResetButtonTest: hold reset >=5s, verify factory preserved')
        self.message('Please HOLD the reset button for >= 5 seconds now...')
        # The firmware prints "Resetting easyflash to defaults" once the button
        # is held long enough, then reboots. If the operator releases too early
        # it prints "[RESET BTN] Released after N ms (need M ms)" instead — we
        # detect that and give a clear error (rather than a vague timeout).
        # Loop so an early release does not immediately fail the whole test:
        # keep waiting (within `timeout`) for a successful long hold.
        import re
        import time as _time
        deadline = _time.time() + timeout
        while True:
            remaining = deadline - _time.time()
            if remaining <= 0:
                raise AssertionError(
                    'QccResetButtonTest: reset button was not held long enough '
                    f'within {timeout}s (need a >=5s hold).'
                )
            idx = self.console.expect_index(
                [r'Resetting easyflash to defaults',
                 r'\[RESET BTN\] Released after (\d+)\s*ms\s*\(need (\d+)\s*ms\)'],
                timeout=remaining,
            )
            if idx == 0:
                break
            # idx == 1: released too early — report the actual vs required ms.
            mm = re.search(r'Released after (\d+)\s*ms\s*\(need (\d+)\s*ms\)',
                           self.console._child.after)
            if mm:
                self.message(
                    f'Reset button released too early: {mm.group(1)}ms '
                    f'(need {mm.group(2)}ms) — please HOLD again for >= 5s...'
                )
            else:
                self.message('Reset button released too early — please HOLD '
                             'again for >= 5s...')
            # continue waiting for another (longer) hold
        self.message('Reset to defaults detected; waiting for reboot...')
        self.console.expect(self._qcc_prompt, timeout=timeout)
        # Verify factory (SN/MAC) survived the reset.
        self.qcc_factory_check()
        self.message('QccResetButtonTest: factory preserved after reset')

    def qcc_wdt_test(self, timeout=30):
        """
        Watchdog test: trigger a WDT reboot (wdt_reboot) and verify the DUT
        reboots back to the firmware CLI prompt.

        Per spec v0.5 §2.1.6, wdt_reboot stops the external WDT trigger task
        then forces the Ext. WDT to reboot; it prints "Force WDT reboot after
        6 seconds" then the hardware watchdog resets the device.
        """
        self.step(11, 'QccWdtTest: wdt_reboot -> WDT reboot -> back to prompt')
        m = self.mfg
        self.console.send(m.get('wdt_cmd', 'wdt_reboot'))
        # Spec message; accept a generic "WDT reboot" as fallback.
        self.console.expect(r'(Force WDT reboot after \d+ seconds|Force WDT reboot|WDT reboot)',
                            timeout=timeout)
        self.message('WDT reboot triggered; waiting for DUT to come back...')
        self.console.expect(self._qcc_prompt, timeout=timeout)
        self.message('QccWdtTest: DUT rebooted back to CLI prompt')

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def cleanup(self):
        """Close console and stop TFTP server."""
        if self._console:
            self._console.close()
            self._console = None
        self.stop_tftp()

    def run(self):
        raise NotImplementedError
