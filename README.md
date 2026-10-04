# Autonomous Market Intelligence Agent

Locally hosted AI agent (Python · FastAPI · LangChain · Ollama Llama 3 · Docker) that continuously pulls
live crypto market data from the free public CoinGecko REST API, computes indicators, and uses a local LLM
in a multi-step chain to produce actionable insights, served through a documented REST API.

## Architecture
```
CoinGecko API -> indicators (SMA, RSI, volatility, drawdown, trend)
              -> LangChain step 1: market summary
              -> LangChain step 2: risk/anomaly analysis
              -> LangChain step 3: structured JSON insights (Pydantic-validated, auto-retry)
              -> SQLite -> FastAPI endpoints
Background task re-runs the whole pipeline every FETCH_INTERVAL_SECONDS (autonomous).
```

## Run with Docker (recommended)
```bash
cp .env.example .env
docker compose up --build
```
First start downloads Llama 3 (~4.7 GB) via the `model-puller` service. Then open http://localhost:8000/docs

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /health | liveness |
| GET | /agent/status | autonomous loop status |
| GET | /market/snapshot?coins=bitcoin,ethereum | live data + indicators (no LLM) |
| POST | /analyze | run the full agent now |
| GET | /insights/latest | latest stored report |
| GET | /insights/history?limit=10 | past reports |

## Run locally without Docker
```bash
ollama pull llama3
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
## Tests
`pytest` (uses a fake LLM and mocked market data; no Ollama or internet needed).

*Educational project. Not financial advice.*
