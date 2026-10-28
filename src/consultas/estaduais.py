"""Consultas para cargos de circunscrição estadual e visões por partido.

Regras:
- Candidatos de UFs diferentes nunca são comparados como se disputassem a mesma
  eleição: consultas por candidato recebem sempre a UF (circunscrição).
- Visões nacionais desses cargos agregam só métricas compatíveis entre UFs:
  votos por partido (somados entre disputas, com aviso de escopo) e eleitos
  oficiais por partido.
- "Eleito" vem sempre da situação oficial (dim_candidato), nunca de ranking.
"""
from __future__ import annotations

import pandas as pd

from src.consultas.eleicao import NIVEL_REGIAO, NIVEL_UF, _a, _filtros_territorio, _m


def partidos_territorios(con, cd_cargo: int, turno: int, nivel: str, sg_uf: str | None = None,
                         regiao: str | None = None) -> pd.DataFrame:
    """Votos por território × partido: nominais, legenda e total (nominais + legenda).

    Para cargos majoritários, legenda = 0 e nominais = votos do candidato do partido.
    """
    f, p = _filtros_territorio("x.", sg_uf, regiao)
    soma = """sum(x.QT_VOTOS_NOMINAIS_VALIDOS) NOMINAIS, sum(x.QT_TOTAL_VOTOS_LEG_VALIDOS) LEGENDA,
              sum(x.QT_VOTOS_NOMINAIS_VALIDOS) + sum(x.QT_TOTAL_VOTOS_LEG_VALIDOS) VOTOS"""
    base = f"WHERE x.CD_CARGO = {cd_cargo} AND x.NR_TURNO = {turno}"
    if nivel in (NIVEL_REGIAO, NIVEL_UF):
        terr = "u.NM_REGIAO" if nivel == NIVEL_REGIAO else "x.SG_UF"
        return con.sql(f"""
            SELECT {terr} TERRITORIO, d.SG_PARTIDO, any_value(d.NM_PARTIDO) NM_PARTIDO, {soma}
            FROM {_a('partido_uf')} x JOIN {_m('dim_uf')} u USING (SG_UF)
            JOIN {_m('dim_partido')} d USING (NR_PARTIDO)
            {base} {f} GROUP BY ALL HAVING VOTOS > 0""", params=p).df()
    return con.sql(f"""
        SELECT m.CD_MUNICIPIO_IBGE TERRITORIO, d.SG_PARTIDO, any_value(d.NM_PARTIDO) NM_PARTIDO, {soma}
        FROM {_a('partido_municipio')} x
        JOIN {_m('dim_municipio')} m ON m.SG_UF = x.SG_UF AND m.CD_MUNICIPIO = x.CD_MUNICIPIO
        JOIN {_m('dim_uf')} u ON u.SG_UF = x.SG_UF
        JOIN {_m('dim_partido')} d USING (NR_PARTIDO)
        {base} AND m.ESTADO_JUNCAO = 'associado' {f}
        GROUP BY ALL HAVING VOTOS > 0""", params=p).df()


def eleitos(con, cd_cargo: int, sg_ue: str | None = None) -> pd.DataFrame:
    """Eleitos pela situação oficial, com o turno em que se elegeram e os votos nesse turno."""
    filtro = "AND c.SG_UE = ?" if sg_ue else ""
    return con.sql(f"""
        SELECT c.SQ_CANDIDATO, c.SG_UE, c.NR_CANDIDATO, c.NM_URNA_CANDIDATO, c.SG_PARTIDO, c.NR_FEDERACAO,
               f.NM_FEDERACAO, c.TURNO_ELEICAO,
               CASE c.TURNO_ELEICAO WHEN 1 THEN c.DS_SIT_TOT_TURNO_1 ELSE c.DS_SIT_TOT_TURNO_2 END SITUACAO,
               sum(n.VOTOS_VALIDOS) VOTOS
        FROM {_m('dim_candidato')} c
        LEFT JOIN {_m('dim_federacao')} f USING (NR_FEDERACAO)
        LEFT JOIN {_a('nominal_uf')} n ON n.SQ_CANDIDATO = c.SQ_CANDIDATO AND n.NR_TURNO = c.TURNO_ELEICAO
        WHERE c.CD_CARGO = {cd_cargo} AND c.SITUACAO_FINAL = 'eleito' {filtro}
        GROUP BY ALL ORDER BY c.SG_UE, VOTOS DESC""", params=[sg_ue] if sg_ue else []).df()


