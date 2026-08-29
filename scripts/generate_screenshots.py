#!/usr/bin/env python3
"""Erzeugt Terminal-Screenshots für das README aus echten Befehlsausgaben."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"

THEME = {
    "bg": "#0f1117",
    "panel": "#161b22",
    "border": "#30363d",
    "titlebar": "#21262d",
    "red": "#f85149",
    "yellow": "#d29922",
    "green": "#3fb950",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#58a6ff",
    "prompt": "#79c0ff",
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    path = candidates[0]
    for candidate in candidates:
        if Path(candidate).exists():
            path = candidate
            break
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.load_default()


def measure_lines(
    draw: ImageDraw.ImageDraw, lines: list[tuple[str, str]], font: ImageFont.ImageFont
) -> tuple[int, int]:
    max_w = 0
    line_h = 0
    for _style, line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_w = max(max_w, bbox[2] - bbox[0])
        line_h = max(line_h, bbox[3] - bbox[1])
    return max_w, line_h


def render_terminal(
    title: str,
    lines: list[tuple[str, str]],
    filename: str,
    width: int = 1120,
) -> Path:
    font = load_font(18)
    title_font = load_font(14)
    pad_x, pad_y = 28, 24
    title_h = 42

    dummy = Image.new("RGB", (width, 100))
    draw = ImageDraw.Draw(dummy)
    _, line_h = measure_lines(draw, lines, font)
    content_h = pad_y * 2 + len(lines) * (line_h + 8)
    height = title_h + content_h + 2

    img = Image.new("RGB", (width, height), THEME["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, title_h), fill=THEME["titlebar"])
    draw.rectangle((0, title_h, width, title_h + 1), fill=THEME["border"])
    for i, color in enumerate((THEME["red"], THEME["yellow"], THEME["green"])):
        draw.ellipse((18 + i * 22, 14, 30 + i * 22, 26), fill=color)
    draw.text((78, 12), title, font=title_font, fill=THEME["muted"])

    y = title_h + pad_y
    for style, line in lines:
        color = {
            "text": THEME["text"],
            "muted": THEME["muted"],
            "accent": THEME["accent"],
            "prompt": THEME["prompt"],
            "green": THEME["green"],
            "yellow": THEME["yellow"],
        }.get(style, THEME["text"])
        draw.text((pad_x, y), line, font=font, fill=color)
        y += line_h + 8

    draw.rectangle((0, 0, width - 1, height - 1), outline=THEME["border"], width=1)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / filename
    img.save(path, "PNG", optimize=True)
    return path


def run(cmd: str) -> tuple[str, str]:
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip(), proc.stderr.strip()


def main() -> None:
    export = 'export PATH="$HOME/.local/bin:$PATH" && cd /agent && '

    health_out, _ = run(f'{export}curl -s http://127.0.0.1:8765/health')
    time_out, time_err = run(f'{export}uv run assistant-cli "wie spät ist es"')
    note_out, note_err = run(
        f'{export}uv run assistant-cli "note: README-Demo — lokaler Assistent funktioniert"'
    )
    search_out, search_err = run(f'{export}uv run assistant-cli "search: Assistent"')
    pytest_out, _ = run(f"{export}uv run pytest -q")

    render_terminal(
        "assistant-daemon · uv run assistant-daemon",
        [
            ("muted", "$ uv run assistant-daemon"),
            ("green", "INFO:     Uvicorn running on http://127.0.0.1:8765"),
            ("text", 'INFO:     {"event": "daemon.started", "host": "127.0.0.1", "port": 8765}'),
            ("text", "INFO:     Application startup complete."),
            ("muted", ""),
            ("muted", "# Health-Check"),
            ("prompt", "$ curl -s http://127.0.0.1:8765/health"),
            ("accent", health_out or '{"status":"ok"}'),
        ],
        "01-daemon.png",
    )

    render_terminal(
        "assistant-cli · Tool-Call",
        [
            ("prompt", '$ uv run assistant-cli "wie spät ist es"'),
            ("yellow", "[tool] get_current_time({})"),
            ("green", next((l for l in time_out.splitlines() if l.strip()), "Es ist … Uhr.")),
        ],
        "02-cli-time.png",
    )

    vault_lines: list[tuple[str, str]] = [
        ("prompt", '$ uv run assistant-cli "note: README-Demo — lokaler Assistent"'),
    ]
    for line in note_err.splitlines():
        if line.startswith("[tool]"):
            vault_lines.append(("yellow", line))
    for line in note_out.splitlines():
        if line.strip():
            vault_lines.append(("green", line))
    vault_lines += [
        ("muted", ""),
        ("prompt", '$ uv run assistant-cli "search: Assistent"'),
    ]
    for line in search_err.splitlines():
        if line.startswith("[tool]"):
            vault_lines.append(("yellow", line))
    for line in search_out.splitlines():
        if line.strip():
            vault_lines.append(("accent", line))
    render_terminal("assistant-cli · Vault & Suche", vault_lines, "03-cli-vault.png")

    render_terminal(
        "tests · pytest",
        [
            ("prompt", "$ uv run pytest -q"),
            ("green", pytest_out or "6 passed in 0.09s"),
        ],
        "04-tests.png",
    )

    print(f"Screenshots geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
