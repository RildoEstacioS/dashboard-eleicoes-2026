"""Constrói o modelo dimensional tipado a partir da camada Parquet bruta.

Granularidade de cada tabela (ver docs/modelo_dados.md):

Fatos (zona eleitoral — menor unidade usada no MVP):
- fato_apuracao      : turno × cargo × UF × município × zona
- fato_nominal       : turno × cargo × UF × município × zona × candidato
- fato_partido       : turno × cargo × UF × município × zona × partido × SQ_COLIGACAO
                       (em federações, um partido pode ter duas linhas por zona com
                       SQ_COLIGACAO distintos; os valores são aditivos)

Dimensões:
- dim_eleicao        : CD_ELEICAO (único por turno)
- dim_cargo          : CD_CARGO
- dim_circunscricao  : cargo × SG_UE (BR ou UF), com vagas oficiais
- dim_candidato      : SQ_CANDIDATO (com situação oficial em cada turno)
- dim_partido        : NR_PARTIDO
- dim_federacao      : NR_FEDERACAO
- dim_uf             : SG_UF
- dim_municipio      : já gerada em geografia (CD_MUNICIPIO TSE)

Dados pessoais do cadastro (CPF, e-mail, título, data de nascimento) não são
copiados para o modelo: não são necessários ao dashboard.
"""
from __future__ import annotations

import time

import duckdb

from src.config import DIR_BRUTO, DIR_MODELO, DIR_PROCESSED
from src.modelagem.vocabulario import DESTINACAO_VALIDA, SITUACAO_TOTALIZACAO
from src.tratamento.chaves import sql_chaves_munzona

CHAVES = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA"]


class ErroModelo(ValueError):
    pass


def _p(path) -> str:
    return "'" + str(path).replace("\\", "/") + "'"


def _texto(c: str) -> str:
    """Texto do TSE com os marcadores #NULO/#NE convertidos em NULL."""
    return f"NULLIF(NULLIF(trim({c}), '#NULO'), '#NE') AS {c}"


def _criar_views_brutas(con: duckdb.DuckDBPyConnection) -> None:
    for nome in ("detalhe_munzona", "votacao_candidato_munzona", "votacao_partido_munzona",
                 "consulta_cand", "consulta_vagas", "municipio_tse_ibge"):
        arq = DIR_BRUTO / f"{nome}.parquet"
        if not arq.exists():
            raise FileNotFoundError(f"{arq} ausente. Rode: python -m scripts.preparar_dados auditar")
        con.sql(f"CREATE OR REPLACE VIEW b_{nome} AS SELECT * FROM {_p(arq)}")


def _colunas_qt(con, view: str) -> list[str]:
    return [c for c in con.sql(f"SELECT * FROM {view} LIMIT 0").columns if c.startswith("QT_")]


