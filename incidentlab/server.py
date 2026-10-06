import asyncio
import json
import sqlite3
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .detector import Detector
from .schema import LogWindow
from .simulation import SCENARIOS, make_window

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
lock = threading.Lock()
detector = None


@contextmanager
def connection():
    db = sqlite3.connect(ARTIFACTS / "incidents.sqlite3")
    try:
        with db:
            yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    global detector
    ARTIFACTS.mkdir(exist_ok=True)
    checkpoint = ARTIFACTS / "models" / "detector.joblib"
    if not checkpoint.exists():
        raise RuntimeError("Run datasets, train, and validate stages first; see README.md")
    detector = await asyncio.to_thread(Detector.load, checkpoint)
    if detector.threshold is None:
        raise RuntimeError("Checkpoint must be calibrated before serving")
    (ARTIFACTS / "calibration.json").write_text(json.dumps(detector.calibration, indent=2), encoding="utf-8")
    with connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS windows (id INTEGER PRIMARY KEY, created TEXT, source TEXT, result TEXT, observations TEXT)")
    yield


app = FastAPI(title="IncidentLab", version="0.2.0", lifespan=lifespan)


def process(window, source):
    with lock:
        result = detector.analyze(window)
        created = datetime.now(timezone.utc).isoformat()
        with connection() as db:
            cursor = db.execute("INSERT INTO windows(created, source, result, observations) VALUES (?, ?, ?, ?)",
                                (created, source, json.dumps(result), window.model_dump_json()))
            result.update(id=cursor.lastrowid, created=created, source=source)
        return result


@app.get("/")
def dashboard():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health():
    return {"ready": detector is not None, "calibration": detector.calibration if detector else None,
            "mode": "local research prototype", "llm_enabled": False}


@app.post("/api/analyze")
def analyze(window: LogWindow):
    return process(window, "submitted")


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str
    seed: int = Field(default=20000, ge=0, le=2147483647)
    step: int = Field(default=0, ge=0, le=1000000)


@app.post("/api/demo")
def demo(request: DemoRequest):
    if request.scenario not in SCENARIOS:
        raise HTTPException(422, "Unknown scenario")
    return process(make_window(request.seed, request.scenario, request.step), "synthetic_demo")


@app.get("/api/history")
def history():
    with connection() as db:
        rows = db.execute("SELECT id, created, source, result FROM windows ORDER BY id DESC LIMIT 50").fetchall()
    return [{"id": i, "created": created, "source": source, **json.loads(result)} for i, created, source, result in rows]


@app.get("/api/evaluation")
def evaluation():
    file = ARTIFACTS / "evaluation.json"
    if not file.exists():
        raise HTTPException(404, "Run python -m incidentlab.evaluate first")
    return json.loads(file.read_text(encoding="utf-8"))
