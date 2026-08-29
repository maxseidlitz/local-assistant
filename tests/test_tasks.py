from daemon.config import VaultConfig
from daemon.memory.tasks import add_task, list_open
from daemon.memory.vault import Vault


def test_add_and_list_tasks(tmp_path):
    vault = Vault(VaultConfig(path=str(tmp_path)))
    add_task(vault, "Milch holen", "2026-08-30")
    listed = list_open(vault)
    assert "Milch holen" in listed
    assert "2026-08-30" in listed
    assert "Keine offenen" not in listed
    empty = list_open(vault, project="unbekannt")
    assert "Keine offenen" in empty
