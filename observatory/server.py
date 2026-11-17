"""Flask web server: JSON API + single-page front end.

Add a new module by: (1) a pipeline step that writes CSVs into data/processed/<group>/,
(2) adding <group> to DATA_GROUPS, (3) a page in web/app.js that calls /api/data/<group>/<file>.
"""
import csv
import json
import secrets
import time
from datetime import timedelta

from flask import Flask, jsonify, request, session, send_from_directory, abort
from werkzeug.security import check_password_hash

from . import db
from .auth import login_required
from .config import PROCESSED, WEB, SECRET_FILE, SESSION_HOURS

DATA_GROUPS = {"stats", "models"}
_cache = {}


def _secret():
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
        SECRET_FILE.chmod(0o600)
    return SECRET_FILE.read_text().strip()


def _num(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v and "e" not in v.lower() else f
    except ValueError:
        return v


def read_csv(path):
    key = (str(path), path.stat().st_mtime)
    if key not in _cache:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:  # numbers back to numbers, empty cells to null
            for k, v in r.items():
                r[k] = _num(v)
        _cache[key] = rows
    return _cache[key]


def create_app():
    db.init()
    app = Flask(__name__, static_folder=None)
    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    app.config.update(SECRET_KEY=_secret(), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=SESSION_HOURS), JSON_AS_ASCII=False,
                      MAX_CONTENT_LENGTH=64 * 1024 * 1024)

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- front end
    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(WEB, name)

    # ---------- auth
    @app.post("/api/login")
    def login():
        body = request.get_json(silent=True) or {}
        with db.session() as con:
            u = con.execute("SELECT * FROM users WHERE username=?", (body.get("username", ""),)).fetchone()
        if not u or not check_password_hash(u["password_hash"], body.get("password", "")):
            time.sleep(1.0)
            db.audit(body.get("username", "?"), "login_failed")
            return jsonify(error="invalid_credentials"), 401
        session.clear()
        session.permanent = True
        session["user"], session["role"] = u["username"], u["role"]
        db.audit(u["username"], "login")
        return jsonify(user=u["username"], role=u["role"])

    @app.post("/api/logout")
    def logout():
        if "user" in session:
            db.audit(session["user"], "logout")
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        if "user" not in session:
            return jsonify(user=None)
        with db.session() as con:
            src = con.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        return jsonify(user=session["user"], role=session["role"], source=src["value"] if src else None)

    # ---------- statistics (aggregates only)
    @app.get("/api/data/<group>/<name>")
    @login_required()
    def data(group, name):
        if group not in DATA_GROUPS or not name.replace("_", "").isalnum():
            abort(404)
        if name == "summary":
            path = PROCESSED / group / "summary.json"
            if not path.exists():
                abort(404)
            return jsonify(json.loads(path.read_text()))
        path = PROCESSED / group / f"{name}.csv"
        if not path.exists():
            return jsonify(error="not_imported", hint="run: python manage.py import"), 404
        return jsonify(read_csv(path))

    @app.get("/api/audit")
    @login_required(role="admin")
    def audit_log():
        with db.session() as con:
            rows = con.execute("SELECT at, username, action, detail FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
        return jsonify([dict(r) for r in rows])

    return app
