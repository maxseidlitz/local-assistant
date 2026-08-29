# HUD — Tauri v2 Overlay (Phase 3)

Das HUD ist ein schlanker WebSocket-Client ohne eigene Logik.

## Voraussetzungen

- **Betriebssystem muss geklärt sein** (blockiert Phase 3 laut PROJECT.md)
- Rust toolchain (`rustup`)
- Node.js 20+

## Geplante Features

- Tray-Icon, globaler Hotkey (`Alt+Space`)
- Transparentes Always-on-Top-Fenster
- Live-Anzeige von Tool-Calls und Daemon-Status
- Bestätigungsdialog für `run_shell`

## Initialisierung (wenn OS geklärt)

```bash
cd hud
npm create tauri-app@latest . -- --template svelte-ts
npm install
npm run tauri dev
```

Der WebSocket-Client verbindet sich mit `ws://127.0.0.1:8765/ws`.
