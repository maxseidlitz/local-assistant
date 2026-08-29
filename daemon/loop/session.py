"""Session-State pro Request."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine


class SessionState(str, Enum):
    ROUTING = "routing"
    THINKING = "thinking"
    TOOL = "tool"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"
    AWAITING_CONFIRM = "awaiting_confirm"


@dataclass
class PendingConfirm:
    action: str
    detail: str
    future: asyncio.Future[bool]


@dataclass
class Session:
    id: str
    source: str
    text: str
    context: dict[str, Any] = field(default_factory=dict)
    state: SessionState = SessionState.ROUTING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: str | None = None
    artifacts: list[str] = field(default_factory=list)
    pending_confirm: PendingConfirm | None = None
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self) -> None:
        self._cancel_event.set()
        self.state = SessionState.CANCELLED

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()


EventEmitter = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        source: str,
        text: str,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        session = Session(
            id=session_id or str(uuid.uuid4()),
            source=source,
            text=text,
            context=context or {},
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def resolve_confirm(self, session_id: str, approved: bool) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.pending_confirm:
            return False
        if not session.pending_confirm.future.done():
            session.pending_confirm.future.set_result(approved)
        return True

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
