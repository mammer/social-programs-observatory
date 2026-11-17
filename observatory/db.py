"""SQLite storage for users, the audit log and small key/value metadata.

Household data never goes into the database: the pipeline turns the input file
into aggregate CSV files, and the app only serves those.
"""
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'analyst',      -- 'admin' can import data and read the log
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT DEFAULT CURRENT_TIMESTAMP,
    username TEXT,
    action TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with session() as con:
        con.executescript(SCHEMA)


def audit(username, action, detail=""):
    with session() as con:
        con.execute("INSERT INTO audit_log(username, action, detail) VALUES (?,?,?)", (username, action, detail[:500]))
