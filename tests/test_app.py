import os
os.environ["AUTONOMOUS_ENABLED"] = "false"
os.environ["DB_PATH"] = "/tmp/test_insights.db"

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agent as agent_mod
import app.main as main
from app.data_sources import compute_metrics

RAW = [{"id": "bitcoin", "symbol": "btc", "current_price": 100.0,
        "price_change_percentage_1h_in_currency": 0.5, "price_change_percentage_24h_in_currency": 2.0,
        "price_change_percentage_7d_in_currency": 5.0,
        "sparkline_in_7d": {"price": [90 + i * 0.06 for i in range(168)]}}]

JSON = ('{"market_outlook":"Mild uptrend","insights":[{"asset":"bitcoin","signal":"bullish",'
        '"confidence":0.7,"rationale":"Steady 7d gain"}],"risks":["Low volume"]}')


def test_metrics():
    m = compute_metrics(RAW)[0]
    assert m.trend == "up" and m.rsi_14 == 100.0 and m.max_drawdown_7d_pct == 0.0


def test_api_flow(monkeypatch):
    monkeypatch.setattr(agent_mod, "fetch_market_data", lambda c=None: RAW)
    monkeypatch.setattr(main, "fetch_market_data", lambda c=None: RAW)
    main.state["agent"] = agent_mod.MarketAgent(llm=FakeListChatModel(responses=["summary", "risks", JSON]))
    c = TestClient(main.app)
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/market/snapshot").json()[0]["id"] == "bitcoin"
    r = c.post("/analyze").json()
    assert r["error"] is None and r["insights"]["insights"][0]["signal"] == "bullish"
    assert c.get("/insights/latest").json()["summary"] == "summary"
    assert len(c.get("/insights/history").json()) >= 1
