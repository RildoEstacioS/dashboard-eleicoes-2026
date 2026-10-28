"""Cores, formatos e modos de coloração.

DADOS SINTÉTICOS: territórios T1..T4, candidatos c1..c3 e partidos P1..P3 são fictícios.
"""
import numpy as np
import pandas as pd

from src.visualizacoes import cores, modos
from src.visualizacoes import formatos as f

CANDS = pd.DataFrame({"SQ_CANDIDATO": ["c1", "c2", "c3"], "NM_URNA_CANDIDATO": ["ALFA", "BETA", "GAMA"],
                      "SG_PARTIDO": ["P1", "P2", "P3"]})
AP = pd.DataFrame({"TERRITORIO": ["T1", "T2", "T3", "T4"], "NOME": ["Um", "Dois", "Três", "Quatro"],
                   "SG_UF": ["XA"] * 4, "QT_APTOS": [100, 100, 100, 50], "QT_COMPARECIMENTO": [80, 80, 80, 0],
                   "QT_ABSTENCOES": [20, 20, 20, 50], "QT_TOTAL_VOTOS_VALIDOS": [70, 60, 70, 0]})
VT = pd.DataFrame({"TERRITORIO": ["T1", "T1", "T2", "T2", "T3", "T3", "T3", "T4", "T4"],
                   "SQ_CANDIDATO": ["c1", "c2", "c1", "c2", "c1", "c2", "c3", "c1", "c2"],
                   "VOTOS": [50, 20, 30, 30, 10, 20, 40, 0, 0]})


def test_cor_segue_entidade_e_ordem_estavel():
    m1 = cores.atribuir_lideranca(["c1", "c2", "c3", "c4"], "padrao", "claro")
    m2 = cores.atribuir_lideranca(["c1", "c2", "c3", "c4"], "padrao", "claro")
    assert m1 == m2 and m1["c4"] == cores.OUTROS["claro"] and len({m1["c1"], m1["c2"], m1["c3"]}) == 3


def test_cor_fixa_de_partido_tem_prioridade_e_exclui_parecidas():
    fixas = {"P2": "#e34948"}  # vermelho escolhido pelo usuário
    m = cores.atribuir_lideranca(["c1", "c2", "c3"], "padrao", "claro", {"c1": "P1", "c2": "P2", "c3": "P3"}, fixas)
    assert m["c2"] == "#e34948"
    assert m["c1"] != "#eb6834" and m["c3"] != "#eb6834"  # laranja ≈ vermelho: excluído
    usadas = [m["c1"], m["c2"], m["c3"]]
    assert all(cores.distintas(a, b) for i, a in enumerate(usadas) for b in usadas[i + 1:])


def test_cores_de_campanha_por_candidato_e_conflito():
    # c1 e c2 com tons quase iguais (fictícios): o segundo é rejeitado com aviso.
    m, avisos = cores.atribuir_com_fixas(["c1", "c2", "c3"], "padrao", "claro",
                                         {"c1": "#e34948", "c2": "#e0503f"})
    assert m["c1"] == "#e34948" and m["c2"] != "#e0503f" and avisos == [("c2", "c1")]
    vals = list(m.values())
    assert all(cores.distintas(a, b) for i, a in enumerate(vals) for b in vals[i + 1:] if cores.OUTROS["claro"] not in (a, b))
    sem, _ = cores.atribuir_com_fixas(["c1", "c2"], "padrao", "claro", {})
    assert sem == cores.atribuir_lideranca(["c1", "c2"], "padrao", "claro")


def test_deputados_eleitos_por_partido_com_tons_e_nao_eleitos_neutros():
    cp = cores.cores_partidos_proporcional(["P1", "P2", "P3"], "claro", {"P2": "#e34948"})
    assert cp["P2"] == "#e34948" and cp["P1"] != cp["P3"]
    assert cp["P1"] != "#eb6834"                       # laranja ≈ vermelho fixo: não é usado
    ce = cores.cores_eleitos([("a", "P1"), ("b", "P1"), ("c", "P2"), ("d", "P1")], cp, "claro")
    assert ce["a"] == cp["P1"] and ce["c"] == cp["P2"]
    assert len({ce["a"], ce["b"], ce["d"]}) == 3      # mesmo partido → tons diferentes
    assert cores.NAO_ELEITO["claro"] not in ce.values()


def test_distintas_reprova_par_confundivel_e_aprova_par_validado():
    assert not cores.distintas("#eb6834", "#e34948")       # laranja × vermelho
    assert cores.distintas("#2a78d6", "#e34948")           # azul × vermelho (validado)


