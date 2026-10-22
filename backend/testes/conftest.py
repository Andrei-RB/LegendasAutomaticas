import os
import tempfile
from pathlib import Path

# Ambiente fixado antes de qualquer import de app, para ignorar o .env local.
_BASE = Path(tempfile.mkdtemp(prefix="viraliza_testes_"))
os.environ["UPLOAD_DIR"] = str(_BASE / "uploads")
os.environ["OUTPUT_DIR"] = str(_BASE / "saidas")
os.environ["LOG_DIR"] = str(_BASE / "logs")
os.environ["DEBUG"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["CORS_ORIGINS"] = ""
os.environ["MAX_UPLOAD_SIZE"] = str(1024 * 1024 * 1024)
os.environ["ALLOWED_EXTENSIONS"] = ".mp4,.avi,.mov,.mkv"

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
