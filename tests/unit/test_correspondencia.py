"""Testes da junção TSE–IBGE.

DADOS SINTÉTICOS: códigos e nomes abaixo são fictícios, criados só para testar
as regras; não representam municípios nem resultados reais.
"""
import pandas as pd
import pytest

from src.geografia import correspondencia as c


def _tabela(**extra):
    base = {
        "SG_UF": ["XA", "XA", "XB"],
        "CD_UF_TSE": ["90", "90", "91"],
        "CD_UF_IBGE": ["11", "11", "21"],
        "CD_MUNICIPIO_TSE": ["101", "00102", "00201"],
        "NM_MUNICIPIO_TSE": ["Alfa", "Beta", "Gama"],
        "CD_MUNICIPIO_IBGE": ["1100001", "1100002", "2100001"],
        "NM_MUNICIPIO_IBGE": ["Alfa", "Beta", "Gama"],
        "DT_GERACAO": ["01/01/2026"] * 3,
    }
    base.update(extra)
    return c.normalizar_tabela(pd.DataFrame(base))


def test_normalizacao_preserva_zeros_e_deriva_regiao():
    t = _tabela()
    assert t["CD_MUNICIPIO_TSE"].tolist() == ["00101", "00102", "00201"]
    assert t["NM_REGIAO"].tolist() == ["Norte", "Norte", "Nordeste"]
    assert c.validar_tabela(t) == []


def test_validacao_detecta_duplicidade_e_prefixo_inconsistente():
    t = _tabela(CD_MUNICIPIO_IBGE=["1100001", "1100001", "1100009"])
    problemas = " ".join(c.validar_tabela(t))
    assert "duplicado" in problemas
    assert "Prefixo de UF" in problemas


def test_classificacao_de_todos_os_estados():
    t = _tabela()
    votacao = pd.DataFrame({
        "SG_UF": ["XA", "XA", "XB", "XA", "ZZ"],
        "CD_MUNICIPIO": ["00101", "00102", "00201", "00999", "88888"],
        "NM_MUNICIPIO": ["ALFA", "BETA", "GAMA", "OMEGA", "CIDADE EXTERIOR"],
    })
    # 1100002 (Beta) sem polígono; 1100077 é polígono sem votação.
    geo = {"1100001", "2100001", "1100077"}
    r = c.classificar_juncao(votacao, t, geo)
    estados = dict(zip(r.territorios["CD_MUNICIPIO"].fillna(r.territorios["CD_MUNICIPIO_IBGE"]),
                       r.territorios["ESTADO_JUNCAO"]))
    assert estados["00101"] == c.ASSOCIADO
    assert estados["00102"] == c.SEM_GEOMETRIA
    assert estados["00999"] == c.SEM_CORRESPONDENCIA
    assert estados["88888"] == c.EXTERIOR
    assert estados["1100077"] == c.GEOMETRIA_SEM_VOTACAO


def test_uf_divergente_nao_associa_mesmo_com_codigo_existente():
    t = _tabela()
    votacao = pd.DataFrame({"SG_UF": ["XB"], "CD_MUNICIPIO": ["00101"], "NM_MUNICIPIO": ["ALFA"]})
    r = c.classificar_juncao(votacao, t, {"1100001"})
    assert r.territorios.loc[0, "ESTADO_JUNCAO"] == c.UF_DIVERGENTE


def test_juncao_nao_usa_nome():
    """Mesmo nome com código diferente não deve associar."""
    t = _tabela()
    votacao = pd.DataFrame({"SG_UF": ["XA"], "CD_MUNICIPIO": ["00555"], "NM_MUNICIPIO": ["ALFA"]})
    r = c.classificar_juncao(votacao, t, {"1100001"})
    assert r.territorios.loc[0, "ESTADO_JUNCAO"] == c.SEM_CORRESPONDENCIA


def test_nome_divergente_e_apenas_informativo():
    t = _tabela()
    votacao = pd.DataFrame({"SG_UF": ["XA"], "CD_MUNICIPIO": ["00101"], "NM_MUNICIPIO": ["ALFA DO SUL"]})
    r = c.classificar_juncao(votacao, t, {"1100001"})
    assert r.territorios.loc[0, "ESTADO_JUNCAO"] == c.ASSOCIADO
    assert bool(r.territorios.loc[0, "NOME_DIVERGE"]) is True
