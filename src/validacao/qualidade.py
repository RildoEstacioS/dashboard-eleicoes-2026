"""Relatório de qualidade do modelo: granularidade, chaves, nulos e casos especiais."""
from __future__ import annotations

import io

import duckdb

from src.aquisicao import manifesto
from src.config import DIR_AGREGADOS, DIR_MODELO, DIR_RELATORIOS

# tabela → colunas que definem a granularidade (devem ser únicas e não nulas)
GRANULARIDADE = {
    "fato_apuracao": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA"],
    "fato_nominal": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "SQ_CANDIDATO"],
    "fato_partido": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_PARTIDO", "SQ_COLIGACAO"],
    "dim_eleicao": ["CD_ELEICAO"],
    "dim_cargo": ["CD_CARGO"],
    "dim_circunscricao": ["CD_CARGO", "SG_UE"],
    "dim_candidato": ["SQ_CANDIDATO"],
    "dim_partido": ["NR_PARTIDO"],
    "dim_federacao": ["NR_FEDERACAO"],
    "dim_uf": ["SG_UF"],
    "dim_municipio": ["SG_UF", "CD_MUNICIPIO"],
    "disponibilidade": ["CD_CARGO", "SG_UE", "NR_TURNO"],
}
GRANULARIDADE_AGREGADOS = {
    "apuracao_municipio": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO"],
    "apuracao_uf": ["NR_TURNO", "CD_CARGO", "SG_UF"],
    "nominal_municipio": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "SQ_CANDIDATO"],
    "nominal_uf": ["NR_TURNO", "CD_CARGO", "SG_UF", "SQ_CANDIDATO"],
    "partido_municipio": ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_PARTIDO"],
    "partido_uf": ["NR_TURNO", "CD_CARGO", "SG_UF", "NR_PARTIDO"],
}


def verificar_granularidade(con) -> list[tuple[str, int, int, int]]:
    """(tabela, linhas, duplicadas na granularidade, nulos nas chaves)."""
    out = []
    for base, mapa in ((DIR_MODELO, GRANULARIDADE), (DIR_AGREGADOS, GRANULARIDADE_AGREGADOS)):
        for tab, chaves in mapa.items():
            p = (base / f"{tab}.parquet").as_posix()
            k = ", ".join(chaves)
            nulos = " + ".join(f"count(*) FILTER (WHERE {c} IS NULL)" for c in chaves)
            n, dup, nul = con.sql(
                f"SELECT count(*), count(*) - count(DISTINCT ({k})), {nulos} FROM '{p}'").fetchall()[0]
            out.append((tab, n, dup, nul))
    return out


def casos_especiais(con) -> list[tuple[str, int, str]]:
    m = lambda t: (DIR_MODELO / f"{t}.parquet").as_posix()  # noqa: E731
    a = lambda t: (DIR_AGREGADOS / f"{t}.parquet").as_posix()  # noqa: E731
    consultas = [
        ("Municípios × cargo × turno com zero votos válidos (estado 'sem votos', não empate)",
         f"SELECT count(*) FROM '{a('apuracao_municipio')}' WHERE QT_TOTAL_VOTOS_VALIDOS = 0", ""),
        ("Candidatos com votos só anulados sub judice (0 válidos)",
         f"""SELECT count(*) FROM (SELECT SQ_CANDIDATO FROM '{m('fato_nominal')}' GROUP BY 1
             HAVING sum(QT_VOTOS_NOMINAIS_VALIDOS) = 0 AND sum(QT_VOTOS_NOMINAIS) > 0)""",
         "Exibidos com votos válidos = 0; votos anulados aparecem à parte."),
        ("Linhas de votação com destinação 'Válido (legenda)'",
         f"SELECT count(*) FROM '{m('fato_nominal')}' WHERE NM_TIPO_DESTINACAO_VOTOS = 'Válido (legenda)'",
         "Votos nominais convertidos em legenda por decisão judicial; contam nos válidos do partido."),
        ("Zonas com linhas de partido repetidas por SQ_COLIGACAO (federações)",
         f"""SELECT count(*) FROM (SELECT NR_TURNO, CD_CARGO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_PARTIDO
             FROM '{m('fato_partido')}' GROUP BY ALL HAVING count(*) > 1)""",
         "Valores aditivos; agregados por partido somam as linhas (conferido contra o detalhe)."),
        ("Zonas do exterior (SG_UF = ZZ)",
         f"SELECT count(*) FROM '{m('fato_apuracao')}' WHERE SG_UF = 'ZZ'", "Só presidente."),
        ("Candidatos (titulares) sem situação de totalização",
         f"SELECT count(*) FROM '{m('dim_candidato')}' WHERE SITUACAO_FINAL = 'sem_situacao'", ""),
        ("Circunscrições sem vagas oficiais",
         f"SELECT count(*) FROM '{m('dim_circunscricao')}' WHERE QT_VAGA IS NULL", ""),
        ("Eleitos ≠ vagas (circunscrições)",
         f"""SELECT count(*) FROM '{m('dim_circunscricao')}' c LEFT JOIN
             (SELECT CD_CARGO, SG_UE, count(*) n FROM '{m('dim_candidato')}' WHERE SITUACAO_FINAL = 'eleito' GROUP BY ALL) e
             USING (CD_CARGO, SG_UE) WHERE coalesce(e.n, 0) <> c.QT_VAGA""", "Deve ser 0."),
    ]
    return [(d, con.sql(s).fetchall()[0][0], nota) for d, s, nota in consultas]


def relatorio() -> dict:
    con = duckdb.connect()
    gran = verificar_granularidade(con)
    casos = casos_especiais(con)
    disp = con.sql(f"""SELECT DS_CARGO, NR_TURNO, ESTADO, count(*) n
                       FROM '{(DIR_MODELO / 'disponibilidade.parquet').as_posix()}' GROUP BY ALL ORDER BY ALL""").fetchall()
    md = io.StringIO()
    md.write(f"# Relatório de qualidade do modelo\n\nGerado em {manifesto.agora_iso()}.\n\n")
    md.write("## Granularidade e chaves\n\n| tabela | linhas | duplicadas na granularidade | nulos nas chaves | resultado |\n|---|---|---|---|---|\n")
    for t, n, d, nul in gran:
        md.write(f"| {t} | {n:,} | {d} | {nul} | {'OK' if d == 0 and nul == 0 else 'FALHA'} |\n")
    md.write("\n## Casos especiais\n\n| caso | quantidade | tratamento |\n|---|---|---|\n")
    for d, n, nota in casos:
        md.write(f"| {d} | {n:,} | {nota} |\n")
    md.write("\n## Disponibilidade das disputas\n\n| cargo | turno | estado | circunscrições |\n|---|---|---|---|\n")
    for c, t, e, n in disp:
        md.write(f"| {c} | {t} | {e} | {n} |\n")
    DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    (DIR_RELATORIOS / "qualidade_modelo.md").write_text(md.getvalue(), encoding="utf-8")
    falhas = [g for g in gran if g[2] or g[3]]
    return {"falhas_granularidade": falhas, "casos": casos}
