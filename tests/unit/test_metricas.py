"""Testes das métricas.

DADOS SINTÉTICOS: territórios T1..T4 e candidatos A..C são fictícios.
"""
import numpy as np
import pandas as pd
import pytest

from src.metricas import indicadores as m


def test_percentual_denominador_zero_e_ausente():
    r = m.percentual([1, 0, 5, 3], [4, 0, np.nan, 0])
    assert r[0] == 25.0
    assert np.isnan(r[1]) and np.isnan(r[2]) and np.isnan(r[3])
    assert list(m.estado_denominador([4, 0, None])) == [m.COM_VALOR, m.SEM_VOTOS, m.SEM_DADO]


def test_agregacao_soma_antes_de_dividir():
    # Município pequeno 10 % (1/10) e grande 50 % (450/900): média simples daria 30 %.
    ap = pd.DataFrame({"uf": ["X", "X"], "QT_ABSTENCOES": [1, 450], "QT_APTOS": [10, 900]})
    g = m.agregar_indicador(ap, ["uf"], "abstencao")
    assert g.loc[0, "valor"] == pytest.approx(100 * 451 / 910)
    assert g.loc[0, "valor"] != pytest.approx(30.0)


def test_filtro_de_candidatos_nao_altera_denominador():
    ap = pd.DataFrame({"t": ["T1"], "QT_TOTAL_VOTOS_VALIDOS": [100]})
    votos = pd.DataFrame({"t": ["T1"] * 3, "cand": ["A", "B", "C"], "votos": [50, 30, 20]})
    todos = m.percentual_sobre_validos(votos, ap, ["t"])
    so_a = m.percentual_sobre_validos(votos[votos.cand == "A"], ap, ["t"])
    assert todos.set_index("cand").loc["A", "pct_validos"] == 50.0
    assert so_a["pct_validos"].iloc[0] == 50.0  # não vira 100 %


def test_percentual_territorio_sem_validos():
    ap = pd.DataFrame({"t": ["T1"], "QT_TOTAL_VOTOS_VALIDOS": [0]})
    votos = pd.DataFrame({"t": ["T1"], "cand": ["A"], "votos": [0]})
    r = m.percentual_sobre_validos(votos, ap, ["t"])
    assert np.isnan(r["pct_validos"].iloc[0]) and r["estado"].iloc[0] == m.SEM_VOTOS


def test_territorio_ausente_na_apuracao_e_sem_dado():
    ap = pd.DataFrame({"t": ["T1"], "QT_TOTAL_VOTOS_VALIDOS": [10]})
    votos = pd.DataFrame({"t": ["T9"], "cand": ["A"], "votos": [3]})
    r = m.percentual_sobre_validos(votos, ap, ["t"])
    assert r["estado"].iloc[0] == m.SEM_DADO


def test_margem_e_participacao_no_par():
    assert m.margem_pp([60], [30], [100])[0] == 30.0
    assert m.participacao_no_par([60], [30])[0] == pytest.approx(66.6667, rel=1e-4)
    assert np.isnan(m.margem_pp([0], [0], [0])[0])          # sem votos ≠ empate
    assert np.isnan(m.participacao_no_par([0], [0])[0])
    assert m.margem_pp([40], [40], [100])[0] == 0.0          # empate real com votos


def test_lideranca_empate_sem_votos_e_normal():
    votos = pd.DataFrame({
        "t":    ["T1", "T1", "T1", "T2", "T2", "T3", "T3", "T4"],
        "cand": ["A",  "B",  "C",  "A",  "B",  "A",  "B",  "A"],
        "votos": [10,   7,    3,    5,    5,    0,    0,    9],
    })
    r = m.lideranca(votos, ["t"], col_cand="cand").set_index("t")
    assert r.loc["T1", "lider"] == "A" and r.loc["T1", "vantagem_votos"] == 3 and r.loc["T1", "estado"] == m.COM_VALOR
    assert r.loc["T2", "estado"] == m.EMPATE and pd.isna(r.loc["T2", "lider"]) and r.loc["T2", "n_empatados"] == 2
    assert r.loc["T3", "estado"] == m.SEM_VOTOS and pd.isna(r.loc["T3", "lider"])
    assert r.loc["T4", "lider"] == "A" and r.loc["T4", "votos_segundo"] == 0


def test_indicadores_documentam_formula_e_denominador():
    for ind in m.INDICADORES.values():
        assert ind.numerador.startswith("QT_") and ind.denominador.startswith("QT_")
        assert ind.formula and ind.unidade == "%"
