#!/bin/bash
# First run: creates the Python environment, generates demo data if there is none,
# builds the statistics and asks for an admin account. Next runs: just starts the app.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Setting up the Python environment (first run only)…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -f data/raw/households.csv ]; then
  echo "No data/raw/households.csv: generating synthetic demo data."
  .venv/bin/python scripts/make_demo_data.py
fi
if [ ! -f data/processed/stats/kpis.csv ]; then
  .venv/bin/python manage.py import
fi
if ! .venv/bin/python -c "from observatory import db; db.init(); import sys; c=db.connect(); sys.exit(0 if c.execute('select count(*) from users').fetchone()[0] else 1)"; then
  echo "Create the first administrator account:"
  read -p "Username: " NAME
  .venv/bin/python manage.py add-user "$NAME" --role admin
fi
.venv/bin/python manage.py serve
