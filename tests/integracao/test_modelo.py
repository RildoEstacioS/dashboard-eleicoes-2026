"""Validação integrada do modelo tipado com dados oficiais.

Pré-requisito: python -m scripts.preparar_dados modelar
"""
import duckdb
import pandas as pd
import pytest

from src.config import DIR_AGREGADOS, DIR_MODELO
from src.metricas import indicadores as m
from src.modelagem import disponibilidade as d
from src.modelagem import vocabulario as v
from src.validacao import qualidade

pytestmark = pytest.mark.integracao


def _m(t):
    return (DIR_MODELO / f"{t}.parquet").as_posix()


def _a(t):
    return (DIR_AGREGADOS / f"{t}.parquet").as_posix()


@pytest.fixture(scope="module")
def con():
    if not (DIR_MODELO / "disponibilidade.parquet").exists():
        pytest.skip("Modelo não construído")
    return duckdb.connect()


@pytest.fixture(scope="module")
def disp():
    return pd.read_parquet(DIR_MODELO / "disponibilidade.parquet")


def test_granularidade_sem_duplicatas_nem_nulos(con):
    assert [g for g in qualidade.verificar_granularidade(con) if g[2] or g[3]] == []


def test_identificadores_preservados_como_texto(con):
    tipos = dict(con.sql(f"SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM '{_m('fato_nominal')}')").fetchall())
    assert tipos["SQ_CANDIDATO"] == "VARCHAR" and tipos["CD_MUNICIPIO"] == "VARCHAR"
    fora = con.sql(f"SELECT count(*) FROM '{_m('fato_apuracao')}' WHERE NOT regexp_full_match(CD_MUNICIPIO, '\\d{{5}}')").fetchall()[0][0]
    assert fora == 0


def test_eleitores_nao_duplicados_por_candidato(con):
    """Eleitorado vem da apuração (1 linha por zona e cargo), nunca da tabela de candidatos."""
    nac = con.sql(f"SELECT sum(QT_APTOS) FROM '{_a('apuracao_uf')}' WHERE CD_CARGO = 1 AND NR_TURNO = 1").fetchall()[0][0]
    zonas = con.sql(f"SELECT sum(QT_APTOS) FROM '{_m('fato_apuracao')}' WHERE CD_CARGO = 1 AND NR_TURNO = 1").fetchall()[0][0]
    assert nac == zonas


def test_segundo_turno_governador_vem_dos_dados(disp, con):
    ufs_2t = set(d.ues_disponiveis(disp, "Governador", 2))
    com_2t_no_1t = {u for (u,) in con.sql(
        f"SELECT DISTINCT SG_UE FROM '{_m('dim_candidato')}' WHERE DS_CARGO = 'Governador' AND DS_SIT_TOT_TURNO_1 = '2º TURNO'").fetchall()}
    assert ufs_2t == com_2t_no_1t and len(ufs_2t) > 0
    for uf in set(disp.loc[disp.DS_CARGO == "Governador", "SG_UE"]) - ufs_2t:
        assert d.estado(disp, "Governador", uf, 2) == v.NAO_HOUVE_SEGUNDO_TURNO


def test_estados_de_turno_e_circunscricao(disp):
    for cargo in ("Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"):
        assert set(disp.loc[(disp.DS_CARGO == cargo) & (disp.NR_TURNO == 2), "ESTADO"]) == {v.TURNO_NAO_APLICAVEL}
    assert d.estado(disp, "Presidente", "BR", 2) == v.DISPONIVEL
    assert d.estado(disp, "Deputado Estadual", "DF", 1) == v.CIRCUNSCRICAO_INEXISTENTE
    assert d.estado(disp, "Deputado Distrital", "DF", 1) == v.DISPONIVEL


def test_senado_dois_votos_por_eleitor(con):
    r = dict(con.sql(f"SELECT DS_CARGO, VOTOS_POR_ELEITOR FROM '{_m('dim_cargo')}'").fetchall())
    assert r["Senador"] == 2 and r["Presidente"] == 1


def test_filtro_nao_altera_denominador_com_dados_reais(con):
    votos = con.sql(f"""SELECT SG_UF, SQ_CANDIDATO, VOTOS_VALIDOS votos FROM '{_a('nominal_uf')}'
                        WHERE CD_CARGO = 1 AND NR_TURNO = 1""").df()
    ap = con.sql(f"SELECT SG_UF, QT_TOTAL_VOTOS_VALIDOS FROM '{_a('apuracao_uf')}' WHERE CD_CARGO = 1 AND NR_TURNO = 1").df()
    alvo = votos["SQ_CANDIDATO"].iloc[0]
    todos = m.percentual_sobre_validos(votos, ap, ["SG_UF"]).query("SQ_CANDIDATO == @alvo").set_index("SG_UF")
    filtrado = m.percentual_sobre_validos(votos[votos.SQ_CANDIDATO == alvo], ap, ["SG_UF"]).set_index("SG_UF")
    pd.testing.assert_series_equal(todos["pct_validos"], filtrado["pct_validos"])
    # Σ % de todos os candidatos numa UF = 100 (todos os válidos nominais; presidente não tem legenda)
    soma = m.percentual_sobre_validos(votos, ap, ["SG_UF"]).groupby("SG_UF")["pct_validos"].sum()
    assert ((soma.dropna() - 100).abs() < 1e-9).all()


