"""Métricas eleitorais com denominadores explícitos.

Princípios:
- Percentual agregado = Σ numerador ÷ Σ denominador, depois de agregar.
  Nunca média de percentuais.
- Denominador zero ou ausente → percentual ausente (NaN) com estado explícito,
  nunca 0 % nem empate.
- O denominador de "% sobre votos válidos" vem da apuração oficial do cargo no
  território (QT_TOTAL_VOTOS_VALIDOS), e não da soma dos candidatos exibidos.
  Filtrar candidatos não altera o denominador.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Estados de um território para uma métrica
COM_VALOR = "com_valor"
SEM_VOTOS = "sem_votos"            # denominador = 0 (ex.: nenhum voto válido)
SEM_DADO = "sem_dado"              # território sem registro no recorte
EMPATE = "empate"


@dataclass(frozen=True)
class Indicador:
    chave: str
    rotulo: str
    numerador: str
    denominador: str
    formula: str
    unidade: str = "%"
    nota: str = ""


# Indicadores de participação/apuração (colunas de fato_apuracao).
INDICADORES = {
    i.chave: i for i in (
        Indicador("comparecimento", "Comparecimento", "QT_COMPARECIMENTO", "QT_APTOS",
                  "comparecimento ÷ eleitorado apto do cargo"),
        Indicador("abstencao", "Abstenção", "QT_ABSTENCOES", "QT_APTOS",
                  "abstenções ÷ eleitorado apto do cargo",
                  nota="No exterior, eleitores de seções não instaladas não entram em abstenções nem em "
                       "comparecimento (QT_ELEITORES_SECOES_NAO_INSTALADAS)."),
        Indicador("brancos", "Votos em branco", "QT_VOTOS_BRANCOS", "QT_VOTOS",
                  "votos em branco ÷ total de votos do cargo",
                  nota="Para Senador em 2026, o total de votos é 2 × comparecimento (dois votos por eleitor)."),
        Indicador("nulos", "Votos nulos", "QT_TOTAL_VOTOS_NULOS", "QT_VOTOS",
                  "votos nulos (inclui nulos técnicos) ÷ total de votos do cargo",
                  nota="Para Senador em 2026, o total de votos é 2 × comparecimento."),
        Indicador("validos", "Votos válidos", "QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS",
                  "votos válidos (nominais + legenda) ÷ total de votos do cargo"),
        Indicador("anulados_subjudice", "Anulados sub judice", "QT_TOTAL_VOTOS_ANUL_SUBJUD", "QT_VOTOS",
                  "votos anulados sub judice ÷ total de votos do cargo"),
    )
}


def percentual(numerador, denominador) -> np.ndarray:
    """100 × num ÷ den, com NaN quando o denominador é 0 ou ausente."""
    num = np.asarray(numerador, dtype="float64")
    den = np.asarray(denominador, dtype="float64")
    out = np.full(np.broadcast(num, den).shape, np.nan)
    ok = np.isfinite(den) & (den > 0) & np.isfinite(num)
    np.divide(100.0 * num, den, out=out, where=ok)
    return out


def estado_denominador(denominador) -> np.ndarray:
    den = pd.to_numeric(pd.Series(denominador), errors="coerce").to_numpy(dtype="float64", na_value=np.nan)
    return np.where(np.isnan(den), SEM_DADO, np.where(den > 0, COM_VALOR, SEM_VOTOS))


def agregar_indicador(apuracao: pd.DataFrame, chaves: list[str], indicador: str) -> pd.DataFrame:
    """Soma numerador e denominador por `chaves` e só então calcula o percentual."""
    ind = INDICADORES[indicador]
    g = apuracao.groupby(chaves, as_index=False, dropna=False)[[ind.numerador, ind.denominador]].sum()
    g["valor"] = percentual(g[ind.numerador], g[ind.denominador])
    g["estado"] = estado_denominador(g[ind.denominador])
    return g


def percentual_sobre_validos(votos: pd.DataFrame, apuracao: pd.DataFrame, chaves: list[str],
                             col_votos: str = "votos") -> pd.DataFrame:
    """Junta cada linha de votos ao denominador oficial do território.

    `votos`: chaves + candidato + `col_votos` (já filtrado ou não — o denominador
    não depende do filtro). `apuracao`: chaves + QT_TOTAL_VOTOS_VALIDOS.
    """
    den = apuracao.groupby(chaves, as_index=False)["QT_TOTAL_VOTOS_VALIDOS"].sum()
    out = votos.merge(den, on=chaves, how="left", validate="many_to_one")
    out["pct_validos"] = percentual(out[col_votos], out["QT_TOTAL_VOTOS_VALIDOS"])
    out["estado"] = estado_denominador(out["QT_TOTAL_VOTOS_VALIDOS"])
    return out


def margem_pp(votos_a, votos_b, validos) -> np.ndarray:
    """100 × (A − B) ÷ válidos do cargo no território (pontos percentuais)."""
    return percentual(np.asarray(votos_a, "float64") - np.asarray(votos_b, "float64"), validos)


def participacao_no_par(votos_a, votos_b) -> np.ndarray:
    """A ÷ (A + B). Exclui os demais candidatos; NÃO é % dos votos válidos."""
    a = np.asarray(votos_a, "float64")
    return percentual(a, a + np.asarray(votos_b, "float64"))


def lideranca(votos: pd.DataFrame, chaves: list[str], col_cand: str = "SQ_CANDIDATO",
              col_votos: str = "votos") -> pd.DataFrame:
    """Mais votado por território, com tratamento de empate e de ausência de votos.

    Retorna por território: lider (ou NaN), votos_lider, segundo, votos_segundo,
    vantagem_votos, n_empatados e estado (com_valor | empate | sem_votos).
    "Mais votado no território" não significa "eleito".
    """
    ordenado = votos.sort_values(chaves + [col_votos, col_cand], ascending=[True] * len(chaves) + [False, True])
    ordenado = ordenado.assign(_pos=ordenado.groupby(chaves).cumcount())
    topo = ordenado[ordenado["_pos"] == 0].set_index(chaves)
    seg = ordenado[ordenado["_pos"] == 1].set_index(chaves)
    max_votos = votos.groupby(chaves)[col_votos].max()
    n_emp = (votos.merge(max_votos.rename("_max"), left_on=chaves, right_index=True)
             .query(f"{col_votos} == _max").groupby(chaves).size())

    r = pd.DataFrame(index=topo.index)
    r["votos_lider"] = topo[col_votos]
    r["segundo"] = seg[col_cand].reindex(r.index)
    r["votos_segundo"] = seg[col_votos].reindex(r.index).fillna(0)
    r["vantagem_votos"] = r["votos_lider"] - r["votos_segundo"]
    r["n_empatados"] = n_emp.reindex(r.index).fillna(0).astype(int)
    r["estado"] = np.where(r["votos_lider"] <= 0, SEM_VOTOS, np.where(r["n_empatados"] > 1, EMPATE, COM_VALOR))
    r["lider"] = topo[col_cand].where(r["estado"] == COM_VALOR)
    return r.reset_index()
