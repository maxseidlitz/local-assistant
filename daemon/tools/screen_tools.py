"""Bildschirm-Werkzeuge: OCR und Vision."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Literal

from daemon.llm.provider import ChatMessage, LLMProvider
from daemon.platform.capture import capture_to_file


def _as_data_url(path: Path) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{encoded}"


def register_screen_tools(registry, provider: LLMProvider, ocr_backend) -> None:
    async def read_screen(region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        return await ocr_backend.capture(region)

    async def look_at(image_path: str = "", question: str = "Was ist auf dem Bild zu sehen?") -> str:
        path = Path(image_path).expanduser() if image_path else Path()
        if not image_path or not path.exists():
            path = capture_to_file("active_window")
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": _as_data_url(path)}},
                ],
            )
        ]
        response = await provider.chat("workhorse", messages)
        if hasattr(response, "content"):
            return response.content or "Keine Antwort vom Vision-Modell."
        return "Keine Antwort vom Vision-Modell."

    registry.register(
        "read_screen",
        read_screen,
        "Liest Text vom Bildschirm per nativer OCR.",
        {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": ["active_window", "full", "selection"],
                }
            },
        },
    )
    registry.register(
        "look_at",
        look_at,
        "Analysiert ein Bild oder den aktuellen Bildschirm mit dem Workhorse-Modell.",
        {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
    )
