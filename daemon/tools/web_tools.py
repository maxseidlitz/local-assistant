"""Web-Werkzeuge."""

from __future__ import annotations

import httpx


def register_web_tools(registry) -> None:
    async def web_fetch(url: str) -> str:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
            return text[:8000] if len(text) > 8000 else text

    async def web_search(query: str) -> str:
        return (
            f"Websuche nicht konfiguriert. Anfrage: '{query}'. "
            "In Phase 6 kann ein lokaler oder API-basierter Provider ergänzt werden."
        )

    registry.register(
        "web_fetch",
        web_fetch,
        "Lädt den Inhalt einer URL.",
        {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    )
    registry.register(
        "web_search",
        web_search,
        "Sucht im Web nach einer Anfrage.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
