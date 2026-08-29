# Local Assistant OS — Projektbeschreibung

**Arbeitstitel** (endgültiger Name offen)
**Stand:** August 2026
**Dokumenttyp:** Bauvorlage für eine KI-Coding-Instanz

---

## Über dieses Dokument

Dies ist die vollständige, eigenständige Projektbeschreibung für ein lokal laufendes,
persönliches Assistenzsystem. Es ist so verfasst, dass eine bauende Instanz ohne weiteren
Kontext damit arbeiten kann: Es enthält Zielsetzung, Architektur, Technologie-Entscheidungen
inklusive Begründung, Schnittstellen, Repo-Struktur und einen phasenweisen Umsetzungsplan
mit Akzeptanzkriterien.

**An die bauende Instanz:** Du sollst dieses System implementieren. Arbeite die Phasen in
Abschnitt 10 strikt der Reihe nach ab; jede Phase hat ein Akzeptanzkriterium, das erfüllt
sein muss, bevor die nächste beginnt. Es gibt offene Entscheidungen (Abschnitt 12), von
denen mindestens eine — das Betriebssystem — vor Phase 3 geklärt sein muss. Kläre diese
Punkte mit dem Auftraggeber, bevor du die betroffenen Phasen startest. Triff im Zweifel
keine stillschweigenden Annahmen über Plattform, Vault-Standort oder Cloud-Nutzung.

---

## 1. Zielsetzung

Ein Daemon läuft dauerhaft auf lokaler Hardware, nimmt Anfragen per Sprache, Tastenkürzel
oder Zeitplan entgegen, bearbeitet sie über ein lokales Sprachmodell mit Werkzeugzugriff und
persistiert Ergebnisse in einem Obsidian-Vault. Ein leichtgewichtiges Overlay dient als
sichtbare Oberfläche. Es gibt keinen Cloud-Roundtrip und keine laufenden Token-Kosten.

### Nicht-Ziele
- Kein Ersatz für ein Cloud-gestütztes Coding-Agent-Setup. Für komplexes Refactoring bleiben
  große Cloud-Modelle überlegen.
- Keine freie, unbegrenzte Agentic-Loop. Lokale Modelle brechen bei langen Werkzeugketten ab.
  Das System setzt bewusst auf viele kleine, eng definierte Werkzeuge.
- Kein permanentes Screencapture. Bildverarbeitung ist ereignisgetrieben.
- Keine Multi-User-Fähigkeit und kein Zugriff von außen. Alles bindet an `127.0.0.1`.

### Leitprinzipien
1. **Der Daemon ist das Produkt.** HUD, Voice und CLI sind austauschbare Clients ohne eigene Logik.
2. **Leerlauf kostet nichts.** Nicht benötigte Komponenten sind entladen oder gar nicht gestartet.
3. **Gedächtnis ist menschenlesbar.** Alles bleibt Markdown und ist jederzeit selbst editierbar.
4. **Deterministisch vor generativ.** OCR statt Bildmodell, Regel statt Modell, wo immer möglich.

---

## 2. Hardware-Baseline

| Ressource | Wert |
|---|---|
| RAM | 32 GB |
| VRAM | 24 GB |
| Betriebssystem | **offen — siehe Abschnitt 12, blockiert Phase 3 und 4** |

Das VRAM-Budget von 24 GB ist die harte Randbedingung. Alle Modellentscheidungen leiten sich
daraus ab.

---

## 3. Modell-Stack

### Entscheidung

| Rolle | Modell | Footprint | `keep_alive` |
|---|---|---|---|
| Router / Alltag | `gemma4:e2b` | ~2 GB effektiv | `-1` (permanent) |
| Workhorse + Vision | `gemma4:26b` | ~15–18 GB | `10m` |
| Embeddings | `nomic-embed-text` (o. ä. klein) | < 1 GB | on demand |

**Peak-Auslastung:** ca. 20 GB Gewichte plus KV-Cache. Passt mit Reserve in 24 GB.

### Begründung: `gemma4:26b` als Workhorse
- **MoE mit ~4B aktiven Parametern pro Token** → Antwortlatenz auf Kleinmodell-Niveau bei
  26B Wissenskapazität. Für einen Assistenten zählt Latenz mehr als Benchmark-Spitzenwerte.
