"""GET /api/market-status — current NSE/BSE session state in IST."""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas.common import MarketStatusOut
from ..services import market_status as ms

router = APIRouter(prefix="/api/market-status", tags=["meta"])


@router.get("", response_model=MarketStatusOut)
def status() -> MarketStatusOut:
    return MarketStatusOut(**ms.get_status().as_dict())
