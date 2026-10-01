"""ProTech-MFG GUI — FastAPI backend (pure MFG)."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from models import TestCreate, RunCreate, FileContent, ScheduleCreate
import db

# Project root = ProTech-MFG repo root (src/web/ -> src -> root).
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
STATIC_DIR = Path(__file__).parent / "static"
GENERATED_DIR = PROJECT_ROOT / "scripts" / "MFG" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
# Let profile API import the mfg-side device_profile loader.
sys.path.insert(0, str(SRC_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    from scheduler import start
    start()
    import asyncio
    from console_stream import console_keepalive
    keepalive_task = asyncio.create_task(console_keepalive())
    yield
    keepalive_task.cancel()
    try:
        await keepalive_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="ProTech-MFG GUI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


app.add_middleware(NoCacheStaticMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Pages ---

@app.get("/")
async def index():
    # Pure MFG: the Blockly editor is the home page.
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/blockly")
async def blockly():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
async def dashboard():
    # MFG monitoring: run history (topology / device status removed — pure MFG).
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/editor")
async def editor():
    # File editor for MFG scripts / testbed / profile YAMLs (whitelisted).
    return FileResponse(STATIC_DIR / "editor.html")


@app.get("/console")
async def console():
    # Live DUT console: tail of the ser2net trace log.
    return FileResponse(STATIC_DIR / "console.html")


# --- Tests CRUD ---

@app.post("/api/tests", status_code=201)
async def create_test(req: TestCreate):
    test_id = db.create_test(req.name, req.tc_id, req.workspace_json, req.python_code)
    stem = req.tc_id.split('/')[-1]
    if stem.endswith('.py'):
        stem = stem[:-3]
    tc_filename = stem + '.py'
    py_path = GENERATED_DIR / tc_filename

    code = req.python_code
    # Inject station / model attributes into the generated script so station &
    # model based filtering / run recording works (see config/stations.yaml).
    # We add each right after the first `tc_id = "..."` line if provided and not
    # already declared. Injected together so both share the tc_id anchor.
    import re as _re
    m = _re.search(r'^(\s*)tc_id\s*=.*$', code, _re.MULTILINE)
    if m:
        indent = m.group(1)
        inject_lines = [m.group(0)]
        station = (req.station or "").strip()
        if station and "station =" not in code and "station=" not in code:
            inject_lines.append(f'{indent}station = "{station}"')
        model = (req.model or "").strip()
        if model and "\n    model =" not in code and "model =" not in code:
            inject_lines.append(f'{indent}model = "{model}"')
        if len(inject_lines) > 1:
            code = code[:m.start()] + "\n".join(inject_lines) + code[m.end():]

    py_path.write_text(code, encoding="utf-8")
    return {"id": test_id, "file": str(py_path)}


@app.get("/api/tests")
async def list_tests():
    return db.list_tests()


@app.get("/api/tests/{test_id}")
async def get_test(test_id: str):
    t = db.get_test(test_id)
    if not t:
        raise HTTPException(404, "Test not found")
    return t


@app.delete("/api/tests/{test_id}")
async def delete_test(test_id: int):
    db.delete_test(test_id)
    return {"ok": True}


# --- Existing Scripts ---

@app.get("/api/scripts")
async def list_scripts():
    from runner import list_existing_scripts
    return list_existing_scripts()


@app.get("/api/scripts/parse")
async def parse_script(path: str):
    from script_parser import parse_script_to_blocks
    full = PROJECT_ROOT / path
    if not full.exists():
        raise HTTPException(404, "Script not found")
    return parse_script_to_blocks(full)


# --- Runs ---

@app.post("/api/runs")
async def create_run(req: RunCreate):
    from runner import start_run
    run_id = await start_run(req.test_id, sku=req.sku)
    return {"run_id": run_id}


@app.get("/api/runs")
async def list_runs():
    return db.list_runs()


@app.get("/api/runs/html")
async def runs_html():
    """Return HTML fragment of run history for HTMX."""
    runs = db.list_runs(limit=20)
    if not runs:
        return HTMLResponse("<p>尚無執行紀錄</p>")
    html = '<table style="width:100%;border-collapse:collapse;">'
    html += '<tr><th>時間</th><th>測試</th><th>站別</th><th>結果</th><th>耗時</th><th>Log</th></tr>'
    for r in runs:
        icon = "✅" if r["status"] == "passed" else ("❌" if r["status"] == "failed" else ("🛑" if r["status"] == "stopped" else "⏳"))
        dur = f'{r["duration_sec"]:.0f}s' if r.get("duration_sec") else "-"
        started = r.get("started_at", "")[:16]
        station = r.get("station") or "-"
        stop_btn = f'<button onclick="stopRun(\'{r["run_id"]}\')" style="color:#F44336;cursor:pointer;">⏹ 停止</button>' if r["status"] == "running" else ""
        html += f'<tr><td>{started}</td><td>{r["test_name"]}</td><td>{station}</td><td>{icon} {r["status"]}</td><td>{dur}</td>'
        html += f'<td><button onclick="toggleLog(\'{r["run_id"]}\')">📋</button> {stop_btn}</td></tr>'
        html += f'<tr id="log-{r["run_id"]}" style="display:none;"><td colspan="6"><pre style="max-height:200px;overflow:auto;background:#000;padding:0.5rem;font-size:0.7rem;"></pre></td></tr>'
    html += '</table>'
    return HTMLResponse(html)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r


@app.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str):
    from runner import stop_run as _stop
    ok = await _stop(run_id)
    if not ok:
        raise HTTPException(404, "Run not active")
    return {"ok": True}


@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    from runner import ws_run_handler
    await ws_run_handler(websocket, run_id)


# --- Live DUT console (ser2net trace log tail) ---

@app.websocket("/ws/console")
async def ws_console(websocket: WebSocket):
    from console_stream import ws_console_handler
    await ws_console_handler(websocket)


@app.get("/api/console/status")
async def console_status():
    from console_stream import latest_log_path, CONSOLE_LOG_DIR
    path = latest_log_path()
    return {
        "log_dir": str(CONSOLE_LOG_DIR),
        "active_log": str(path) if path else None,
        "available": path is not None,
    }


# --- Profiles / SKUs ---

@app.get("/api/profiles")
async def list_profiles_api():
    from mfg.device_profile import list_profiles, load_profile
    result = []
    for name in list_profiles():
        p = load_profile(name)
        result.append(p.to_dict())
    return result


@app.get("/api/skus")
async def list_skus_api():
    """Return {model: {default, skus:[...]}} scanned from testbeds' ap.mfg.skus."""
    import glob
    import yaml
    result = {}
    tb_dir = PROJECT_ROOT / "config" / "test_node"
    for path in glob.glob(str(tb_dir / "*.yaml")):
        try:
            with open(path) as f:
                d = yaml.safe_load(f) or {}
            ap = (d.get("ap") or {})
            model = ap.get("model")
            mfg = (ap.get("mfg") or {})
            skus = mfg.get("skus") or {}
            if model and skus:
                result[model] = {
                    "default": mfg.get("default_sku", ""),
                    "skus": sorted(skus.keys()),
                }
        except Exception:
            continue
    return result


