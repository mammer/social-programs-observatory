"""Admin features: replace the household file from the browser and rebuild the statistics."""
import csv
import io
import shutil
import threading
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from . import db, pipeline
from .auth import login_required
from .config import HOUSEHOLDS, PROGRAMS

bp = Blueprint("admin", __name__)

REQUIRED = ["area", "age", "sex", "social_status", "health_cover", "work_sector", "household_size", *PROGRAMS]
MAX_BYTES = 60 * 1024 * 1024
JOB = {"running": False, "log": [], "started": None, "finished": None, "error": None}
_lock = threading.Lock()


@bp.post("/api/upload")
@login_required(role="admin")
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify(error="bad_request"), 400
    if not f.filename.lower().endswith(".csv"):
        return jsonify(error="wrong_type", expected=".csv"), 400
    raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return jsonify(error="too_large"), 400
    try:
        cols = next(csv.reader(io.StringIO(raw[:200000].decode("utf-8-sig"))), [])
    except UnicodeDecodeError:
        return jsonify(error="unreadable"), 400
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        return jsonify(error="missing_columns", missing=missing), 400
    archive = HOUSEHOLDS.parent / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    if HOUSEHOLDS.exists():
        shutil.copy2(HOUSEHOLDS, archive / f"{datetime.now():%Y%m%d-%H%M%S}_{HOUSEHOLDS.name}")
    HOUSEHOLDS.write_bytes(raw)
    db.audit(session["user"], "upload", f"{f.filename} ({len(raw):,} bytes)")
    return jsonify(ok=True, saved=HOUSEHOLDS.name, columns=len(cols))


def _job():
    def log(msg):
        JOB["log"].append(f"{datetime.now():%H:%M:%S} {msg}")
    pipeline.log = log
    try:
        pipeline.run_all()
    except Exception as e:  # keep the app alive, show the error
        JOB["error"] = str(e)
        log("ERROR: " + str(e))
        traceback.print_exc()
    finally:
        pipeline.log = print
        JOB["running"], JOB["finished"] = False, f"{datetime.now():%Y-%m-%d %H:%M:%S}"


@bp.post("/api/rebuild")
@login_required(role="admin")
def rebuild():
    with _lock:
        if JOB["running"]:
            return jsonify(error="already_running"), 409
        JOB.update(running=True, log=[], started=f"{datetime.now():%Y-%m-%d %H:%M:%S}", finished=None, error=None)
    db.audit(session["user"], "rebuild")
    threading.Thread(target=_job, daemon=True).start()
    return jsonify(ok=True)


@bp.get("/api/rebuild")
@login_required(role="admin")
def rebuild_status():
    return jsonify(JOB)


@bp.get("/api/sources")
@login_required()
def sources():
    p = HOUSEHOLDS
    return jsonify([{"target": "households", "file": p.name, "exists": p.exists(),
                     "size": p.stat().st_size if p.exists() else None,
                     "modified": f"{datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}" if p.exists() else None}])
