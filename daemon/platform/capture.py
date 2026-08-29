"""Screenshot-Helfer für OCR und Vision."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal


def capture_to_file(region: Literal["active_window", "full", "selection"] = "active_window") -> Path:
    dest = Path(tempfile.gettempdir()) / f"assistant-cap-{int(time.time() * 1000)}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if region == "selection":
        subprocess.run(["screencapture", "-i", "-x", str(dest)], check=False, timeout=60)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        raise RuntimeError("Auswahl abgebrochen oder leer.")

    if region == "active_window" and _capture_front_window(dest):
        return dest

    subprocess.run(["screencapture", "-x", str(dest)], check=True, timeout=15)
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("Screenshot fehlgeschlagen.")
    return dest


def _capture_front_window(dest: Path) -> bool:
    wid = _front_window_id()
    if not wid:
        return False
    result = subprocess.run(
        ["screencapture", "-x", "-l", str(wid), str(dest)],
        check=False,
        timeout=15,
        capture_output=True,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def _front_window_id() -> int | None:
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
    except Exception:
        return None

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) or []
    skip = {"Window Server", "Dock", "SystemUIServer", "Control Center", "Notification Center"}
    for window in windows:
        if window.get("kCGWindowLayer", 0) != 0:
            continue
        owner = window.get("kCGWindowOwnerName", "")
        if owner in skip:
            continue
        if window.get("kCGWindowAlpha", 1) == 0:
            continue
        bounds = window.get("kCGWindowBounds") or {}
        if bounds.get("Width", 0) < 80 or bounds.get("Height", 0) < 80:
            continue
        number = window.get("kCGWindowNumber")
        if number:
            return int(number)
    return None
