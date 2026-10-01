"""pytest runner with WebSocket log streaming (pure MFG)."""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

import db

# Project root = ProTech-MFG repo root (src/web/ -> src -> root).
PROJECT_ROOT = Path(__file__).parent.parent.parent
GENERATED_DIR = PROJECT_ROOT / "scripts" / "MFG" / "generated"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPORTS_DIR = PROJECT_ROOT / "reports"
SRC_DIR = PROJECT_ROOT / "src"
PYTHON_BIN = os.environ.get("TEST_PYTHON", sys.executable)

GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _test_env() -> dict:
    """Environment for the pytest subprocess.

    Pure MFG: no Spirent/Tcl. Only ensure the subprocess can ``import mfg`` by
    putting src/ on PYTHONPATH.
    """
    env = os.environ.copy()
    src = str(SRC_DIR)
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = f"{src}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src
    return env


# Active WebSocket connections per run_id
_ws_clients: dict[str, list[WebSocket]] = {}
# Active subprocess per run_id
_active_procs: dict[str, asyncio.subprocess.Process] = {}
# Resolved test name per run_id (for naming the report log file)
_run_names: dict[str, str] = {}


def _write_report_log(run_id: str, test_name: str, status: str, log_text: str) -> Path | None:
    """Persist a run's full console log to a file under reports/.

    File name: reports/<safe_test_name>_<YYYYmmdd-HHMMSS>_<run_id>_<status>.log
    Best-effort: failures are swallowed (returns None); the DB copy is authoritative.
    """
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', test_name or 'run').strip('_') or 'run'
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = REPORTS_DIR / f"{safe_name}_{ts}_{run_id}_{status}.log"
        header = (
            f"# test: {test_name}\n"
            f"# run_id: {run_id}\n"
            f"# status: {status}\n"
            f"# time: {datetime.now().isoformat()}\n"
            f"{'=' * 70}\n"
        )
        path.write_text(header + (log_text or "") + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def _parse_attr(py_file: Path, attr: str) -> str:
    """Extract a class-level string attribute (e.g. station/model) from source.

    Lightweight regex scan (no import). Returns "" if absent.
    """
    try:
        src = py_file.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(rf'^\s*{re.escape(attr)}\s*=\s*[\'"]([^\'"]*)[\'"]', src, re.MULTILINE)
    return m.group(1) if m else ""


def _parse_station(py_file: Path) -> str:
    """Extract the script's station code from its source (station = "PT" etc.)."""
    return _parse_attr(py_file, "station")


def list_existing_scripts() -> list[dict]:
    """List all .py test scripts under scripts/ (excluding __pycache__).

    Includes scripts/MFG/generated/ (GUI-saved scripts). For generated scripts
    the model/station come from the script's own class attributes (they have no
    model directory); for hand-written scripts model is inferred from the
    directory name and station is parsed from the source.
    """
    scripts = []
    for py_file in sorted(SCRIPTS_DIR.rglob("*.py")):
        rel = py_file.relative_to(PROJECT_ROOT)
        if "__pycache__" in rel.parts:
            continue
        parts = rel.parts
        # Pure MFG: everything under scripts/MFG is a manufacturing test.
        dtype = "mfg"
        is_generated = "generated" in parts
        station = _parse_station(py_file)
        if is_generated:
            # Generated scripts declare model/station as class attributes.
            model = _parse_attr(py_file, "model")
        else:
            # Hand-written scripts: infer model from the directory name.
            model = ""
            for p in parts:
                if p in ("EAP111", "OAP101", "Pi7a") or p.startswith(("EAP", "OAP", "Pi")):
                    model = p
                    break
        scripts.append({"name": py_file.stem, "path": str(rel), "type": dtype,
                        "model": model, "station": station})
    return scripts


def _resolve_script(test_id: str) -> Path:
    """Resolve test_id to a script path. Supports relative paths and name lookup."""
    if "/" in test_id or test_id.endswith(".py"):
        candidate = PROJECT_ROOT / test_id
        if candidate.exists():
            return candidate

    py_file = GENERATED_DIR / f"{test_id}.py"
    if py_file.exists():
        return py_file

    for f in SCRIPTS_DIR.rglob(f"{test_id}.py"):
        if "generated" not in f.parts and "__pycache__" not in f.parts:
            return f

    test = db.get_test(test_id)
    if test:
        py_file = GENERATED_DIR / f"{test['tc_id']}.py"
        if py_file.exists():
            return py_file

    return GENERATED_DIR / f"{test_id}.py"


async def start_run(test_id: str, sku: str = "") -> str:
    """Start a pytest run, return run_id."""
    run_id = uuid.uuid4().hex[:8]
    test = db.get_test(test_id)
    test_name = test["name"] if test else test_id

    # Resolve the script first so we can record its station on the run.
    py_file = _resolve_script(test_id)
    station = _parse_station(py_file) if py_file.exists() else ""

    # Record which fixture (Pi4) produced this run, identified by eth0 MAC.
    from host import get_host
    host = get_host()

    db.create_run(run_id, test_id, test_name, station=station, host=host)
    _run_names[run_id] = test_name

    if not py_file.exists():
        msg = (f"[ERROR] Test script not found for '{test_id}' "
               f"(looked for {py_file}). "
               f"Pick a test from the search box (so the test name is set), "
               f"or save the current blocks first.")
        db.finish_run(run_id, "failed", msg)

        async def _emit():
            await _broadcast(run_id, msg)
            await _broadcast(run_id, "\n[FAILED] exit code: 2")
        asyncio.create_task(_emit())
        return run_id

    asyncio.create_task(_run_pytest(run_id, str(py_file), sku))
    return run_id


async def _run_pytest(run_id: str, script_path: str, sku: str = ""):
    """Execute pytest as subprocess, stream output to WebSocket clients."""
    log_lines = []
    cmd = [PYTHON_BIN, "-m", "pytest", script_path, "-v", "--tb=long", "-s",
           "--log-cli-level=DEBUG", "--log-cli-format=%(asctime)s [%(levelname)s] %(name)s: %(message)s"]
    if sku:
        cmd += ["--sku", sku]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=_test_env(),
    )
    _active_procs[run_id] = proc

    status = "failed"
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            log_lines.append(text)
            await _broadcast(run_id, text)

        await proc.wait()
        status = "passed" if proc.returncode == 0 else "failed"
        if proc.returncode == -15 or proc.returncode == -9:
            status = "stopped"
        await _broadcast(run_id, f"\n[{status.upper()}] exit code: {proc.returncode}")
    except Exception as e:
        status = "failed"
        log_lines.append(f"[runner error] {type(e).__name__}: {e}")
        try:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        except Exception:
            pass
    finally:
        _active_procs.pop(run_id, None)
        full_log = "\n".join(log_lines)
        db.finish_run(run_id, status, full_log)
        report_path = _write_report_log(
            run_id, _run_names.get(run_id, run_id), status, full_log)
        _run_names.pop(run_id, None)
        if report_path is not None:
            try:
                rel = report_path.relative_to(PROJECT_ROOT)
            except ValueError:
                rel = report_path
            await _broadcast(run_id, f"[log saved] {rel}")


