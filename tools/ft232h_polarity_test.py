#!/usr/bin/env python3
"""
ft232h_polarity_test.py — Interactive FT232H relay polarity / pin locator.

IMPORTANT — FT232H has a 16-bit wide port:
    * ADBUS0..7  = bit 0..7   (breakout silk: D0..D7)
    * ACBUS0..7  = bit 8..15  (breakout silk: C0..C7)   <-- likely your relays

The plain GpioController (async) can ONLY drive the low 8 bits (ADBUS/D0..D7).
To drive ACBUS (C0..C7) we MUST use GpioMpsseController, which can access the
full 16-bit port. This script uses GpioMpsseController so BOTH banks are
testable, letting us locate which pins the relays are actually wired to.

Run with -i so the GPIO stays open in ONE process (prevents ftdi_sio from
re-grabbing the chip between separate python invocations):

    ~/projects/kiro-ATLAS/.venv/bin/python3 -i tools/ft232h_polarity_test.py

Prerequisite:
    tools/setup_ft232h_gpio.sh has been run (ftdi_sio unbound, udev rule set).

At the >>> prompt, call these and WATCH THE DUT POWER + measure the pin voltage
each time (clean HIGH ~3.3V / LOW ~0V means we are driving the right pin):

    ADBUS bank (silk D0/D1):
        d0_high()  d0_low()   d1_high()  d1_low()
    ACBUS bank (silk C0/C1):
        c0_high()  c0_low()   c1_high()  c1_low()
    off()       # everything LOW (safe)
    status()    # print current readback (16-bit)
    quit()      # drive all LOW then exit

Locate the relay:
    Whichever command makes the DUT power change AND shows a clean voltage
    swing on the measured pin is the relay wiring.
        D0->ADBUS0  D1->ADBUS1   C0->ACBUS0  C1->ACBUS1
Polarity:
    pin=HIGH powers DUT  -> active_high: true
    pin=HIGH cuts  DUT   -> active_high: false
"""
import sys

URL = "ftdi://ftdi:232h/1"

# Bit positions in the 16-bit wide port.
BIT_D0 = 0      # ADBUS0
BIT_D1 = 1      # ADBUS1
BIT_C0 = 8      # ACBUS0
BIT_C1 = 9      # ACBUS1

# Configure all four candidate pins as outputs.
DIRECTION = (1 << BIT_D0) | (1 << BIT_D1) | (1 << BIT_C0) | (1 << BIT_C1)  # 0x0303

try:
    from pyftdi.gpio import GpioMpsseController
except ImportError:
    sys.exit("pyftdi not installed. Run: pip install -r requirements.txt (in .venv)")

_g = GpioMpsseController()
# frequency is required by the MPSSE controller; 1 MHz is fine for relays.
_g.configure(URL, direction=DIRECTION, frequency=1e6)

_state = 0  # current 16-bit output latch


def _readback():
    """Return the port level as a single 16-bit int, whatever read() gives."""
    rb = _g.read()
    if isinstance(rb, (bytes, bytearray)):
        return int.from_bytes(bytes(rb[:2]), "little")
    if isinstance(rb, (tuple, list)):
        return int(rb[0]) if rb else 0
    return int(rb)


def _apply(label):
    global _state
    _g.write(_state & DIRECTION)
    rb = _readback()
    print(f"{label:9s} state={_state:#06x}  readback={rb:#06x}  "
          f"(D1D0={_state >> 0 & 3:02b}  C1C0={_state >> 8 & 3:02b})")


def _set(bit, high, label):
    global _state
    if high:
        _state |= (1 << bit)
    else:
        _state &= ~(1 << bit)
    _apply(label)


def d0_high(): _set(BIT_D0, True,  "D0=HIGH")
def d0_low():  _set(BIT_D0, False, "D0=LOW")
def d1_high(): _set(BIT_D1, True,  "D1=HIGH")
def d1_low():  _set(BIT_D1, False, "D1=LOW")
def c0_high(): _set(BIT_C0, True,  "C0=HIGH")
def c0_low():  _set(BIT_C0, False, "C0=LOW")
def c1_high(): _set(BIT_C1, True,  "C1=HIGH")
def c1_low():  _set(BIT_C1, False, "C1=LOW")


def off():
    global _state
    _state = 0
    _apply("OFF(all)")


def status():
    rb = _readback()
    print(f"readback={rb:#06x}  (D1D0={rb & 3:02b}  C1C0={rb >> 8 & 3:02b})")


def quit():  # noqa: A001 - intentional convenience override
    try:
        global _state
        _state = 0
        _g.write(0x0000)
        _g.close()
    finally:
        raise SystemExit(0)


print("=== FT232H polarity / pin locator (MPSSE, 16-bit port) ===")
_apply("init(LOW)")
print("ADBUS: d0_high() d0_low() d1_high() d1_low()")
print("ACBUS: c0_high() c0_low() c1_high() c1_low()")
print("       off()  status()  quit()")
print("Measure each pin's voltage + watch DUT power after every command.")
