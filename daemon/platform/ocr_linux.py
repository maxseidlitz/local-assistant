"""Native OCR für Linux (tesseract + scrot)."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Literal


class LinuxOCR:
    async def capture(
        self, region: Literal["active_window", "full", "selection"] = "active_window"
    ) -> str:
        if not shutil.which("tesseract"):
            return "OCR nicht verfügbar: tesseract nicht installiert."
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_path = tmp.name
        try:
            await self._screenshot(img_path, region)
            proc = await asyncio.create_subprocess_exec(
                "tesseract",
                img_path,
                "stdout",
                "-l",
                "deu+eng",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            text = stdout.decode().strip()
            if not text:
                return f"Kein Text erkannt. stderr: {stderr.decode()[:200]}"
            return text
        finally:
            Path(img_path).unlink(missing_ok=True)

    async def _screenshot(self, path: str, region: str) -> None:
        if shutil.which("scrot"):
            args = ["scrot", "-u", path] if region == "active_window" else ["scrot", path]
            proc = await asyncio.create_subprocess_exec(*args)
            await proc.wait()
            return
        if shutil.which("import"):
            proc = await asyncio.create_subprocess_exec("import", "-window", "root", path)
            await proc.wait()
            return
        raise RuntimeError("Kein Screenshot-Tool gefunden (scrot oder imagemagick).")
