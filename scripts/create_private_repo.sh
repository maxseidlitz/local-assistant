#!/usr/bin/env bash
# Privates GitHub-Repository anlegen und pushen
set -euo pipefail

REPO_NAME="${1:-local-assistant}"
BRANCH="${2:-$(git branch --show-current)}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) nicht gefunden."
  echo "Installation: https://cli.github.com/"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Bitte zuerst anmelden: gh auth login"
  exit 1
fi

echo "==> Erstelle privates Repository: $REPO_NAME"
gh repo create "$REPO_NAME" --private --source=. --remote=origin --description "Lokales persönliches Assistenzsystem — privat"

echo "==> Pushe Branch: $BRANCH"
git push -u origin "$BRANCH"

echo "==> Fertig. Repository ist privat."
gh repo view --web 2>/dev/null || true
