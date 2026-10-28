"""Formatação numérica em português brasileiro (sem depender do locale do SO)."""
from __future__ import annotations

import math


def _vazio(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def inteiro(v) -> str:
    if _vazio(v):
        return "—"
    return f"{int(round(v)):,}".replace(",", ".")


def decimal(v, casas: int = 1) -> str:
    if _vazio(v):
        return "—"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(v, casas: int = 1) -> str:
    return "—" if _vazio(v) else f"{decimal(v, casas)}%"


def pp(v, casas: int = 1) -> str:
    """Pontos percentuais com sinal explícito."""
    if _vazio(v):
        return "—"
    sinal = "+" if v > 0 else ("−" if v < 0 else "±")
    return f"{sinal}{decimal(abs(v), casas)} p.p."


def compacto(v) -> str:
    """1.234.567 → '1,23 mi'; 12.345 → '12,3 mil'."""
    if _vazio(v):
        return "—"
    a = abs(v)
    if a >= 1e6:
        return f"{decimal(v / 1e6, 1)} mi"
    if a >= 1e4:
        return f"{decimal(v / 1e3, 1)} mil"
    return inteiro(v)
