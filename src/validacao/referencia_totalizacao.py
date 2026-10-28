"""Validação contra o Relatório de Resultado da Totalização (PDF oficial do TSE).

É uma referência independente dos CSVs de dados abertos: o PDF é emitido pelo
SISTOT da circunscrição. Extraímos:
- Anexo IV "Resultado de votação": votos, % e situação por candidato e cargo;
- Resumo: eleitorado apto, abstenção e "Votos válidos" de cada cargo.

O "% Votos computados" do PDF é sobre a votação de TODOS os concorrentes
(válidos + anulados sub judice — nota de rodapé do relatório), e não sobre os
válidos; a comparação recalcula com QT_VOTOS_CONCORRENTES.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd
from pypdf import PdfReader

from src.aquisicao import manifesto
from src.aquisicao.download import baixar
from src.aquisicao.extracao import extrair
from src.aquisicao.fontes import recurso_relatorio_totalizacao
from src.config import DIR_AGREGADOS, DIR_EXTRAIDO, DIR_MODELO, DIR_RELATORIOS

RE_ANEXO = re.compile(r"^(?:Anexo [IVXL]+\s*-|Resultado de votação)")
# Relatórios de UF: "Anexo IV/IX - Resultado de votação"; relatório nacional: só o título.
RE_ANEXO_RESULTADO = re.compile(r"^(?:Anexo [IVXL]+\s*- )?Resultado de votação$")
COLUNAS_PDF = ["cargo", "NR_CANDIDATO", "nome_pdf", "votos_pdf", "pct_pdf", "situacao_pdf", "destinacao_pdf"]
RE_CARGO = re.compile(r"^Cargo: (?P<cargo>[A-Za-zÀ-ú ]+?)(?:\s+Vagas:.*)?$")
RE_CANDIDATO = re.compile(
    # Deputados não trazem %; nas seções por UF do PDF nacional, % vem colado ao número.
    r"^(?P<votos>\d{1,3}(?:\.\d{3})*) (?:(?P<pct>\d+[,.]\d+)% ?)?(?P<sit>[^*]*?)\*?"
    r"(?P<nr>\d{2,5}) - (?P<nome>.+?)\s*(?P<dest>Válido(?: \(legenda\))?|Anulado(?: sub judice)?)?$"
)
RE_APTOS = re.compile(r"Eleitorado apto a votar (?P<v>\d{1,3}(?:\.\d{3})*)$")
RE_ABST = re.compile(r"Abstenção\s+[\d,]+%\s+(?P<v>\d{1,3}(?:\.\d{3})*)$")
RE_VALIDOS = re.compile(r"^Votos válidos(?: \(nominais \+ legenda\))? [\d,]+% (?P<v>\d{1,3}(?:\.\d{3})*)$")


def _int(s: str) -> int:
    return int(s.replace(".", ""))


@dataclass
class Relatorio:
    arquivo: str
    candidatos: pd.DataFrame
    aptos: list[int] = field(default_factory=list)
    abstencoes: list[int] = field(default_factory=list)
    validos: list[int] = field(default_factory=list)


def ler_pdf(caminho: Path) -> Relatorio:
    texto = "\n".join(p.extract_text() or "" for p in PdfReader(caminho).pages)
    return analisar_texto(texto, caminho.name)


def analisar_texto(texto: str, arquivo: str = "") -> Relatorio:
    linhas = [l.strip() for l in texto.splitlines()]
    cands, aptos, abst, validos = [], [], [], []
    no_anexo_iv, cargo = False, None
    for l in linhas:
        # A numeração do anexo varia (IV no 2º turno, IX no 1º); vale o título exato.
        if RE_ANEXO.match(l):
            no_anexo_iv = RE_ANEXO_RESULTADO.match(l) is not None
            continue
        if (m := RE_CARGO.match(l)):
            cargo = m["cargo"].strip()
            continue
        if (m := RE_APTOS.search(l)):
            aptos.append(_int(m["v"]))
        if (m := RE_ABST.search(l)):
            abst.append(_int(m["v"]))
        if (m := RE_VALIDOS.match(l)):
            validos.append(_int(m["v"]))
        if no_anexo_iv and cargo and (m := RE_CANDIDATO.match(l)):
            sit = re.sub(r"^\d+º SUPLENTE$", "SUPLENTE", m["sit"].strip().upper())
            cands.append({"cargo": cargo, "NR_CANDIDATO": m["nr"], "nome_pdf": m["nome"],
                          "votos_pdf": _int(m["votos"]),
                          "pct_pdf": float(m["pct"].replace(",", ".")) if m["pct"] else None,
                          "situacao_pdf": sit or None, "destinacao_pdf": m["dest"]})
    # O 1º bloco é a circunscrição; o PDF nacional repete o resultado por UF em seguida.
    df = pd.DataFrame(cands, columns=COLUNAS_PDF).drop_duplicates(["cargo", "NR_CANDIDATO"], keep="first")
    return Relatorio(arquivo, df, aptos, abst, validos)


def relatorios_da_circunscricao(sigla: str) -> list[Path]:
    zip_path = baixar(recurso_relatorio_totalizacao(sigla))
    return [p for p in extrair(zip_path, DIR_EXTRAIDO / zip_path.stem) if p.suffix.lower() == ".pdf"
            and not p.name.startswith("_")]


def _turno(nome_arquivo: str) -> int:
    return int(re.search(r"_T(\d)", nome_arquivo).group(1))


def processados(con, sg_uf: str, turno: int) -> pd.DataFrame:
    """Votos por candidato no modelo, na UF (ou 'BR' para presidente nacional)."""
    filtro_uf = "" if sg_uf == "BR" else f"AND n.SG_UF = '{sg_uf}'"
    # Presidente é circunscrição nacional: validado só contra o relatório BR.
    cargo_filtro = "AND c.CD_CARGO = 1" if sg_uf == "BR" else "AND c.CD_CARGO <> 1"
    return con.sql(f"""
        WITH ap AS (SELECT CD_CARGO, sum(QT_VOTOS_CONCORRENTES) conc FROM '{(DIR_AGREGADOS / 'apuracao_uf.parquet').as_posix()}'
                    WHERE NR_TURNO = {turno} {"" if sg_uf == "BR" else f"AND SG_UF = '{sg_uf}'"} GROUP BY 1)
        SELECT c.DS_CARGO cargo, c.NR_CANDIDATO, c.NM_URNA_CANDIDATO,
               sum(n.VOTOS_VALIDOS) votos_validos, coalesce(sum(n.VOTOS_ANUL_SUBJUD), 0) subjud,
               coalesce(sum(n.VOTOS_ANULADOS), 0) anulados,
               -- "Votos computados" do PDF = válidos + anulados sub judice + anulados (pela destinação)
               sum(n.VOTOS_VALIDOS) + coalesce(sum(n.VOTOS_ANUL_SUBJUD), 0) + coalesce(sum(n.VOTOS_ANULADOS), 0) votos,
               any_value(CASE {turno} WHEN 1 THEN c.DS_SIT_TOT_TURNO_1 ELSE c.DS_SIT_TOT_TURNO_2 END) situacao,
               100.0 * (sum(n.VOTOS_VALIDOS) + coalesce(sum(n.VOTOS_ANUL_SUBJUD), 0)) / any_value(ap.conc) pct_concorrentes
        FROM '{(DIR_AGREGADOS / 'nominal_uf.parquet').as_posix()}' n
        JOIN '{(DIR_MODELO / 'dim_candidato.parquet').as_posix()}' c USING (SQ_CANDIDATO, CD_CARGO)
        JOIN ap USING (CD_CARGO)
        WHERE n.NR_TURNO = {turno} {filtro_uf} {cargo_filtro}
        GROUP BY ALL""").df()


def comparar(sg_uf: str) -> tuple[pd.DataFrame, list[dict]]:
    con = duckdb.connect()
    ap_uf = (DIR_AGREGADOS / "apuracao_uf.parquet").as_posix()
    linhas_cand, resumo = [], []
    for pdf in sorted(relatorios_da_circunscricao(sg_uf)):
        if sg_uf != "BR" and "PRESIDENTE" in pdf.name.upper():
            continue  # presidente é validado no relatório BR (circunscrição nacional)
        turno = _turno(pdf.name)
        rel = ler_pdf(pdf)
        proc = processados(con, sg_uf, turno)
        m = rel.candidatos.merge(proc, on=["cargo", "NR_CANDIDATO"], how="outer", indicator=True)
        m["arquivo"], m["turno"] = pdf.name, turno
        linhas_cand.append(m)

        filtro = "" if sg_uf == "BR" else f"AND SG_UF = '{sg_uf}'"
        cargos = "AND CD_CARGO = 1" if sg_uf == "BR" else "AND CD_CARGO <> 1"
        tot = con.sql(f"""SELECT CD_CARGO, sum(QT_APTOS) aptos, sum(QT_ABSTENCOES) abst, sum(QT_TOTAL_VOTOS_VALIDOS) validos
                          FROM '{ap_uf}' WHERE NR_TURNO = {turno} {filtro} {cargos} GROUP BY 1""").df()
        # Resumo: o 1º bloco de cada PDF é o total da circunscrição.
        resumo.append({
            "arquivo": pdf.name, "turno": turno,
            "aptos_pdf": rel.aptos[:1], "aptos_processado": sorted(set(tot["aptos"].astype(int))),
            "abstencoes_pdf": rel.abstencoes[:1], "abstencoes_processado": sorted(set(tot["abst"].astype(int))),
            "validos_pdf": sorted(set(rel.validos)), "validos_processado": sorted(tot["validos"].astype(int)),
        })
    return pd.concat(linhas_cand, ignore_index=True), resumo


def avaliar(cand: pd.DataFrame, resumo: list[dict]) -> dict:
    ambos = cand[cand["_merge"] == "both"]
    return {
        "candidatos_comparados": int(len(ambos)),
        "so_no_pdf": int((cand["_merge"] == "left_only").sum()),
        "so_no_processado": int((cand["_merge"] == "right_only").sum()),
        "votos_divergentes": int((ambos["votos_pdf"] != ambos["votos"]).sum()),
        "situacao_divergente": int((ambos["situacao_pdf"].notna()
                                    & (ambos["situacao_pdf"] != ambos["situacao"].str.upper())).sum()),
        "pct_comparados": int(ambos["pct_pdf"].notna().sum()),
        "pct_divergente_>0,01pp": int(((ambos["pct_pdf"] - ambos["pct_concorrentes"]).abs() > 0.01).sum()),
        "resumo_ok": all(r["aptos_pdf"] == r["aptos_processado"] and r["abstencoes_pdf"] == r["abstencoes_processado"]
                         and set(r["validos_processado"]) <= set(r["validos_pdf"]) for r in resumo),
    }


def relatorio(siglas: list[str]) -> dict[str, dict]:
    md = io.StringIO()
    md.write("# Validação contra o Relatório de Resultado da Totalização (PDF oficial)\n\n")
    md.write(f"Gerado em {manifesto.agora_iso()} por `python -m scripts.preparar_dados validar`.\n\n")
    md.write("O % do PDF é sobre votos concorrentes (válidos + anulados sub judice); "
             "o processado é recalculado com QT_VOTOS_CONCORRENTES para comparar.\n\n")
    saida = {}
    for sg in siglas:
        cand, resumo = comparar(sg)
        av = avaliar(cand, resumo)
        saida[sg] = av
        md.write(f"## {sg}\n\n")
        md.write("| item | valor |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in av.items()) + "\n")
        md.write("| arquivo | aptos PDF | aptos processado | abstenções PDF | abstenções processado | válidos PDF | válidos processado |\n")
        md.write("|---|---|---|---|---|---|---|\n")
        for r in resumo:
            md.write(f"| {r['arquivo']} | {r['aptos_pdf']} | {r['aptos_processado']} | {r['abstencoes_pdf']} | "
                     f"{r['abstencoes_processado']} | {r['validos_pdf']} | {r['validos_processado']} |\n")
        div = cand[(cand["_merge"] != "both") | (cand["votos_pdf"] != cand["votos"])]
        if len(div):
            cols = ["arquivo", "cargo", "NR_CANDIDATO", "nome_pdf", "NM_URNA_CANDIDATO", "votos_pdf", "votos", "_merge"]
            md.write("\n**Divergências**\n\n| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
            for r in div[cols].astype("object").fillna("—").itertuples(index=False):
                md.write("| " + " | ".join(str(x) for x in r) + " |\n")
        md.write("\n\n")
        cand.drop(columns="_merge").assign(origem=cand["_merge"].astype(str)).to_csv(
            DIR_RELATORIOS / f"validacao_totalizacao_{sg}.csv", index=False, encoding="utf-8-sig")
    (DIR_RELATORIOS / "validacao_totalizacao.md").write_text(md.getvalue(), encoding="utf-8")
    return saida
