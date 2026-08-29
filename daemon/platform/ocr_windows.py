"""OCR-Stub für Windows."""

from __future__ import annotations

from typing import Literal


class WindowsOCR:
    async def capture(self, region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        return "Windows-OCR ist in dieser Stufe nicht implementiert."
