"""ChromaDB-backed historical event memory.

Stores notable Indian market events with descriptions and a sentiment label.
The embedding function is provided by Ollama's embeddings API (free + local).
A deterministic hashing fallback is used when Ollama is offline so unit
tests / dev runs still work.
"""
from __future__ import annotations

import hashlib
from typing import List, Optional

from loguru import logger

from ..config import get_settings
from .ai_engine import get_client

_settings = get_settings()


class _HashEmbedding:
    """Deterministic 256-d hash embedding (offline fallback)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def __call__(self, input: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in input:
            h = hashlib.sha512(text.encode("utf-8")).digest()
            vec = [(h[i] - 128) / 128.0 for i in range(self.dim)]
            out.append(vec)
        return out


class _OllamaEmbedding:
    """Embedding function wrapping the Ollama embeddings endpoint."""

    def __init__(self) -> None:
        self.client = get_client()

    def __call__(self, input: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in input:
            try:
                out.append(self.client.embed(text))
            except Exception as exc:
                logger.warning(f"Ollama embed failed, using hash fallback: {exc}")
                out.append(_HashEmbedding()([text])[0])
        return out


class MemoryStore:
    """Simple wrapper exposing add() and query() over a Chroma collection."""

    def __init__(self, collection: str = "events") -> None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings  # type: ignore

            self.client = chromadb.PersistentClient(
                path=_settings.chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            try:
                emb_fn = _OllamaEmbedding()
            except Exception:
                emb_fn = _HashEmbedding()
            self.col = self.client.get_or_create_collection(
                name=collection,
                embedding_function=emb_fn,  # type: ignore[arg-type]
                metadata={"hnsw:space": "cosine"},
            )
            self.enabled = True
        except Exception as exc:
            logger.warning(f"ChromaDB unavailable: {exc}")
            self.client = None
            self.col = None
            self.enabled = False

    def add(self, doc_id: str, text: str, metadata: Optional[dict] = None) -> None:
        if not self.enabled or self.col is None:
            return
        try:
            self.col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata or {}])
        except Exception as exc:
            logger.warning(f"Memory add failed: {exc}")

    def query(self, text: str, top_k: int = 5) -> List[dict]:
        if not self.enabled or self.col is None:
            return []
        try:
            res = self.col.query(query_texts=[text], n_results=top_k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            ids = res.get("ids", [[]])[0]
            dists = res.get("distances", [[]])[0]
            out = []
            for i, d in enumerate(docs):
                out.append({
                    "id": ids[i] if i < len(ids) else None,
                    "document": d,
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": float(dists[i]) if i < len(dists) else None,
                })
            return out
        except Exception as exc:
            logger.warning(f"Memory query failed: {exc}")
            return []

    def count(self) -> int:
        if not self.enabled or self.col is None:
            return 0
        try:
            return int(self.col.count())
        except Exception:
            return 0


_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
