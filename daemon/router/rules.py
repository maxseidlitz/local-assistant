"""Regelbasiertes Intent-Routing ohne LLM-Aufruf."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

RouteAction = Literal[
    "quick_answer",
    "vault_op",
    "tool_task",
    "vision_task",
    "complex",
    "direct_tool",
]


@dataclass
class RuleMatch:
    action: RouteAction
    tool_name: str | None = None
    tool_args: dict | None = None
    category: str | None = None


_PREFIX_RULES: list[tuple[str, RouteAction, str | None]] = [
    (r"^note:\s*", "direct_tool", "write_note"),
    (r"^daily:\s*", "direct_tool", "append_daily"),
    (r"^search:\s*", "direct_tool", "search_vault"),
]

_PATTERN_RULES: list[tuple[re.Pattern[str], RouteAction, str | None]] = [
    (re.compile(r"remind me", re.I), "direct_tool", "create_reminder"),
    (re.compile(r"erinner mich", re.I), "direct_tool", "create_reminder"),
    (re.compile(r"was steht heute an", re.I), "direct_tool", "get_schedule"),
    (re.compile(r"wie spät", re.I), "direct_tool", "get_current_time"),
    (re.compile(r"what time", re.I), "direct_tool", "get_current_time"),
    (re.compile(r"welche uhr", re.I), "direct_tool", "get_current_time"),
    (re.compile(r"lies.*notiz", re.I), "vault_op", None),
    (re.compile(r"schreib.*notiz", re.I), "vault_op", None),
    (re.compile(r"screenshot|bildschirm|screen", re.I), "vision_task", None),
]


def match_rules(text: str) -> RuleMatch | None:
    stripped = text.strip()

    for pattern, action, tool in _PREFIX_RULES:
        if re.match(pattern, stripped, re.I):
            args: dict = {}
            if tool == "write_note":
                content = re.sub(pattern, "", stripped, flags=re.I).strip()
                args = {"path": "notes/quick.md", "content": content, "mode": "append"}
            elif tool == "append_daily":
                content = re.sub(pattern, "", stripped, flags=re.I).strip()
                args = {"content": content}
            elif tool == "search_vault":
                query = re.sub(pattern, "", stripped, flags=re.I).strip()
                args = {"query": query}
            return RuleMatch(action=action, tool_name=tool, tool_args=args)

    for pattern, action, tool in _PATTERN_RULES:
        if pattern.search(stripped):
            args = {}
            if tool == "get_current_time":
                args = {}
            elif tool == "create_reminder":
                args = {"text": stripped, "due": "tomorrow"}
            elif tool == "get_schedule":
                from datetime import date

                today = date.today().isoformat()
                args = {"date_from": today, "date_to": today}
            return RuleMatch(action=action, tool_name=tool, tool_args=args, category=action)

    return None
