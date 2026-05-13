"""Ollama-backed AI engine.

Used for:
- Natural-language reasoning around computed signals
- Free-form chat over market context
- Embeddings (when calling memory_engine)

If Ollama isn't reachable, the engine falls back to deterministic templates
so the rest of the app keeps working.
"""
from __future__ import annotations

import json
from typing import List, Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from ..config import get_settings


_settings = get_settings()


class OllamaClient:
    """Tiny HTTP wrapper around the local Ollama daemon."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        embed_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or _settings.ollama_base_url).rstrip("/")
        self.model = model or _settings.ollama_model
        self.embed_model = embed_model or _settings.ollama_embed_model
        self.timeout = timeout or _settings.ollama_timeout

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()

    def is_alive(self) -> bool:
        try:
            with httpx.Client(timeout=3) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        try:
            data = self._post(
                "/api/chat",
                {
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": temperature},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            return data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning(f"Ollama chat error: {exc}")
            raise

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
    def embed(self, text: str) -> List[float]:
        data = self._post(
            "/api/embeddings",
            {"model": self.embed_model, "prompt": text},
        )
        emb = data.get("embedding") or []
        return [float(x) for x in emb]


_client: Optional[OllamaClient] = None


def get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


SYSTEM_ANALYST = (
    "You are BharatQuant, a careful Indian-equity research assistant. "
    "Speak like a professional buy-side analyst. Be concise, structured, and "
    "always include a brief educational disclaimer that this is not "
    "financial advice. Prefer bullet points. When the user gives you "
    "indicator JSON, ground every claim in those numbers. Use Indian "
    "market terminology (Nifty, Bank Nifty, FII/DII, NSE/BSE)."
)


def explain_signal(symbol: str, indicators_dict: dict, signal_dict: dict,
                   patterns: List[str], extra_context: str = "") -> str:
    """LLM-generated explanation for a single signal."""
    client = get_client()
    payload = {
        "symbol": symbol,
        "indicators": indicators_dict,
        "signal": signal_dict,
        "patterns": patterns,
        "extra_context": extra_context,
    }
    user = (
        "Given the following Indian stock analysis, write a short (max 8 bullet "
        "points) trading thesis. End with a one-line **Disclaimer:** that this "
        "is for education only.\n\n"
        f"```json\n{json.dumps(payload, default=str, indent=2)}\n```"
    )
    try:
        if client.is_alive():
            return client.chat(SYSTEM_ANALYST, user, temperature=0.25)
    except Exception as exc:
        logger.warning(f"explain_signal LLM unavailable: {exc}")
    return _template_explanation(symbol, signal_dict, patterns)


def chat_with_context(question: str, context_blocks: List[str]) -> str:
    """Free-form chat with extra grounding blocks (news, indicators, memories)."""
    client = get_client()
    ctx = "\n\n---\n".join(context_blocks) if context_blocks else "(no extra context provided)"
    user = (
        f"## Context\n{ctx}\n\n## Question\n{question}\n\n"
        "Answer using the context where possible. If unsure, say so. "
        "End with: *Educational only — not financial advice.*"
    )
    try:
        if client.is_alive():
            return client.chat(SYSTEM_ANALYST, user, temperature=0.3)
    except Exception as exc:
        logger.warning(f"chat LLM unavailable: {exc}")
    return _template_chat(question, context_blocks)


def _template_explanation(symbol: str, signal: dict, patterns: List[str]) -> str:
    action = signal.get("action", "HOLD")
    conf = signal.get("confidence", 0)
    sl = signal.get("stoploss")
    t1 = signal.get("target1")
    t2 = signal.get("target2")
    rr = signal.get("rr")
    bullets = [
        f"- Recommendation: **{action}** on {symbol} with {conf}% confidence.",
        f"- Stoploss: {sl} | T1: {t1} | T2: {t2} | R:R: {rr}",
    ]
    if patterns:
        bullets.append("- Patterns: " + ", ".join(patterns[:5]))
    bullets.append("- Reasoning: " + signal.get("reasoning", "Mixed indicators."))
    bullets.append("\n*Disclaimer: Educational only — not financial advice.*")
    return "\n".join(bullets)


def _template_chat(question: str, context_blocks: List[str]) -> str:
    out = [
        f"**Q:** {question}",
        "",
        "_(Local LLM unavailable — showing rule-based summary.)_",
        "",
        "Top context observed:",
    ]
    for blk in context_blocks[:5]:
        out.append(f"- {blk[:240]}{'...' if len(blk) > 240 else ''}")
    out.append("\n*Disclaimer: Educational only — not financial advice.*")
    return "\n".join(out)
