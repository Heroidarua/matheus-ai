"""Funções matemáticas pequenas, sem dependências. Usadas por módulos puros e de sensores."""


def valor_real(valor, minimo=float("-inf"), maximo=float("inf")):
    """Converte para float e rejeita NaN, infinito ou fora do intervalo (levanta ValueError)."""
    x = float(valor)
    if x != x or not minimo <= x <= maximo:
        raise ValueError(f"valor fora do domínio: {valor!r}")
    return x


def clamp(x, lo=0.0, hi=1.0):
    """Limita `x` ao intervalo [lo, hi]."""
    return lo if x < lo else hi if x > hi else x
