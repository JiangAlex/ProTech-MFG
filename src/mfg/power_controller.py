"""PowerController — FT232H GPIO relay control for DUT power (PDU).

The lab PDU is an FTDI FT232H (VID:PID 0403:6014) whose ACBUS GPIO pins drive
two relays:

    C0 = ACBUS0 = bit 8  -> relay1   (DC Jack power, default)
    C1 = ACBUS1 = bit 9  -> relay2   (spare / second power line)

IMPORTANT — FT232H is a 16-bit wide port: ADBUS0..7 = bit0..7 (silk D0..D7),
ACBUS0..7 = bit8..15 (silk C0..C7). The relays are wired to ACBUS (C0/C1), so
we MUST use pyftdi's ``GpioMpsseController`` (which can access the full 16-bit
port). The plain async ``GpioController`` can only reach the low 8 bits
(ADBUS/D0..D7) and therefore CANNOT drive C0/C1 -- an earlier version used it
and the relays never switched.

This is mutually exclusive with the kernel ``ftdi_sio`` UART driver: the FT232H
must be unbound from ``ftdi_sio`` first (see tools/setup_ft232h_gpio.sh and
docs/kiro-memory.md for the setup steps).

Device is addressed by VID:PID via the URL ``ftdi://ftdi:232h/1`` so it does not
depend on the (non-fixed) /dev/ttyUSBx numbering.

Design notes
------------
* ``active_high`` is configurable because relay board trigger polarity varies.
  active_high=True  -> driving the pin HIGH energizes the relay (power ON).
  active_high=False -> driving the pin LOW  energizes the relay (power ON),
                       i.e. a low-trigger board (measured on this hardware:
                       pin LOW closes the relay).
* Only the pins listed in ``relays`` are configured as outputs; other pins are
  left as inputs so we do not disturb anything else on the FT232H.
* All methods are best-effort and log via an injected ``message`` callback so
  the calling script's log format is preserved.
"""

import logging

log = logging.getLogger(__name__)

# Default relay -> GPIO bit mapping on the FT232H (ACBUS, 16-bit wide port).
DEFAULT_RELAY_BITS = {1: 8, 2: 9}  # relay1=C0=ACBUS0(bit8), relay2=C1=ACBUS1(bit9)

# MPSSE clock frequency (Hz). Relays are DC; any low frequency is fine.
DEFAULT_FREQUENCY = 1e6

# Default FTDI device URL: first FT232H found by VID:PID (0403:6014).
DEFAULT_URL = "ftdi://ftdi:232h/1"


class PowerController:
    """Control DUT power relays wired to an FT232H's C0/C1 GPIO pins."""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        relay_bits: dict | None = None,
        active_high: bool = True,
        frequency: float = DEFAULT_FREQUENCY,
        logger=None,
    ):
        """Create a controller.

        Args:
            url: pyftdi device URL. Defaults to the first FT232H by VID:PID.
            relay_bits: mapping of relay number -> GPIO bit. Defaults to
                {1: 8, 2: 9} i.e. relay1=C0=ACBUS0, relay2=C1=ACBUS1.
            active_high: True if driving a pin HIGH energizes its relay
                (power ON). Set False for low-trigger relay boards.
            frequency: MPSSE clock frequency in Hz (relays are DC; default 1MHz).
            logger: optional callable(msg) used for user-facing messages
                (e.g. ManufacturingScript.message). Falls back to module log.
        """
        self.url = url
        self.relay_bits = dict(relay_bits) if relay_bits else dict(DEFAULT_RELAY_BITS)
        self.active_high = bool(active_high)
        self.frequency = float(frequency)
        self._log = logger or (lambda m: log.info(m))
        self._gpio = None
        # Direction mask: only our relay bits are outputs (16-bit wide port).
        self._direction = 0
        for bit in self.relay_bits.values():
            self._direction |= (1 << bit)
        # Cached output state (bit pattern actually written to the port).
        self._state = 0

    # -- lifecycle ---------------------------------------------------------
    def open(self):
        """Open the FT232H GPIO controller (lazy; safe to call repeatedly)."""
        if self._gpio is not None:
            return
        # Imported here so importing this module never requires pyftdi to be
        # installed unless power control is actually used.
        # GpioMpsseController is REQUIRED to access ACBUS pins (bit8..15 =
        # C0..C7); the plain async GpioController only reaches ADBUS (bit0..7).
        from pyftdi.gpio import GpioMpsseController

        gpio = GpioMpsseController()
        gpio.configure(self.url, direction=self._direction, frequency=self.frequency)
        self._gpio = gpio
        # Initialize output register to the de-energized (OFF) state.
        self._state = self._all_off_pattern()
        self._write()

    def close(self):
        """Close the GPIO controller if open."""
        if self._gpio is not None:
            try:
                self._gpio.close()
            finally:
                self._gpio = None

    # -- relay control -----------------------------------------------------
    def relay_on(self, relay: int = 1):
        """Energize (power ON) the given relay number."""
        self._set_relay(relay, True)

    def relay_off(self, relay: int = 1):
        """De-energize (power OFF) the given relay number."""
        self._set_relay(relay, False)

    def all_off(self):
        """Turn every configured relay OFF."""
        self.open()
        self._state = self._all_off_pattern()
        self._write()

    def power_cycle(self, relay: int = 1, off_delay: float = 2.0):
        """Power-cycle: turn the relay OFF, wait, then ON (DC Jack OFF->ON)."""
        import time

        self.relay_off(relay)
        if off_delay > 0:
            time.sleep(off_delay)
        self.relay_on(relay)

    # -- internals ---------------------------------------------------------
    def _all_off_pattern(self) -> int:
        """Bit pattern that de-energizes all relays (respects active_high)."""
        if self.active_high:
            return 0  # all LOW -> all OFF for high-trigger boards
        # Low-trigger: OFF means driving the pins HIGH.
        pattern = 0
        for bit in self.relay_bits.values():
            pattern |= (1 << bit)
        return pattern

    def _set_relay(self, relay: int, energize: bool):
        if relay not in self.relay_bits:
            raise ValueError(f"Unknown relay {relay}; known: {sorted(self.relay_bits)}")
        self.open()
        bit = self.relay_bits[relay]
        # On (energize) drives HIGH when active_high, LOW otherwise.
        drive_high = energize if self.active_high else (not energize)
        if drive_high:
            self._state |= (1 << bit)
        else:
            self._state &= ~(1 << bit)
        self._write()

    def _write(self):
        if self._gpio is None:
            return
        # Only bits in the direction mask are outputs.
        self._gpio.write(self._state & self._direction)
