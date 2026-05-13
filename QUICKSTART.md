# 🚀 BharatQuant — Quick Start

This file is the TL;DR. See `README.md` for the full guide.

## Prerequisites
- **Python 3.11+**
- **Node.js 20+** (with npm)
- **Ollama** (for the local LLM): https://ollama.com/download

## 1) Pull free local models (one-time)
```bash
ollama pull llama3
ollama pull nomic-embed-text
```

Make sure the Ollama daemon is running:
```bash
ollama serve   # or start the desktop app
```

## 2) One-shot setup

### Windows (PowerShell)
```powershell
.\scripts\setup.ps1
```

### macOS / Linux
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

## 3) Seed historical event memory, knowledge base + default watchlists
```bash
cd backend
# Activate venv first:
#   Windows:  .\.venv\Scripts\Activate.ps1
#   *nix:     source .venv/bin/activate
python -m app.scripts.seed_memory
python -m app.scripts.seed_knowledge
python -m app.scripts.seed_watchlists
```

## 4) Run

Terminal 1 — backend (FastAPI on :8000):
```bash
cd backend
uvicorn app.main:app --reload
```

Terminal 2 — frontend (Next.js on :3000):
```bash
cd frontend
npm run dev
```

Open: **http://localhost:3000**

API docs (Swagger): **http://localhost:8000/docs**

## 5) (Optional) Docker

```bash
docker compose up --build
# After containers boot:
docker exec -it bharatquant-ollama ollama pull llama3
docker exec -it bharatquant-ollama ollama pull nomic-embed-text
docker exec -it bharatquant-backend python -m app.scripts.seed_memory
docker exec -it bharatquant-backend python -m app.scripts.seed_knowledge
docker exec -it bharatquant-backend python -m app.scripts.seed_watchlists
```

## 6) Watch the AI learn

After ~10 minutes of running, open the new **AI Brain** pages in the sidebar:

- `/performance` — accuracy, win-rate, sector × regime heatmap
- `/profit` — cumulative simulated P&L (₹10k per signal)
- `/learning` — failure reasons, indicator edge, learning log
- `/regime` — current Indian-market regime + history
- `/confidence` — confidence calibration buckets

You can also force a learning pass instead of waiting for the 15-min job:
```bash
curl -X POST http://localhost:8000/api/validate-signals
```

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. Nothing here
is investment, financial, legal, tax, or trading advice. Markets carry risk —
do your own research and consult a SEBI-registered advisor.
