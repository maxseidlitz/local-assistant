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
        try:
            from ddgs import DDGS
        except ImportError:
            return (
                f"Websuche nicht verfügbar (Paket ddgs fehlt). Anfrage: '{query}'."
            )
        try:
            rows = list(DDGS().text(query, max_results=5))
        except Exception as exc:
            return f"Websuche fehlgeschlagen: {exc}"
        if not rows:
            return f"Keine Treffer für '{query}'."
        lines = []
        for row in rows:
            title = row.get("title") or row.get("href") or ""
            href = row.get("href") or ""
            body = row.get("body") or ""
            lines.append(f"- {title}\n  {href}\n  {body}")
        return "\n".join(lines)

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