def resumo_partidos(con, cd_cargo: int, sg_uf: str, turno: int = 1) -> pd.DataFrame:
    """Por partido na UF: votos nominais, de legenda, total, % dos válidos e eleitos oficiais.

    Federações aparecem pelo nome; cadeiras são as dos eleitos oficiais (nenhum cálculo de QP/sobras).
    """
    return con.sql(f"""
        WITH v AS (
            SELECT x.NR_PARTIDO, sum(x.QT_VOTOS_NOMINAIS_VALIDOS) NOMINAIS, sum(x.QT_TOTAL_VOTOS_LEG_VALIDOS) LEGENDA,
                   any_value(x.NR_FEDERACAO) NR_FEDERACAO
            FROM {_a('partido_uf')} x WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno} AND SG_UF = ? GROUP BY 1),
        den AS (SELECT sum(QT_TOTAL_VOTOS_VALIDOS) validos FROM {_a('apuracao_uf')}
                WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = {turno} AND SG_UF = ?),
        e AS (SELECT NR_PARTIDO, count(*) FILTER (WHERE SITUACAO_FINAL = 'eleito') ELEITOS,
                     count(*) FILTER (WHERE DS_SIT_TOT_TURNO_1 = 'ELEITO POR QP') ELEITOS_QP,
                     count(*) FILTER (WHERE DS_SIT_TOT_TURNO_1 = 'ELEITO POR MÉDIA') ELEITOS_MEDIA,
                     count(*) FILTER (WHERE SITUACAO_FINAL = 'suplente') SUPLENTES
              FROM {_m('dim_candidato')} WHERE CD_CARGO = {cd_cargo} AND SG_UE = ? AND SITUACAO_FINAL IN ('eleito', 'suplente')
              GROUP BY 1)
        SELECT d.SG_PARTIDO, d.NM_PARTIDO, f.NM_FEDERACAO, v.NOMINAIS, v.LEGENDA, v.NOMINAIS + v.LEGENDA TOTAL,
               100.0 * (v.NOMINAIS + v.LEGENDA) / nullif(den.validos, 0) PCT_VALIDOS,
               coalesce(e.ELEITOS, 0) ELEITOS, coalesce(e.ELEITOS_QP, 0) ELEITOS_QP,
               coalesce(e.ELEITOS_MEDIA, 0) ELEITOS_MEDIA, den.validos VALIDOS
        FROM v CROSS JOIN den JOIN {_m('dim_partido')} d USING (NR_PARTIDO)
        LEFT JOIN {_m('dim_federacao')} f ON f.NR_FEDERACAO = v.NR_FEDERACAO
        LEFT JOIN e USING (NR_PARTIDO)
        WHERE v.NOMINAIS + v.LEGENDA > 0
        ORDER BY ELEITOS DESC, TOTAL DESC""", params=[sg_uf, sg_uf, sg_uf]).df()


def ordem_partidos(con, cd_cargo: int) -> list[str]:
    """Ordem ESTÁVEL dos partidos de um cargo (para cores): eleitos oficiais, depois votos no 1º turno."""
    return [s for (s,) in con.sql(f"""
        WITH e AS (SELECT SG_PARTIDO, count(*) n FROM {_m('dim_candidato')}
                   WHERE CD_CARGO = {cd_cargo} AND SITUACAO_FINAL = 'eleito' GROUP BY 1),
             v AS (SELECT d.SG_PARTIDO, sum(QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS) votos
                   FROM {_a('partido_uf')} x JOIN {_m('dim_partido')} d USING (NR_PARTIDO)
                   WHERE CD_CARGO = {cd_cargo} AND NR_TURNO = 1 GROUP BY 1)
        SELECT v.SG_PARTIDO FROM v LEFT JOIN e USING (SG_PARTIDO)
        ORDER BY coalesce(e.n, 0) DESC, v.votos DESC, v.SG_PARTIDO""").fetchall()]
