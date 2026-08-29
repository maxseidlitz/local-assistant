"""Werkzeug-Registry: Definitionen und Dispatch."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog

logger = structlog.get_logger(__name__)

ToolHandler = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._schemas: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        description: str,
        parameters: dict[str, Any],
    ) -> None:
        self._handlers[name] = handler
        self._schemas[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    def openai_schemas(self) -> list[dict[str, Any]]:
        return list(self._schemas.values())

    async def execute(self, name: str, args: dict[str, Any], session_id: str = "") -> str:
        handler = self._handlers.get(name)
        if not handler:
            return f"Unbekanntes Werkzeug: {name}"
        result = await handler(**args)
        if isinstance(result, str):
            return result
        return str(result)

    def has(self, name: str) -> bool:
        return name in self._handlers
