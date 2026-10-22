import pytest

from app.midia.srt import formatar_timestamp


@pytest.mark.parametrize(
    ("segundos", "esperado"),
    [
        (0, "00:00:00,000"),
        (61.5, "00:01:01,500"),
        (1.9996, "00:00:02,000"),
        (3599.9996, "01:00:00,000"),
        (3600, "01:00:00,000"),
        (0.001, "00:00:00,001"),
        (59.999, "00:00:59,999"),
        (3725.25, "01:02:05,250"),
        (7322.5, "02:02:02,500"),
        (-1, "00:00:00,000"),
        (-0.0004, "00:00:00,000"),
    ],
)
def test_formatar_timestamp(segundos, esperado):
    assert formatar_timestamp(segundos) == esperado
