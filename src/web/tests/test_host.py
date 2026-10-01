"""Tests for fixture host identity (eth0 MAC) and run recording.

Run from project root:
    PYTHONPATH=src/web .venv/bin/python -m pytest src/web/tests/test_host.py -v
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

# src/web must be importable (host, db are top-level modules there).
WEB = Path(__file__).resolve().parent.parent
if str(WEB) not in sys.path:
    sys.path.insert(0, str(WEB))

import host as host_mod  # noqa: E402


# --- get_host() resolution order -----------------------------------------

def test_mfg_host_env_override(monkeypatch):
    """MFG_HOST env var takes top priority and is lowercased."""
    monkeypatch.setenv("MFG_HOST", "AA:BB:CC:DD:EE:FF")
    assert host_mod.get_host() == "aa:bb:cc:dd:ee:ff"


def test_reads_iface_mac_from_sysfs(monkeypatch, tmp_path):
    """With no override, reads /sys/class/net/<iface>/address."""
    monkeypatch.delenv("MFG_HOST", raising=False)
    # Point the reader at a fake sysfs file via a patched iface + open.
    fake_mac = "dc:a6:32:12:34:56"

    def fake_read(iface):
        assert iface == "eth0"
        return fake_mac

    monkeypatch.setattr(host_mod, "_read_iface_mac", fake_read)
    assert host_mod.get_host() == fake_mac


def test_custom_iface_via_env(monkeypatch):
    """MFG_HOST_IFACE overrides which interface is read."""
    monkeypatch.delenv("MFG_HOST", raising=False)
    monkeypatch.setenv("MFG_HOST_IFACE", "enp0s31f6")
    seen = {}

    def fake_read(iface):
        seen["iface"] = iface
        return "04:42:1a:8e:d7:0d"

    monkeypatch.setattr(host_mod, "_read_iface_mac", fake_read)
    assert host_mod.get_host() == "04:42:1a:8e:d7:0d"
    assert seen["iface"] == "enp0s31f6"


def test_unknown_returns_empty(monkeypatch):
    """No override and unreadable iface -> '' (keeps runs working)."""
    monkeypatch.delenv("MFG_HOST", raising=False)
    monkeypatch.delenv("MFG_HOST_IFACE", raising=False)
    monkeypatch.setattr(host_mod, "_read_iface_mac", lambda iface: "")
    assert host_mod.get_host() == ""


def test_normalize_rejects_all_zero():
    assert host_mod._normalize_mac("00:00:00:00:00:00") == ""
    assert host_mod._normalize_mac("") == ""
    assert host_mod._normalize_mac("  AA:BB:CC:dd:ee:ff \n") == "aa:bb:cc:dd:ee:ff"


# --- db records host on runs ---------------------------------------------

def test_db_create_run_records_host(monkeypatch, tmp_path):
    """create_run persists host; list_runs/get_run return it. Uses a temp DB."""
    # Redirect the DB to a temp file BEFORE importing db, then re-init schema.
    import db as db_mod
    importlib.reload(db_mod)
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "gui.db")
    db_mod.init_db()

    db_mod.create_run("run-xyz", "tc-1", "EAP111-MFG",
                      station="FT", host="dc:a6:32:12:34:56")
    run = db_mod.get_run("run-xyz")
    assert run["host"] == "dc:a6:32:12:34:56"
    assert run["station"] == "FT"

    rows = db_mod.list_runs(limit=10)
    assert any(r["run_id"] == "run-xyz" and r["host"] == "dc:a6:32:12:34:56"
               for r in rows)


def test_db_backward_compat_adds_host_column(monkeypatch, tmp_path):
    """A pre-existing runs table without `host` gets the column via ALTER."""
    import sqlite3
    import db as db_mod
    importlib.reload(db_mod)
    dbfile = tmp_path / "legacy.db"
    # Simulate an old DB: runs table without host (but with station).
    conn = sqlite3.connect(str(dbfile))
    conn.execute("""CREATE TABLE runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL, test_id TEXT NOT NULL, test_name TEXT,
        started_at TEXT, finished_at TEXT, status TEXT DEFAULT 'pending',
        duration_sec REAL, log TEXT DEFAULT '', station TEXT DEFAULT '')""")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_mod, "DB_PATH", dbfile)
    db_mod.init_db()  # should ALTER TABLE to add host
    cols = []
    import sqlite3 as _s
    c = _s.connect(str(dbfile))
    cols = [r[1] for r in c.execute("PRAGMA table_info(runs)").fetchall()]
    c.close()
    assert "host" in cols
