#!/usr/bin/env bash
# Modelle pullen, Umgebung aufsetzen
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Local Assistant Setup"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv nicht gefunden — installiere..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Python-Umgebung"
uv sync

if ! command -v ollama >/dev/null 2>&1; then
  echo "WARNUNG: Ollama nicht installiert."
  echo "  Linux: curl -fsSL https://ollama.com/install.sh | sh"
  echo "  macOS: brew install ollama"
  exit 0
fi

echo "==> Ollama-Modelle ziehen"
CONFIG="$ROOT/daemon/config.toml"
ROUTER=$(grep -E '^\s*router\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')
WORKHORSE=$(grep -E '^\s*workhorse\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')
EMBED=$(grep -E '^\s*embed\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')

for model in "$ROUTER" "$WORKHORSE" "$EMBED"; do
  echo "  pulling $model..."
  ollama pull "$model" || echo "  WARNUNG: $model konnte nicht geladen werden"
done

echo "==> Vault-Verzeichnis"
VAULT_PATH=$(grep -E '^\s*path\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')
mkdir -p "${VAULT_PATH/#\~/$HOME}"

echo "==> Fertig. Starte den Daemon mit:"
echo "  uv run assistant-daemon"
echo "  uv run assistant-cli \"wie spät ist es\""
