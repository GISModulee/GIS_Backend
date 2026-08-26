from __future__ import annotations

from typing import Any

import httpx

from services.chatbot.prompts import GIS_AGENT_SYSTEM_PROMPT
from utils.config import settings
from utils.constants import DETAIL_SERVICE_UNAVAILABLE
from utils.exceptions import ServiceUnavailableError
from utils.logger import logger


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    async def chat(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": GIS_AGENT_SYSTEM_PROMPT}, *messages],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.warning("Ollama request failed | error=%s", type(exc).__name__)
            raise ServiceUnavailableError(
                "The GIS assistant is currently unavailable because the local AI service is not running."
            ) from exc
        except Exception as exc:
            logger.error("Unexpected Ollama client failure | error=%s", exc, exc_info=True)
            raise ServiceUnavailableError(DETAIL_SERVICE_UNAVAILABLE) from exc
