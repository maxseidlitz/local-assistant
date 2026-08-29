"""Konfigurationsladen für den Daemon."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.toml"


@dataclass
class ModelsConfig:
    router: str = "gemma4:e2b"
    workhorse: str = "gemma4:26b"
    embed: str = "nomic-embed-text"
    options: dict[str, Any] = field(default_factory=dict)
    keep_alive: dict[str, str] = field(default_factory=dict)


@dataclass
class LoopConfig:
    max_iterations: int = 8
    timeout_seconds: float = 45.0


@dataclass
class VaultConfig:
    path: str = "~/Vault"
    daily_folder: str = "daily"


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class SecurityConfig:
    shell_whitelist: list[str] = field(default_factory=list)
    require_confirm_outside_whitelist: bool = True


@dataclass
class SchedulerConfig:
    daily_note_hour: int = 0
    daily_note_minute: int = 5


@dataclass
class AppConfig:
    models: ModelsConfig = field(default_factory=ModelsConfig)
    ollama_base_url: str = "http://127.0.0.1:11434"
    loop: LoopConfig = field(default_factory=LoopConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    models_raw = raw.get("models", {})
    return AppConfig(
        models=ModelsConfig(
            router=models_raw.get("router", "gemma4:e2b"),
            workhorse=models_raw.get("workhorse", "gemma4:26b"),
            embed=models_raw.get("embed", "nomic-embed-text"),
            options=models_raw.get("options", {}),
            keep_alive=models_raw.get("keep_alive", {}),
        ),
        ollama_base_url=raw.get("ollama", {}).get("base_url", "http://127.0.0.1:11434"),
        loop=LoopConfig(**raw.get("loop", {})),
        vault=VaultConfig(**raw.get("vault", {})),
        server=ServerConfig(**raw.get("server", {})),
        security=SecurityConfig(**raw.get("security", {})),
        scheduler=SchedulerConfig(**raw.get("scheduler", {})),
    )


def expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()