def _copiar(con, sql: str, nome: str) -> int:
    destino = DIR_MODELO / f"{nome}.parquet"
    con.sql(f"COPY ({sql}) TO {_p(destino)} (FORMAT parquet, COMPRESSION zstd)")
    con.sql(f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM {_p(destino)}")
    return con.sql(f"SELECT count(*) FROM {nome}").fetchall()[0][0]


def _valores_desconhecidos(con, view: str, coluna: str, conhecidos: dict) -> list[str]:
    valores = {v for (v,) in con.sql(f"SELECT DISTINCT {coluna} FROM {view}").fetchall()}
    return sorted(str(v) for v in valores - set(conhecidos))


def construir() -> dict[str, int]:
    DIR_MODELO.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    _criar_views_brutas(con)
    k = sql_chaves_munzona()
    linhas: dict[str, int] = {}
    t0 = time.perf_counter()

    # Vocabulário: falha se o TSE publicar valores não mapeados.
    for view, col, voc in (("b_votacao_candidato_munzona", "DS_SIT_TOT_TURNO", SITUACAO_TOTALIZACAO),
                           ("b_consulta_cand", "DS_SIT_TOT_TURNO", SITUACAO_TOTALIZACAO),
                           ("b_votacao_candidato_munzona", "NM_TIPO_DESTINACAO_VOTOS", DESTINACAO_VALIDA)):
        novos = _valores_desconhecidos(con, view, col, voc)
        if novos:
            raise ErroModelo(f"{view}.{col} tem valores não mapeados em vocabulario.py: {novos}")

    # ---------- fatos ----------
    qt_det = _colunas_qt(con, "b_detalhe_munzona")
    linhas["fato_apuracao"] = _copiar(con, f"""
        SELECT {k}, CAST(CD_ELEICAO AS INTEGER) CD_ELEICAO,
               {", ".join(f"CAST({c} AS BIGINT) {c}" for c in qt_det)},
               strptime(DT_ULTIMA_TOTALIZACAO || ' ' || HH_ULTIMA_TOTALIZACAO, '%d/%m/%Y %H:%M:%S') TS_ULTIMA_TOTALIZACAO
        FROM b_detalhe_munzona""", "fato_apuracao")

    mapa_valida = " ".join(f"WHEN '{d}' THEN {str(v).upper()}" for d, v in DESTINACAO_VALIDA.items())
    linhas["fato_nominal"] = _copiar(con, f"""
        SELECT {k}, SQ_CANDIDATO, NM_TIPO_DESTINACAO_VOTOS,
               CASE NM_TIPO_DESTINACAO_VOTOS {mapa_valida} END AS VOTO_VALIDO,
               CAST(QT_VOTOS_NOMINAIS AS BIGINT) QT_VOTOS_NOMINAIS,
               CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT) QT_VOTOS_NOMINAIS_VALIDOS
        FROM b_votacao_candidato_munzona""", "fato_nominal")

    qt_par = _colunas_qt(con, "b_votacao_partido_munzona")
    linhas["fato_partido"] = _copiar(con, f"""
        SELECT {k}, CAST(NR_PARTIDO AS SMALLINT) NR_PARTIDO, SQ_COLIGACAO,
               CAST(NULLIF(NR_FEDERACAO, '-1') AS SMALLINT) NR_FEDERACAO,
               {", ".join(f"CAST({c} AS BIGINT) {c}" for c in qt_par)}
        FROM b_votacao_partido_munzona""", "fato_partido")

    # ---------- dimensões ----------
    linhas["dim_eleicao"] = _copiar(con, """
        SELECT DISTINCT CAST(CD_ELEICAO AS INTEGER) CD_ELEICAO, CAST(ANO_ELEICAO AS SMALLINT) ANO_ELEICAO,
               CAST(NR_TURNO AS TINYINT) NR_TURNO, DS_ELEICAO, strptime(DT_ELEICAO, '%d/%m/%Y')::DATE DT_ELEICAO,
               TP_ABRANGENCIA, CAST(CD_TIPO_ELEICAO AS TINYINT) CD_TIPO_ELEICAO, NM_TIPO_ELEICAO
        FROM b_detalhe_munzona""", "dim_eleicao")

    # Votos por eleitor DERIVADO dos dados (QT_VOTOS / QT_COMPARECIMENTO); exige razão inteira exata.
    linhas["dim_cargo"] = _copiar(con, """
        WITH r AS (
            SELECT CD_CARGO, any_value(DS_CARGO) DS_CARGO, any_value(TP_ABRANGENCIA) TP_ABRANGENCIA,
                   sum(QT_VOTOS) votos, sum(QT_COMPARECIMENTO) comp
            FROM fato_apuracao JOIN (SELECT DISTINCT CAST(CD_CARGO AS SMALLINT) CD_CARGO, DS_CARGO, TP_ABRANGENCIA
                                     FROM b_detalhe_munzona) USING (CD_CARGO)
            GROUP BY CD_CARGO),
        s AS (SELECT CAST(CD_CARGO AS SMALLINT) CD_CARGO,
                     bool_or(DS_SIT_TOT_TURNO IN ('ELEITO POR QP', 'ELEITO POR MÉDIA')) proporcional
              FROM b_votacao_candidato_munzona GROUP BY 1)
        SELECT r.CD_CARGO, DS_CARGO, TP_ABRANGENCIA,
               CAST(votos / comp AS TINYINT) VOTOS_POR_ELEITOR,
               votos % comp = 0 AS VOTOS_POR_ELEITOR_EXATO,
               CASE WHEN proporcional THEN 'proporcional' ELSE 'majoritario' END SISTEMA
        FROM r JOIN s USING (CD_CARGO) ORDER BY r.CD_CARGO""", "dim_cargo")
    inexatos = con.sql("SELECT DS_CARGO FROM dim_cargo WHERE NOT VOTOS_POR_ELEITOR_EXATO").fetchall()
    if inexatos:
        raise ErroModelo(f"Razão votos/comparecimento não inteira para: {inexatos}")

    linhas["dim_partido"] = _copiar(con, """
        SELECT CAST(NR_PARTIDO AS SMALLINT) NR_PARTIDO, any_value(SG_PARTIDO) SG_PARTIDO,
               any_value(NM_PARTIDO) NM_PARTIDO, count(DISTINCT SG_PARTIDO) n_siglas
        FROM (SELECT NR_PARTIDO, SG_PARTIDO, NM_PARTIDO FROM b_votacao_candidato_munzona
              UNION ALL SELECT NR_PARTIDO, SG_PARTIDO, NM_PARTIDO FROM b_votacao_partido_munzona)
        GROUP BY 1 ORDER BY 1""", "dim_partido")

    # SG_FEDERACAO tem grafias divergentes no TSE; o rótulo usa nome e composição.
    linhas["dim_federacao"] = _copiar(con, """
        SELECT CAST(NR_FEDERACAO AS SMALLINT) NR_FEDERACAO, any_value(NM_FEDERACAO) NM_FEDERACAO,
               any_value(DS_COMPOSICAO_FEDERACAO) DS_COMPOSICAO_FEDERACAO,
               string_agg(DISTINCT SG_FEDERACAO, ' | ') SG_FEDERACAO_VARIANTES
        FROM b_votacao_candidato_munzona WHERE NR_FEDERACAO <> '-1' GROUP BY 1 ORDER BY 1""", "dim_federacao")

    linhas["dim_circunscricao"] = _copiar(con, """
        WITH c AS (SELECT DISTINCT CAST(CD_CARGO AS SMALLINT) CD_CARGO, DS_CARGO, SG_UE, NM_UE
                   FROM b_votacao_candidato_munzona),
             v AS (SELECT CAST(CD_CARGO AS SMALLINT) CD_CARGO, SG_UE, sum(CAST(QT_VAGA AS SMALLINT)) QT_VAGA
                   FROM b_consulta_vagas GROUP BY ALL)
        SELECT c.*, v.QT_VAGA FROM c LEFT JOIN v USING (CD_CARGO, SG_UE) ORDER BY CD_CARGO, SG_UE""",
        "dim_circunscricao")

    # Candidato: atributos estáveis da votação; situação oficial por turno (pivot).
    sit = " ".join(f"WHEN '{s}' THEN '{c}'" for s, c in SITUACAO_TOTALIZACAO.items())
    linhas["dim_candidato"] = _copiar(con, f"""
        WITH v AS (
            SELECT SQ_CANDIDATO, CAST(NR_TURNO AS TINYINT) NR_TURNO, DS_SIT_TOT_TURNO,
                   any_value(CAST(CD_CARGO AS SMALLINT)) CD_CARGO, any_value(DS_CARGO) DS_CARGO,
                   any_value(SG_UE) SG_UE, any_value(NR_CANDIDATO) NR_CANDIDATO,
                   any_value(NM_URNA_CANDIDATO) NM_URNA_CANDIDATO,
                   any_value(NULLIF(NM_SOCIAL_CANDIDATO, '#NULO')) NM_SOCIAL_CANDIDATO,
                   any_value(CAST(NR_PARTIDO AS SMALLINT)) NR_PARTIDO, any_value(SG_PARTIDO) SG_PARTIDO,
                   any_value(CAST(NULLIF(NR_FEDERACAO, '-1') AS SMALLINT)) NR_FEDERACAO,
                   any_value(TP_AGREMIACAO) TP_AGREMIACAO, any_value(SQ_COLIGACAO) SQ_COLIGACAO,
                   any_value(NULLIF(NM_COLIGACAO, '#NULO')) NM_COLIGACAO,
                   any_value(DS_SITUACAO_JULGAMENTO) DS_SITUACAO_JULGAMENTO
            FROM b_votacao_candidato_munzona GROUP BY SQ_CANDIDATO, NR_TURNO, DS_SIT_TOT_TURNO)
        SELECT SQ_CANDIDATO, any_value(CD_CARGO) CD_CARGO, any_value(DS_CARGO) DS_CARGO, any_value(SG_UE) SG_UE,
               any_value(NR_CANDIDATO) NR_CANDIDATO, any_value(NM_URNA_CANDIDATO) NM_URNA_CANDIDATO,
               any_value(NM_SOCIAL_CANDIDATO) NM_SOCIAL_CANDIDATO,
               any_value(NR_PARTIDO) NR_PARTIDO, any_value(SG_PARTIDO) SG_PARTIDO, any_value(NR_FEDERACAO) NR_FEDERACAO,
               any_value(TP_AGREMIACAO) TP_AGREMIACAO, any_value(SQ_COLIGACAO) SQ_COLIGACAO,
               any_value(NM_COLIGACAO) NM_COLIGACAO, any_value(DS_SITUACAO_JULGAMENTO) DS_SITUACAO_JULGAMENTO,
               any_value(DS_SIT_TOT_TURNO) FILTER (WHERE NR_TURNO = 1) DS_SIT_TOT_TURNO_1,
               any_value(DS_SIT_TOT_TURNO) FILTER (WHERE NR_TURNO = 2) DS_SIT_TOT_TURNO_2,
               max(NR_TURNO) ULTIMO_TURNO_DISPUTADO,
               -- Situação final = a do último turno disputado pelo candidato.
               CASE arg_max(DS_SIT_TOT_TURNO, NR_TURNO) {sit} END SITUACAO_FINAL,
               CASE WHEN arg_max(DS_SIT_TOT_TURNO, NR_TURNO) IN ('ELEITO', 'ELEITO POR QP', 'ELEITO POR MÉDIA')
                    THEN max(NR_TURNO) END TURNO_ELEICAO
        FROM v GROUP BY SQ_CANDIDATO""", "dim_candidato")
    multi = con.sql("SELECT count(*) FROM (SELECT SQ_CANDIDATO FROM b_votacao_candidato_munzona "
                    "GROUP BY 1 HAVING count(DISTINCT NM_URNA_CANDIDATO) > 1 OR count(DISTINCT CD_CARGO) > 1 "
                    "OR count(DISTINCT SG_UE) > 1 OR count(DISTINCT NR_PARTIDO) > 1)").fetchall()[0][0]
    if multi:
        raise ErroModelo(f"{multi} candidatos com atributos que variam entre linhas")

    linhas["dim_uf"] = _copiar(con, """
        SELECT DISTINCT SG_UF, lpad(CD_UF_IBGE, 2, '0') CD_UF_IBGE, NM_UF,
               CASE left(lpad(CD_UF_IBGE, 2, '0'), 1) WHEN '1' THEN 'Norte' WHEN '2' THEN 'Nordeste'
                    WHEN '3' THEN 'Sudeste' WHEN '4' THEN 'Sul' WHEN '5' THEN 'Centro-Oeste' END NM_REGIAO
        FROM b_municipio_tse_ibge ORDER BY SG_UF""", "dim_uf")

    dim_mun = DIR_PROCESSED / "dim_municipio.parquet"
    if not dim_mun.exists():
        raise FileNotFoundError("dim_municipio.parquet ausente. Rode: python -m scripts.preparar_dados geografia")
    linhas["dim_municipio"] = _copiar(con, f"SELECT * FROM {_p(dim_mun)}", "dim_municipio")

    print(f"[modelo] construído em {time.perf_counter() - t0:.1f}s")
    for n, q in linhas.items():
        print(f"    {n:20s} {q:>12,}")
    return linhas
