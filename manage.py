"""Command-line entry point.

  python manage.py import [step ...]      rebuild the statistics from data/raw/households.csv
  python manage.py add-user NAME [--role admin|analyst]
  python manage.py serve                  start the app on http://127.0.0.1:8050
  python manage.py audit [N]              show the last N audit entries
"""
import argparse
import getpass
import os

from werkzeug.security import generate_password_hash

from observatory import db, pipeline
from observatory.config import HOST, PORT


def main():
    p = argparse.ArgumentParser(description="Social programmes observatory")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("import"); i.add_argument("steps", nargs="*", help="any of: " + ", ".join(pipeline.STEPS))
    u = sub.add_parser("add-user"); u.add_argument("name"); u.add_argument("--role", default="analyst", choices=["admin", "analyst"])
    sub.add_parser("serve")
    a = sub.add_parser("audit"); a.add_argument("n", nargs="?", type=int, default=30)
    args = p.parse_args()

    db.init()
    if args.cmd == "import":
        bad = [s for s in args.steps if s not in pipeline.STEPS]
        if bad:
            raise SystemExit(f"Unknown step(s): {bad}. Choose from {list(pipeline.STEPS)}")
        pipeline.run_all(args.steps or None)
    elif args.cmd == "add-user":
        # OBS_PASSWORD lets scripts and tests create a user without a prompt.
        pw = os.environ.get("OBS_PASSWORD") or getpass.getpass("Password (min. 10 characters): ")
        if len(pw) < 10:
            raise SystemExit("Password too short.")
        if not os.environ.get("OBS_PASSWORD") and pw != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords do not match.")
        with db.session() as con:
            con.execute("INSERT OR REPLACE INTO users(username, password_hash, role) VALUES (?,?,?)",
                        (args.name, generate_password_hash(pw), args.role))
        print(f"User '{args.name}' saved with role '{args.role}'.")
    elif args.cmd == "serve":
        from observatory.server import create_app
        print(f"Open http://{HOST}:{PORT} in your browser (Ctrl+C to stop).")
        create_app().run(host=HOST, port=PORT, debug=False)
    elif args.cmd == "audit":
        with db.session() as con:
            for r in con.execute("SELECT at, username, action, detail FROM audit_log ORDER BY id DESC LIMIT ?", (args.n,)):
                print(dict(r))


if __name__ == "__main__":
    main()
