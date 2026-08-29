"""Native OCR für macOS (Vision Framework) — Stub für Phase 4."""

from __future__ import annotations

from typing import Literal


class MacOSOCR:
    async def capture(self, region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        return "macOS OCR: Vision Framework-Integration in Phase 4 erforderlich."
