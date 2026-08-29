"""Tool-Loop mit Abbruchgrenzen und Streaming."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog

from daemon.config import AppConfig
from daemon.llm.provider import ChatMessage, LLMProvider
from daemon.loop.session import EventEmitter, PendingConfirm, Session, SessionState
from daemon.router.classifier import classify_intent, needs_workhorse
from daemon.router.rules import RuleMatch, match_rules
from daemon.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """Du bist ein lokaler persönlicher Assistent.
Nutze Werkzeuge wenn nötig. Antworte auf Deutsch, kurz und präzise.
Schreibe nur außerhalb des Vaults mit expliziter Bestätigung."""


class AgentLoop:
    def __init__(
        self,
        config: AppConfig,
        provider: LLMProvider,
        tools: ToolRegistry,
    ) -> None:
        self._config = config
        self._provider = provider
        self._tools = tools

    async def run(self, session: Session, emit: EventEmitter) -> str:
        await emit({"type": "status", "id": session.id, "state": SessionState.ROUTING.value})

        rule_match = match_rules(session.text)
        if rule_match and rule_match.action == "direct_tool" and rule_match.tool_name:
            return await self._run_direct_tool(session, rule_match, emit)

        category = "tool_task"
        if rule_match:
            category = rule_match.category or rule_match.action
        else:
            category = await classify_intent(self._provider, session.text)

        role = "workhorse" if needs_workhorse(category) else "router"
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=session.text),
        ]
        return await self._tool_loop(session, messages, role, emit)

    async def _run_direct_tool(
        self, session: Session, match: RuleMatch, emit: EventEmitter
    ) -> str:
        assert match.tool_name
        result = await self._execute_tool(session, match.tool_name, match.tool_args or {}, emit)
        await emit({"type": "result", "id": session.id, "text": result, "artifacts": []})
        return result

    async def _tool_loop(
        self,
        session: Session,
        messages: list[ChatMessage],
        role: str,
        emit: EventEmitter,
    ) -> str:
        max_iter = self._config.loop.max_iterations
        timeout = self._config.loop.timeout_seconds
        start = time.monotonic()
        seen_calls: set[str] = set()
        tools_schema = self._tools.openai_schemas()
        partial = ""

        for iteration in range(max_iter):
            if session.cancelled:
                raise asyncio.CancelledError()
            if time.monotonic() - start > timeout:
                msg = partial or "Zeitlimit erreicht — Teilergebnis."
                await emit({"type": "error", "id": session.id, "message": "timeout"})
                await emit({"type": "result", "id": session.id, "text": msg, "artifacts": []})
                return msg

            await emit({"type": "status", "id": session.id, "state": SessionState.THINKING.value})

            model_role = role if role in ("router", "workhorse") else "router"
            response = await self._provider.chat(
                model_role,  # type: ignore[arg-type]
                messages,
                tools=tools_schema if tools_schema else None,
                disable_thinking=model_role == "router",
            )

            if response.content:
                partial = response.content
                await emit({"type": "token", "id": session.id, "text": response.content})

            if not response.tool_calls:
                final = response.content or partial or "Keine Antwort."
                await emit({"type": "status", "id": session.id, "state": SessionState.DONE.value})
                await emit({"type": "result", "id": session.id, "text": final, "artifacts": []})
                return final

            for tc in response.tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}

                call_key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if call_key in seen_calls:
                    msg = "Abbruch: wiederholter identischer Tool-Call."
                    logger.warning("loop.duplicate_tool", name=name, args=args)
                    await emit({"type": "error", "id": session.id, "message": msg})
                    await emit({"type": "result", "id": session.id, "text": partial or msg, "artifacts": []})
                    return partial or msg
                seen_calls.add(call_key)

                tool_result = await self._execute_tool(session, name, args, emit)
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tc.get("id", f"call_{iteration}"),
                        name=name,
                    )
                )

        msg = partial or "Maximale Iterationen erreicht."
        await emit({"type": "error", "id": session.id, "message": "max_iterations"})
        await emit({"type": "result", "id": session.id, "text": msg, "artifacts": []})
        return msg

    async def _execute_tool(
        self,
        session: Session,
        name: str,
        args: dict[str, Any],
        emit: EventEmitter,
    ) -> str:
        await emit({"type": "status", "id": session.id, "state": SessionState.TOOL.value})
        await emit({"type": "tool_call", "id": session.id, "name": name, "args": args})

        if name == "run_shell":
            command = args.get("command", "")
            confirm = args.get("confirm", True)
            whitelist = self._config.security.shell_whitelist
            needs_confirm = (
                self._config.security.require_confirm_outside_whitelist
                and command.split()[0] not in whitelist
                and confirm
            )
            if needs_confirm:
                approved = await self._request_confirm(session, "run_shell", command, emit)
                if not approved:
                    return "Befehl abgelehnt."

        try:
            return await self._tools.execute(name, args, session_id=session.id)
        except Exception as exc:
            logger.exception("tool.error", name=name)
            return f"Werkzeugfehler ({name}): {exc}"

    async def _request_confirm(
        self, session: Session, action: str, detail: str, emit: EventEmitter
    ) -> bool:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        session.pending_confirm = PendingConfirm(action=action, detail=detail, future=future)
        session.state = SessionState.AWAITING_CONFIRM
        await emit({"type": "confirm_req", "id": session.id, "action": action, "detail": detail})
        try:
            return await asyncio.wait_for(future, timeout=120.0)
        except asyncio.TimeoutError:
            return False
        finally:
            session.pending_confirm = None
