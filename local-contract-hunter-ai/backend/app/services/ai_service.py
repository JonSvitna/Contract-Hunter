from __future__ import annotations

import json

from app.config import settings

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


class AIService:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key and OpenAI)
        self.client = OpenAI(api_key=settings.openai_api_key) if self.enabled else None

    def score_text(self, prompt: str) -> dict | None:
        if not self.enabled or not self.client:
            return None
        try:
            resp = self.client.responses.create(
                model=settings.openai_model,
                input=prompt,
                temperature=0.2,
            )
            text = resp.output_text or "{}"
            return json.loads(text)
        except Exception:
            return None


ai_service = AIService()
