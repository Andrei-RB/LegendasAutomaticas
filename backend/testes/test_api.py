import uuid


def test_health_retorna_saudavel(cliente):
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "healthy"}


def test_raiz_nao_serve_arquivos_estaticos(cliente):
    assert cliente.get("/").status_code == 404


def test_upload_sem_arquivo_retorna_422(cliente):
    assert cliente.post("/api/v1/upload-video").status_code == 422


def test_upload_extensao_invalida_retorna_400(cliente):
    resposta = cliente.post(
        "/api/v1/upload-video",
        files={"file": ("malicioso.js", b"payload", "application/javascript")},
    )
    assert resposta.status_code == 400
    assert "permitida" in resposta.json()["detail"].lower()


def test_upload_metodo_get_retorna_405(cliente):
    assert cliente.get("/api/v1/upload-video").status_code == 405


def test_download_inexistente_retorna_404(cliente):
    assert cliente.get(f"/api/v1/download/{uuid.uuid4()}").status_code == 404


def test_download_id_invalido_retorna_400(cliente):
    assert cliente.get("/api/v1/download/a_b").status_code == 400


def test_download_path_traversal_rejeitado(cliente):
    resposta = cliente.get("/api/v1/download/..%2F..%2Fetc%2Fpasswd")
    assert resposta.status_code in (400, 404)


def test_upload_nome_com_path_traversal_rejeitado(cliente):
    resposta = cliente.post(
        "/api/v1/upload-video",
        files={"file": ("../../etc/passwd", b"x", "text/plain")},
    )
    assert resposta.status_code == 400
