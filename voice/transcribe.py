"""faster-whisper auf CPU."""

from __future__ import annotations

from pathlib import Path

_model = None


def transcribe_file(path: Path, model_size: str = "distil-small") -> str:
    global _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper ist nicht installiert.") from exc

    if _model is None:
        try:
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception:
            _model = WhisperModel("small", device="cpu", compute_type="int8")

    segments, _info = _model.transcribe(str(path), language="de", vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()
