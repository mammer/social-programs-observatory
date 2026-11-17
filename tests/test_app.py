"""End-to-end smoke test: demo data -> pipeline -> API with roles."""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("obs")
    csv = tmp / "households.csv"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_data.py"), "--rows", "3000", "--out", str(csv)], check=True)
    os.environ["OBS_HOUSEHOLDS"] = str(csv)
    import observatory.config as config
    importlib.reload(config)
    # Keep everything the test writes inside the temporary folder
    config.PROCESSED, config.DB_PATH, config.SECRET_FILE = tmp / "processed", tmp / "obs.db", tmp / ".secret_key"
    from observatory import db, pipeline, admin, server
    for m in (db, pipeline, admin, server):
        importlib.reload(m)
    pipeline.run_all()
    from werkzeug.security import generate_password_hash
    with db.session() as con:
        con.execute("INSERT INTO users VALUES ('admin', ?, 'admin', CURRENT_TIMESTAMP)", (generate_password_hash("admin-password-1"),))
        con.execute("INSERT INTO users VALUES ('analyst', ?, 'analyst', CURRENT_TIMESTAMP)", (generate_password_hash("analyst-password-1"),))
    a = server.create_app()
    a.testing = True
    return a


def login(client, user):
    r = client.post("/api/login", json={"username": user, "password": f"{user}-password-1"})
    assert r.status_code == 200


def test_data_needs_login(app):
    assert app.test_client().get("/api/data/stats/kpis").status_code == 401


def test_wrong_password(app):
    r = app.test_client().post("/api/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_stats_and_models(app):
    c = app.test_client()
    login(c, "analyst")
    kpis = {r["metric"]: r["value"] for r in c.get("/api/data/stats/kpis").get_json()}
    assert kpis["records"] == 3000
    assert 0 < kpis["any_aid"] <= 3000
    assert len(c.get("/api/data/stats/areas").get_json()) > 0
    assert len(c.get("/api/data/models/knn_results").get_json()) == 4
    assert "kmeans_k" in c.get("/api/data/models/summary").get_json()


def test_unknown_group_and_bad_name(app):
    c = app.test_client()
    login(c, "analyst")
    assert c.get("/api/data/secret/kpis").status_code == 404
    assert c.get("/api/data/stats/..%2Fx").status_code == 404


def test_admin_only_routes(app):
    c = app.test_client()
    login(c, "analyst")
    assert c.get("/api/audit").status_code == 403
    assert c.post("/api/rebuild").status_code == 403
    c2 = app.test_client()
    login(c2, "admin")
    log = c2.get("/api/audit").get_json()
    assert any(r["action"] == "login" for r in log)


def test_upload_checks_columns(app):
    import io
    c = app.test_client()
    login(c, "admin")
    r = c.post("/api/upload", data={"file": (io.BytesIO(b"area,age\nA,30\n"), "x.csv")}, content_type="multipart/form-data")
    assert r.status_code == 400 and "sex" in r.get_json()["missing"]
