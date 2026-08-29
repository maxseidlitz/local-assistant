"""Tests für Tool-Loop-Abbruchgrenzen."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from daemon.config import AppConfig, LoopConfig
from daemon.llm.provider import ChatResponse, StreamChunk
from daemon.loop.agent import AgentLoop
from daemon.loop.session import Session
from daemon.tools.registry import ToolRegistry


@dataclass
class FakeProvider:
    responses: list[ChatResponse] = field(default_factory=list)
    _call: int = 0

    def model_for_role(self, role: str) -> str:
        return f"fake-{role}"

    async def chat(self, role, messages, **kwargs):
        response = self.responses[self._call]
        self._call += 1
        if kwargs.get("stream"):
            async def gen():
                if response.content:
                    mid = max(1, len(response.content) // 2)
                    yield StreamChunk(text=response.content[:mid])
                    if mid < len(response.content):
                        yield StreamChunk(text=response.content[mid:])
                yield StreamChunk(done=True, tool_calls=response.tool_calls)

            return gen()
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
    assert any(e.get("type") == "tool_result" for e in events)


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
    assert any(e.get("type") == "tool_result" and e.get("name") == "get_current_time" for e in events)


@pytest.mark.asyncio
async def test_streamed_tokens_and_model_status():
    registry = ToolRegistry()
    provider = FakeProvider(
        responses=[
            ChatResponse(content='{"category": "quick_answer"}'),
            ChatResponse(content="Hallo Welt"),
        ]
    )
    agent = AgentLoop(AppConfig(), provider, registry)  # type: ignore[arg-type]
    session = Session(id="s1", source="hud", text="sag hallo")
    events: list[dict] = []

    async def emit(msg: dict) -> None:
        events.append(msg)

    result = await agent.run(session, emit)
    assert result == "Hallo Welt"
    tokens = [e["text"] for e in events if e.get("type") == "token"]
    assert "".join(tokens) == "Hallo Welt"
    assert len(tokens) >= 2
    assert any(e.get("type") == "status" and e.get("model") == "fake-router" for e in events)
