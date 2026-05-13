"""Alert endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.alerts import Alert
from ..schemas.common import AlertOut
from ..services import alert_engine, universe

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
def list_alerts(limit: int = 100, db: Session = Depends(get_db)) -> list[AlertOut]:
    rows = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
    return [
        AlertOut(
            id=a.id, symbol=a.symbol, kind=a.kind, severity=a.severity,
            title=a.title, message=a.message, price=a.price, created_at=a.created_at,
        )
        for a in rows
    ]


@router.post("/scan")
def scan_alerts(symbols: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Trigger an alert scan. `symbols` is a comma-separated list,
    defaults to the full curated universe."""
    syms = [s.strip() for s in symbols.split(",")] if symbols else universe.all_symbols()[:30]
    new_alerts = alert_engine.scan_for_alerts(db, syms)
    return {"created": len(new_alerts)}
