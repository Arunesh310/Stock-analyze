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
import tempfile
from pathlib import Path

# Ensure the backend package is importable when Vercel runs this file
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent  # backend/
sys.path.insert(0, str(_BACKEND_DIR))


def _writable_tmp_dir() -> str:
    """Pick a writable scratch directory.

    Vercel/Lambda only allow writes under ``/tmp``. tempfile.gettempdir()
    returns that on Linux. On Windows local dev this falls back to the
    standard temp folder so we never crash on import.
    """
    candidates = ["/tmp", tempfile.gettempdir()]
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".bharatquant_probe")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return path
        except OSError:
            continue
    # Last resort — shouldn't happen.
    return "/tmp"


_TMP = _writable_tmp_dir()
_DB_PATH = os.path.join(_TMP, "bharatquant.db")

# Pydantic Settings prefers env vars over .env files, but we also explicitly
# OVERRIDE here (not setdefault) because anything left over from build-time
# can otherwise win — and our local .env carries a sqlite:///./app.db value
# that won't resolve under /var/task at runtime.
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SERVERLESS"] = "1"
os.environ.setdefault("CORS_ORIGINS", "*")

print(f"[bharatquant] serverless boot — DB={os.environ['DATABASE_URL']}", file=sys.stderr)

from app.main import create_app  # noqa: E402

app = create_app()
