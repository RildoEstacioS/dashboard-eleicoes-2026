"""Auditoria de layout dos arquivos brutos do TSE.

Gera `docs/relatorios/auditoria_layout.md` com, para cada recurso:
membros do ZIP, colunas, contagem de linhas, datas de geração, distribuição
por turno × cargo × abrangência e perfil de colunas categóricas. Também
confere se o CSV `_BRASIL` é exatamente a soma dos demais recortes
(evidência da sobreposição que o pipeline precisa evitar).
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import duckdb

from src.aquisicao import manifesto
from src.aquisicao.fontes import RECURSOS_TSE
from src.config import DIR_PROCESSED, DIR_RAW, DIR_RELATORIOS
from src.tratamento.leitura_tse import (
    csv_para_parquet_texto,
    escolher_membro_consolidado,
    extrair_consolidado,
)

LIMITE_CATEGORICA = 40


def contar_linhas_membros(zip_path: Path) -> dict[str, int]:
    """Conta linhas de dados (sem cabeçalho) de cada CSV do ZIP, em streaming."""
    contagens = {}
    with zipfile.ZipFile(zip_path) as zf:
        for nome in zf.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            n = 0
            with zf.open(nome) as f:
                for bloco in iter(lambda: f.read(8 * 1024 * 1024), b""):
                    n += bloco.count(b"\n")
            contagens[nome] = n - 1
    return contagens


def verificar_sobreposicao(contagens: dict[str, int]) -> dict[str, int | bool | None]:
    brasil = {k: v for k, v in contagens.items() if k.upper().endswith("_BRASIL.CSV")}
    if not brasil:
        return {"tem_brasil": False, "linhas_brasil": None, "soma_demais": None, "brasil_e_soma": None}
    soma = sum(v for k, v in contagens.items() if k not in brasil)
    lb = next(iter(brasil.values()))
    return {"tem_brasil": True, "linhas_brasil": lb, "soma_demais": soma, "brasil_e_soma": lb == soma}


def _valor(con: duckdb.DuckDBPyConnection, sql: str):
    return con.sql(sql).fetchall()[0][0]


def perfil(con: duckdb.DuckDBPyConnection, parquet_path: Path) -> dict:
    rel = con.read_parquet(str(parquet_path))
    con.register("t", rel)
    colunas = rel.columns
    out: dict = {"colunas": colunas, "linhas": _valor(con, "SELECT count(*) FROM t")}

    if {"DT_GERACAO", "HH_GERACAO"} <= set(colunas):
        out["geracao"] = con.sql(
            "SELECT DT_GERACAO, HH_GERACAO, count(*) n FROM t GROUP BY ALL ORDER BY n DESC"
        ).fetchall()

    dims = [c for c in ("NR_TURNO", "DS_CARGO", "TP_ABRANGENCIA") if c in colunas]
    if dims:
        cols = ", ".join(dims)
        uf = ", count(DISTINCT SG_UF) n_uf" if "SG_UF" in colunas else ""
        out["distribuicao"] = {
            "colunas": dims + ["linhas"] + (["n_uf"] if uf else []),
            "valores": con.sql(f"SELECT {cols}, count(*) linhas{uf} FROM t GROUP BY ALL ORDER BY ALL").fetchall(),
        }

    distintos = con.sql(
        "SELECT " + ", ".join(f'count(DISTINCT "{c}")' for c in colunas) + " FROM t"
    ).fetchall()[0]
    categoricas = {}
    for c, n in zip(colunas, distintos):
        if n <= LIMITE_CATEGORICA:
            categoricas[c] = con.sql(
                f'SELECT "{c}", count(*) n FROM t GROUP BY 1 ORDER BY n DESC'
            ).fetchall()
        else:
            categoricas[c] = f"{n} valores distintos"
    out["perfil_colunas"] = categoricas
    con.unregister("t")
    return out


def _md_tabela(cabecalho: list[str], linhas: list) -> str:
    s = io.StringIO()
    s.write("| " + " | ".join(cabecalho) + " |\n")
    s.write("|" + "---|" * len(cabecalho) + "\n")
    for l in linhas:
        s.write("| " + " | ".join("" if v is None else str(v) for v in l) + " |\n")
    return s.getvalue()


def auditar(chaves: list[str] | None = None) -> dict:
    DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    resultado = {}
    md = io.StringIO()
    md.write("# Auditoria de layout — arquivos brutos do TSE\n\n")
    md.write(f"Gerado em {manifesto.agora_iso()} por `python -m scripts.preparar_dados auditar`.\n\n")

    for chave in chaves or list(RECURSOS_TSE):
        rec = RECURSOS_TSE[chave]
        zip_path = DIR_RAW / rec.arquivo
        if not zip_path.exists():
            md.write(f"## {chave}\n\nArquivo não baixado.\n\n")
            continue
        print(f"[auditoria] {chave}")
        contagens = contar_linhas_membros(zip_path)
        sobre = verificar_sobreposicao(contagens)
        membro = escolher_membro_consolidado(zip_path)
        csv_path = extrair_consolidado(zip_path)
        parquet = csv_para_parquet_texto(csv_path, DIR_PROCESSED / "bruto" / f"{chave}.parquet")
        p = perfil(con, parquet)
        resultado[chave] = {"membro_consolidado": membro, "sobreposicao": sobre, **p}

        if p.get("geracao"):
            dt, hh, _ = p["geracao"][0]
            manifesto.registrar(chave, {"dt_geracao_fonte": f"{dt} {hh}"})

        md.write(f"## {chave} — {rec.descricao}\n\n")
        md.write(f"- URL: {rec.url}\n- Membro lido: `{membro}`\n- Linhas: {p['linhas']:,}\n")
        md.write(f"- Geração informada pela fonte: {p.get('geracao')}\n")
        md.write(f"- `_BRASIL` = soma dos demais recortes: {sobre}\n\n")
        md.write("<details><summary>Membros do ZIP (linhas de dados)</summary>\n\n")
        md.write(_md_tabela(["membro", "linhas"], sorted(contagens.items())))
        md.write("\n</details>\n\n")
        if p.get("distribuicao"):
            md.write("**Distribuição**\n\n")
            md.write(_md_tabela(p["distribuicao"]["colunas"], p["distribuicao"]["valores"]))
            md.write("\n")
        md.write("**Colunas**\n\n")
        linhas_perfil = []
        for c in p["colunas"]:
            v = p["perfil_colunas"][c]
            if isinstance(v, list):
                v = "; ".join(f"{a!s}={b}" for a, b in v[:LIMITE_CATEGORICA])
            linhas_perfil.append([f"`{c}`", v])
        md.write(_md_tabela(["coluna", "valores"], linhas_perfil))
        md.write("\n")

    (DIR_RELATORIOS / "auditoria_layout.md").write_text(md.getvalue(), encoding="utf-8")
    (DIR_RELATORIOS / "auditoria_layout.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(f"[auditoria] relatório em {DIR_RELATORIOS / 'auditoria_layout.md'}")
    return resultado
