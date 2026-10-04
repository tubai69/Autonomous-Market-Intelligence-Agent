import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query

from app import store
from app.agent import MarketAgent
from app.config import settings
from app.data_sources import compute_metrics, fetch_market_data
from app.schemas import AnalyzeRequest, AssetMetrics, Report

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

state = {"agent": None, "last_run": None, "last_error": None, "cycles": 0}


def get_agent() -> MarketAgent:
    if state["agent"] is None:
        state["agent"] = MarketAgent()
    return state["agent"]


async def _cycle(coins=None) -> Report:
    report = await asyncio.to_thread(get_agent().run_cycle, coins)
    store.save_report(report)
    state.update(last_run=report.created_at, last_error=report.error, cycles=state["cycles"] + 1)
    return report


async def _loop():
    await asyncio.sleep(5)
    while True:
        try:
            await _cycle()
        except Exception as e:
            state["last_error"] = str(e)
            log.exception("Autonomous cycle failed")
        await asyncio.sleep(settings.fetch_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_loop()) if settings.autonomous_enabled else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="Autonomous Market Intelligence Agent",
    description="Local LLM (Ollama + LangChain) agent that continuously analyzes live market data.",
    version="1.0.0", lifespan=lifespan,
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "model": settings.ollama_model, "autonomous": settings.autonomous_enabled}


@app.get("/agent/status", tags=["system"])
def agent_status():
    return {**{k: v for k, v in state.items() if k != "agent"},
            "interval_seconds": settings.fetch_interval_seconds, "tracked_coins": settings.coin_list}


@app.get("/market/snapshot", response_model=list[AssetMetrics], tags=["market"])
def snapshot(coins: Optional[str] = Query(None, description="Comma-separated CoinGecko ids")):
    """Live market data + computed indicators (no LLM)."""
    try:
        ids = [c.strip() for c in coins.split(",")] if coins else None
        return compute_metrics(fetch_market_data(ids))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Upstream market API error: {e}")


@app.post("/analyze", response_model=Report, tags=["insights"])
async def analyze(req: Optional[AnalyzeRequest] = None):
    """Trigger the full agent workflow on demand."""
    try:
        return await _cycle(req.coins if req else None)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Upstream market API error: {e}")


@app.get("/insights/latest", response_model=Report, tags=["insights"])
def latest():
    r = store.latest_report()
    if not r:
        raise HTTPException(404, "No report yet. Wait for the first cycle or POST /analyze.")
    return r


@app.get("/insights/history", response_model=list[Report], tags=["insights"])
def history(limit: int = Query(10, ge=1, le=100)):
    return store.list_reports(limit)