- **Nativ multimodal** (Vision, Audio, Tools, Thinking) → ein separates Vision-Modell entfällt,
  die Architektur schrumpft von drei auf zwei Modelle.
- **Stabilität bei langem Kontext.** In Messreihen auf einer 24-GB-Karte über Kontextgrößen von
  8K bis 64K war dieses Modell der klare Stabilitätssieger, ohne den bei anderen Modellen
  typischen Qualitätseinbruch bei hoher Kontextfüllung — das zentrale Ausfallrisiko in
  Agenten-Loops.
- **Headroom.** ~15–18 GB lassen Platz für Router, KV-Cache und Embeddings.

### Verworfene Alternativen
- **`qwen3.8:27b`** — stärker in Benchmarks, aber dicht statt MoE und damit spürbar langsamer.
  Der Footprint schwankt je nach Quelle zwischen 18 GB und ~24 GB; letzteres füllt die Karte
  vollständig. Die veröffentlichten Benchmarkzahlen sind bislang nicht unabhängig reproduziert,
  und der Multimodal-Pfad ist erst wenige Wochen alt (frühe Parser-Fehler bei Bildeingabe,
  inzwischen behoben). Für ein dauerhaft laufendes System zu unruhig.
- **`qwen3-coder:30b`** — auf Code spezialisiert, hier nicht der Schwerpunkt.
- **Separates Vision-Modell** (z. B. Qwen2.5-VL 7B) — überflüssig, seit Gemma 4 nativ
  multimodal ist.

### Fallback
Falls `gemma4:26b` beim Tool-Calling unzuverlässig ist: **`qwen3.6:27b`** (~17 GB, seit
April 2026 im Feld, mehr Praxiserfahrung). Der Wechsel muss eine einzige Konfigurationszeile
sein — siehe Anforderung an die Modell-Abstraktion in Abschnitt 6.1.

### Kontext-Policy
Der KV-Cache wächst etwa linear mit dem Kontext. Trotz 256K nativem Fenster gilt:
- **Standard: 16K** (`num_ctx: 16384`)
- **Erhöhung auf 32K** nur für explizit lange Aufgaben, per Werkzeug-Flag
- Flash Attention aktiv, KV-Cache-Quantisierung `q8_0`

---

## 4. Systemarchitektur

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  HUD        │  │  Voice      │  │  CLI        │  │  Scheduler  │
│  (Tauri)    │  │  (STT/TTS)  │  │  (Debug)    │  │  (Cron)     │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴───────WebSocket┴────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │        DAEMON           │
                    │  ┌───────────────────┐  │
                    │  │ Intent-Router     │  │
                    │  ├───────────────────┤  │
                    │  │ Tool-Loop         │  │
                    │  ├───────────────────┤  │
                    │  │ Session-State     │  │
                    │  └───────────────────┘  │
                    └───┬─────────┬────────┬──┘
                        │         │        │
              ┌─────────▼──┐ ┌────▼─────┐ ┌▼──────────────┐
              │  Ollama    │ │  Vault   │ │  Tool-Layer   │
              │  :11434    │ │  Markdown│ │  OCR, Shell,  │
              │            │ │  + SQLite│ │  Kalender, Web│
              └────────────┘ └──────────┘ └───────────────┘
