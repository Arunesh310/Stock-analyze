"""WebSocket: streams live tick + alert updates to the frontend.

Implementation note: we emulate ticks by polling our cached quote service
on a short interval; this is intentional so we don't depend on any paid
real-time websocket feed. Replace with a true feed if you have one.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..database import db_session
from ..services import alert_engine, market_data, market_status, universe

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        msg = json.dumps(payload, default=str)
        dead: List[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.discard(ws)


manager = ConnectionManager()


async def _tick_loop() -> None:
    """Periodically push quote refreshes + alert scans to subscribers.

    Cadence:
      - market open       : 30 s
      - pre-open/after    : 90 s
      - closed (weekend)  : 300 s
    Status pings go out every loop so the UI knows when we shift cadence.
    """
    syms = ["^NSEI", "^NSEBANK", "^INDIAVIX", "INR=X"] + universe.all_symbols()[:15]
    cycle = 0
    while True:
        status = market_status.get_status()
        if status.state == "regular":
            sleep_s = 30
        elif status.state in {"preopen", "afterhours"}:
            sleep_s = 90
        else:
            sleep_s = 300

        try:
            if manager.active:
                # Always send a status update with each cycle for UI
                await manager.broadcast({
                    "type": "status",
                    "data": status.as_dict(),
                })

                # Only fetch quotes when there's a real session or recent close
                if status.state in {"regular", "preopen", "afterhours"} or cycle == 0:
                    quotes = market_data.get_quotes(syms)
                    await manager.broadcast({
                        "type": "ticks",
                        "data": [q.model_dump(mode="json") for q in quotes],
                    })

                if status.is_open and cycle % 5 == 0:
                    try:
                        with db_session() as db:
                            alerts = alert_engine.scan_for_alerts(
                                db, universe.all_symbols()[:20]
                            )
                            if alerts:
                                await manager.broadcast({
                                    "type": "alerts",
                                    "data": [
                                        {
                                            "id": a.id,
                                            "symbol": a.symbol,
                                            "kind": a.kind,
                                            "severity": a.severity,
                                            "title": a.title,
                                            "message": a.message,
                                            "price": a.price,
                                            "created_at": a.created_at.isoformat(),
                                        }
                                        for a in alerts
                                    ],
                                })
                    except Exception as exc:
                        logger.warning(f"WS alert scan error: {exc}")
            cycle += 1
        except Exception as exc:
            logger.warning(f"WS tick loop error: {exc}")
        await asyncio.sleep(sleep_s)


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "msg": "connected"}))
        while True:
            # We mostly push; just keep the connection alive.
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


def start_background_tasks(loop: asyncio.AbstractEventLoop) -> None:
    """Schedule the tick loop as a background task."""
    loop.create_task(_tick_loop())
