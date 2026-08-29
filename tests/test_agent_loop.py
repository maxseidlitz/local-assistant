"""Tests für Tool-Loop-Abbruchgrenzen."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from daemon.config import AppConfig, LoopConfig
from daemon.llm.provider import ChatMessage, ChatResponse, LLMProvider
from daemon.loop.agent import AgentLoop
from daemon.loop.session import Session
from daemon.tools.registry import ToolRegistry


@dataclass
class FakeProvider:
    responses: list[ChatResponse] = field(default_factory=list)
    _call: int = 0

    async def chat(self, role, messages, **kwargs) -> ChatResponse:
        response = self.responses[self._call]
        self._call += 1
        return response

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_loop_aborts_on_duplicate_tool_call():
    registry = ToolRegistry()

    async def echo_ping(**kwargs) -> str:
        return "pong"

    registry.register("echo_ping", echo_ping, "echo", {"type": "object", "properties": {}})

    provider = FakeProvider(
        responses=[
            ChatResponse(content='{"category": "tool_task"}'),
            ChatResponse(
                tool_calls=[
                    {
                        "id": "1",
                        "type": "function",
                        "function": {"name": "echo_ping", "arguments": "{}"},
                    }
                ]
            ),
            ChatResponse(
                tool_calls=[
                    {
                        "id": "2",
                        "type": "function",
                        "function": {"name": "echo_ping", "arguments": "{}"},
                    }
                ]
            ),
        ]
    )
    config = AppConfig(loop=LoopConfig(max_iterations=8, timeout_seconds=45))
    agent = AgentLoop(config, provider, registry)  # type: ignore[arg-type]
    session = Session(id="test", source="test", text="test duplicate")
    events: list[dict] = []

    async def emit(msg: dict) -> None:
        events.append(msg)

    result = await agent.run(session, emit)
    assert "wiederholter" in result.lower() or any(e.get("type") == "error" for e in events)


@pytest.mark.asyncio
async def test_direct_tool_time_without_llm():
    registry = ToolRegistry()

    async def get_current_time() -> str:
        return "Es ist 12:00 Uhr."

    registry.register("get_current_time", get_current_time, "time", {"type": "object", "properties": {}})

    config = AppConfig()
    agent = AgentLoop(config, FakeProvider(), registry)  # type: ignore[arg-type]
    session = Session(id="t1", source="cli", text="wie spät ist es")
    events: list[dict] = []

    async def emit(msg: dict) -> None:
        events.append(msg)

    result = await agent.run(session, emit)
    assert "12:00" in result
    assert any(e.get("type") == "tool_call" and e.get("name") == "get_current_time" for e in events)
