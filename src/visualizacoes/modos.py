"""Prepara os dados dos modos de coloração (pandas puro, testável).

Entradas comuns:
- `apuracao`: saída de consultas.apuracao_territorios (uma linha por território);
- `votos`: saída de consultas.votos_territorios (território × candidato);
- `cands`: saída de consultas.candidatos (nome, partido, cor...).

Denominadores sempre vêm de `apuracao` (válidos do cargo no território).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.metricas import indicadores as m
from src.visualizacoes import cores
from src.visualizacoes import formatos as f

INTENSIDADE_PCT = "pct"
INTENSIDADE_VANTAGEM = "vantagem"


def _rotulo(cands: pd.DataFrame) -> dict[str, str]:
    return {r.SQ_CANDIDATO: f"{r.NM_URNA_CANDIDATO} ({r.SG_PARTIDO})" for r in cands.itertuples()}


def _participacao(ap: pd.DataFrame) -> pd.DataFrame:
    ap = ap.copy()
    ap["PCT_COMP"] = m.percentual(ap["QT_COMPARECIMENTO"], ap["QT_APTOS"])
    ap["PCT_ABST"] = m.percentual(ap["QT_ABSTENCOES"], ap["QT_APTOS"])
    return ap


def _cabecalho(r, nivel_uf: bool) -> str:
    return f"<b>{r.NOME}</b>" + ("" if nivel_uf else f" — {r.SG_UF}")


def _rodape(r, compacto: bool = False) -> str:
    """Rodapé do tooltip. Compacto (mapa nacional por município): só o denominador, para reduzir o envio."""
    if compacto:
        return f"<br>Válidos (denominador): {f.inteiro(r.QT_TOTAL_VOTOS_VALIDOS)}"
    return (f"<br>Votos válidos do cargo (denominador): {f.inteiro(r.QT_TOTAL_VOTOS_VALIDOS)}"
            f"<br>Comparecimento: {f.pct(r.PCT_COMP)} · Abstenção: {f.pct(r.PCT_ABST)}")


def ausentes_sem_votos(ap: pd.DataFrame, nivel_uf: bool) -> dict[str, str]:
    """Territórios com denominador zero: estado 'sem votos válidos', não empate."""
    z = _participacao(ap[ap["QT_TOTAL_VOTOS_VALIDOS"].fillna(0) <= 0])
    return {r.TERRITORIO: _cabecalho(r, nivel_uf) + "<br><i>Sem votos válidos — percentual não calculável</i>"
            for r in z.itertuples()}


def lideranca(apuracao, votos, cands, mapa_cores: dict[str, str], modo: str, nivel_uf: bool,
              termo: str = "Mais votado no território", intensidade: str | None = None,
              compacto: bool = False) -> tuple[pd.DataFrame, dict]:
    """Retorna (dados do mapa, info da legenda)."""
    rot = _rotulo(cands)
    lid = m.lideranca(votos, ["TERRITORIO"], col_cand="SQ_CANDIDATO", col_votos="VOTOS")
    d = _participacao(apuracao).merge(lid, on="TERRITORIO", how="left")
    d = d[d["QT_TOTAL_VOTOS_VALIDOS"].fillna(0) > 0].copy()
    d["PCT_LIDER"] = m.percentual(d["votos_lider"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["VANTAGEM_PP"] = m.percentual(d["vantagem_votos"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["COR"] = np.where(d["estado"] == m.EMPATE, cores.EMPATE[modo],
                        d["lider"].map(mapa_cores).fillna(cores.OUTROS[modo]))

    hov = []
    for r in d.itertuples():
        t = _cabecalho(r, nivel_uf)
        if r.estado == m.EMPATE:
            t += f"<br><b>Empate</b> entre {r.n_empatados} candidatos com {f.inteiro(r.votos_lider)} votos cada"
        else:
            t += (f"<br>{termo}: <b>{rot.get(r.lider, r.lider)}</b>"
                  f"<br>Votos: {f.inteiro(r.votos_lider)} ({f.pct(r.PCT_LIDER)} dos válidos)")
            if isinstance(r.segundo, str) and not compacto:
                t += (f"<br>2º: {rot.get(r.segundo, r.segundo)} — {f.inteiro(r.votos_segundo)}"
                      f"<br>Vantagem: {f.inteiro(r.vantagem_votos)} votos ({f.pp(r.VANTAGEM_PP)})")
        hov.append(t + _rodape(r, compacto))
    d["HOVER"] = hov

    legenda = {"intensidade": None}
    if intensidade:
        col = "PCT_LIDER" if intensidade == INTENSIDADE_PCT else "VANTAGEM_PP"
        lo, hi = float(np.nanmin(d[col])), float(np.nanmax(d[col]))
        d["INTENSIDADE"] = (d[col] - lo) / (hi - lo) if hi > lo else 1.0
        d.loc[d["estado"] == m.EMPATE, "INTENSIDADE"] = 1.0
        legenda["intensidade"] = {"metrica": "% do mais votado sobre os válidos" if intensidade == INTENSIDADE_PCT
                                  else "vantagem sobre o 2º colocado (p.p. dos válidos)",
                                  "min": lo, "max": hi, "unidade": "%" if intensidade == INTENSIDADE_PCT else "p.p."}
    contagem = d.groupby("COR").size().to_dict()
    legenda["territorios_por_cor"] = contagem
    legenda["empates"] = int((d["estado"] == m.EMPATE).sum())
    return d[["TERRITORIO", "COR", "HOVER"] + (["INTENSIDADE"] if intensidade else [])], legenda


def candidato(apuracao, votos, cands, sq: str, metrica: str, nivel_uf: bool, compacto: bool = False) -> pd.DataFrame:
    """Modo 2. metrica: 'pct' (sobre válidos) ou 'abs' (votos)."""
    rot = _rotulo(cands)
    v = votos[votos["SQ_CANDIDATO"] == sq][["TERRITORIO", "VOTOS"]]
    d = _participacao(apuracao).merge(v, on="TERRITORIO", how="left")
    d["VOTOS"] = d["VOTOS"].fillna(0)  # território com apuração e sem linha do candidato = 0 votos
    d["PCT"] = m.percentual(d["VOTOS"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["Z"] = d["PCT"] if metrica == "pct" else d["VOTOS"].where(d["QT_TOTAL_VOTOS_VALIDOS"] > 0)
    hov = []
    for r in d.itertuples():
        t = _cabecalho(r, nivel_uf) + f"<br><b>{rot.get(sq, sq)}</b>"
        if r.QT_TOTAL_VOTOS_VALIDOS and r.QT_TOTAL_VOTOS_VALIDOS > 0:
            t += f"<br>Votos: {f.inteiro(r.VOTOS)}<br>% dos válidos: {f.pct(r.PCT)}"
        else:
            t += "<br><i>Sem votos válidos — percentual não calculável</i>"
        hov.append(t + _rodape(r, compacto))
    d["HOVER"] = hov
    return d[["TERRITORIO", "Z", "HOVER", "VOTOS", "PCT", "NOME", "SG_UF", "QT_TOTAL_VOTOS_VALIDOS", "QT_APTOS"]]


def comparacao(apuracao, votos, cands, sq_a: str, sq_b: str, metrica: str, nivel_uf: bool,
               compacto: bool = False) -> pd.DataFrame:
    """Modo 3. metrica: 'margem' (p.p. dos válidos) ou 'par' (A ÷ (A+B), centro 50 %).

    Z > 0 (ou > 50 no par): A à frente. Z = 0 com votos: empate. Sem válidos: NaN.
    """
    rot = _rotulo(cands)
    va = votos[votos["SQ_CANDIDATO"] == sq_a].set_index("TERRITORIO")["VOTOS"]
    vb = votos[votos["SQ_CANDIDATO"] == sq_b].set_index("TERRITORIO")["VOTOS"]
    d = _participacao(apuracao)
    d["A"] = d["TERRITORIO"].map(va).fillna(0)
    d["B"] = d["TERRITORIO"].map(vb).fillna(0)
    d["PCT_A"] = m.percentual(d["A"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["PCT_B"] = m.percentual(d["B"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["MARGEM_PP"] = m.margem_pp(d["A"], d["B"], d["QT_TOTAL_VOTOS_VALIDOS"])
    d["PAR_A"] = m.participacao_no_par(d["A"], d["B"])
    d["Z"] = d["MARGEM_PP"] if metrica == "margem" else d["PAR_A"]
    d["LIDERA"] = np.select([d["MARGEM_PP"].isna(), d["A"] > d["B"], d["B"] > d["A"]], ["sem_votos", "A", "B"], "empate")
    na, nb = rot.get(sq_a, sq_a), rot.get(sq_b, sq_b)
    hov = []
    for r in d.itertuples():
        t = _cabecalho(r, nivel_uf)
        if r.LIDERA == "sem_votos":
            t += "<br><i>Sem votos válidos — comparação não calculável</i>"
        else:
            t += (f"<br>A · {na}: {f.inteiro(r.A)} ({f.pct(r.PCT_A)})"
                  f"<br>B · {nb}: {f.inteiro(r.B)} ({f.pct(r.PCT_B)})"
                  f"<br>Margem A − B: {f.inteiro(r.A - r.B)} votos ({f.pp(r.MARGEM_PP)})"
                  + ("" if compacto else f"<br>Participação de A no par: {f.pct(r.PAR_A)}"))
            if r.LIDERA == "empate":
                t += "<br><b>Empate entre A e B</b>"
        hov.append(t + _rodape(r, compacto))
    d["HOVER"] = hov
    return d


def indicador(apuracao: pd.DataFrame, chave: str, nivel_uf: bool) -> pd.DataFrame:
    """Modo 4: indicador de participação por território (numerador ÷ denominador somados)."""
    ind = m.INDICADORES[chave]
    d = _participacao(apuracao)
    d["NUM"], d["DEN"] = d[ind.numerador], d[ind.denominador]
    d["Z"] = m.percentual(d["NUM"], d["DEN"])
    rot_den = {"QT_APTOS": "eleitores aptos", "QT_VOTOS": "votos do cargo"}.get(ind.denominador, ind.denominador)
    d["HOVER"] = [
        _cabecalho(r, nivel_uf) + (f"<br><b>{ind.rotulo}: {f.pct(r.Z)}</b><br>{f.inteiro(r.NUM)} ÷ {f.inteiro(r.DEN)} "
                                   f"{rot_den}" if r.DEN and r.DEN > 0 else "<br><i>Sem denominador — não calculável</i>")
        + f"<br>Eleitorado apto: {f.inteiro(r.QT_APTOS)}"
        for r in d.itertuples()]
    return d


def lideranca_partido(apuracao, partidos, mapa_cores: dict[str, str], modo: str, nivel_uf: bool,
                      termo: str = "Partido mais votado no território", compacto: bool = False) -> tuple[pd.DataFrame, dict]:
    """Liderança por PARTIDO (votos nominais + legenda), denominador = válidos do cargo.

    `partidos`: saída de consultas.estaduais.partidos_territorios. Usado nas visões
    nacionais de cargos estaduais e nos mapas de deputados.
    """
    votos = partidos.rename(columns={"SG_PARTIDO": "SQ_CANDIDATO"})[["TERRITORIO", "SQ_CANDIDATO", "VOTOS"]]
    pseudo = (partidos[["SG_PARTIDO", "NM_PARTIDO"]].drop_duplicates("SG_PARTIDO")
              .rename(columns={"SG_PARTIDO": "SQ_CANDIDATO"})
              .assign(NM_URNA_CANDIDATO=lambda x: x.SQ_CANDIDATO, SG_PARTIDO=lambda x: x.NM_PARTIDO.str.title()))
    return lideranca(apuracao, votos, pseudo, mapa_cores, modo, nivel_uf, termo=termo, compacto=compacto)


def eleitos_por_uf(eleitos: pd.DataFrame, mapa_cores: dict[str, str], cor_outros: str, cargo: str) -> pd.DataFrame:
    """Mapa "resultado final por UF": um eleito por UF (governador), cor do partido.

    Hover informa se a definição ocorreu no 1º ou no 2º turno (situação oficial).
    """
    out = []
    for r in eleitos.itertuples():
        out.append({"TERRITORIO": r.SG_UE, "COR": mapa_cores.get(r.SG_PARTIDO, cor_outros),
                    "HOVER": (f"<b>{r.SG_UE}</b><br>{cargo} eleito (situação oficial do TSE): <b>{r.NM_URNA_CANDIDATO}</b> "
                              f"({r.SG_PARTIDO})<br>Definido no <b>{int(r.TURNO_ELEICAO)}º turno</b>"
                              f"<br>Votos no turno da eleição: {f.inteiro(r.VOTOS)}")})
    return pd.DataFrame(out, columns=["TERRITORIO", "COR", "HOVER"])


def cadeiras_por_uf(eleitos: pd.DataFrame, vagas: dict[str, int], mapa_cores: dict[str, str],
                    cor_outros: str, cor_empate: str) -> pd.DataFrame:
    """Partido com mais eleitos (oficiais) em cada UF; empate em cadeiras tem cor própria."""
    out = []
    for uf, g in eleitos.groupby("SG_UE"):
        cont = g.SG_PARTIDO.value_counts()
        topo = cont[cont == cont.max()]
        lista = "<br>".join(f"{p}: {n}" for p, n in cont.head(5).items())
        empate = len(topo) > 1
        out.append({"TERRITORIO": uf, "COR": cor_empate if empate else mapa_cores.get(topo.index[0], cor_outros),
                    "HOVER": (f"<b>{uf}</b> — {vagas.get(uf, len(g))} vagas<br>"
                              + (f"<b>Empate</b> em cadeiras: {', '.join(topo.index)}" if empate
                                 else f"Partido com mais eleitos: <b>{topo.index[0]}</b> ({int(topo.iloc[0])})")
                              + f"<br><br>Eleitos por partido (situação oficial):<br>{lista}")})
    return pd.DataFrame(out, columns=["TERRITORIO", "COR", "HOVER"])


def limite_simetrico(z: pd.Series, centro: float = 0.0, passo: float = 5.0) -> float:
    """Meia-amplitude simétrica em torno do centro, arredondada para cima em `passo`."""
    dev = (z.dropna() - centro).abs()
    if dev.empty or dev.max() == 0:
        return passo
    return math.ceil(dev.max() / passo) * passo
