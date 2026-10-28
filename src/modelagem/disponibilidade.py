"""Disponibilidade de cada disputa: ano × eleição × cargo × circunscrição × turno.

Regras (nenhuma UF ou candidato fixado no código):
- Uma disputa está DISPONÍVEL se há registros de votação do cargo, da
  circunscrição e do turno com votos (comparecimento > 0).
- 2º turno de um cargo que admite 2º turno (vocabulario.CARGOS_SEGUNDO_TURNO_POSSIVEL):
    * se o 1º turno teve candidato com situação "2º TURNO" e há registros
      válidos no 2º turno → DISPONÍVEL;
    * se o 1º turno teve "2º TURNO" mas faltam registros → DADOS INDISPONÍVEIS;
    * se o 1º turno terminou com eleito → NÃO HOUVE SEGUNDO TURNO.
  A mera existência de um arquivo não basta: contam linhas do cargo, UF e turno.
- 2º turno de cargo que não admite 2º turno → TURNO NÃO APLICÁVEL.
- Cargo sem disputa na UF (ex.: Deputado Estadual no DF) → CIRCUNSCRIÇÃO INEXISTENTE.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src.config import DIR_MODELO
from src.modelagem import vocabulario as v


def _p(nome: str) -> str:
    return "'" + str(DIR_MODELO / f"{nome}.parquet").replace("\\", "/") + "'"


def calcular(con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """Uma linha por cargo × circunscrição × turno possível (1 e 2), com o estado."""
    con = con or duckdb.connect()
    cargos_2t = ", ".join(f"'{c}'" for c in v.CARGOS_SEGUNDO_TURNO_POSSIVEL)
    return con.sql(f"""
        WITH circ AS (SELECT CD_CARGO, DS_CARGO, SG_UE FROM {_p('dim_circunscricao')}),
        eleicao AS (SELECT NR_TURNO, TP_ABRANGENCIA, CD_ELEICAO, ANO_ELEICAO FROM {_p('dim_eleicao')}),
        cargo AS (SELECT CD_CARGO, TP_ABRANGENCIA FROM {_p('dim_cargo')}),
        -- votação efetiva por cargo × circunscrição × turno
        vot AS (
            SELECT a.NR_TURNO, a.CD_CARGO,
                   CASE WHEN c.TP_ABRANGENCIA = 'F' THEN 'BR' ELSE a.SG_UF END SG_UE,
                   count(*) n_zonas, sum(a.QT_COMPARECIMENTO) comparecimento,
                   sum(a.QT_TOTAL_VOTOS_VALIDOS) votos_validos
            FROM {_p('fato_apuracao')} a JOIN cargo c USING (CD_CARGO) GROUP BY ALL),
        sit AS (
            SELECT CD_CARGO, SG_UE,
                   count(*) FILTER (WHERE DS_SIT_TOT_TURNO_1 = '2º TURNO') n_2t_no_1t,
                   count(*) FILTER (WHERE SITUACAO_FINAL = 'eleito' AND TURNO_ELEICAO = 1) eleitos_1t,
                   count(*) FILTER (WHERE SITUACAO_FINAL = 'eleito' AND TURNO_ELEICAO = 2) eleitos_2t,
                   count(*) FILTER (WHERE ULTIMO_TURNO_DISPUTADO >= 1) cand_1t,
                   count(*) FILTER (WHERE ULTIMO_TURNO_DISPUTADO = 2) cand_2t
            FROM {_p('dim_candidato')} GROUP BY ALL),
        grade AS (SELECT circ.*, t.NR_TURNO FROM circ CROSS JOIN (VALUES (1), (2)) t(NR_TURNO))
        SELECT e.ANO_ELEICAO, e.CD_ELEICAO, g.NR_TURNO, g.CD_CARGO, g.DS_CARGO, g.SG_UE,
               coalesce(vot.n_zonas, 0) n_zonas, coalesce(vot.comparecimento, 0) comparecimento,
               coalesce(vot.votos_validos, 0) votos_validos,
               CASE g.NR_TURNO WHEN 1 THEN sit.cand_1t ELSE sit.cand_2t END n_candidatos,
               CASE g.NR_TURNO WHEN 1 THEN sit.eleitos_1t ELSE sit.eleitos_2t END n_eleitos,
               CASE
                 WHEN g.NR_TURNO = 1 AND coalesce(vot.comparecimento, 0) > 0 THEN '{v.DISPONIVEL}'
                 WHEN g.NR_TURNO = 1 THEN '{v.DADOS_INDISPONIVEIS}'
                 WHEN g.DS_CARGO NOT IN ({cargos_2t}) THEN '{v.TURNO_NAO_APLICAVEL}'
                 WHEN sit.n_2t_no_1t > 0 AND coalesce(vot.comparecimento, 0) > 0 THEN '{v.DISPONIVEL}'
                 WHEN sit.n_2t_no_1t > 0 THEN '{v.DADOS_INDISPONIVEIS}'
                 WHEN sit.eleitos_1t > 0 THEN '{v.NAO_HOUVE_SEGUNDO_TURNO}'
                 ELSE '{v.DADOS_INDISPONIVEIS}'
               END ESTADO
        FROM grade g
        JOIN cargo c USING (CD_CARGO)
        LEFT JOIN eleicao e ON e.NR_TURNO = g.NR_TURNO AND e.TP_ABRANGENCIA = c.TP_ABRANGENCIA
        LEFT JOIN vot ON vot.NR_TURNO = g.NR_TURNO AND vot.CD_CARGO = g.CD_CARGO AND vot.SG_UE = g.SG_UE
        LEFT JOIN sit ON sit.CD_CARGO = g.CD_CARGO AND sit.SG_UE = g.SG_UE
        ORDER BY g.CD_CARGO, g.SG_UE, g.NR_TURNO
    """).df()


def salvar() -> pd.DataFrame:
    df = calcular()
    df.to_parquet(DIR_MODELO / "disponibilidade.parquet", index=False)
    return df


def estado(disp: pd.DataFrame, ds_cargo: str, sg_ue: str, turno: int) -> str:
    """Estado de uma combinação; circunscrição ausente → CIRCUNSCRICAO_INEXISTENTE."""
    linha = disp[(disp["DS_CARGO"] == ds_cargo) & (disp["SG_UE"] == sg_ue) & (disp["NR_TURNO"] == turno)]
    return linha["ESTADO"].iloc[0] if len(linha) else v.CIRCUNSCRICAO_INEXISTENTE


def ues_disponiveis(disp: pd.DataFrame, ds_cargo: str, turno: int) -> list[str]:
    m = (disp["DS_CARGO"] == ds_cargo) & (disp["NR_TURNO"] == turno) & (disp["ESTADO"] == v.DISPONIVEL)
    return sorted(disp.loc[m, "SG_UE"])
