"""Piper TTS — Phase 5 Stub."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Piper TTS (Stub Phase 5)")
    parser.add_argument("text", nargs="?", default="Hallo")
    args = parser.parse_args()
    print(f"[TTS Stub] Würde sprechen: {args.text}")
    print("Phase 5: Piper-Integration folgt.")


if __name__ == "__main__":
    main()
