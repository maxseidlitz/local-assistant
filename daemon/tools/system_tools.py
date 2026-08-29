"""System-Werkzeuge: Shell und Apps."""

from __future__ import annotations

import asyncio
import shutil
import subprocess


def register_system_tools(registry, shell_whitelist: list[str]) -> None:
    async def run_shell(command: str, confirm: bool = True) -> str:
        first = command.strip().split()[0] if command.strip() else ""
        if first not in shell_whitelist and confirm:
            return f"Befehl '{command}' erfordert Bestätigung im HUD."
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            output = stdout.decode() + stderr.decode()
            return output.strip() or f"Befehl beendet mit Code {proc.returncode}."
        except asyncio.TimeoutError:
            return "Befehl-Timeout nach 30 Sekunden."
        except Exception as exc:
            return f"Shell-Fehler: {exc}"

    async def open_app(name: str) -> str:
        for cmd in (["xdg-open", name], ["open", name]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, check=False, timeout=10)
                    return f"App '{name}' gestartet."
                except Exception as exc:
                    return f"Fehler beim Öffnen: {exc}"
        return f"Konnte '{name}' nicht öffnen — kein Launcher gefunden."

    registry.register(
        "run_shell",
        run_shell,
        "Führt einen Shell-Befehl aus (Whitelist oder mit Bestätigung).",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "confirm": {"type": "boolean", "default": True},
            },
            "required": ["command"],
        },
    )
    registry.register(
        "open_app",
        open_app,
        "Öffnet eine Anwendung.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
