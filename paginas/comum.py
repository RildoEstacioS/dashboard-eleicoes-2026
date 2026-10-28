"""Cálculos de escopo compartilhados entre páginas."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src.componentes import dados_app as dados
from src.componentes.estado import NIVEL_MUNICIPIO, NIVEL_REGIAO, NIVEL_UF, eh_municipal
from src.metricas import indicadores as m
from src.visualizacoes import cores


@dataclass(frozen=True)
class Escopo:
    """Recorte dos KPIs e do ranking: o mais específico entre município, UF, região e Brasil."""
    rotulo: str
    tipo: str               # 'brasil' | 'regiao' | 'uf' | 'municipio'
    uf: str | None = None
    regiao: str | None = None
    municipio: str | None = None


def escopo(ctx) -> Escopo:
    s = ctx.sel
    if s.uf == "ZZ":
        return Escopo("Exterior (votos fora do Brasil)", "exterior", uf="ZZ")
    if s.municipio:
        return Escopo(f"{ctx.rotulo_municipio.get(s.municipio, s.municipio)} ({s.uf})", "municipio",
                      uf=s.uf, municipio=s.municipio)
    if s.uf:
        return Escopo(s.uf, "uf", uf=s.uf)
    if s.regiao:
        return Escopo(f"Região {s.regiao}", "regiao", regiao=s.regiao)
    if getattr(ctx, "estadual", False):
        return Escopo(f"Brasil · soma de {len(ctx.ufs_disputa)} disputas estaduais", "brasil")
    return Escopo("Brasil (inclui exterior)", "brasil")


def totais_escopo(ctx, e: Escopo) -> dict:
    if e.tipo == "municipio":
        ap = dados.apuracao_territorios(ctx.cd_cargo, ctx.sel.turno, NIVEL_MUNICIPIO, e.uf)
        t = ap[ap.TERRITORIO == e.municipio].iloc[0]
        return {"aptos": t.QT_APTOS, "comparecimento": t.QT_COMPARECIMENTO, "abstencoes": t.QT_ABSTENCOES,
                "validos": t.QT_TOTAL_VOTOS_VALIDOS, "votos": t.QT_VOTOS, "brancos": t.QT_VOTOS_BRANCOS,
                "nulos": t.QT_TOTAL_VOTOS_NULOS}
    return dados.totais(ctx.cd_cargo, ctx.sel.turno, e.uf, True, e.regiao)


def ranking_escopo(ctx, cands: pd.DataFrame) -> pd.DataFrame:
    """Votos e % por candidato no recorte, com o denominador oficial do recorte."""
    e = escopo(ctx)
    if e.tipo == "brasil":
        return cands.copy()
    t = ctx.sel.turno
    if e.tipo == "exterior":
        ex = dados.exterior(ctx.cd_cargo, t)
        out = cands.drop(columns=["VOTOS", "PCT_VALIDOS", "VALIDOS_CIRCUNSCRICAO"]).merge(
            ex[["SQ_CANDIDATO", "VOTOS", "PCT_VALIDOS", "VALIDOS"]].rename(columns={"VALIDOS": "VALIDOS_CIRCUNSCRICAO"}),
            on="SQ_CANDIDATO", how="left")
        out["VOTOS"] = out["VOTOS"].fillna(0)
        return out.sort_values("VOTOS", ascending=False)
    if e.tipo == "municipio":
        ap = dados.apuracao_territorios(ctx.cd_cargo, t, NIVEL_MUNICIPIO, e.uf)
        vt = dados.votos_territorios(ctx.cd_cargo, t, NIVEL_MUNICIPIO, e.uf)
        alvo = e.municipio
    elif e.tipo == "uf":
        ap = dados.apuracao_territorios(ctx.cd_cargo, t, NIVEL_UF, None)
        vt = dados.votos_territorios(ctx.cd_cargo, t, NIVEL_UF, None)
        alvo = e.uf
    else:
        ap = dados.apuracao_territorios(ctx.cd_cargo, t, NIVEL_REGIAO, None)
        vt = dados.votos_territorios(ctx.cd_cargo, t, NIVEL_REGIAO, None)
        alvo = e.regiao
    ap, vt = ap[ap.TERRITORIO == alvo], vt[vt.TERRITORIO == alvo]
    r = m.percentual_sobre_validos(vt.rename(columns={"VOTOS": "votos"}), ap, ["TERRITORIO"])
    out = cands.drop(columns=["VOTOS", "PCT_VALIDOS", "VALIDOS_CIRCUNSCRICAO"]).merge(
        r[["SQ_CANDIDATO", "votos", "pct_validos", "QT_TOTAL_VOTOS_VALIDOS"]], on="SQ_CANDIDATO", how="left")
    out = out.rename(columns={"votos": "VOTOS", "pct_validos": "PCT_VALIDOS",
                              "QT_TOTAL_VOTOS_VALIDOS": "VALIDOS_CIRCUNSCRICAO"})
    out["VOTOS"] = out["VOTOS"].fillna(0)
    return out.sort_values("VOTOS", ascending=False)


def mostrar_uf(ctx) -> bool:
    """Hover inclui a UF só nos níveis municipais."""
    return eh_municipal(ctx.sel.nivel)


def unidade(ctx) -> str:
    return {NIVEL_REGIAO: "região", NIVEL_UF: "UF"}.get(ctx.sel.nivel, "município")


def destaque(ctx) -> str | None:
    """Território a contornar no mapa atual."""
    s = ctx.sel
    if eh_municipal(s.nivel):
        return s.municipio
    if s.nivel == NIVEL_UF:
        return s.uf
    return s.regiao


def mapa_cores_partidos(ctx) -> tuple[dict[str, str], str]:
    """Cores por PARTIDO, estáveis por cargo (ordem: eleitos oficiais, depois votos)."""
    fixas = cores.cores_partidos(ctx.fundo)
    if proporcional(ctx):
        ordem = _ordem_partidos_proporcional(ctx)
        return cores.cores_partidos_proporcional(ordem, ctx.fundo, fixas), cores.OUTROS_PARTIDOS[ctx.fundo]
    ordem = dados.ordem_partidos(ctx.cd_cargo)
    paleta = ctx.paleta if ctx.fundo == "claro" else "padrao"
    mapa, _ = cores.atribuir_com_fixas(ordem, paleta, ctx.fundo, {p: fixas[p] for p in ordem if p in fixas})
    return mapa, cores.OUTROS[ctx.fundo]


def contexto_da_disputa(ctx, pagina: str):
    """Para análises de candidatos em cargos estaduais: exige UF e usa os municípios dela.

    Retorna o contexto ajustado ou None (a página deve parar). A troca para o nível
    municipal é explícita na tela — não é uma mudança silenciosa de filtro.
    """
    from dataclasses import replace
    if ctx.sel.uf == "ZZ":
        st.info("O **exterior** não tem geometria no mapa: veja os votos por cidade do exterior na Visão geral "
                "(filtro UF = Exterior).", icon="🌍")
        return None
    if not getattr(ctx, "estadual", False):
        return ctx
    if not ctx.sg_ue:
        st.info(f"**{pagina}** compara candidatos de uma mesma disputa. Para {ctx.sel.cargo.lower()}, cada UF tem "
                "sua própria eleição: escolha uma UF na barra lateral.", icon="👆")
        return None
    if ctx.sel.nivel != NIVEL_MUNICIPIO:
        st.caption(f"Disputa estadual: análise feita nos municípios de {ctx.sg_ue} (circunscrição da eleição).")
        return replace(ctx, sel=replace(ctx.sel, nivel=NIVEL_MUNICIPIO))
    return ctx


def bloqueio_disputa(ctx) -> bool:
    """Se a UF escolhida não tem a disputa no turno, explica e oferece ações explícitas.

    Nunca troca UF ou turno em silêncio. Retorna True se a página deve parar.
    """
    from src.componentes.filtros import agendar
    from src.modelagem import vocabulario as voc
    if not ctx.conflito:
        return False
    s = ctx.sel
    if ctx.conflito == voc.NAO_HOUVE_SEGUNDO_TURNO:
        st.warning(f"**Não houve segundo turno para {s.cargo.lower()} em {s.uf}.** "
                   "A eleição foi decidida no 1º turno.", icon="ℹ️")
        c = st.columns([1, 1, 1])
        if c[0].button(f"Ver primeiro turno em {s.uf}", type="primary", use_container_width=True):
            agendar(f_turno=1)
        if c[1].button("Ver UFs com segundo turno", use_container_width=True):
            agendar(f_uf=None, f_nivel=NIVEL_UF)
        st.caption("UFs com 2º turno para este cargo: " + ", ".join(ctx.ufs_disputa))
    else:
        st.warning(f"**{voc.ROTULOS_ESTADO.get(ctx.conflito, ctx.conflito)}** — {s.cargo} em {s.uf}, "
                   f"{s.turno}º turno.", icon="ℹ️")
        if st.button("Escolher outra UF", type="primary"):
            agendar(f_uf=None)
    return True


def proporcional(ctx) -> bool:
    cg = dados.cargos()
    return cg.loc[cg.CD_CARGO == ctx.cd_cargo, "SISTEMA"].iloc[0] == "proporcional"


def _ordem_partidos_proporcional(ctx) -> list[str]:
    """Partidos por nº de eleitos na UF (ou no Brasil, sem UF), depois votos — ordem estável do cargo."""
    if ctx.sg_ue and ctx.sg_ue != "BR":
        rp = dados.resumo_partidos(ctx.cd_cargo, ctx.sg_ue, 1)
        return rp.sort_values(["ELEITOS", "TOTAL"], ascending=False).SG_PARTIDO.tolist()
    return dados.ordem_partidos(ctx.cd_cargo)


def mapa_cores(ctx) -> tuple[dict[str, str], str]:
    """Cores estáveis da disputa: ordem do 1º turno, independente do turno exibido.

    Deputados: eleitos na cor do partido (tons diferentes no mesmo partido) e todos os
    não eleitos numa única cor neutra — retornada como 2º valor.
    """
    if proporcional(ctx) and ctx.sg_ue:
        cp, _ = mapa_cores_partidos(ctx)
        el = dados.eleitos(ctx.cd_cargo, ctx.sg_ue).sort_values("VOTOS", ascending=False)
        return (cores.cores_eleitos(list(zip(el.SQ_CANDIDATO, el.SG_PARTIDO)), cp, ctx.fundo),
                cores.NAO_ELEITO[ctx.fundo])
    c1 = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, 1)
    ordem = c1.sort_values("ORDEM_ESTAVEL")["SQ_CANDIDATO"].tolist()
    paleta = ctx.paleta if ctx.fundo == "claro" else "padrao"
    # Cores fixas do usuário: candidato (campanha) > partido > paleta automática.
    por_cand, por_part = cores.cores_candidatos(ctx.fundo), cores.cores_partidos(ctx.fundo)
    fixa_de = {}
    for r in c1.itertuples():
        chaves = cores.chave_candidato(ctx.sel.cargo, str(r.NR_CANDIDATO), ctx.sg_ue)
        cor = next((por_cand[k] for k in chaves if k in por_cand), None) or por_part.get(r.SG_PARTIDO)
        if cor:
            fixa_de[r.SQ_CANDIDATO] = cor
    mapa, avisos = cores.atribuir_com_fixas(ordem, paleta, ctx.fundo, fixa_de)
    nomes = dict(zip(c1.SQ_CANDIDATO, c1.NM_URNA_CANDIDATO))
    for sq, conflito in avisos:
        motivo = "para daltonismo" if paleta == "daltonismo" else "visualmente"
        st.caption(f"⚠ A cor configurada para {nomes.get(sq)} é indistinguível {motivo} da de {nomes.get(conflito)}; "
                   "usando outra cor da paleta. Ajuste config/cores_partidos.toml.")
    return mapa, cores.OUTROS[ctx.fundo]
