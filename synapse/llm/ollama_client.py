"""Ollama HTTP client for local LLM inference."""

from __future__ import annotations

import json
import logging

import aiohttp

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        fallback_model: str = "llama3",
        timeout: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._fallback = fallback_model
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_available(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)

    async def chat(self, messages: list[dict]) -> str:
        for model in [self._model, self._fallback]:
            try:
                result = await self._chat_with_model(model, messages)
                return result
            except Exception as e:
                logger.warning("Model %s failed: %s, trying fallback", model, e)
        return "[Synapse: LLM unavailable]"

    async def _chat_with_model(self, model: str, messages: list[dict]) -> str:
        session = await self._get_session()
        payload = {"model": model, "messages": messages, "stream": False}
        async with session.post(f"{self._base_url}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        session = await self._get_session()
        payload = {"model": self._model, "prompt": text}
        async with session.post(f"{self._base_url}/api/embeddings", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["embedding"]