def test_escala_divergente_tem_centro_neutro_e_extremos():
    e = cores.escala_divergente("#000000", "#ffffff", "#808080", passos=2)
    assert e[0] == [0.0, "#000000"] and e[-1] == [1.0, "#ffffff"]
    assert [0.5, "#808080"] in e


def test_escala_do_candidato_usa_a_cor_do_ranking():
    e = cores.escala_do_candidato("#e34948")
    assert e[1] == [0.5, "#e34948"]                       # cor do ranking no meio da escala
    assert e[0][1] != "#ffffff"                           # mínimo tingido ≠ "sem dado" (branco)


def test_formatos_ptbr():
    assert f.inteiro(1234567) == "1.234.567"
    assert f.pct(12.345) == "12,3%"
    assert f.pp(-3.21) == "−3,2 p.p." and f.pp(0) == "±0,0 p.p."
    assert f.compacto(158_745_502) == "158,7 mi" and f.inteiro(np.nan) == "—"


def test_lideranca_trata_empate_e_sem_votos():
    cm = cores.atribuir_lideranca(["c1", "c2", "c3"], "padrao", "claro")
    d, leg = modos.lideranca(AP, VT, CANDS, cm, "claro", nivel_uf=False)
    d = d.set_index("TERRITORIO")
    assert d.loc["T1", "COR"] == cm["c1"] and d.loc["T3", "COR"] == cm["c3"]
    assert d.loc["T2", "COR"] == cores.EMPATE["claro"] and "Empate" in d.loc["T2", "HOVER"]
    assert "T4" not in d.index                                    # sem válidos: vai para "sem dado"
    assert "T4" in modos.ausentes_sem_votos(AP, False)
    assert leg["empates"] == 1
    assert "Mais votado no território" in d.loc["T1", "HOVER"] and "denominador" in d.loc["T1", "HOVER"]


def test_modo_candidato_zero_votos_e_denominador():
    d = modos.candidato(AP, VT, CANDS, "c3", "pct", nivel_uf=False).set_index("TERRITORIO")
    assert d.loc["T1", "Z"] == 0.0                 # tem válidos, candidato sem votos → 0 %
    assert np.isnan(d.loc["T4", "Z"])              # sem válidos → sem valor
    assert d.loc["T3", "Z"] == 100 * 40 / 70


def test_comparacao_margem_par_e_sem_votos():
    d = modos.comparacao(AP, VT, CANDS, "c1", "c2", "margem", nivel_uf=False).set_index("TERRITORIO")
    assert d.loc["T1", "Z"] == 100 * 30 / 70 and d.loc["T1", "LIDERA"] == "A"
    assert d.loc["T2", "Z"] == 0 and d.loc["T2", "LIDERA"] == "empate"
    assert d.loc["T3", "LIDERA"] == "B"
    assert np.isnan(d.loc["T4", "Z"]) and d.loc["T4", "LIDERA"] == "sem_votos"
    p = modos.comparacao(AP, VT, CANDS, "c1", "c2", "par", nivel_uf=False).set_index("TERRITORIO")
    assert p.loc["T1", "Z"] == 100 * 50 / 70


def test_indicador_soma_antes_e_trata_denominador_zero():
    d = modos.indicador(AP, "abstencao", nivel_uf=False).set_index("TERRITORIO")
    assert d.loc["T1", "Z"] == 20.0 and d.loc["T4", "Z"] == 100.0       # 50 abstenções ÷ 50 aptos
    ap0 = AP.assign(QT_VOTOS=[0, 10, 10, 0], QT_VOTOS_BRANCOS=[0, 1, 2, 0])
    b = modos.indicador(ap0, "brancos", nivel_uf=False).set_index("TERRITORIO")
    assert np.isnan(b.loc["T1", "Z"]) and "não calculável" in b.loc["T1", "HOVER"]
    assert b.loc["T3", "Z"] == 20.0 and "÷" in b.loc["T3", "HOVER"]


def test_tooltip_compacto_e_menor_e_mantem_denominador():
    cm = cores.atribuir_lideranca(["c1", "c2", "c3"], "padrao", "claro")
    cheio, _ = modos.lideranca(AP, VT, CANDS, cm, "claro", False)
    curto, _ = modos.lideranca(AP, VT, CANDS, cm, "claro", False, compacto=True)
    assert curto["HOVER"].str.len().sum() < cheio["HOVER"].str.len().sum()
    assert curto["HOVER"].str.contains("denominador").all()


def test_limite_simetrico():
    assert modos.limite_simetrico(pd.Series([-12.0, 3.0])) == 15
    assert modos.limite_simetrico(pd.Series([52.0, 61.0]), centro=50) == 15
    assert modos.limite_simetrico(pd.Series([np.nan])) == 5
