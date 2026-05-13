"""Vercel Python runtime entry-point.

This file is the entrypoint when the backend is deployed as a Vercel
``experimentalServices`` Python service. It imports the FastAPI ``app``
defined in ``app.main`` and exposes it as ``app`` at module level so
Vercel's ASGI adapter can pick it up.

Notes vs. local dev:
- The APScheduler-based background jobs are disabled here because each
  serverless invocation is stateless; instead, you should call the
  cycle endpoints on a Vercel cron (or external scheduler).
- WebSocket endpoints are not supported on Vercel's serverless runtime —
  the frontend gracefully falls back to polling when WS is unreachable.
- SQLite writes go to ``/tmp`` (the only writeable path on Vercel) and
  are wiped between cold starts; for persistent state, point
  ``DATABASE_URL`` at an external Postgres (Neon / Supabase / Railway).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the backend package is importable when Vercel runs this file
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent  # backend/
sys.path.insert(0, str(_BACKEND_DIR))

# Force SQLite into /tmp (the only writeable filesystem on Vercel).
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/bharatquant.db")
# Tell the app it's running serverless so it can skip scheduler/WS work.
os.environ.setdefault("SERVERLESS", "1")

from app.main import create_app  # noqa: E402

app = create_app()
