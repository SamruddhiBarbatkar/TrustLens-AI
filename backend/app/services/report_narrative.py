"""Optional xAI narrative generated only from saved TrustLens analysis facts."""

import json
from typing import Any

import httpx

from app.models.analysis import AnalysisInDatabase


class GrokReportNarrativeService:
    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, analysis: AnalysisInDatabase) -> str | None:
        if not self._api_key:
            return None
        facts: dict[str, Any] = {
            "trust_score": None if analysis.trust_score is None else analysis.trust_score.model_dump(mode="json"),
            "signals": {name: signal.model_dump(mode="json") for name, signal in analysis.signals.items()},
            "limitations": [] if analysis.explanation is None else list(analysis.explanation.limitations),
        }
        prompt = (
            "Write a concise report narrative using only the supplied JSON facts. "
            "Do not add claims, measurements, causes, or conclusions. State that this is decision support, not proof. "
            f"FACTS: {json.dumps(facts, ensure_ascii=False)}"
        )
        try:
            response = httpx.post(
                "https://api.x.ai/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "input": prompt, "max_output_tokens": 500},
                timeout=20.0,
            )
            response.raise_for_status()
            text = response.json().get("output_text")
            return text.strip() if isinstance(text, str) and text.strip() else None
        except (httpx.HTTPError, ValueError, TypeError):
            return None
