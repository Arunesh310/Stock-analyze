"""Chat endpoint — natural-language Q&A grounded in market + news context."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter

from ..schemas.common import ChatRequest, ChatResponse
from ..services import market_data, news_engine, signal_engine
from ..services.ai_engine import chat_with_context
from ..services.knowledge_base import query_concepts
from ..services.memory_engine import get_memory_store

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    blocks: List[str] = []

    if req.symbols:
        for s in req.symbols[:5]:
            try:
                q = market_data.get_quote(s)
                sig, ind, pats = signal_engine.build_signal(s)
                blocks.append(
                    "STOCK CONTEXT: "
                    + json.dumps({
                        "symbol": s,
                        "quote": q.model_dump(mode="json"),
                        "indicators": ind.model_dump(),
                        "signal": sig.model_dump(mode="json"),
                        "patterns": pats,
                    }, default=str)
                )
            except Exception:
                continue

    used_news_count = 0
    if req.context_news:
        items = news_engine.fetch_news()[:8]
        used_news_count = len(items)
        if items:
            blocks.append(
                "NEWS CONTEXT: "
                + json.dumps([
                    {
                        "title": n.title,
                        "source": n.source,
                        "sentiment": n.sentiment,
                        "impacted_sectors": n.impacted_sectors,
                        "impacted_symbols": n.impacted_symbols,
                    } for n in items
                ])
            )

    mem = get_memory_store()
    mem_hits = mem.query(req.question, top_k=3) if mem.enabled else []
    if mem_hits:
        blocks.append(
            "MEMORY CONTEXT (similar historical events): "
            + json.dumps([
                {"event": h["document"], "meta": h["metadata"]}
                for h in mem_hits
            ])
        )

    # Trading knowledge base (Wyckoff / VSA / SMC / risk-mgmt / psychology).
    kb_hits = query_concepts(req.question, top_k=3)
    if kb_hits:
        blocks.append(
            "TRADING KNOWLEDGE: "
            + json.dumps([
                {"concept": h["document"], "meta": h["metadata"]}
                for h in kb_hits
            ])
        )

    answer = chat_with_context(req.question, blocks)
    return ChatResponse(
        answer=answer,
        used_symbols=req.symbols,
        used_news_count=used_news_count,
        used_memories=len(mem_hits) + len(kb_hits),
    )
