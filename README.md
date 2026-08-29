# Local Assistant OS

Lokales, persönliches Assistenzsystem: Daemon auf `127.0.0.1:8765`, Ollama-Modelle, Obsidian-Vault als Gedächtnis, optionales HUD und Voice.

## Schnellstart

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh

# Terminal 1 — Daemon
uv run assistant-daemon

# Terminal 2 — CLI
uv run assistant-cli "wie spät ist es"
```

## Healthcheck (Phase 0)

```bash
uv run python scripts/healthcheck.py
```

Gibt die Latenz für Router- und Workhorse-Modell aus (benötigt laufendes Ollama).

## Projektstatus

| Phase | Status | Beschreibung |
|-------|--------|--------------|
| 0 | ✅ | uv-Projekt, LLM-Provider, Healthcheck |
| 1 | ✅ | Daemon, WebSocket, Tool-Loop, CLI |
| 2 | ✅ | Vault, SQLite-Index, Hybrid-Retrieval, Scheduler |
| 3 | ⏸ | HUD (Tauri) — **OS-Entscheidung erforderlich** |
| 4 | ⏸ | Vision/OCR — **OS-Entscheidung erforderlich** |
| 5 | 📋 | Voice (Stub vorhanden) |
| 6 | 📋 | Härtung |

Details: siehe [PROJECT.md](PROJECT.md).

## Konfiguration

`daemon/config.toml` — Modellwechsel nur hier, nie im Code.

## Offene Entscheidungen

Vor Phase 3/4 mit dem Auftraggeber klären:

1. **Betriebssystem** (OCR, Overlay, Autostart)
2. **Vault-Standort** (neuer vs. bestehender Obsidian-Vault)
3. **Wake-Word vs. Hotkey**
4. **Optionale Cloud-Eskalation**
5. **Projektname**

## Lizenz

MIT (anpassbar)
