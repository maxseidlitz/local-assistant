"""Bildschirm-Werkzeuge: OCR und Vision."""

from __future__ import annotations

from typing import Literal

from daemon.llm.provider import ChatMessage, LLMProvider


def register_screen_tools(registry, provider: LLMProvider, ocr_backend) -> None:
    async def read_screen(region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        return await ocr_backend.capture(region)

    async def look_at(image_path: str, question: str) -> str:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"file://{image_path}"}},
                ],
            )
        ]
        response = await provider.chat("workhorse", messages)
        return response.content or "Keine Antwort vom Vision-Modell."

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
        "Analysiert ein Bild mit dem Workhorse-Modell.",
        {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "question": {"type": "string"},
            },
            "required": ["image_path", "question"],
        },
    )
