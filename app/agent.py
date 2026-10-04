"""Multi-step LangChain reasoning workflow:
   fetch -> compute indicators -> (1) summarize -> (2) risk analysis -> (3) structured insights."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.data_sources import compute_metrics, fetch_market_data
from app.schemas import LLMInsights, Report

log = logging.getLogger("agent")

SYSTEM = "You are a careful quantitative market analyst. Use ONLY the data provided. Never invent numbers."

SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "Market metrics (JSON):\n{metrics}\n\nWrite a concise 4-6 sentence summary of the current market state: "
              "leaders, laggards, momentum, and volatility."),
])

RISK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "Market metrics (JSON):\n{metrics}\n\nSummary:\n{summary}\n\n"
              "Identify the main risks and anomalies (overbought RSI > 70, oversold < 30, high volatility, deep drawdowns). "
              "Answer as a short bullet list."),
])

INSIGHT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM + " Respond with valid JSON only, no markdown."),
    ("human", "Metrics:\n{metrics}\n\nSummary:\n{summary}\n\nRisks:\n{risks}\n\n"
              "Produce final actionable insights for every asset.\n{format_instructions}"),
])


def build_llm() -> BaseChatModel:
    from langchain_ollama import ChatOllama
    return ChatOllama(
        base_url=settings.ollama_base_url, model=settings.ollama_model,
        temperature=settings.llm_temperature, client_kwargs={"timeout": settings.llm_timeout_seconds},
    )


class MarketAgent:
    def __init__(self, llm: Optional[BaseChatModel] = None):
        self.llm = llm or build_llm()
        parser = PydanticOutputParser(pydantic_object=LLMInsights)
        self.summary_chain = SUMMARY_PROMPT | self.llm | StrOutputParser()
        self.risk_chain = RISK_PROMPT | self.llm | StrOutputParser()
        self.insight_chain = INSIGHT_PROMPT.partial(format_instructions=parser.get_format_instructions()) | self.llm | parser

    def run_cycle(self, coins: Optional[list[str]] = None) -> Report:
        now = datetime.now(timezone.utc)
        raw = fetch_market_data(coins)                      # step 0: external REST API
        metrics = compute_metrics(raw)                      # step 0b: deterministic indicators
        report = Report(created_at=now, model=settings.ollama_model, metrics=metrics)
        payload = json.dumps([m.model_dump() for m in metrics], indent=1)
        try:
            report.summary = self.summary_chain.invoke({"metrics": payload})                                # step 1
            report.risk_analysis = self.risk_chain.invoke({"metrics": payload, "summary": report.summary})  # step 2
            args = {"metrics": payload, "summary": report.summary, "risks": report.risk_analysis}
            for attempt in range(2):                                                                        # step 3 (retry on bad JSON)
                try:
                    report.insights = self.insight_chain.invoke(args)
                    break
                except OutputParserException as e:
                    log.warning("Insight JSON parse failed (attempt %d): %s", attempt + 1, e)
            if report.insights is None:
                report.error = "LLM returned invalid JSON for structured insights."
        except Exception as e:  # Ollama down / model not pulled / timeout
            log.exception("LLM step failed")
            report.error = f"LLM unavailable: {e}"
        return report
