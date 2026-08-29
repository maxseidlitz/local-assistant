"""Hybrid-Retrieval: ripgrep + Vektorsuche."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from daemon.llm.provider import LLMProvider
from daemon.memory.index import VaultIndex
from daemon.memory.vault import Vault

logger = structlog.get_logger(__name__)


@dataclass
class Chunk:
    path: str
    text: str
    source: str  # "ripgrep" | "vector"


class HybridRetriever:
    def __init__(self, vault: Vault, index: VaultIndex, provider: LLMProvider) -> None:
        self._vault = vault
        self._index = index
        self._provider = provider

    async def search(self, query: str, limit: int = 6) -> list[Chunk]:
        rg_chunks = await self._ripgrep_search(query, limit=limit)
        vec_chunks = await self._vector_search(query, limit=limit)
        return self._merge(rg_chunks, vec_chunks, limit=limit)

    async def _ripgrep_search(self, query: str, limit: int) -> list[Chunk]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ripgrep_sync, query, limit)

    def _ripgrep_sync(self, query: str, limit: int) -> list[Chunk]:
        try:
            result = subprocess.run(
                [
                    "rg",
                    "--no-heading",
                    "--line-number",
                    "--max-count",
                    "3",
                    "-i",
                    query,
                    str(self._vault.root),
                    "--glob",
                    "!.assistant/**",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("retrieve.rg_failed", error=str(exc))
            return []

        chunks: list[Chunk] = []
        for line in result.stdout.splitlines():
            if len(chunks) >= limit:
                break
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, _line_no, text = parts
            rel = str(Path(file_path).relative_to(self._vault.root))
            chunks.append(Chunk(path=rel, text=text.strip(), source="ripgrep"))
        return chunks

    async def _vector_search(self, query: str, limit: int) -> list[Chunk]:
        try:
            embedding = await self._provider.embed(query)
            rows = self._index.vector_search(embedding, limit=limit)
            return [
                Chunk(path=r["path"], text=r["text"], source="vector")
                for r in rows
            ]
        except Exception as exc:
            logger.warning("retrieve.vector_failed", error=str(exc))
            return []

    def _merge(
        self, rg: list[Chunk], vec: list[Chunk], limit: int
    ) -> list[Chunk]:
        seen: set[tuple[str, str]] = set()
        merged: list[Chunk] = []
        for chunk in rg + vec:
            key = (chunk.path, chunk.text[:80])
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
            if len(merged) >= limit:
                break
        return merged
