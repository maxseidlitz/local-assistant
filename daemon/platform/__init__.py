"""Plattform-OCR-Backend auswählen."""

from __future__ import annotations

import platform


def get_ocr_backend():
    system = platform.system()
    if system == "Darwin":
        from daemon.platform.ocr_macos import MacOSOCR
        return MacOSOCR()
    if system == "Windows":
        from daemon.platform.ocr_windows import WindowsOCR
        return WindowsOCR()
    from daemon.platform.ocr_linux import LinuxOCR
    return LinuxOCR()
