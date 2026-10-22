import os
import tempfile
from pathlib import Path

# Diretórios temporários definidos antes de qualquer import de app.
_BASE = Path(tempfile.mkdtemp(prefix="viraliza_testes_"))
os.environ["UPLOAD_DIR"] = str(_BASE / "uploads")
os.environ["OUTPUT_DIR"] = str(_BASE / "saidas")
os.environ["LOG_DIR"] = str(_BASE / "logs")
os.environ["DEBUG"] = "false"

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
