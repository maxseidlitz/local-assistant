#!/usr/bin/env python3
"""Healthcheck: Modelle, VRAM-Hinweis, Latenz pro Rolle."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Projektroot zum Python-Pfad hinzufügen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daemon.config import load_config
from daemon.llm.provider import LLMProvider


def gpu_info() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "note": "nvidia-smi nicht gefunden"}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"available": False, "error": result.stderr.strip()}
        used, total, name = [p.strip() for p in result.stdout.strip().split(",")]
        return {
            "available": True,
            "name": name,
            "vram_used_mb": int(used),
            "vram_total_mb": int(total),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


async def main() -> int:
    config = load_config()
    provider = LLMProvider(config)
    report: dict = {"ollama": config.ollama_base_url, "models": {}, "gpu": gpu_info()}

    try:
        available = await provider.list_models()
        report["available_models"] = available
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Ollama nicht erreichbar: {exc}"}, indent=2))
        await provider.aclose()
        return 1

    all_ok = True
    for role in ("router", "workhorse"):
        model = provider.model_for_role(role)  # type: ignore[arg-type]
        if model not in available and not any(model in m for m in available):
            report["models"][role] = {"ok": False, "error": f"Modell {model} nicht geladen"}
            all_ok = False
            continue
        try:
            ping = await provider.health_ping(role)  # type: ignore[arg-type]
            report["models"][role] = ping
            print(f"{role}: {ping['model']} — {ping['latency_ms']} ms")
        except Exception as exc:
            report["models"][role] = {"ok": False, "error": str(exc)}
            all_ok = False
            print(f"{role}: FEHLER — {exc}")

    if report["gpu"].get("available"):
        g = report["gpu"]
        print(f"GPU: {g['name']} — {g['vram_used_mb']}/{g['vram_total_mb']} MB VRAM")

    await provider.aclose()
    report["ok"] = all_ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