async def stop_run(run_id: str) -> bool:
    """Stop a running test (SIGTERM live proc, or reconcile a ghost run)."""
    import signal
    proc = _active_procs.get(run_id)
    if proc and proc.returncode is None:
        proc.send_signal(signal.SIGTERM)
        await _broadcast(run_id, "\n[STOPPED] Test terminated by user.")
        return True

    _active_procs.pop(run_id, None)
    run = db.get_run(run_id)
    if run and run.get("status") == "running":
        db.finish_run(run_id, "stopped", (run.get("log") or "") +
                      "\n[STOPPED] Reconciled: subprocess no longer running.")
        await _broadcast(run_id, "\n[STOPPED] Reconciled ghost run.")
        return True
    return False


async def send_stdin(run_id: str, data: str) -> bool:
    """Write a line to the running test subprocess's stdin (e.g. scanned SN/MAC)."""
    proc = _active_procs.get(run_id)
    if not proc or proc.returncode is not None or proc.stdin is None:
        return False
    try:
        payload = data if data.endswith("\n") else data + "\n"
        proc.stdin.write(payload.encode("utf-8"))
        await proc.stdin.drain()
        await _broadcast(run_id, f"[stdin] {data.rstrip()}")
        return True
    except Exception:
        return False


async def _broadcast(run_id: str, message: str):
    """Send message to all WebSocket clients watching this run."""
    clients = _ws_clients.get(run_id, [])
    for ws in clients[:]:
        try:
            await ws.send_text(message)
        except Exception:
            clients.remove(ws)


async def ws_run_handler(websocket: WebSocket, run_id: str):
    """WebSocket endpoint handler for streaming run logs."""
    await websocket.accept()
    _ws_clients.setdefault(run_id, []).append(websocket)

    run = db.get_run(run_id)
    if run and run.get("log"):
        await websocket.send_text(run["log"])

    try:
        while True:
            msg = await websocket.receive_text()
            # {"type":"stdin","data":"<text>"} feeds the running test's stdin
            # (e.g. a scanned barcode). Other messages are keep-alive.
            try:
                import json
                payload = json.loads(msg)
            except (ValueError, TypeError):
                payload = None
            if isinstance(payload, dict) and payload.get("type") == "stdin":
                await send_stdin(run_id, str(payload.get("data", "")))
    except WebSocketDisconnect:
        _ws_clients.get(run_id, []).remove(websocket)
