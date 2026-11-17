"""Import pipeline: household file -> aggregate statistics (CSV files).

Run with `python manage.py import`. Each step can also run alone, so a new
analysis can be added as a new step without touching the others.
"""
import subprocess
import sys

from . import db
from .config import HOUSEHOLDS, PROCESSED, ANALYSIS

log = print  # the web app replaces this to show progress in the browser


def run(script, *args):
    log(f"  -> {script}")
    res = subprocess.run([sys.executable, "-I", str(ANALYSIS / script), *map(str, args)], capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip().splitlines()
        raise RuntimeError(f"{script} failed: {err[-1] if err else res.returncode}")


def step_stats():
    out = PROCESSED / "stats"
    out.mkdir(parents=True, exist_ok=True)
    run("stats.py", HOUSEHOLDS, out)


def step_models():
    out = PROCESSED / "models"
    out.mkdir(parents=True, exist_ok=True)
    feats = PROCESSED / "_features_tmp.csv"
    run("features.py", HOUSEHOLDS, feats)
    try:
        run("models.py", feats, out)
    finally:
        feats.unlink(missing_ok=True)  # household-level features are not kept


STEPS = {"stats": step_stats, "models": step_models}


def run_all(only=None):
    if not HOUSEHOLDS.exists():
        raise RuntimeError(f"{HOUSEHOLDS} not found. Run `python scripts/make_demo_data.py` for demo data.")
    for name, fn in STEPS.items():
        if only and name not in only:
            continue
        log(f"[{name}]")
        fn()
    db.init()
    with db.session() as con:
        con.execute("INSERT OR REPLACE INTO meta VALUES ('source', ?)", (HOUSEHOLDS.name,))
    log("Import finished.")