@app.get("/api/profiles/{model}")
async def get_profile(model: str):
    from mfg.device_profile import load_profile
    try:
        p = load_profile(model)
        return p.to_dict()
    except FileNotFoundError:
        raise HTTPException(404, f"Profile '{model}' not found")


# --- MFG stations (data-driven; open & extensible) ---

@app.get("/api/stations")
async def list_stations():
    """Return the MFG station list from config/stations.yaml.

    Stations are an open set (PT/FT/FDL + optional sub-stations like PT1/PT2).
    The GUI uses this for the station dropdown / filtering. Falls back to a
    minimal built-in list if the file is missing.
    """
    import yaml
    path = PROJECT_ROOT / "config" / "stations.yaml"
    if not path.exists():
        return [
            {"code": "PT", "name": "PT"},
            {"code": "FT", "name": "FT"},
            {"code": "FDL", "name": "FDL"},
        ]
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        stations = data.get("stations") or []
        # Normalize to {code, name, description}.
        out = []
        for s in stations:
            if not isinstance(s, dict) or not s.get("code"):
                continue
            out.append({
                "code": s["code"],
                "name": s.get("name", s["code"]),
                "description": s.get("description", ""),
            })
        return out
    except Exception as e:
        raise HTTPException(500, f"Failed to read stations.yaml: {e}")


