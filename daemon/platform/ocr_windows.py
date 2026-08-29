"""Native OCR für Windows — Stub für Phase 4."""

from __future__ import annotations

from typing import Literal


class WindowsOCR:
    async def capture(self, region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        return "Windows OCR: Windows.Media.Ocr-Integration in Phase 4 erforderlich."