def test_regiao_soma_de_ufs_igual_brasil_sem_exterior(con):
    r = con.sql(f"""
        SELECT (SELECT sum(QT_TOTAL_VOTOS_VALIDOS) FROM '{_a('apuracao_uf')}' a JOIN '{_m('dim_uf')}' u USING (SG_UF)
                WHERE CD_CARGO = 1 AND NR_TURNO = 2),
               (SELECT sum(QT_TOTAL_VOTOS_VALIDOS) FROM '{_a('apuracao_uf')}' WHERE CD_CARGO = 1 AND NR_TURNO = 2 AND SG_UF <> 'ZZ')
    """).fetchall()[0]
    assert r[0] == r[1]


def test_quatro_niveis_somam_o_mesmo_total():
    """Região, UF e municípios do Brasil somam os mesmos válidos (Brasil sem exterior)."""
    from src.consultas import eleicao as q
    c = q.conectar()
    for turno in (1, 2):
        totais = {nivel: int(q.apuracao_territorios(c, 1, turno, nivel).QT_TOTAL_VOTOS_VALIDOS.sum())
                  for nivel in ("regiao", "uf", "municipio")}
        votos = {nivel: int(q.votos_territorios(c, 1, turno, nivel).VOTOS.sum()) for nivel in ("regiao", "uf", "municipio")}
        sem_ext = int(q.totais(c, 1, turno, incluir_exterior=False)["validos"])
        assert set(totais.values()) == {sem_ext}
        assert len(set(votos.values())) == 1  # presidente: válidos = nominais (sem legenda)
    assert len(q.apuracao_territorios(c, 1, 1, "regiao")) == 5
    n_mun = len(q.apuracao_territorios(c, 1, 1, "municipio"))
    dim = pd.read_parquet(DIR_MODELO / "dim_municipio.parquet")
    assert n_mun == int((dim.ESTADO_JUNCAO == "associado").sum())


def test_filtro_de_regiao_restringe_e_preserva_total():
    from src.consultas import eleicao as q
    c = q.conectar()
    sul = q.apuracao_territorios(c, 1, 1, "uf", regiao="Sul")
    assert set(sul.TERRITORIO) == {u for (u,) in c.sql(f"SELECT SG_UF FROM '{_m('dim_uf')}' WHERE NM_REGIAO = 'Sul'").fetchall()}
    assert int(sul.QT_TOTAL_VOTOS_VALIDOS.sum()) == int(q.totais(c, 1, 1, regiao="Sul")["validos"])
    mun_sul = q.apuracao_territorios(c, 1, 1, "municipio", regiao="Sul")
    assert set(mun_sul.SG_UF) == set(sul.TERRITORIO)


def test_resumo_partidario_bate_vagas_e_validos(con):
    """Eleitos por partido (oficiais) somam as vagas; votos do partido somam os válidos — todas as UFs."""
    from src.consultas import eleicao as q, estaduais as e
    c = q.conectar()
    circ = pd.read_parquet(DIR_MODELO / "dim_circunscricao.parquet")
    prop = circ[circ.DS_CARGO.str.startswith("Deputado")]
    for r in prop.itertuples():
        rp = e.resumo_partidos(c, int(r.CD_CARGO), r.SG_UE)
        assert int(rp.ELEITOS.sum()) == int(r.QT_VAGA), (r.DS_CARGO, r.SG_UE)
        assert int(rp.TOTAL.sum()) == int(rp.VALIDOS.iloc[0]), (r.DS_CARGO, r.SG_UE)


def test_exterior_localidades_somam_o_exterior():
    from src.consultas import eleicao as q
    c = q.conectar()
    loc = q.exterior_localidades(c, 1, 2)
    ext = q.exterior(c, 1, 2)
    assert loc.CD_MUNICIPIO.nunique() == int(ext.LOCALIDADES.iloc[0])
    assert int(loc.VOTOS.sum()) == int(ext.VOTOS.sum())


def test_exterior_todas_as_cidades_tem_pais_e_totais_fecham():
    from src.consultas import eleicao as q
    from src.consultas.exterior import por_pais, tabela_paises
    c = q.conectar()
    dim = pd.read_parquet(DIR_MODELO / "dim_municipio.parquet")
    zz = set(dim.loc[dim.SG_UF == "ZZ", "CD_MUNICIPIO"])
    t = tabela_paises()
    assert zz == set(t.CD_MUNICIPIO), sorted(zz ^ set(t.CD_MUNICIPIO))
    assert t.ISO3.str.fullmatch(r"[A-Z]{3}").all()
    for turno in (1, 2):
        ap, vt, sem = por_pais(q.exterior_localidades(c, 1, turno))
        ext = q.exterior(c, 1, turno)
        assert sem == []
        assert int(vt.VOTOS.sum()) == int(ext.VOTOS.sum())
        assert int(ap.QT_TOTAL_VOTOS_VALIDOS.sum()) == int(ext.VALIDOS.iloc[0])


def test_validacao_contra_relatorio_oficial():
    from src.validacao.referencia_totalizacao import comparar, avaliar
    for sg in ("ES", "BR"):
        av = avaliar(*comparar(sg))
        assert av["candidatos_comparados"] > 0
        assert av["so_no_pdf"] == av["so_no_processado"] == av["votos_divergentes"] == 0
        assert av["situacao_divergente"] == 0 and av["pct_divergente_>0,01pp"] == 0 and av["resumo_ok"]
