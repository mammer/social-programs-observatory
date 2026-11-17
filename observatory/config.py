"""Central configuration. Every path and setting the app uses is defined here."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
DB_PATH = DATA / "observatory.db"
WEB = Path(__file__).resolve().parent / "web"
ANALYSIS = ROOT / "analysis"

# The one input file: one row per household (see docs/data-format.md).
HOUSEHOLDS = Path(os.environ.get("OBS_HOUSEHOLDS", RAW / "households.csv"))

# Aid programmes are the columns named program_<x>. Their display names live in web/i18n.js.
PROGRAMS = ["program_a", "program_b", "program_c", "program_d", "program_e", "program_f"]

# Server: local only by default. Do not expose this app on a public network.
HOST = os.environ.get("OBS_HOST", "127.0.0.1")
PORT = int(os.environ.get("OBS_PORT", "8050"))
SESSION_HOURS = 8
SECRET_FILE = DATA / ".secret_key"
