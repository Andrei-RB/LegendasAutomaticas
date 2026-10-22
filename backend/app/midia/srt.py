def formatar_timestamp(segundos: float) -> str:
    """Formata segundos como HH:MM:SS,mmm, arredondando ao milissegundo."""
    total_ms = max(0, round(segundos * 1000))
    horas, resto = divmod(total_ms, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segs, ms = divmod(resto, 1000)
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{ms:03d}"
