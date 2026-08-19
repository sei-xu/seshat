import pytest

from seshat.core.vault import VaultClient


@pytest.fixture
def vault(tmp_path):
    """Clone de teste mínimo do vault — só as pastas que o schema exige."""
    for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
        (tmp_path / folder).mkdir()
    return VaultClient(tmp_path)
