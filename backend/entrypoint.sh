#!/bin/sh
# Wait for Postgres, run migrations, seed note, start API.
set -e
echo "Waiting for database..."
python - <<'EOF'
import os, re, time
from sqlalchemy import create_engine, text

raw = os.environ["DATABASE_URL"]
url = ("postgresql+psycopg://" + raw[len("postgresql://"):]
       if raw.startswith("postgresql://") else raw)
for i in range(60):
    try:
        eng = create_engine(url)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        print("Database ready.")
        break
    except Exception as e:
        if i == 59:
            raise
        time.sleep(2)
EOF
alembic upgrade head
if [ "${SEED_DEMO:-false}" = "true" ]; then
  echo "Seeding demo data..."
  DATABASE_URL="$DATABASE_URL" SEED_DEMO=true python - <<'EOF'
import os
os.environ.setdefault("DATABASE_URL", os.environ["DATABASE_URL"])
from app.database import SessionLocal
from app.seed import seed_demo
db = SessionLocal()
try:
    print(seed_demo(db))
finally:
    db.close()
EOF
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
