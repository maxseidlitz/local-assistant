"""Tests für Vault-Zugriff."""

from daemon.config import VaultConfig
from daemon.memory.vault import Vault


def test_write_and_read_note(tmp_path):
    vault = Vault(VaultConfig(path=str(tmp_path)))
    result = vault.write_note("notes/test.md", "Hallo Welt", mode="create", source="cli")
    assert "geschrieben" in result
    content = vault.read_note("notes/test.md")
    assert "Hallo Welt" in content


def test_append_daily(tmp_path):
    vault = Vault(VaultConfig(path=str(tmp_path)))
    vault.append_daily("Erster Eintrag", source="cli")
    vault.append_daily("Zweiter Eintrag", source="cli")
    daily = vault.read_note(str(vault.daily_path().relative_to(vault.root)))
    assert "Erster Eintrag" in daily
    assert "Zweiter Eintrag" in daily
