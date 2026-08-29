"""Native OCR für macOS (Vision Framework)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from daemon.platform.capture import capture_to_file


class MacOSOCR:
    async def capture(self, region: Literal["active_window", "full", "selection"] = "active_window") -> str:
        path = capture_to_file(region)
        text = ocr_image(path)
        if text.strip():
            return text
        return f"Kein Text erkannt. Screenshot: {path}"


def ocr_image(path: Path) -> str:
    try:
        from ocrmac import ocrmac

        rows = ocrmac.OCR(str(path), language_preference=["de-DE", "en-US"]).recognize()
        return "\n".join(item[0] for item in rows if item and item[0].strip())
    except Exception:
        pass
    return _ocr_vision(path)


def _ocr_vision(path: Path) -> str:
    try:
        from Foundation import NSURL
        from Vision import VNImageRequestHandler, VNRecognizeTextRequest
    except Exception:
        return ""

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)
    request.setUsesLanguageCorrection_(True)
    url = NSURL.fileURLWithPath_(str(path))
    handler = VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    ok = handler.performRequests_error_([request], None)
    if not ok:
        return ""
    lines: list[str] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append(str(candidates[0].string()))
    return "\n".join(lines)