```

### Komponenten

**Daemon** — der Kern und einzige Ort für Logik. Ein langlebiger Prozess auf
`127.0.0.1:8765`. Nimmt Requests entgegen, entscheidet über Routing, führt die Tool-Loop aus,
verwaltet Sessions, schreibt ins Vault. Läuft auch ohne verbundenen Client.

**Clients** — HUD, Voice, CLI, Scheduler. Alle sprechen dasselbe WebSocket-Protokoll und
enthalten keine Logik. Jeder Client ist einzeln startbar und beendbar, ohne dass das System
stehenbleibt. Das ist die zentrale Entkopplungsregel.

**Ollama** — Modell-Server, ausschließlich über eine eigene Abstraktionsschicht
(`llm/provider.py`) angesprochen, damit ein Modellwechsel Konfiguration bleibt.

**Vault** — Obsidian-Verzeichnis, direkt über das Dateisystem angesprochen. Kein REST-Plugin,
keine zusätzliche Laufzeitabhängigkeit. Ergänzt um eine SQLite-Datei für den Embedding-Index.

---

## 5. Technologie-Entscheidungen

| Bereich | Wahl | Begründung |
|---|---|---|
| Daemon-Sprache | **Python 3.12** | Bestes Ökosystem für STT, Embeddings, Tooling. Latenz ist I/O-, nicht CPU-gebunden. |
| Web-Framework | **FastAPI + `websockets`** | Async, WebSocket nativ, minimaler Overhead. |
| Env-Verwaltung | **`uv`** | Schnell und reproduzierbar. |
| Modell-Runtime | **Ollama** | Einfachster Pfad zu offiziellen Q4-Builds, OpenAI-kompatibler Endpoint unter `/v1`. |
| HUD | **Tauri v2** | Rust-Backend plus Web-Frontend, transparentes Always-on-Top-Fenster, globaler Hotkey, ~40–80 MB RAM im Leerlauf. Electron wäre 3–4× so schwer. |
| HUD-Frontend | **Svelte + Tailwind** | Kleines Bundle, wenig Runtime-Overhead. |
| STT | **`faster-whisper`** (`distil-small` / `small`) | Läuft auf CPU oder wenigen hundert MB VRAM, gute Qualität bei kurzen Kommandos. |
| TTS | **Piper** | Sehr schnell, klein, offline, brauchbare deutsche Stimmen. |
| Wake-Word | **openWakeWord** | Einziger echter Dauerläufer. ~1–2 % CPU, kein VRAM. |
| OCR | **nativ pro Plattform** (Vision Framework / Windows.Media.Ocr) | ~50 ms statt ~2–4 s beim Bildmodell, höhere Genauigkeit bei Fließtext, keine VRAM-Kosten. |
| Volltextsuche | **ripgrep** | Exakte Treffer in Millisekunden, keine Indexpflege. |
| Semantische Suche | **SQLite + `sqlite-vec`** | Eine Datei, keine Serverkomponente, im Leerlauf kostenlos. |
| Scheduler | **APScheduler im Daemon** | Kein externer Cron, plattformunabhängig, teilt sich den Prozess-State. |
| Logging | **structlog → JSONL** | Maschinenlesbar, für HUD-Anzeige und Fehlersuche. |

---

## 6. Kernkomponenten im Detail

### 6.1 LLM-Abstraktion (`llm/provider.py`)
Einzige Stelle im Code, die Ollama kennt. Aufgaben:
- Modellauswahl nach Rolle (`router`, `workhorse`, `embed`) aus `config.toml`
- Werkzeug-Definitionen im OpenAI-Format übergeben (Ollamas Endpoint akzeptiert dieses Schema)
- Retry bei fehlerhaftem Tool-Call-JSON (lokale Modelle produzieren das gelegentlich)
- Timeout- und Abbruchbehandlung
- Optionales Deaktivieren des Thinking-Modus pro Aufruf

**Harte Anforderung:** Ein Modellwechsel darf ausschließlich `config.toml` betreffen, niemals Code.

### 6.2 Intent-Router
Zweistufig, um das große Modell nicht unnötig zu wecken:
1. **Regelbasiert.** Feste Präfixe und Muster (`note:`, `remind me`, `was steht heute an`)
   werden direkt auf Werkzeuge gemappt, ohne LLM-Aufruf. Deckt den Großteil der Alltagsanfragen ab.
2. **Router-Modell.** `gemma4:e2b` klassifiziert den Rest in Kategorien:
   `quick_answer`, `vault_op`, `tool_task`, `vision_task`, `complex`.
3. Nur `complex`, `tool_task` und `vision_task` gehen an den Workhorse.

### 6.3 Tool-Loop
```
Prompt + Werkzeugkatalog
  → Modellantwort
  → enthält Tool-Call? → ausführen → Ergebnis anhängen → zurück zum Modell
  → kein Tool-Call → fertig
