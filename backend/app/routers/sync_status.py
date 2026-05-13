"""GET /api/sync-status — Live System Sync Panel."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import sync_status

router = APIRouter(prefix="/api/sync-status", tags=["system"])


@router.get("")
def status():
    return sync_status.get_status()