# --- Testbed wiring (read-only "how this bench is wired") ---

@app.get("/api/testbed/{model}")
async def get_testbed(model: str):
    """Return read-only wiring info from config/test_node/<model>_testbed.yaml.

    Exposes only the wiring-relevant sections (console / ssh / tftp / power /
    pc.ports) for the monitoring dashboard's "治具接線" block. Password-like
    values are masked so secrets are never echoed to the UI.
    """
    import re
    import yaml

    # Resolve <model>_testbed.yaml case-insensitively (EAP111 -> eap111_...).
    stem = re.sub(r'[^A-Za-z0-9]', '', model).lower()
    path = PROJECT_ROOT / "config" / "test_node" / f"{stem}_testbed.yaml"
    if not path.exists():
        raise HTTPException(404, f"Testbed for model '{model}' not found")
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        raise HTTPException(500, f"Failed to read testbed: {e}")

    ap = (data.get("ap") or {})
    pc = (data.get("pc") or {})

    def _mask(d):
        """Recursively mask password-like keys (never echo secrets to UI)."""
        if isinstance(d, dict):
            out = {}
            for k, v in d.items():
                if isinstance(k, str) and any(
                    s in k.lower() for s in ("password", "passwd", "secret", "token")
                ):
                    out[k] = "••••" if v else ""
                else:
                    out[k] = _mask(v)
            return out
        if isinstance(d, list):
            return [_mask(x) for x in d]
        return d

    return {
        "model": ap.get("model", model),
        "console": _mask(ap.get("console") or {}),
        "ssh": _mask(ap.get("ssh") or {}),
        "tftp": _mask(ap.get("tftp") or {}),
        "power": _mask(ap.get("power") or {}),
        "pc": {
            "label": pc.get("label", ""),
            "ip": pc.get("ip", ""),
            "ports": _mask(pc.get("ports") or {}),
        },
    }


# --- Schedules ---

@app.post("/api/schedules", status_code=201)
async def create_schedule(req: ScheduleCreate):
    sid = db.create_schedule(req.test_id, req.cron, req.enabled)
    if req.enabled:
        from scheduler import add_schedule
        add_schedule(sid, req.test_id, req.cron)
    return {"id": sid}


@app.get("/api/schedules")
async def list_schedules():
    from scheduler import get_next_run
    schedules = db.list_schedules()
    for s in schedules:
        s["next_run"] = get_next_run(s["id"])
    return schedules


@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int):
    from scheduler import remove_schedule
    remove_schedule(schedule_id)
    db.delete_schedule(schedule_id)
    return {"ok": True}


# --- File Editor (whitelist) ---

import fnmatch

EDITABLE_PATTERNS = [
    "scripts/MFG/generated/*.py",
    "config/test_node/*.yaml",
    "config/profiles/*.yaml",
    "pytest.ini",
]


def _is_allowed(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in EDITABLE_PATTERNS)


def _list_editable_files() -> list:
    files = []
    for pattern in EDITABLE_PATTERNS:
        for p in PROJECT_ROOT.glob(pattern):
            files.append(str(p.relative_to(PROJECT_ROOT)))
    return sorted(files)


@app.get("/api/files")
async def list_files():
    return _list_editable_files()


@app.get("/api/files/{path:path}")
async def read_file(path: str):
    if not _is_allowed(path):
        raise HTTPException(403, "Path not in whitelist")
    full = PROJECT_ROOT / path
    if not full.exists():
        raise HTTPException(404, "File not found")
    return {"path": path, "content": full.read_text(encoding="utf-8")}


@app.put("/api/files/{path:path}")
async def write_file(path: str, body: FileContent):
    if not _is_allowed(path):
        raise HTTPException(403, "Path not in whitelist")
    full = PROJECT_ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(body.content, encoding="utf-8")
    return {"ok": True, "path": path}


if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