```
Harte Grenzen gegen Endlosschleifen:
- **max. 8 Iterationen** pro Request
- **max. 45 s** Gesamtlaufzeit, danach Abbruch mit Teilergebnis
- Wiederholter identischer Tool-Call (gleicher Name plus gleiche Argumente) → sofortiger Abbruch
- Jeder Tool-Call wird geloggt und ans HUD gestreamt

### 6.4 Memory-Layer

**Struktur im Vault:**
```
vault/
├── daily/2026-08-29.md        # Tagesnotiz, Auto-Anlage
├── notes/                     # freie Notizen
├── projects/<slug>.md         # Projektkontext
├── people/<slug>.md           # Personenkontext
└── .assistant/
    ├── index.db               # SQLite: Embeddings + Metadaten
    └── log.jsonl              # Aktionsprotokoll
```

**Frontmatter-Konvention:**
```yaml
---
created: 2026-08-29T14:22:00
tags: [projekt, assistant]
source: voice | hud | cron | manual
---
```

**Retrieval — hybrid, in dieser Reihenfolge:**
1. `ripgrep` über den Vault (exakte Begriffe, Dateinamen)
2. Vektorsuche über `sqlite-vec` (semantisch verwandt)
3. Ergebnisse zusammenführen, dedupliziert, max. 6 Chunks in den Kontext

**Indexierung:** Dateisystem-Watcher (`watchdog`), debounced auf 5 s. Nur geänderte Dateien
werden neu eingebettet.

### 6.5 HUD
**Verhalten:**
- Startet versteckt im Tray
- Globaler Hotkey (Vorschlag: `Alt+Space`) blendet ein transparentes Overlay ein
- Zeigt: Eingabefeld, laufende Tool-Calls live, letzte Antwort, Daemon-Status
- `Esc` blendet aus, der Prozess bleibt bestehen

**Regel:** Das HUD enthält keine Logik. Es rendert ausschließlich State vom Daemon und schickt
Inputs zurück. Bei geschlossenem HUD läuft alles weiter.

**Plattformdetail:** Unter macOS braucht ein Overlay, das den Fokus nicht stiehlt, ein
`NSPanel` mit `nonactivatingPanel`. Tauri kann das, teils aber nur über eigenes Swift-Binding.
Unter Windows und Linux ist es unkomplizierter. Dieser Punkt ist früh in Phase 3 zu verifizieren.

### 6.6 Voice
```
Wake-Word (openWakeWord, permanent)
  → Aufnahme bis Stille (VAD)
  → faster-whisper → Text
  → an Daemon (identischer Pfad wie HUD)
  → Antwort → Piper → Audio
```
Die Voice-Komponente ist bewusst dumm: Sie übersetzt nur zwischen Audio und Text, ohne eigenen
State. Perspektivisch kann ein `listen_to(audio)`-Werkzeug über Gemmas native Audio-Fähigkeit
Whisper ersetzen — erst nach Phase 5 evaluieren.

### 6.7 Vision
Zwei getrennte Werkzeuge, bewusst unterschiedlich teuer:

| Werkzeug | Mechanismus | Latenz | Einsatz |
|---|---|---|---|
| `read_screen(region)` | native OCR | ~50 ms | Text auslesen, Standardfall |
| `look_at(image, frage)` | `gemma4:26b` | ~2–4 s | Verstehen: Diagramme, Layouts, Fotos |

Ergänzend liefern Accessibility-APIs Fenstertext strukturiert, ganz ohne Pixel.
**Kein Dauer-Capture-Loop.** Trigger nur per Hotkey oder Fensterwechsel.

---

## 7. Werkzeugkatalog (v1)

Signaturen als Zielbild für die Implementierung.

```python
# Memory
search_vault(query: str, limit: int = 6) -> list[Chunk]
read_note(path: str) -> str
write_note(path: str, content: str, mode: Literal["create","append","replace"]) -> str
append_daily(content: str, section: str | None = None) -> str

# Zeit & Aufgaben
get_schedule(date_from: str, date_to: str) -> list[Event]
create_reminder(text: str, due: str) -> str
list_open_tasks(project: str | None = None) -> list[Task]

# Bildschirm
read_screen(region: Literal["active_window","full","selection"]) -> str
look_at(image_path: str, question: str) -> str

# System
run_shell(command: str, confirm: bool = True) -> str   # Whitelist + Bestätigung
open_app(name: str) -> str

