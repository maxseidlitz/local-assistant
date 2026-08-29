"""Zeit- und Aufgaben-Werkzeuge."""

from __future__ import annotations

from datetime import datetime, timezone


def register_time_tools(registry) -> None:
    async def get_current_time() -> str:
        now = datetime.now().astimezone()
        return now.strftime("Es ist %H:%M Uhr (%Z).")

    async def get_schedule(date_from: str, date_to: str) -> str:
        return f"Kein Kalender verbunden. Angefragter Zeitraum: {date_from} bis {date_to}."

    async def create_reminder(text: str, due: str) -> str:
        return f"Erinnerung notiert: '{text}' (fällig: {due}). Vault-Integration folgt in Phase 6."

    async def list_open_tasks(project: str | None = None) -> str:
        suffix = f" für Projekt '{project}'" if project else ""
        return f"Keine Aufgabenliste konfiguriert{suffix}."

    registry.register(
        "get_current_time",
        get_current_time,
        "Gibt die aktuelle Uhrzeit zurück.",
        {"type": "object", "properties": {}},
    )
    registry.register(
        "get_schedule",
        get_schedule,
        "Liest Termine im angegebenen Datumsbereich.",
        {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["date_from", "date_to"],
        },
    )
    registry.register(
        "create_reminder",
        create_reminder,
        "Erstellt eine Erinnerung.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "due": {"type": "string"},
            },
            "required": ["text", "due"],
        },
    )
    registry.register(
        "list_open_tasks",
        list_open_tasks,
        "Listet offene Aufgaben, optional gefiltert nach Projekt.",
        {
            "type": "object",
            "properties": {"project": {"type": "string"}},
        },
    )
