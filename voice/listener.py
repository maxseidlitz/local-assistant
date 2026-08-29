"""Wake-Word + VAD + STT — Phase 5."""

from __future__ import annotations

import argparse
import asyncio
import json

import websockets

DAEMON_WS = "ws://127.0.0.1:8765/ws"


async def send_text(text: str) -> None:
    async with websockets.connect(DAEMON_WS) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "request",
                    "id": "voice-1",
                    "source": "voice",
                    "text": text,
                    "attachments": [],
                    "context": {},
                }
            )
        )
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "result":
                print(msg.get("text", ""))
                return


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice listener (Stub Phase 5)")
    parser.add_argument("--text", help="Simuliere STT-Ergebnis")
    args = parser.parse_args()
    if not args.text:
        print("Phase 5: openWakeWord + faster-whisper noch nicht implementiert.")
        print("Nutze --text zum Simulieren einer Spracheingabe.")
        return
    asyncio.run(send_text(args.text))


if __name__ == "__main__":
    main()
