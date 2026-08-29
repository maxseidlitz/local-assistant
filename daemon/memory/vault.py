"""Vault-Zugriff mit Frontmatter-Konvention."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import frontmatter

from daemon.config import VaultConfig, expand_path


class Vault:
    def __init__(self, config: VaultConfig) -> None:
        self._config = config
        self.root = expand_path(config.path)
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        for sub in ("notes", "projects", "people", "daily", ".assistant"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        resolved = p.resolve()
        if not str(resolved).startswith(str(self.root)):
            raise ValueError(f"Pfad außerhalb des Vaults: {path}")
        return resolved

    def read_note(self, path: str) -> str:
        fp = self._resolve(path)
        if not fp.exists():
            return f"Notiz nicht gefunden: {path}"
        post = frontmatter.load(fp)
        body = post.content.strip()
        meta = dict(post.metadata)
        header = "\n".join(f"{k}: {v}" for k, v in meta.items())
        return f"---\n{header}\n---\n\n{body}" if header else body

    def write_note(
        self,
        path: str,
        content: str,
        mode: Literal["create", "append", "replace"] = "create",
        source: str = "manual",
    ) -> str:
        fp = self._resolve(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()

        if mode == "create" and fp.exists():
            return f"Notiz existiert bereits: {path}"
        if mode == "replace" or (mode == "create" and not fp.exists()):
            post = frontmatter.Post(content)
            post.metadata.update({"created": now, "source": source, "tags": []})
            fp.write_text(frontmatter.dumps(post), encoding="utf-8")
            return f"Notiz geschrieben: {path}"
        if mode == "append":
            if fp.exists():
                existing = frontmatter.load(fp)
                existing.content = (existing.content.rstrip() + "\n\n" + content).strip() + "\n"
                fp.write_text(frontmatter.dumps(existing), encoding="utf-8")
            else:
                post = frontmatter.Post(content)
                post.metadata.update({"created": now, "source": source, "tags": []})
                fp.write_text(frontmatter.dumps(post), encoding="utf-8")
            return f"Notiz ergänzt: {path}"
        return f"Unbekannter Modus: {mode}"

    def daily_path(self, day: date | None = None) -> Path:
        d = day or date.today()
        folder = self.root / self._config.daily_folder
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{d.isoformat()}.md"

    def ensure_daily_note(self, source: str = "cron") -> Path:
        fp = self.daily_path()
        if fp.exists():
            return fp
        post = frontmatter.Post(f"# {date.today().isoformat()}\n")
        post.metadata.update({
            "created": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "tags": ["daily"],
        })
        fp.write_text(frontmatter.dumps(post), encoding="utf-8")
        return fp

    def append_daily(self, content: str, section: str | None = None, source: str = "assistant") -> str:
        fp = self.ensure_daily_note(source=source)
        post = frontmatter.load(fp)
        block = content.strip()
        if section:
            block = f"\n## {section}\n\n{block}"
        post.content = (post.content.rstrip() + "\n\n" + block).strip() + "\n"
        fp.write_text(frontmatter.dumps(post), encoding="utf-8")
        return f"Tagesnotiz aktualisiert: {fp.relative_to(self.root)}"

    def iter_markdown_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.root.rglob("*.md"):
            if ".assistant" in path.parts:
                continue
            files.append(path)
        return files
