"""Vault-Werkzeuge: lesen, schreiben, Daily Notes."""

from __future__ import annotations

from typing import Literal

from daemon.memory.retrieve import HybridRetriever
from daemon.memory.vault import Vault


def register_vault_tools(registry, vault: Vault, retriever: HybridRetriever) -> None:
    async def search_vault(query: str, limit: int = 6) -> str:
        chunks = await retriever.search(query, limit=limit)
        if not chunks:
            return "Keine Treffer im Vault."
        lines = []
        for c in chunks:
            lines.append(f"[{c.path}] ({c.source}): {c.text[:300]}")
        return "\n\n".join(lines)

    async def read_note(path: str) -> str:
        return vault.read_note(path)

    async def write_note(
        path: str, content: str, mode: Literal["create", "append", "replace"] = "create"
    ) -> str:
        return vault.write_note(path, content, mode=mode, source="assistant")

    async def append_daily(content: str, section: str | None = None) -> str:
        return vault.append_daily(content, section=section, source="assistant")

    registry.register(
        "search_vault",
        search_vault,
        "Durchsucht den Obsidian-Vault hybrid (ripgrep + semantisch).",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 6},
            },
            "required": ["query"],
        },
    )
    registry.register(
        "read_note",
        read_note,
        "Liest eine Notiz aus dem Vault.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    registry.register(
        "write_note",
        write_note,
        "Schreibt oder aktualisiert eine Notiz im Vault.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["create", "append", "replace"]},
            },
            "required": ["path", "content"],
        },
    )
    registry.register(
        "append_daily",
        append_daily,
        "Fügt Inhalt zur heutigen Tagesnotiz hinzu.",
        {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "section": {"type": "string"},
            },
            "required": ["content"],
        },
    )
