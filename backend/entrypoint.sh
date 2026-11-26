#!/bin/sh
# Wait for Postgres, run migrations, seed note, start API.
set -e
echo "Waiting for database..."
python - <<'EOF'
import os, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
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
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
