"""SQLite database operations for WLAN Test GUI."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "gui.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if not exist."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tc_id TEXT NOT NULL UNIQUE,
            workspace_json TEXT,
            python_code TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        # Ensure unique index exists (covers existing DBs without the constraint)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tests_tc_id ON tests(tc_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE NOT NULL,
            test_id TEXT NOT NULL,
            test_name TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT DEFAULT 'pending',
            duration_sec REAL,
            log TEXT DEFAULT '',
            station TEXT DEFAULT ''
        )""")
        # Backward-compat: add `station` column to pre-existing runs tables.
        cols = [r[1] for r in c.execute("PRAGMA table_info(runs)").fetchall()]
        if "station" not in cols:
            c.execute("ALTER TABLE runs ADD COLUMN station TEXT DEFAULT ''")
        c.execute("""CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            cron TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS topology_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            topology_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        )""")


# --- Tests CRUD ---

def create_test(name, tc_id, workspace_json, python_code):
    """Upsert: insert if tc_id is new, replace if it already exists."""
    with _conn() as c:
        c.execute(
            """INSERT INTO tests (name, tc_id, workspace_json, python_code)
               VALUES (?,?,?,?)
               ON CONFLICT(tc_id) DO UPDATE SET
                 name = excluded.name,
                 workspace_json = excluded.workspace_json,
                 python_code = excluded.python_code""",
            (name, tc_id, json.dumps(workspace_json), python_code)
        )
        row = c.execute("SELECT id FROM tests WHERE tc_id=?", (tc_id,)).fetchone()
        return row['id'] if row else None


def list_tests():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT id, name, tc_id, created_at FROM tests ORDER BY id DESC")]


def get_test(test_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM tests WHERE id=? OR tc_id=?", (test_id, test_id)).fetchone()
        if row:
            d = dict(row)
            d['workspace_json'] = json.loads(d['workspace_json']) if d['workspace_json'] else {}
            return d
        return None


def delete_test(test_id):
    with _conn() as c:
        c.execute("DELETE FROM tests WHERE id=?", (test_id,))


# --- Runs CRUD ---

def create_run(run_id, test_id, test_name, station=""):
    with _conn() as c:
        c.execute(
            "INSERT INTO runs (run_id, test_id, test_name, started_at, status, station) VALUES (?,?,?,?,?,?)",
            (run_id, test_id, test_name, datetime.now().isoformat(), "running", station or "")
        )


def finish_run(run_id, status, log_text):
    with _conn() as c:
        started = c.execute("SELECT started_at FROM runs WHERE run_id=?", (run_id,)).fetchone()
        duration = None
        if started:
            start_dt = datetime.fromisoformat(started['started_at'])
            duration = (datetime.now() - start_dt).total_seconds()
        c.execute(
            "UPDATE runs SET finished_at=?, status=?, duration_sec=?, log=? WHERE run_id=?",
            (datetime.now().isoformat(), status, duration, log_text, run_id)
        )


def list_runs(limit=50):
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT id, run_id, test_id, test_name, started_at, finished_at, status, duration_sec, station FROM runs ORDER BY id DESC LIMIT ?", (limit,))]


def get_run(run_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None


# --- Schedules CRUD ---

def create_schedule(test_id, cron, enabled=True):
    with _conn() as c:
        cur = c.execute("INSERT INTO schedules (test_id, cron, enabled) VALUES (?,?,?)", (test_id, cron, int(enabled)))
        return cur.lastrowid


def list_schedules():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM schedules ORDER BY id DESC")]


def delete_schedule(schedule_id):
    with _conn() as c:
        c.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))


# --- Topology Plans CRUD ---

def create_topology_plan(name, topology_json):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO topology_plans (name, topology_json) VALUES (?,?)",
            (name, json.dumps(topology_json))
        )
        return cur.lastrowid


def list_topology_plans():
    with _conn() as c:
        rows = c.execute("SELECT id, name, created_at FROM topology_plans ORDER BY id DESC")
        return [dict(r) for r in rows]


def get_topology_plan(plan_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM topology_plans WHERE id=?", (plan_id,)).fetchone()
        if row:
            d = dict(row)
            d['topology_json'] = json.loads(d['topology_json']) if d['topology_json'] else {}
            return d
        return None


def update_topology_plan(plan_id, topology_json):
    with _conn() as c:
        c.execute("UPDATE topology_plans SET topology_json=? WHERE id=?",
                  (json.dumps(topology_json), plan_id))


def delete_topology_plan(plan_id):
    with _conn() as c:
        c.execute("DELETE FROM topology_plans WHERE id=?", (plan_id,))


# Initialize on import
init_db()
