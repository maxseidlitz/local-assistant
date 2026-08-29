"""Piper TTS mit macOS-say-Fallback."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def synthesize(text: str) -> Path:
    dest = Path(tempfile.gettempdir()) / f"assistant-tts-{int(time.time() * 1000)}.wav"
    if shutil.which("piper"):
        model = Path.home() / ".local/share/piper/de_DE-thorsten-medium.onnx"
        cmd = ["piper", "--output_file", str(dest)]
        if model.exists():
            cmd.extend(["--model", str(model)])
        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            timeout=30,
            capture_output=True,
        )
        if result.returncode == 0 and dest.exists():
            return dest

    if shutil.which("say"):
        aiff = dest.with_suffix(".aiff")
        voice = _macos_voice()
        cmd = ["say", "-o", str(aiff)]
        if voice:
            cmd.extend(["-v", voice])
        cmd.append(text)
        subprocess.run(cmd, check=True, timeout=30)
        if shutil.which("afconvert"):
            subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(dest)],
                check=True,
                timeout=15,
            )
            aiff.unlink(missing_ok=True)
            return dest
        return aiff

    raise RuntimeError("Kein TTS verfügbar (piper oder say).")


def _macos_voice() -> str | None:
    try:
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    for line in result.stdout.splitlines():
        name = line.split()[0] if line.split() else ""
        if "de_DE" in line or name in {"Anna", "Helena", "Markus"}:
            return name
    return None
