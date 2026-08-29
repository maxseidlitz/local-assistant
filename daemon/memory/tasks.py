"""Offene Aufgaben als Markdown im Vault."""

from __future__ import annotations

import re
from datetime import date

from daemon.memory.vault import Vault

TASKS_PATH = "tasks.md"
_ITEM = re.compile(r"^- \[([ xX])\]\s+(.*)$")


def _ensure(vault: Vault) -> None:
    fp = vault.root / TASKS_PATH
    if fp.exists():
        return
    vault.write_note(
        TASKS_PATH,
        "# Aufgaben\n",
        mode="create",
        source="assistant",
    )


def add_task(vault: Vault, text: str, due: str) -> str:
    _ensure(vault)
    fp = vault.root / TASKS_PATH
    body = fp.read_text(encoding="utf-8").rstrip() + "\n"
    line = f"- [ ] {text.strip()} (due: {due.strip()})"
    fp.write_text(body + line + "\n", encoding="utf-8")
    try:
        vault.append_daily(f"- [ ] {text.strip()} — {due.strip()}", section="Aufgaben")
    except Exception:
        pass
    return f"Aufgabe gespeichert in {TASKS_PATH}: {text.strip()} (fällig {due.strip()})"


def list_open(vault: Vault, project: str | None = None) -> str:
    _ensure(vault)
    fp = vault.root / TASKS_PATH
    open_items: list[str] = []
    for raw in fp.read_text(encoding="utf-8").splitlines():
        match = _ITEM.match(raw.strip())
        if not match or match.group(1).lower() == "x":
            continue
        item = match.group(2)
        if project and project.lower() not in item.lower():
            continue
        open_items.append(f"- {item}")
    if not open_items:
        suffix = f" für '{project}'" if project else ""
        return f"Keine offenen Aufgaben{suffix}."
    return "Offene Aufgaben:\n" + "\n".join(open_items)


def due_label(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"tomorrow", "morgen"}:
        from datetime import timedelta

        return (date.today() + timedelta(days=1)).isoformat()
    if value in {"today", "heute"}:
        return date.today().isoformat()
    return raw.strip()
