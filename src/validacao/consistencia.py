"""Verificações contábeis entre os arquivos oficiais (validação integrada).

Cada verificação devolve o número de chaves que violam a identidade. Zero
significa consistente. As identidades foram derivadas do leiame do TSE e
confirmadas empiricamente na Etapa 1 (ver docs/auditoria_fontes.md).
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import duckdb

from src.aquisicao import manifesto
from src.config import DIR_PROCESSED, DIR_RELATORIOS
from src.tratamento.chaves import sql_chaves_munzona

BRUTO = DIR_PROCESSED / "bruto"


def _i(c: str) -> str:
    return f"CAST({c} AS BIGINT)"


@dataclass
class Verificacao:
    nome: str
    descricao: str
    sql: str  # deve retornar colunas (grupo..., violacoes, total)


def _views(con: duckdb.DuckDBPyConnection) -> None:
    k = sql_chaves_munzona()
    for nome in ("detalhe_munzona", "votacao_candidato_munzona", "votacao_partido_munzona"):
        caminho = str(BRUTO / f"{nome}.parquet").replace("\\", "/")
        con.sql(f"CREATE OR REPLACE VIEW {nome} AS SELECT {k}, * EXCLUDE (NR_TURNO, CD_CARGO, SG_UF, CD_MUNICIPIO, NR_ZONA) FROM '{caminho}'")


K = "NR_TURNO, CD_CARGO, SG_UF, CD_MUNICIPIO, NR_ZONA"

VERIFICACOES = [
    Verificacao(
        "chave_unica_detalhe",
        "Detalhe: uma linha por turno × cargo × UF × município × zona",
        f"SELECT 'todos' grupo, count(*) - count(DISTINCT ({K})) violacoes, count(*) total FROM detalhe_munzona",
    ),
    Verificacao(
        "chave_unica_candidato",
        "Votação nominal: uma linha por chave territorial × SQ_CANDIDATO",
        f"SELECT 'todos', count(*) - count(DISTINCT ({K}, SQ_CANDIDATO)), count(*) FROM votacao_candidato_munzona",
    ),
    Verificacao(
        "aptos_comparecimento_abstencao",
        "QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES + QT_ELEITORES_SECOES_NAO_INSTALADAS",
        f"""SELECT 'todos', sum(({_i('QT_APTOS')} <> {_i('QT_COMPARECIMENTO')} + {_i('QT_ABSTENCOES')}
                + {_i('QT_ELEITORES_SECOES_NAO_INSTALADAS')})::INT), count(*) FROM detalhe_munzona""",
    ),
    Verificacao(
        "votos_por_eleitor",
        "QT_VOTOS = QT_COMPARECIMENTO × votos por eleitor (2 para Senador em 2026; 1 nos demais)",
        f"""SELECT DS_CARGO, sum(({_i('QT_VOTOS')} <> {_i('QT_COMPARECIMENTO')} *
                CASE WHEN DS_CARGO = 'Senador' THEN 2 ELSE 1 END)::INT), count(*) FROM detalhe_munzona GROUP BY 1""",
    ),
    Verificacao(
        "composicao_votos",
        "QT_VOTOS = válidos + brancos + total nulos + anulados + anulados sub judice + anulados apurados em separado",
        f"""SELECT DS_CARGO, sum(({_i('QT_VOTOS')} <> {_i('QT_TOTAL_VOTOS_VALIDOS')} + {_i('QT_VOTOS_BRANCOS')}
                + {_i('QT_TOTAL_VOTOS_NULOS')} + {_i('QT_TOTAL_VOTOS_ANULADOS')} + {_i('QT_TOTAL_VOTOS_ANUL_SUBJUD')}
                + {_i('QT_VOTOS_ANULADOS_APU_SEP')})::INT), count(*) FROM detalhe_munzona GROUP BY 1""",
    ),
    Verificacao(
        "validos_nominais_legenda",
        "QT_TOTAL_VOTOS_VALIDOS = QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS",
        f"""SELECT DS_CARGO, sum(({_i('QT_TOTAL_VOTOS_VALIDOS')} <> {_i('QT_VOTOS_NOMINAIS_VALIDOS')}
                + {_i('QT_TOTAL_VOTOS_LEG_VALIDOS')})::INT), count(*) FROM detalhe_munzona GROUP BY 1""",
    ),
    Verificacao(
        "nominais_candidato_vs_detalhe",
        "Σ QT_VOTOS_NOMINAIS_VALIDOS (votação nominal) = QT_VOTOS_NOMINAIS_VALIDOS (detalhe), por chave",
        f"""WITH c AS (SELECT {K}, sum({_i('QT_VOTOS_NOMINAIS_VALIDOS')}) v FROM votacao_candidato_munzona GROUP BY ALL)
            SELECT d.DS_CARGO || ' T' || d.NR_TURNO, sum(({_i('d.QT_VOTOS_NOMINAIS_VALIDOS')} <> coalesce(c.v, 0))::INT), count(*)
            FROM detalhe_munzona d LEFT JOIN c USING ({K}) GROUP BY 1""",
    ),
    Verificacao(
        "subjudice_candidato_vs_detalhe",
        "Σ QT_VOTOS_NOMINAIS com destinação 'Anulado sub judice' = QT_VOTOS_NOMINAIS_ANUL_SUBJUD (detalhe)",
        f"""WITH c AS (SELECT {K}, sum({_i('QT_VOTOS_NOMINAIS')}) v FROM votacao_candidato_munzona
                       WHERE NM_TIPO_DESTINACAO_VOTOS = 'Anulado sub judice' GROUP BY ALL)
            SELECT d.DS_CARGO || ' T' || d.NR_TURNO, sum(({_i('d.QT_VOTOS_NOMINAIS_ANUL_SUBJUD')} <> coalesce(c.v, 0))::INT), count(*)
            FROM detalhe_munzona d LEFT JOIN c USING ({K}) GROUP BY 1""",
    ),
    Verificacao(
        "legenda_partido_vs_detalhe",
        "Σ QT_TOTAL_VOTOS_LEG_VALIDOS (votação em partido) = QT_TOTAL_VOTOS_LEG_VALIDOS (detalhe), por chave",
        f"""WITH p AS (SELECT {K}, sum({_i('QT_TOTAL_VOTOS_LEG_VALIDOS')}) v FROM votacao_partido_munzona GROUP BY ALL)
            SELECT d.DS_CARGO || ' T' || d.NR_TURNO, sum(({_i('d.QT_TOTAL_VOTOS_LEG_VALIDOS')} <> coalesce(p.v, 0))::INT), count(*)
            FROM detalhe_munzona d LEFT JOIN p USING ({K}) GROUP BY 1""",
    ),
    Verificacao(
        "nominais_partido_vs_detalhe",
        "Σ QT_VOTOS_NOMINAIS_VALIDOS (votação em partido) = QT_VOTOS_NOMINAIS_VALIDOS (detalhe), por chave",
        f"""WITH p AS (SELECT {K}, sum({_i('QT_VOTOS_NOMINAIS_VALIDOS')}) v FROM votacao_partido_munzona GROUP BY ALL)
            SELECT d.DS_CARGO || ' T' || d.NR_TURNO, sum(({_i('d.QT_VOTOS_NOMINAIS_VALIDOS')} <> coalesce(p.v, 0))::INT), count(*)
            FROM detalhe_munzona d LEFT JOIN p USING ({K}) GROUP BY 1""",
    ),
    Verificacao(
        "situacao_constante",
        "Cada candidato tem uma única DS_SIT_TOT_TURNO por turno",
        """SELECT 'todos', count(*) FILTER (WHERE n > 1), count(*) FROM
           (SELECT NR_TURNO, SQ_CANDIDATO, count(DISTINCT DS_SIT_TOT_TURNO) n FROM votacao_candidato_munzona GROUP BY ALL)""",
    ),
]


def executar() -> list[tuple[str, str, str, int, int]]:
    con = duckdb.connect()
    _views(con)
    resultados = []
    for v in VERIFICACOES:
        for grupo, viol, total in con.sql(v.sql).fetchall():
            resultados.append((v.nome, v.descricao, str(grupo), int(viol or 0), int(total)))
    return resultados


def relatorio() -> list[tuple[str, str, str, int, int]]:
    res = executar()
    md = io.StringIO()
    md.write("# Verificações contábeis entre arquivos oficiais\n\n")
    md.write(f"Gerado em {manifesto.agora_iso()}. Chaves territoriais normalizadas "
             "(`src/tratamento/chaves.py`).\n\n")
    md.write("| verificação | grupo | violações | linhas/chaves | resultado |\n|---|---|---|---|---|\n")
    for nome, _, grupo, viol, total in res:
        md.write(f"| {nome} | {grupo} | {viol} | {total} | {'OK' if viol == 0 else 'FALHA'} |\n")
    md.write("\n## Descrição das verificações\n\n")
    for v in VERIFICACOES:
        md.write(f"- **{v.nome}**: {v.descricao}\n")
    DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    (DIR_RELATORIOS / "consistencia.md").write_text(md.getvalue(), encoding="utf-8")
    return res
