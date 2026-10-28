"""Validação integrada com os dados oficiais baixados (não usa dados sintéticos).

Executar:
    python -m pytest -m integracao
Pré-requisito: python -m scripts.preparar_dados baixar / auditar / geografia
"""
import duckdb
import pandas as pd
import pytest

from src.config import DIR_PROCESSED
from src.geografia import correspondencia as corr
from src.validacao.consistencia import executar

pytestmark = pytest.mark.integracao
BRUTO = DIR_PROCESSED / "bruto"


@pytest.fixture(scope="module")
def con():
    if not (BRUTO / "votacao_candidato_munzona.parquet").exists():
        pytest.skip("Dados oficiais não preparados")
    c = duckdb.connect()
    for n in ("votacao_candidato_munzona", "consulta_vagas", "detalhe_munzona"):
        c.sql(f"CREATE VIEW {n} AS SELECT * FROM '{(BRUTO / f'{n}.parquet').as_posix()}'")
    return c


def test_identidades_contabeis_sem_violacao(con):
    falhas = [r for r in executar() if r[3] != 0]
    assert falhas == []


def test_juncao_sem_municipio_perdido():
    dim = pd.read_parquet(DIR_PROCESSED / "dim_municipio.parquet")
    estados = set(dim["ESTADO_JUNCAO"])
    assert corr.SEM_CORRESPONDENCIA not in estados
    assert corr.UF_DIVERGENTE not in estados
    assert corr.SEM_GEOMETRIA not in estados
    assert (dim.loc[dim["SG_UF"] == "ZZ", "ESTADO_JUNCAO"] == corr.EXTERIOR).all()


def test_eleitos_senado_igual_vagas_oficiais_por_uf(con):
    r = con.sql("""
        WITH e AS (SELECT SG_UF, count(DISTINCT SQ_CANDIDATO) eleitos FROM votacao_candidato_munzona
                   WHERE DS_CARGO = 'Senador' AND DS_SIT_TOT_TURNO = 'ELEITO' GROUP BY 1),
             v AS (SELECT SG_UF, sum(CAST(QT_VAGA AS INT)) vagas FROM consulta_vagas WHERE DS_CARGO = 'Senador' GROUP BY 1)
        SELECT v.SG_UF, v.vagas, coalesce(e.eleitos, 0) eleitos FROM v LEFT JOIN e USING (SG_UF)
    """).df()
    assert len(r) > 0
    assert (r["vagas"] == r["eleitos"]).all(), r[r["vagas"] != r["eleitos"]]


def test_eleitos_proporcionais_igual_vagas(con):
    """Eleitos por QP + por média = vagas oficiais, por cargo e UF (sem ranking de votos)."""
    r = con.sql("""
        WITH e AS (SELECT DS_CARGO, SG_UF, count(DISTINCT SQ_CANDIDATO) eleitos FROM votacao_candidato_munzona
                   WHERE DS_SIT_TOT_TURNO IN ('ELEITO POR QP', 'ELEITO POR MÉDIA') GROUP BY ALL),
             v AS (SELECT DS_CARGO, SG_UF, sum(CAST(QT_VAGA AS INT)) vagas FROM consulta_vagas
                   WHERE DS_CARGO LIKE 'Deputado%' GROUP BY ALL)
        SELECT v.*, coalesce(e.eleitos, 0) eleitos FROM v LEFT JOIN e USING (DS_CARGO, SG_UF)
    """).df()
    assert len(r) > 0
    assert (r["vagas"] == r["eleitos"]).all(), r[r["vagas"] != r["eleitos"]]


def test_segundo_turno_governador_coerente(con):
    """UFs com 2º turno descobertas nos dados: 2 candidatos com '2º TURNO' no 1º turno e 1 eleito no 2º."""
    t1 = con.sql("""SELECT SG_UF, count(DISTINCT SQ_CANDIDATO) n FROM votacao_candidato_munzona
                    WHERE DS_CARGO = 'Governador' AND NR_TURNO = '1' AND DS_SIT_TOT_TURNO = '2º TURNO' GROUP BY 1""").df()
    t2 = con.sql("""SELECT SG_UF, count(DISTINCT SQ_CANDIDATO) FILTER (WHERE DS_SIT_TOT_TURNO = 'ELEITO') eleitos,
                           count(DISTINCT SQ_CANDIDATO) n FROM votacao_candidato_munzona
                    WHERE DS_CARGO = 'Governador' AND NR_TURNO = '2' GROUP BY 1""").df()
    assert set(t1["SG_UF"]) == set(t2["SG_UF"])
    assert (t1["n"] == 2).all() and (t2["n"] == 2).all() and (t2["eleitos"] == 1).all()
    # UFs sem 2º turno têm exatamente um eleito no 1º turno.
    t1_eleito = con.sql("""SELECT SG_UF, count(DISTINCT SQ_CANDIDATO) n FROM votacao_candidato_munzona
                           WHERE DS_CARGO = 'Governador' AND NR_TURNO = '1' AND DS_SIT_TOT_TURNO = 'ELEITO' GROUP BY 1""").df()
    assert (t1_eleito["n"] == 1).all()
    assert set(t1_eleito["SG_UF"]).isdisjoint(set(t2["SG_UF"]))


def test_presidente_um_eleito_no_turno_final(con):
    r = con.sql("""SELECT NR_TURNO, count(DISTINCT SQ_CANDIDATO) FILTER (WHERE DS_SIT_TOT_TURNO = 'ELEITO') eleitos
                   FROM votacao_candidato_munzona WHERE DS_CARGO = 'Presidente' GROUP BY 1 ORDER BY 1""").fetchall()
    turnos = dict(r)
    assert sum(turnos.values()) == 1


def test_exterior_so_presidente(con):
    cargos = {c for (c,) in con.sql("SELECT DISTINCT DS_CARGO FROM detalhe_munzona WHERE SG_UF = 'ZZ'").fetchall()}
    assert cargos == {"Presidente"}
