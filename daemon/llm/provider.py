"""Einzige Stelle im Code, die Ollama kennt."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

import httpx
import structlog

from daemon.config import AppConfig

logger = structlog.get_logger(__name__)

ModelRole = Literal["router", "workhorse", "embed"]


@dataclass
class ChatMessage:
    role: str
    content: str | list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ChatResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False


class LLMProvider:
    """Ollama-Abstraktion mit Rollenkonzept und Retry-Logik."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def model_for_role(self, role: ModelRole) -> str:
        models = self._config.models
        return {
            "router": models.router,
            "workhorse": models.workhorse,
            "embed": models.embed,
        }[role]

    def keep_alive_for_role(self, role: ModelRole) -> str | int | None:
        value = self._config.models.keep_alive.get(role)
        if value is None:
            return None
        if value == "-1":
            return -1
        return value

    def _build_options(self, num_ctx: int | None = None) -> dict[str, Any]:
        opts = dict(self._config.models.options)
        if num_ctx is not None:
            opts["num_ctx"] = num_ctx
        return opts

    def _serialize_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.name:
                entry["name"] = msg.name
            serialized.append(entry)
        return serialized

    async def chat(
        self,
        role: ModelRole,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        disable_thinking: bool = False,
        num_ctx: int | None = None,
        max_retries: int = 2,
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        model = self.model_for_role(role)
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._serialize_messages(messages),
            "stream": stream,
            "options": self._build_options(num_ctx),
        }
        keep_alive = self.keep_alive_for_role(role)
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if tools:
            payload["tools"] = tools
        if disable_thinking:
            payload["think"] = False

        if stream:
            return self._chat_stream(payload)

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = await self._client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    self._validate_tool_calls(tool_calls)
                return ChatResponse(
                    content=message.get("content"),
                    tool_calls=tool_calls,
                    finish_reason=choice.get("finish_reason"),
                    raw=data,
                )
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
                last_error = exc
                logger.warning("llm.chat_retry", attempt=attempt, error=str(exc))
                if attempt < max_retries:
                    messages = messages + [
                        ChatMessage(
                            role="user",
                            content=(
                                "Deine letzte Antwort enthielt ungültiges Tool-Call-JSON. "
                                "Antworte erneut mit gültigem JSON gemäß dem Schema."
                            ),
                        )
                    ]
                    payload["messages"] = self._serialize_messages(messages)
                    continue
                raise RuntimeError(f"LLM-Aufruf fehlgeschlagen: {exc}") from exc
        raise RuntimeError(f"LLM-Aufruf fehlgeschlagen: {last_error}")

    async def _chat_stream(self, payload: dict[str, Any]) -> AsyncIterator[StreamChunk]:
        async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            tool_calls_acc: dict[int, dict[str, Any]] = {}
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    yield StreamChunk(done=True, tool_calls=list(tool_calls_acc.values()))
                    return
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = data.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content") or ""
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        fn = tool_calls_acc[idx]["function"]
                        if tc.get("id"):
                            tool_calls_acc[idx]["id"] = tc["id"]
                        if "function" in tc:
                            if tc["function"].get("name"):
                                fn["name"] = tc["function"]["name"]
                            if tc["function"].get("arguments"):
                                fn["arguments"] += tc["function"]["arguments"]
                if text:
                    yield StreamChunk(text=text)

    def _validate_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        for tc in tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", "")
            if isinstance(args, str) and args:
                json.loads(args)

    async def embed(self, text: str) -> list[float]:
        model = self.model_for_role("embed")
        payload = {
            "model": model,
            "input": text,
            "keep_alive": self.keep_alive_for_role("embed"),
        }
        response = await self._client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def health_ping(self, role: ModelRole) -> dict[str, Any]:
        """Misst Latenz für ein Modell (Router/Workhorse)."""
        model = self.model_for_role(role)
        start = time.perf_counter()
        response = await self._client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "keep_alive": self.keep_alive_for_role(role),
                "options": {"num_predict": 8},
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        return {"role": role, "model": model, "latency_ms": round(elapsed_ms, 1), "ok": True}

    async def list_models(self) -> list[str]:
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
