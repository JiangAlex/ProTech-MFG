"""Fixture host identity for multi-Pi4 deployments.

Each Pi4 fixture is identified by its ``eth0`` MAC address (hardware-unique,
survives hostname changes, and needs no per-device config). The resolved value
is recorded on every run (see db.create_run) so the central controller can tell
which fixture produced a result.

Resolution order (first non-empty wins):
  1. ``MFG_HOST`` env var               -- explicit override (tests / special cases)
  2. ``/sys/class/net/<iface>/address`` -- iface defaults to eth0, override via
                                            ``MFG_HOST_IFACE``
  3. ""                                  -- unknown (keeps runs working; matches
                                            the db column's default)

MAC is normalized to lowercase colon form, e.g. "dc:a6:32:ab:cd:ef".
"""

import os

DEFAULT_IFACE = "eth0"


def _normalize_mac(raw: str) -> str:
    """Normalize a MAC string to lowercase colon form, or '' if not a MAC."""
    s = (raw or "").strip().lower()
    # Accept the kernel's canonical "aa:bb:cc:dd:ee:ff"; reject empty/all-zero.
    if not s or s == "00:00:00:00:00:00":
        return ""
    return s


def _read_iface_mac(iface: str) -> str:
    """Read a network interface's MAC from sysfs. Returns '' on any failure."""
    try:
        with open(f"/sys/class/net/{iface}/address", "r", encoding="ascii") as f:
            return _normalize_mac(f.read())
    except OSError:
        return ""


def get_host() -> str:
    """Return this fixture's identity (eth0 MAC), or '' if undeterminable.

    See module docstring for the resolution order.
    """
    override = os.environ.get("MFG_HOST", "").strip()
    if override:
        return override.lower()

    iface = os.environ.get("MFG_HOST_IFACE", DEFAULT_IFACE).strip() or DEFAULT_IFACE
    return _read_iface_mac(iface)
