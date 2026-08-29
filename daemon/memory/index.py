"""SQLite + sqlite-vec Embedding-Index mit Dateisystem-Watcher."""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import struct
import threading
from pathlib import Path

import sqlite_vec
import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from daemon.llm.provider import LLMProvider
from daemon.memory.vault import Vault

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


class VaultIndex:
    def __init__(self, vault: Vault, provider: LLMProvider) -> None:
        self._vault = vault
        self._provider = provider
        self._db_path = vault.root / ".assistant" / "index.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        sqlite_vec.load(self._conn)
        self._lock = threading.Lock()
        self._observer: Observer | None = None
        self._debounce_task: asyncio.Task | None = None
        self._pending_files: set[str] = set()
        self._embedding_dim: int | None = None
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    UNIQUE(path, chunk_index)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)"
            )
            self._conn.commit()

    def _ensure_vec_table(self, dim: int) -> None:
        with self._lock:
            self._conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                    chunk_id INTEGER PRIMARY KEY,
                    embedding float[{dim}]
                )
                """
            )
            self._conn.commit()
        self._embedding_dim = dim

    async def embed_text(self, text: str) -> list[float]:
        return await self._provider.embed(text)

    async def index_file(self, path: Path) -> int:
        rel = str(path.relative_to(self._vault.root))
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("index.read_failed", path=rel, error=str(exc))
            return 0

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        with self._lock:
            row = self._conn.execute(
                "SELECT content_hash FROM chunks WHERE path = ? LIMIT 1", (rel,)
            ).fetchone()
            if row and row["content_hash"] == content_hash:
                return 0

        chunks = _chunk_text(content)
        if not chunks:
            return 0

        embeddings: list[list[float]] = []
        for chunk in chunks:
            embedding = await self.embed_text(chunk)
            if self._embedding_dim is None:
                self._ensure_vec_table(len(embedding))
            embeddings.append(embedding)

        with self._lock:
            old_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM chunks WHERE path = ?", (rel,)
                ).fetchall()
            ]
            for old_id in old_ids:
                self._conn.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", (old_id,))
            self._conn.execute("DELETE FROM chunks WHERE path = ?", (rel,))

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                cur = self._conn.execute(
                    "INSERT INTO chunks (path, chunk_index, text, content_hash) "
                    "VALUES (?, ?, ?, ?)",
                    (rel, i, chunk, content_hash),
                )
                chunk_id = cur.lastrowid
                self._conn.execute(
                    "INSERT INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, struct.pack(f"{len(embedding)}f", *embedding)),
                )
            self._conn.commit()
        return len(chunks)

    async def index_all(self) -> int:
        total = 0
        for path in self._vault.iter_markdown_files():
            total += await self.index_file(path)
        return total

    def vector_search(self, query_embedding: list[float], limit: int = 6) -> list[dict]:
        if self._embedding_dim is None:
            return []
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT c.path, c.text, c.chunk_index, v.distance
                FROM vec_chunks v
                JOIN chunks c ON c.id = v.chunk_id
                WHERE v.embedding MATCH ?
                  AND k = ?
                ORDER BY v.distance
                """,
                (
                    struct.pack(f"{len(query_embedding)}f", *query_embedding),
                    limit,
                ),
            ).fetchall()
        return [dict(r) for r in rows]

    def start_watcher(self, loop: asyncio.AbstractEventLoop) -> None:
        handler = _DebouncedHandler(self, loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._vault.root), recursive=True)
        self._observer.start()
        logger.info("index.watcher_started", path=str(self._vault.root))

    def stop_watcher(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

    def close(self) -> None:
        self.stop_watcher()
        self._conn.close()


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, index: VaultIndex, loop: asyncio.AbstractEventLoop) -> None:
        self._index = index
        self._loop = loop

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".md" or ".assistant" in path.parts:
            return
        self._index._pending_files.add(str(path))
        if self._index._debounce_task and not self._index._debounce_task.done():
            self._index._debounce_task.cancel()
        self._index._debounce_task = self._loop.create_task(self._flush())

    def on_created(self, event: FileSystemEvent) -> None:
        self.on_modified(event)

    async def _flush(self) -> None:
        await asyncio.sleep(5)
        files = list(self._index._pending_files)
        self._index._pending_files.clear()
        for f in files:
            try:
                await self._index.index_file(Path(f))
            except Exception as exc:
                logger.warning("index.debounce_failed", path=f, error=str(exc))
