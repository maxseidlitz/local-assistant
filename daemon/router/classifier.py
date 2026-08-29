"""Router-Modell-Klassifikation für Anfragen ohne Regel-Treffer."""

from __future__ import annotations

import json
import re

import structlog

from daemon.llm.provider import ChatMessage, LLMProvider

logger = structlog.get_logger(__name__)

CATEGORIES = ("quick_answer", "vault_op", "tool_task", "vision_task", "complex")

CLASSIFIER_PROMPT = """Klassifiziere die Benutzeranfrage in genau eine Kategorie.
Antworte NUR mit JSON: {{"category": "<kategorie>"}}

Kategorien:
- quick_answer: einfache Fakten, Smalltalk, kurze Erklärungen
- vault_op: Notizen lesen/schreiben/suchen im Vault
- tool_task: Aufgaben die Werkzeuge brauchen (Shell, Apps, Web)
- vision_task: Bildschirm, Bilder, visuelle Inhalte
- complex: mehrstufige Aufgaben, Planung, längere Reasoning-Ketten

Anfrage: {text}"""


async def classify_intent(provider: LLMProvider, text: str) -> str:
    messages = [ChatMessage(role="user", content=CLASSIFIER_PROMPT.format(text=text))]
    try:
        response = await provider.chat("router", messages, disable_thinking=True)
        content = (response.content or "").strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            category = data.get("category", "complex")
            if category in CATEGORIES:
                return category
    except Exception as exc:
        logger.warning("classifier.fallback", error=str(exc))
    return "complex"


def needs_workhorse(category: str) -> bool:
    return category in ("complex", "tool_task", "vision_task")