# Web
web_fetch(url: str) -> str
web_search(query: str) -> list[Result]
```

**Sicherheitsregel:** `run_shell` arbeitet mit Whitelist. Alles außerhalb erfordert eine
explizite Bestätigung im HUD. Kein stiller Schreibzugriff außerhalb des Vaults.

---

## 8. Daemon-Protokoll (WebSocket)

**Client → Daemon**
```json
{ "type": "request", "id": "uuid", "source": "hud|voice|cron|cli",
  "text": "...", "attachments": [], "context": { "active_app": "..." } }

{ "type": "cancel", "id": "uuid" }
{ "type": "confirm", "id": "uuid", "approved": true }
```

**Daemon → Client**
```json
{ "type": "status",     "id": "uuid", "state": "routing|thinking|tool|done" }
{ "type": "tool_call",  "id": "uuid", "name": "search_vault", "args": {} }
{ "type": "token",      "id": "uuid", "text": "..." }
{ "type": "result",     "id": "uuid", "text": "...", "artifacts": [] }
{ "type": "confirm_req","id": "uuid", "action": "run_shell", "detail": "..." }
{ "type": "error",      "id": "uuid", "message": "..." }
```

Streaming ist ab Phase 1 vorzusehen, damit das HUD später nichts nachrüsten muss.

---

## 9. Repo-Struktur

```
local-assistant/
├── daemon/
│   ├── main.py                 # FastAPI + WebSocket-Server
│   ├── config.toml             # Modelle, Pfade, Limits
│   ├── router/
│   │   ├── rules.py            # regelbasiertes Routing
│   │   └── classifier.py       # Router-Modell
│   ├── loop/
│   │   ├── agent.py            # Tool-Loop mit Limits
│   │   └── session.py          # State pro Request
│   ├── llm/
│   │   └── provider.py         # Ollama-Abstraktion
│   ├── memory/
│   │   ├── vault.py            # Dateizugriff, Frontmatter
│   │   ├── index.py            # sqlite-vec, Watcher
│   │   └── retrieve.py         # Hybrid-Retrieval
│   ├── tools/
│   │   ├── registry.py         # Werkzeug-Definitionen + Dispatch
│   │   ├── vault_tools.py
│   │   ├── screen_tools.py
│   │   ├── time_tools.py
│   │   └── system_tools.py
│   └── platform/
│       ├── ocr_macos.py
│       └── ocr_windows.py
├── hud/                        # Tauri v2
│   ├── src-tauri/
│   └── src/                    # Svelte
├── voice/
│   ├── listener.py             # Wake-Word + VAD + STT
│   └── speaker.py              # Piper
├── scripts/
│   ├── setup.sh                # Modelle pullen, Env aufsetzen
│   └── healthcheck.py
└── PROJECT.md
```

---

## 10. Umsetzungsplan

Jede Phase ist eigenständig lauffähig und einzeln testbar. Keine Phase beginnt, bevor das
Akzeptanzkriterium der vorigen erfüllt ist.

### Phase 0 — Fundament
- `uv`-Projekt, Ollama-Installation, Modelle ziehen
- `llm/provider.py` mit Rollenkonzept
- Healthcheck-Skript: Modelle geladen, VRAM-Auslastung, Antwortzeit pro Rolle

**Akzeptanz:** `python scripts/healthcheck.py` gibt die Latenz für Router und Workhorse aus.

### Phase 1 — Daemon-Kern
- FastAPI + WebSocket, Protokoll aus Abschnitt 8
- Werkzeug-Registry mit zwei Dummy-Werkzeugen
- Tool-Loop inklusive aller Abbruchgrenzen
- CLI-Client zum Testen

**Akzeptanz:** `cli.py "wie spät ist es"` liefert eine Antwort über einen echten Tool-Call;
die Loop bricht bei einer erzwungenen Endlosschleife nachweislich ab.

### Phase 2 — Memory
- Vault-Werkzeuge (lesen, schreiben, Daily Note)
- SQLite-Index, Embeddings, Watcher
- Hybrid-Retrieval
- Automatische Tagesnotiz per Scheduler

**Akzeptanz:** Eine per CLI angelegte Notiz wird über eine semantisch anders formulierte Frage
wiedergefunden.

### Phase 3 — HUD  *(benötigt geklärtes Betriebssystem)*
- Tauri-Grundgerüst, Tray, globaler Hotkey, transparentes Fenster
- WebSocket-Client, Live-Anzeige der Tool-Calls
- Bestätigungsdialog für `run_shell`

**Akzeptanz:** Der Hotkey öffnet das Overlay in < 150 ms; das Beenden des HUD bricht keinen
laufenden Request ab; Idle-RAM unter 100 MB.

### Phase 4 — Vision  *(benötigt geklärtes Betriebssystem)*
- Native OCR pro Plattform, `read_screen`
- `look_at` über `gemma4:26b`
- Trigger per Hotkey, kein Dauer-Capture

**Akzeptanz:** Das aktive Fenster wird in < 200 ms als Text erfasst; eine Bildfrage wird
beantwortet, ohne den Router dauerhaft aus dem VRAM zu drängen.

### Phase 5 — Voice
- Wake-Word, VAD, STT, TTS
- Anbindung an den bestehenden Daemon-Pfad

**Akzeptanz:** Sprachbefehl → Aktion → gesprochene Antwort in < 6 s end-to-end;
Idle-CPU-Last des Wake-Words unter 3 %.

### Phase 6 — Härtung
- Fehlerbehandlung, Reconnect, Autostart
- Werkzeug-Erweiterung nach tatsächlichem Bedarf
- Modell-A/B: `gemma4:26b` gegen `qwen3.6:27b` auf realen Prompts messen

---

## 11. Risiken

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| Tool-Calling lokal unzuverlässig | Loop bricht ab, falsche Werkzeuge | Wenige, eng definierte Werkzeuge; Retry mit Schema-Hinweis; Fallback auf `qwen3.6:27b` |
| VRAM-Konkurrenz beim Modellwechsel | Wartezeit von Sekunden | Router permanent geladen; Workhorse mit `keep_alive` statt Dauerlast; Nachladen im HUD sichtbar machen |
| macOS-Overlay stiehlt Fokus | HUD unbrauchbar | Früh in Phase 3 verifizieren; ggf. Swift-Binding |
| Kontext-Einbruch bei langen Sessions | Qualitätsverlust | `num_ctx` klein halten; Session nach N Turns zusammenfassen statt anhängen |
| Workhorse zu schwach für komplexe Aufgaben | Frust | Bewusste Eskalationsgrenze: `complex` kann optional an ein Cloud-Modell gehen (opt-in, klar markiert) |
| Scope-Kriechen | Projekt wird nie fertig | Phasen strikt sequenziell; Werkzeuge erst in Phase 6 erweitern |

---

## 12. Offene Entscheidungen

Vom Auftraggeber zu klären, bevor die betroffenen Phasen starten.

1. **Betriebssystem.** *(Blockiert Phase 3 und 4.)* Bestimmt OCR-Backend, Overlay-Aufwand und
   Autostart-Mechanik.
2. **Vault-Standort.** Bestehender Obsidian-Vault oder neuer, dedizierter Vault?
   Empfehlung: neuer Vault für Phase 2, später zusammenführen.
3. **Wake-Word oder nur Hotkey.** Hotkey ist zuverlässiger und billiger.
4. **Cloud-Eskalation.** Darf `complex` optional an ein API-Modell gehen? Widerspricht dem
   Kostenziel, wäre aber ein Sicherheitsnetz.
5. **Projektname.** Aktuell nur ein Arbeitstitel.

---

## 13. Konfigurationsvorlage

```toml
# daemon/config.toml

[models]
router    = "gemma4:e2b"
workhorse = "gemma4:26b"
embed     = "nomic-embed-text"

[models.options]
num_ctx         = 16384
flash_attention = true
kv_cache_type   = "q8_0"

[models.keep_alive]
router    = "-1"
workhorse = "10m"
embed     = "60s"

[loop]
max_iterations  = 8
timeout_seconds = 45

[vault]
path         = "~/Vault"
daily_folder = "daily"

[server]
host = "127.0.0.1"
port = 8765

[security]
shell_whitelist = ["ls", "cat", "open", "git status"]
require_confirm_outside_whitelist = true
```
