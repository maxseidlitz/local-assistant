from pathlib import Path

from daemon.tools.screen_tools import _as_data_url
from daemon.platform import get_ocr_backend


def test_as_data_url(tmp_path):
    image = tmp_path / "x.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    url = _as_data_url(image)
    assert url.startswith("data:image/png;base64,")


def test_ocr_backend_constructs():
    backend = get_ocr_backend()
    assert hasattr(backend, "capture")
