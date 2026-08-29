"""FastAPI + WebSocket-Server — Daemon-Kern."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import structlog
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from daemon.config import load_config
from daemon.llm.provider import LLMProvider
from daemon.loop.agent import AgentLoop
from daemon.loop.session import SessionManager
from daemon.memory.index import VaultIndex
from daemon.memory.retrieve import HybridRetriever
from daemon.memory.vault import Vault
from daemon.platform import get_ocr_backend
from daemon.tools.registry import ToolRegistry
from daemon.tools.screen_tools import register_screen_tools
from daemon.tools.system_tools import register_system_tools
from daemon.tools.time_tools import register_time_tools
from daemon.tools.vault_tools import register_vault_tools
from daemon.tools.web_tools import register_web_tools

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

config = load_config()
sessions = SessionManager()
clients: set[WebSocket] = set()
provider: LLMProvider | None = None
vault: Vault | None = None
vault_index: VaultIndex | None = None
scheduler: AsyncIOScheduler | None = None


def build_tool_registry(
    llm: LLMProvider, v: Vault, retriever: HybridRetriever
) -> ToolRegistry:
    registry = ToolRegistry()
    register_time_tools(registry)
    register_vault_tools(registry, v, retriever)
    register_system_tools(registry, config.security.shell_whitelist)
    register_web_tools(registry)
    register_screen_tools(registry, llm, get_ocr_backend())
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    global provider, vault, vault_index, scheduler
    provider = LLMProvider(config)
    vault = Vault(config.vault)
    vault_index = VaultIndex(vault, provider)
    retriever = HybridRetriever(vault, vault_index, provider)
    app.state.agent = AgentLoop(config, provider, build_tool_registry(provider, vault, retriever))
    app.state.retriever = retriever

    loop = asyncio.get_running_loop()
    vault_index.start_watcher(loop)
    await vault_index.index_all()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        vault.ensure_daily_note,
        "cron",
        hour=config.scheduler.daily_note_hour,
        minute=config.scheduler.daily_note_minute,
        id="daily_note",
    )
    scheduler.start()
    logger.info("daemon.started", host=config.server.host, port=config.server.port)
    yield
    scheduler.shutdown(wait=False)
    vault_index.close()
    await provider.aclose()
    logger.info("daemon.stopped")


app = FastAPI(title="Local Assistant Daemon", lifespan=lifespan)


async def broadcast(message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    payload = json.dumps(message)
    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def emit_to_clients(message: dict[str, Any]) -> None:
    await broadcast(message)
    log_path = vault.root / ".assistant" / "log.jsonl" if vault else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            await handle_message(data, ws)
    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception as exc:
        logger.exception("ws.error", error=str(exc))
        clients.discard(ws)


async def handle_message(data: dict[str, Any], ws: WebSocket) -> None:
    msg_type = data.get("type")
    if msg_type == "cancel":
        session = sessions.get(data.get("id", ""))
        if session:
            session.cancel()
        return
    if msg_type == "confirm":
        sessions.resolve_confirm(data.get("id", ""), data.get("approved", False))
        return
    if msg_type != "request":
        await ws.send_text(json.dumps({"type": "error", "message": f"Unbekannter Typ: {msg_type}"}))
        return

    session = sessions.create(
        source=data.get("source", "cli"),
        text=data.get("text", ""),
        context=data.get("context", {}),
        session_id=data.get("id"),
    )

    async def emit(message: dict[str, Any]) -> None:
        message.setdefault("id", session.id)
        await broadcast(message)

    try:
        result = await app.state.agent.run(session, emit)
        session.result = result
    except asyncio.CancelledError:
        await emit({"type": "error", "id": session.id, "message": "abgebrochen"})
    except Exception as exc:
        logger.exception("request.failed", session_id=session.id)
        await emit({"type": "error", "id": session.id, "message": str(exc)})


def main() -> None:
    uvicorn.run(
        "daemon.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
