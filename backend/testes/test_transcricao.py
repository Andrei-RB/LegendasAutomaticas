from types import SimpleNamespace

from app.midia import transcricao
from app.nucleo.config import settings


class _ModeloFalso:
    def __init__(self, segmentos):
        self._segmentos = segmentos

    def transcribe(self, *_, **__):
        return iter(self._segmentos), SimpleNamespace(duration=10.0)


def _palavra(texto, inicio, fim):
    return SimpleNamespace(word=texto, start=inicio, end=fim)


def _gerar(monkeypatch, segmentos, job_id):
    monkeypatch.setattr(transcricao, "carregar_modelo", lambda: _ModeloFalso(segmentos))
    caminho = transcricao.transcrever_e_gerar_srt("audio.wav", job_id)
    assert caminho.startswith(settings.OUTPUT_DIR)
    with open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


def test_gera_uma_entrada_por_palavra(monkeypatch):
    segmento = SimpleNamespace(
        start=0.0,
        end=1.0,
        text="Olá mundo",
        words=[_palavra(" Olá", 0.0, 0.4), _palavra(" mundo", 0.4, 0.9996), _palavra("  ", 1, 1)],
    )

    srt = _gerar(monkeypatch, [segmento], "palavras")

    assert srt == (
        "1\n00:00:00,000 --> 00:00:00,400\nOlá\n\n2\n00:00:00,400 --> 00:00:01,000\nmundo\n\n"
    )


def test_usa_o_segmento_quando_nao_ha_palavras(monkeypatch):
    segmento = SimpleNamespace(start=1.5, end=2.5, text=" frase inteira ", words=None)

    srt = _gerar(monkeypatch, [segmento], "segmento")

    assert srt == "1\n00:00:01,500 --> 00:00:02,500\nfrase inteira\n\n"
