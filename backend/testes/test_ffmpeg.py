import subprocess

from app.midia.ffmpeg import extrair_audio, montar_comando_audio


def test_comando_audio_estrutura():
    cmd = montar_comando_audio("/dados/video.mp4", "/dados/audio.wav")
    assert isinstance(cmd, list)
    assert all(isinstance(item, str) for item in cmd)
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-i") + 1] == "/dados/video.mp4"
    assert cmd[cmd.index("-ar") + 1] == "16000"
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert cmd[-1] == "/dados/audio.wav"


def test_comando_audio_metacaracteres_ficam_em_um_unico_argumento():
    perigoso = "/dados/v; rm -rf $(id) `x`.mp4"
    cmd = montar_comando_audio(perigoso, "/dados/a b.wav")
    assert perigoso in cmd
    assert cmd[-1] == "/dados/a b.wav"


def test_comando_audio_caminho_unicode():
    cmd = montar_comando_audio("/dados/vídeo_ação.mp4", "/dados/áudio.wav")
    assert "/dados/vídeo_ação.mp4" in cmd
    assert cmd[-1] == "/dados/áudio.wav"


def test_extrair_audio_usa_lista_e_nunca_shell(monkeypatch):
    chamadas = []

    def falso(args, *posicionais, **nomeados):
        chamadas.append((args, nomeados))
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", falso)

    resultado = extrair_audio("/dados/video.mp4", "job-123")

    assert isinstance(resultado, str)
    assert len(chamadas) == 1
    args, nomeados = chamadas[0]
    assert isinstance(args, list)
    assert args[0] == "ffmpeg"
    assert not nomeados.get("shell", False)
    assert args[-1] == resultado
