from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AssetMetrics(BaseModel):
    id: str
    symbol: str
    price: float
    change_1h_pct: Optional[float] = None
    change_24h_pct: Optional[float] = None
    change_7d_pct: Optional[float] = None
    sma_24h: Optional[float] = None
    volatility_pct: Optional[float] = Field(None, description="Std-dev of hourly returns (%)")
    rsi_14: Optional[float] = None
    max_drawdown_7d_pct: Optional[float] = None
    trend: Literal["up", "down", "sideways"] = "sideways"


class Insight(BaseModel):
    asset: str = Field(description="Asset id, e.g. bitcoin")
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0, le=1, description="0 to 1")
    rationale: str


class LLMInsights(BaseModel):
    market_outlook: str
    insights: list[Insight]
    risks: list[str]


class Report(BaseModel):
    id: Optional[int] = None
    created_at: datetime
    model: str
    metrics: list[AssetMetrics]
    summary: Optional[str] = None
    risk_analysis: Optional[str] = None
    insights: Optional[LLMInsights] = None
    error: Optional[str] = None
    disclaimer: str = "Automated analysis for educational purposes only. Not financial advice."


class AnalyzeRequest(BaseModel):
    coins: Optional[list[str]] = Field(None, examples=[["bitcoin", "ethereum"]])
