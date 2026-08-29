#!/usr/bin/env python3
"""CLI-Client zum Testen des Daemons."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

import websockets


async def send_request(
    text: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    source: str = "cli",
    timeout: float = 60.0,
) -> str:
    uri = f"ws://{host}:{port}/ws"
    request_id = str(uuid.uuid4())
    result_text = ""
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "request",
                    "id": request_id,
                    "source": source,
                    "text": text,
                    "attachments": [],
                    "context": {},
                }
            )
        )
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                return result_text or "Timeout beim Warten auf Antwort."
            msg = json.loads(raw)
            msg_type = msg.get("type")
            if msg_type == "token":
                token = msg.get("text", "")
                print(token, end="", flush=True)
                result_text += token
            elif msg_type == "tool_call":
                print(
                    f"\n[tool] {msg.get('name')}({json.dumps(msg.get('args', {}), ensure_ascii=False)})",
                    file=sys.stderr,
                )
            elif msg_type == "result":
                result_text = msg.get("text", result_text)
                break
            elif msg_type == "error":
                print(f"\n[error] {msg.get('message')}", file=sys.stderr)
                if result_text:
                    break
                return f"Fehler: {msg.get('message')}"
    return result_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Assistant CLI")
    parser.add_argument("text", nargs="?", help="Anfrage an den Daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not args.text:
        parser.print_help()
        sys.exit(1)

    result = asyncio.run(send_request(args.text, host=args.host, port=args.port))
    if result and not result.endswith("\n"):
        print()
    sys.stdout.flush()


if __name__ == "__main__":
    main()
