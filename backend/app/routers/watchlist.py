"""Watchlist CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.watchlist import Watchlist, WatchlistItem
from ..schemas.common import WatchlistAddSymbol, WatchlistCreate, WatchlistOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _to_out(wl: Watchlist) -> WatchlistOut:
    return WatchlistOut(id=wl.id, name=wl.name, symbols=[i.symbol for i in wl.items])


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(db: Session = Depends(get_db)) -> list[WatchlistOut]:
    rows = db.query(Watchlist).order_by(Watchlist.id.asc()).all()
    return [_to_out(w) for w in rows]


@router.post("", response_model=WatchlistOut, status_code=201)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)) -> WatchlistOut:
    if db.query(Watchlist).filter_by(name=payload.name).first():
        raise HTTPException(status_code=409, detail="Watchlist already exists")
    wl = Watchlist(name=payload.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return _to_out(wl)


@router.delete("/{wid}", status_code=204)
def delete_watchlist(wid: int, db: Session = Depends(get_db)) -> None:
    wl = db.get(Watchlist, wid)
    if not wl:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(wl)
    db.commit()


@router.post("/{wid}/symbols", response_model=WatchlistOut)
def add_symbol(wid: int, payload: WatchlistAddSymbol, db: Session = Depends(get_db)) -> WatchlistOut:
    wl = db.get(Watchlist, wid)
    if not wl:
        raise HTTPException(status_code=404, detail="Not found")
    if any(i.symbol == payload.symbol for i in wl.items):
        raise HTTPException(status_code=409, detail="Symbol already present")
    wl.items.append(WatchlistItem(symbol=payload.symbol, note=payload.note))
    db.commit()
    db.refresh(wl)
    return _to_out(wl)


@router.delete("/{wid}/symbols/{symbol}", response_model=WatchlistOut)
def remove_symbol(wid: int, symbol: str, db: Session = Depends(get_db)) -> WatchlistOut:
    wl = db.get(Watchlist, wid)
    if not wl:
        raise HTTPException(status_code=404, detail="Not found")
    wl.items = [i for i in wl.items if i.symbol != symbol]
    db.commit()
    db.refresh(wl)
    return _to_out(wl)
