"""Local trading-knowledge base built on top of ChromaDB.

This sits *next to* the historical-event ``memory_engine`` but in a
separate collection (``knowledge``) so we can:

- retrieve relevant *trading concepts* during AI explanations
  ("current setup resembles a Wyckoff accumulation"),
- show educational context in the chat UI,
- ground LLM answers in well-known TA / market-psychology principles.

Everything is local + offline-friendly. The seed script populates the
collection with concise notes on:

    Trend following, momentum, mean reversion, Wyckoff method, Dow Theory,
    Volume Spread Analysis, Smart Money Concepts, market structure, price
    action, risk management, market psychology, sector rotation,
    institutional accumulation / distribution.

NOTHING in here is investment advice.
"""
from __future__ import annotations

from typing import List, Optional

from loguru import logger

from .memory_engine import MemoryStore


_kb: Optional[MemoryStore] = None


def get_knowledge_base() -> MemoryStore:
    global _kb
    if _kb is None:
        _kb = MemoryStore(collection="knowledge")
    return _kb


def query_concepts(text: str, top_k: int = 5) -> List[dict]:
    """Find the closest trading concepts to ``text``."""
    try:
        return get_knowledge_base().query(text, top_k=top_k)
    except Exception as exc:
        logger.warning(f"knowledge query failed: {exc}")
        return []


def count() -> int:
    try:
        return get_knowledge_base().count()
    except Exception:
        return 0
