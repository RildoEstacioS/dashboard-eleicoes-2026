"""Consultas analíticas sobre o modelo e os agregados (DuckDB sobre Parquet).

Funções puras: recebem uma conexão e parâmetros, devolvem DataFrames pequenos.
O cache fica na camada de interface. Só colunas e recortes necessários são lidos.

Identificadores de território usados pelos mapas:
- nível "uf": SG_UF (propriedade SIGLA_UF de ufs.geojson);
- nível "municipio": código IBGE de 7 dígitos (propriedade CD_MUN).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src.config import DIR_AGREGADOS, DIR_MODELO

SG_EXTERIOR = "ZZ"
NIVEL_REGIAO = "regiao"
NIVEL_UF = "uf"
NIVEL_MUNICIPIO = "municipio"


def _m(t: str) -> str:
    return "'" + (DIR_MODELO / f"{t}.parquet").as_posix() + "'"


def _a(t: str) -> str:
    return "'" + (DIR_AGREGADOS / f"{t}.parquet").as_posix() + "'"


def conectar() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    return con


def _filtro_ue(sg_ue: str, alias: str = "") -> str:
    """Circunscrição: 'BR' (todas as UFs + exterior) ou uma UF."""
    p = f"{alias}." if alias else ""
    return "" if sg_ue == "BR" else f"AND {p}SG_UF = '{sg_ue}'"


# ---------------- dimensões ----------------

def cargos(con) -> pd.DataFrame:
    return con.sql(f"SELECT * FROM {_m('dim_cargo')} ORDER BY CD_CARGO").df()


def disponibilidade(con) -> pd.DataFrame:
    return con.sql(f"SELECT * FROM {_m('disponibilidade')}").df()


def ufs(con) -> pd.DataFrame:
    return con.sql(f"SELECT * FROM {_m('dim_uf')} ORDER BY SG_UF").df()


def municipios(con, sg_uf: str) -> pd.DataFrame:
    return con.sql(f"""SELECT CD_MUNICIPIO, CD_MUNICIPIO_IBGE, NM_MUN_MALHA NOME
                       FROM {_m('dim_municipio')} WHERE SG_UF = ? AND ESTADO_JUNCAO = 'associado'
                       ORDER BY strip_accents(lower(NM_MUN_MALHA))""", params=[sg_uf]).df()


# ---------------- candidatos e totais da disputa ----------------

def candidatos(con, cd_cargo: int, sg_ue: str, turno: int) -> pd.DataFrame:
    """Candidatos da disputa no turno, com votos e % sobre os válidos da circunscrição.

    ORDEM_ESTAVEL: posição no 1º turno da mesma disputa (base para cores estáveis).
    """
    return con.sql(f"""
        WITH v AS (SELECT SQ_CANDIDATO, NR_TURNO, sum(VOTOS_VALIDOS) votos, sum(VOTOS_ANUL_SUBJUD) subjud
                   FROM {_a('nominal_uf')} WHERE CD_CARGO = {cd_cargo} {_filtro_ue(sg_ue)} GROUP BY ALL),
             den AS (SELECT NR_TURNO, sum(QT_TOTAL_VOTOS_VALIDOS) validos
                     FROM {_a('apuracao_uf')} WHERE CD_CARGO = {cd_cargo} {_filtro_ue(sg_ue)} GROUP BY 1),
             ordem AS (SELECT SQ_CANDIDATO, row_number() OVER (ORDER BY votos DESC, SQ_CANDIDATO) ORDEM_ESTAVEL
                       FROM v WHERE NR_TURNO = 1)
        SELECT c.SQ_CANDIDATO, c.NR_CANDIDATO, c.NM_URNA_CANDIDATO, c.SG_PARTIDO, c.NR_PARTIDO,
               c.NR_FEDERACAO, f.NM_FEDERACAO,
               CASE {turno} WHEN 1 THEN c.DS_SIT_TOT_TURNO_1 ELSE c.DS_SIT_TOT_TURNO_2 END SITUACAO_TURNO,
               c.SITUACAO_FINAL, c.TURNO_ELEICAO, v.votos VOTOS, coalesce(v.subjud, 0) VOTOS_ANUL_SUBJUD,
               den.validos VALIDOS_CIRCUNSCRICAO,
               100.0 * v.votos / nullif(den.validos, 0) PCT_VALIDOS, o.ORDEM_ESTAVEL
        FROM v JOIN {_m('dim_candidato')} c USING (SQ_CANDIDATO)
        LEFT JOIN {_m('dim_federacao')} f USING (NR_FEDERACAO)
        JOIN den USING (NR_TURNO) LEFT JOIN ordem o USING (SQ_CANDIDATO)
        WHERE v.NR_TURNO = {turno} AND c.SG_UE = '{sg_ue}'
        ORDER BY VOTOS DESC, c.SQ_CANDIDATO""").df()


def totais(con, cd_cargo: int, turno: int, sg_uf: str | None = None, incluir_exterior: bool = True,
           regiao: str | None = None) -> dict:
    """Somas de apuração no escopo: Brasil (com/sem exterior), uma região ou uma UF."""
    if sg_uf:
        filtro = f"AND SG_UF = '{sg_uf}'"
    elif regiao:
        filtro = (f"AND SG_UF IN (SELECT SG_UF FROM {_m('dim_uf')} WHERE NM_REGIAO = "
                  + "'" + regiao.replace("'", "''") + "')")
    else:
        filtro = "" if incluir_exterior else f"AND SG_UF <> '{SG_EXTERIOR}'"
    r = con.sql(f"""
        SELECT sum(QT_APTOS) aptos, sum(QT_COMPARECIMENTO) comparecimento, sum(QT_ABSTENCOES) abstencoes,
               sum(QT_ELEITORES_SECOES_NAO_INSTALADAS) secoes_nao_instaladas,
               sum(QT_VOTOS) votos, sum(QT_TOTAL_VOTOS_VALIDOS) validos, sum(QT_VOTOS_BRANCOS) brancos,
               sum(QT_TOTAL_VOTOS_NULOS) nulos, sum(QT_TOTAL_VOTOS_ANUL_SUBJUD) anul_subjud,
               sum(QT_TOTAL_VOTOS_ANULADOS) anulados, max(TS_ULTIMA_TOTALIZACAO) ultima_totalizacao,
               sum(N_ZONAS) zonas
        FROM {_a('apuracao_uf')} WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno} {filtro}""").df()
    return r.iloc[0].to_dict()


# ---------------- territórios ----------------

_COLS_AP = """sum(QT_APTOS) QT_APTOS, sum(QT_COMPARECIMENTO) QT_COMPARECIMENTO, sum(QT_ABSTENCOES) QT_ABSTENCOES,
              sum(QT_VOTOS) QT_VOTOS, sum(QT_TOTAL_VOTOS_VALIDOS) QT_TOTAL_VOTOS_VALIDOS,
              sum(QT_VOTOS_BRANCOS) QT_VOTOS_BRANCOS, sum(QT_TOTAL_VOTOS_NULOS) QT_TOTAL_VOTOS_NULOS,
              sum(QT_TOTAL_VOTOS_ANUL_SUBJUD) QT_TOTAL_VOTOS_ANUL_SUBJUD"""


def _filtros_territorio(prefixo: str, sg_uf: str | None, regiao: str | None) -> tuple[str, list]:
    sql, params = "", []
    if sg_uf:
        sql += f" AND {prefixo}SG_UF = ?"
        params.append(sg_uf)
    if regiao:
        sql += " AND u.NM_REGIAO = ?"
        params.append(regiao)
    return sql, params


def apuracao_territorios(con, cd_cargo: int, turno: int, nivel: str, sg_uf: str | None = None,
                         regiao: str | None = None) -> pd.DataFrame:
    """Uma linha por território do mapa com os totais da apuração do cargo.

    Níveis: 'regiao' (5 grandes regiões), 'uf', 'municipio' (de uma UF, se
    `sg_uf`; senão, todos os municípios do Brasil). `regiao` restringe UFs e
    municípios a uma grande região. Exterior (ZZ) nunca entra: não há geometria.
    Regiões são somas das UFs (numeradores e denominadores somados).
    """
    f, p = _filtros_territorio("a.", sg_uf, regiao)
    base = f"WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno}"
    if nivel == NIVEL_REGIAO:
        return con.sql(f"""
            SELECT u.NM_REGIAO TERRITORIO, u.NM_REGIAO NOME, '' SG_UF, u.NM_REGIAO, {_COLS_AP}
            FROM {_a('apuracao_uf')} a JOIN {_m('dim_uf')} u USING (SG_UF)
            {base} {f} GROUP BY ALL""", params=p).df()
    if nivel == NIVEL_UF:
        return con.sql(f"""
            SELECT a.SG_UF TERRITORIO, u.NM_UF NOME, a.SG_UF, u.NM_REGIAO, {_COLS_AP}
            FROM {_a('apuracao_uf')} a JOIN {_m('dim_uf')} u USING (SG_UF)
            {base} {f} GROUP BY ALL""", params=p).df()
    return con.sql(f"""
        SELECT d.CD_MUNICIPIO_IBGE TERRITORIO, any_value(d.NM_MUN_MALHA) NOME, a.SG_UF,
               any_value(u.NM_REGIAO) NM_REGIAO, any_value(a.CD_MUNICIPIO) CD_MUNICIPIO_TSE, {_COLS_AP}
        FROM {_a('apuracao_municipio')} a
        JOIN {_m('dim_municipio')} d ON d.SG_UF = a.SG_UF AND d.CD_MUNICIPIO = a.CD_MUNICIPIO
        JOIN {_m('dim_uf')} u ON u.SG_UF = a.SG_UF
        {base} AND d.ESTADO_JUNCAO = 'associado' {f}
        GROUP BY d.CD_MUNICIPIO_IBGE, a.SG_UF""", params=p).df()


def votos_territorios(con, cd_cargo: int, turno: int, nivel: str, sg_uf: str | None = None,
                      regiao: str | None = None, candidatos_sq: list[str] | None = None) -> pd.DataFrame:
    """Votos válidos por território × candidato (formato longo), nos mesmos níveis.

    `candidatos_sq` restringe as LINHAS retornadas; nunca muda denominadores
    (que vêm de `apuracao_territorios`).
    """
    f, p = _filtros_territorio("n.", sg_uf, regiao)
    if candidatos_sq is not None:
        f += f" AND n.SQ_CANDIDATO IN ({', '.join('?' for _ in candidatos_sq)})"
        p += list(candidatos_sq)
    base = f"WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno}"
    if nivel in (NIVEL_REGIAO, NIVEL_UF):
        terr = "u.NM_REGIAO" if nivel == NIVEL_REGIAO else "n.SG_UF"
        return con.sql(f"""
            SELECT {terr} TERRITORIO, n.SQ_CANDIDATO, sum(n.VOTOS_VALIDOS) VOTOS
            FROM {_a('nominal_uf')} n JOIN {_m('dim_uf')} u USING (SG_UF)
            {base} {f} GROUP BY ALL""", params=p).df()
    return con.sql(f"""
        SELECT d.CD_MUNICIPIO_IBGE TERRITORIO, n.SQ_CANDIDATO, sum(n.VOTOS_VALIDOS) VOTOS
        FROM {_a('nominal_municipio')} n
        JOIN {_m('dim_municipio')} d ON d.SG_UF = n.SG_UF AND d.CD_MUNICIPIO = n.CD_MUNICIPIO
        JOIN {_m('dim_uf')} u ON u.SG_UF = n.SG_UF
        {base} AND d.ESTADO_JUNCAO = 'associado' {f}
        GROUP BY ALL""", params=p).df()


def exterior_localidades(con, cd_cargo: int, turno: int) -> pd.DataFrame:
    """Uma linha por localidade no exterior × candidato (votos), com totais da localidade."""
    return con.sql(f"""
        WITH ap AS (SELECT CD_MUNICIPIO, sum(QT_APTOS) APTOS, sum(QT_COMPARECIMENTO) COMPARECIMENTO,
                           sum(QT_ABSTENCOES) ABSTENCOES, sum(QT_TOTAL_VOTOS_VALIDOS) VALIDOS
                    FROM {_a('apuracao_municipio')}
                    WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno} AND SG_UF = '{SG_EXTERIOR}' GROUP BY 1)
        SELECT ap.CD_MUNICIPIO, d.NM_MUNICIPIO LOCALIDADE, ap.APTOS, ap.COMPARECIMENTO, ap.ABSTENCOES, ap.VALIDOS,
               n.SQ_CANDIDATO, n.VOTOS_VALIDOS VOTOS
        FROM ap JOIN {_m('dim_municipio')} d ON d.SG_UF = '{SG_EXTERIOR}' AND d.CD_MUNICIPIO = ap.CD_MUNICIPIO
        LEFT JOIN {_a('nominal_municipio')} n ON n.SG_UF = '{SG_EXTERIOR}' AND n.CD_MUNICIPIO = ap.CD_MUNICIPIO
             AND n.CD_CARGO = {cd_cargo} AND n.NR_TURNO = {turno}
        ORDER BY ap.APTOS DESC""").df()


def exterior(con, cd_cargo: int, turno: int) -> pd.DataFrame:
    """Resultado no exterior (ZZ), por candidato, com denominador do exterior."""
    return con.sql(f"""
        WITH den AS (SELECT sum(QT_TOTAL_VOTOS_VALIDOS) validos, sum(QT_APTOS) aptos,
                            sum(QT_COMPARECIMENTO) comp, count(DISTINCT CD_MUNICIPIO) localidades
                     FROM {_a('apuracao_municipio')}
                     WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno} AND SG_UF = '{SG_EXTERIOR}')
        SELECT n.SQ_CANDIDATO, sum(n.VOTOS_VALIDOS) VOTOS, any_value(den.validos) VALIDOS,
               100.0 * sum(n.VOTOS_VALIDOS) / nullif(any_value(den.validos), 0) PCT_VALIDOS,
               any_value(den.aptos) APTOS, any_value(den.comp) COMPARECIMENTO, any_value(den.localidades) LOCALIDADES
        FROM {_a('nominal_uf')} n, den
        WHERE n.CD_CARGO = {cd_cargo} AND n.NR_TURNO = {turno} AND n.SG_UF = '{SG_EXTERIOR}'
        GROUP BY 1 ORDER BY VOTOS DESC""").df()
