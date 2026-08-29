# HUD — Web-Overlay und Tauri

Das HUD ist ein schlanker Client ohne eigene Logik. Derselbe `index.html` läuft im Browser und in Tauri.

## Browser

```bash
uv run assistant-daemon
# http://127.0.0.1:8765/
```

## Tauri

```bash
uv run assistant-daemon
cd hud
npm install
npm run tauri dev
```

- Tray, Start versteckt
- `Alt+Space` blendet ein
- `Esc` blendet aus, der Daemon läuft weiter
- `Ctrl+Space` halten: Push-to-Talk
- Transparent, always-on-top, ohne Fensterdekoration

macOS-`NSPanel` / Fokus-Diebstahl: in dieser Stufe Always-on-Top ohne native `nonactivatingPanel`-Garantie. Wenn das Overlay den Fokus stiehlt, als Nächstes ein Swift-Binding nachziehen.

## Protokoll

Verbindet sich mit `ws://127.0.0.1:8765/ws` (`ASSISTANT_URL` überschreibt die Basis-URL).

Sendet `request` / `cancel` / `confirm`. Zeigt `status` (inkl. Modell), `token`, `tool_call`, `tool_result` und den `run_shell`-Dialog.
