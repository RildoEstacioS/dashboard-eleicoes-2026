"""Pré-agregações usadas pela interface.

Granularidades:
- apuracao_municipio : turno × cargo × UF × município
- apuracao_uf        : turno × cargo × UF            (ZZ = exterior, só presidente)
- nominal_municipio  : turno × cargo × UF × município × candidato
- nominal_uf         : turno × cargo × UF × candidato
- partido_municipio  : turno × cargo × UF × município × partido
- partido_uf         : turno × cargo × UF × partido

Região e Brasil são somas de UF feitas na consulta (baratas). Toda agregação
soma numeradores e denominadores; percentuais só são calculados na consulta.
Depois de gravar, confere que cada soma preserva o total da tabela de zona.
"""
from __future__ import annotations

import time

import duckdb

from src.config import DIR_AGREGADOS, DIR_MODELO


class ErroAgregacao(ValueError):
    pass


def _p(path) -> str:
    return "'" + str(path).replace("\\", "/") + "'"


def _m(nome: str) -> str:
    return _p(DIR_MODELO / f"{nome}.parquet")


def construir() -> dict[str, int]:
    DIR_AGREGADOS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    qt_ap = [c for c in con.sql(f"SELECT * FROM {_m('fato_apuracao')} LIMIT 0").columns if c.startswith("QT_")]
    qt_pa = [c for c in con.sql(f"SELECT * FROM {_m('fato_partido')} LIMIT 0").columns if c.startswith("QT_")]
    s_ap = ", ".join(f"sum({c}) {c}" for c in qt_ap)
    s_pa = ", ".join(f"sum({c}) {c}" for c in qt_pa)
    nominal = """sum(QT_VOTOS_NOMINAIS_VALIDOS) VOTOS_VALIDOS,
                 sum(QT_VOTOS_NOMINAIS) FILTER (WHERE NM_TIPO_DESTINACAO_VOTOS = 'Anulado sub judice') VOTOS_ANUL_SUBJUD,
                 sum(QT_VOTOS_NOMINAIS) FILTER (WHERE NM_TIPO_DESTINACAO_VOTOS = 'Anulado') VOTOS_ANULADOS"""
    mun = "NR_TURNO, CD_CARGO, SG_UF, CD_MUNICIPIO"
    uf = "NR_TURNO, CD_CARGO, SG_UF"
    consultas = {
        "apuracao_municipio": f"SELECT {mun}, {s_ap}, max(TS_ULTIMA_TOTALIZACAO) TS_ULTIMA_TOTALIZACAO, count(*) N_ZONAS FROM {_m('fato_apuracao')} GROUP BY ALL",
        "apuracao_uf": f"SELECT {uf}, {s_ap}, max(TS_ULTIMA_TOTALIZACAO) TS_ULTIMA_TOTALIZACAO, count(*) N_ZONAS FROM {_m('fato_apuracao')} GROUP BY ALL",
        "nominal_municipio": f"SELECT {mun}, SQ_CANDIDATO, {nominal} FROM {_m('fato_nominal')} GROUP BY ALL",
        "nominal_uf": f"SELECT {uf}, SQ_CANDIDATO, {nominal} FROM {_m('fato_nominal')} GROUP BY ALL",
        "partido_municipio": f"SELECT {mun}, NR_PARTIDO, any_value(NR_FEDERACAO) NR_FEDERACAO, {s_pa} FROM {_m('fato_partido')} GROUP BY ALL",
        "partido_uf": f"SELECT {uf}, NR_PARTIDO, any_value(NR_FEDERACAO) NR_FEDERACAO, {s_pa} FROM {_m('fato_partido')} GROUP BY ALL",
    }
    t0 = time.perf_counter()
    linhas = {}
    for nome, sql in consultas.items():
        destino = DIR_AGREGADOS / f"{nome}.parquet"
        con.sql(f"COPY ({sql} ORDER BY ALL) TO {_p(destino)} (FORMAT parquet, COMPRESSION zstd)")
        linhas[nome] = con.sql(f"SELECT count(*) FROM {_p(destino)}").fetchall()[0][0]

    # Conservação dos totais (zona → município → UF)
    verif = [
        ("fato_apuracao", "apuracao_municipio", "apuracao_uf", "QT_APTOS"),
        ("fato_apuracao", "apuracao_municipio", "apuracao_uf", "QT_TOTAL_VOTOS_VALIDOS"),
        ("fato_nominal", "nominal_municipio", "nominal_uf", None),
        ("fato_partido", "partido_municipio", "partido_uf", "QT_TOTAL_VOTOS_LEG_VALIDOS"),
    ]
    for fato, agm, agu, col in verif:
        c_fato = col or "QT_VOTOS_NOMINAIS_VALIDOS"
        c_ag = col or "VOTOS_VALIDOS"
        r = con.sql(f"""
            SELECT (SELECT sum({c_fato}) FROM {_m(fato)}),
                   (SELECT sum({c_ag}) FROM {_p(DIR_AGREGADOS / f'{agm}.parquet')}),
                   (SELECT sum({c_ag}) FROM {_p(DIR_AGREGADOS / f'{agu}.parquet')})""").fetchall()[0]
        if len(set(r)) != 1:
            raise ErroAgregacao(f"Total de {c_fato} não se conserva: zona/município/UF = {r}")
    print(f"[agregados] construídos e conferidos em {time.perf_counter() - t0:.1f}s")
    for n, q in linhas.items():
        print(f"    {n:20s} {q:>12,}")
    return linhas
