import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "exportar_openapi.py"


def _exportar(destino: Path, cwd: Path | None = None) -> bytes:
    subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(destino)], check=True, timeout=120, cwd=cwd
    )
    return destino.read_bytes()


def test_exportacao_e_deterministica_e_contem_rotas_de_auth(tmp_path: Path) -> None:
    primeira = _exportar(tmp_path / "a" / "openapi.json")
    segunda = _exportar(tmp_path / "b" / "openapi.json")
    assert primeira == segunda
    assert primeira.endswith(b"\n") and b"\r" not in primeira
    caminhos = json.loads(primeira)["paths"]
    assert "/api/v1/auth/login" in caminhos
    assert "/api/v1/auth/eu" in caminhos


def test_exportacao_nao_cria_diretorios_no_cwd(tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    _exportar(tmp_path / "saida" / "openapi.json", cwd=cwd)
    assert list(cwd.iterdir()) == []
