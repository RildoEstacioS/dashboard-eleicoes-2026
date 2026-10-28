"""D. Primeiro × segundo turno — só onde houve 2º turno (presidente; governador por UF).

Mapas lado a lado na MESMA escala, variação em votos e em pontos percentuais,
mudança de liderança e variação de participação. Nenhuma inferência de
transferência individual de votos a partir de agregados territoriais.
"""
from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from paginas import comum
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.metricas import indicadores as m
from src.modelagem import vocabulario as voc
from src.visualizacoes import cores, mapas, modos
from src.visualizacoes import formatos as f

ALTURA = 380


def _com_turno(ctx, turno: int):
    return replace(ctx, sel=replace(ctx.sel, turno=turno))


def render(ctx) -> None:
    s = ctx.sel
    esc = comum.escopo(ctx)
    visuais.cabecalho(ctx, f"1º × 2º turno · {s.cargo}", esc.rotulo)
    if s.cargo not in voc.CARGOS_SEGUNDO_TURNO_POSSIVEL:
        st.info(f"{s.cargo} não tem segundo turno. Esta comparação existe para Presidente e Governador "
                "(nas UFs em que houve 2º turno).", icon="ℹ️")
        return
    disp = dados.disponibilidade()
    ufs_2t = sorted(disp.loc[(disp.DS_CARGO == s.cargo) & (disp.NR_TURNO == 2) & (disp.ESTADO == voc.DISPONIVEL),
                             "SG_UE"])
    if ctx.estadual:
        if not s.uf:
            st.info(f"Escolha uma UF com 2º turno para {s.cargo.lower()}: {', '.join(ufs_2t)}.", icon="👆")
            return
        if s.uf not in ufs_2t:
            st.warning(f"**Não houve segundo turno para {s.cargo.lower()} em {s.uf}.** "
                       f"UFs com 2º turno: {', '.join(ufs_2t)}.", icon="ℹ️")
            return
        ctx = replace(ctx, sg_ue=s.uf, conflito=None)
        ctx = comum.contexto_da_disputa(ctx, "A comparação entre turnos")
    elif esc.tipo == "exterior":
        st.info("O exterior não tem geometria; compare os turnos na Visão geral (Exterior, por país).", icon="🌍")
        return
    if ctx is None:
        return
    s = ctx.sel

    c1 = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, 1)
    c2 = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, 2)
    finalistas = c2.SQ_CANDIDATO.tolist()
    rot = dict(zip(c1.SQ_CANDIDATO, c1.NM_URNA_CANDIDATO + " (" + c1.SG_PARTIDO + ")"))
    cmap, cor_outros = comum.mapa_cores(_com_turno(ctx, 1))
    if st.session_state.get("tur_cand") not in finalistas:
        st.session_state["tur_cand"] = finalistas[0]
    sq = st.segmented_control("Candidato do 2º turno", finalistas, key="tur_cand", format_func=rot.get) or finalistas[0]

    ap1, vt1 = cmapa.dados_do_mapa(_com_turno(ctx, 1))
    ap2, vt2 = cmapa.dados_do_mapa(_com_turno(ctx, 2))
    nivel_uf = not comum.mostrar_uf(ctx)
    d1 = modos.candidato(ap1, vt1, c1, sq, "pct", nivel_uf)
    d2 = modos.candidato(ap2, vt2, c2, sq, "pct", nivel_uf)

    # ---- KPIs do recorte ----
    r1 = comum.ranking_escopo(_com_turno(ctx, 1), c1).set_index("SQ_CANDIDATO")
    r2 = comum.ranking_escopo(_com_turno(ctx, 2), c2).set_index("SQ_CANDIDATO")
    t1 = comum.totais_escopo(_com_turno(ctx, 1), comum.escopo(ctx))
    t2 = comum.totais_escopo(_com_turno(ctx, 2), comum.escopo(ctx))
    comp1, comp2 = (m.percentual([t["comparecimento"]], [t["aptos"]])[0] for t in (t1, t2))
    l1 = m.lideranca(vt1, ["TERRITORIO"], col_cand="SQ_CANDIDATO", col_votos="VOTOS").set_index("TERRITORIO")
    l2 = m.lideranca(vt2, ["TERRITORIO"], col_cand="SQ_CANDIDATO", col_votos="VOTOS").set_index("TERRITORIO")
    comuns = l1.index.intersection(l2.index)
    mudou = (l1.loc[comuns, "lider"] != l2.loc[comuns, "lider"]) & l1.loc[comuns, "lider"].notna() \
        & l2.loc[comuns, "lider"].notna()
    visuais.kpis([
        (f"{c1.set_index('SQ_CANDIDATO').NM_URNA_CANDIDATO[sq]} · 1º turno", f.pct(r1.PCT_VALIDOS.get(sq)),
         f"{f.inteiro(r1.VOTOS.get(sq))} votos", "% dos válidos no recorte"),
        ("2º turno", f.pct(r2.PCT_VALIDOS.get(sq)), f"{f.inteiro(r2.VOTOS.get(sq))} votos", "% dos válidos no recorte"),
        ("Variação", f.pp(r2.PCT_VALIDOS.get(sq) - r1.PCT_VALIDOS.get(sq)),
         f"{f.inteiro(r2.VOTOS.get(sq) - r1.VOTOS.get(sq))} votos", "2º turno − 1º turno"),
        ("Comparecimento", f"{f.pct(comp1)} → {f.pct(comp2)}", f.pp(comp2 - comp1), "÷ eleitorado apto do cargo"),
        (f"Liderança mudou em", f"{int(mudou.sum())} de {len(comuns)}", comum.unidade(ctx) + "s",
         "Mais votado no 1º turno (entre todos) ≠ mais votado no 2º"),
    ])

    # ---- mapas lado a lado, mesma escala ----
    zmax = float(pd.concat([d1["Z"], d2["Z"]]).max())
    escala = cores.escala_do_candidato(cmap.get(sq, cor_outros), ctx.fundo)
    col = st.columns(2, gap="small")
    for coluna, d, ap, turno in ((col[0], d1, ap1, 1), (col[1], d2, ap2, 2)):
        with coluna, st.container(border=True):
            st.markdown(f"**{turno}º turno · % dos válidos**")
            mold = cmapa.moldura(_com_turno(ctx, turno), ap, altura=ALTURA)
            fig = mapas.mapa_continuo(mold, d, ctx.fundo, cmapa.revisao(ctx, f"tur{turno}"), escala, 0, zmax,
                                      "%", hover_ausentes=modos.ausentes_sem_votos(ap, nivel_uf))
            st.plotly_chart(fig, use_container_width=True, key=f"tur_mapa_{turno}",
                            config={"scrollZoom": True, "displaylogo": False})
    st.caption(f"Mesma escala nos dois mapas (0 a {f.pct(zmax)}), na cor do candidato.")

    # ---- variação em p.p. ----
    v = d1[["TERRITORIO", "NOME", "SG_UF", "VOTOS", "PCT", "QT_APTOS"]].merge(
        d2[["TERRITORIO", "VOTOS", "PCT"]], on="TERRITORIO", how="outer", suffixes=("_1", "_2"))
    v["VAR_PP"] = v["PCT_2"] - v["PCT_1"]
    v["VAR_VOTOS"] = v["VOTOS_2"] - v["VOTOS_1"]
    v["Z"] = v["VAR_PP"]
    v["SEM_UM_TURNO"] = v["PCT_1"].isna() | v["PCT_2"].isna()
    v["HOVER"] = [(f"<b>{r.NOME}</b>" + ("" if nivel_uf else f" — {r.SG_UF}")
                   + f"<br>1º turno: {f.pct(r.PCT_1)} ({f.inteiro(r.VOTOS_1)} votos)"
                   + f"<br>2º turno: {f.pct(r.PCT_2)} ({f.inteiro(r.VOTOS_2)} votos)"
                   + f"<br>Variação: <b>{f.pp(r.VAR_PP)}</b> · {f.inteiro(r.VAR_VOTOS)} votos"
                   + ("<br><i>Sem dado em um dos turnos</i>" if r.SEM_UM_TURNO else ""))
                  for r in v.itertuples()]
    with st.container(border=True):
        st.markdown("**Variação do % dos válidos (2º − 1º turno, em p.p.)**")
        par = cores.PARES_DIVERGENTES["violeta_verde"]
        queda, alta = par.claro if ctx.fundo == "claro" else par.escuro
        lim = modos.limite_simetrico(v["Z"], 0)
        mold = cmapa.moldura(ctx, ap2, altura=ALTURA + 40)
        fig = mapas.mapa_continuo(mold, v, ctx.fundo, cmapa.revisao(ctx, "turv"),
                                  cores.escala_divergente(queda, alta, cores.NEUTRO[ctx.fundo]), -lim, lim, "p.p.",
                                  zmid=0, ticks=([-lim, 0, lim], [f"−{f.decimal(lim, 0)}", "0", f"+{f.decimal(lim, 0)}"]))
        visuais.legenda([(queda, "perdeu participação"), (cores.NEUTRO[ctx.fundo], "estável"),
                         (alta, "ganhou participação"), (cores.SEM_DADO[ctx.fundo], "Sem dado")])
        st.plotly_chart(fig, use_container_width=True, key="tur_var", config={"scrollZoom": True, "displaylogo": False})
        st.info("**Mudanças agregadas não identificam o comportamento individual do eleitor.** Um ganho em um "
                "território não significa que eleitores de outro candidato “migraram”: o eleitorado que comparece "
                "muda entre os turnos e o voto é secreto. Por isso não há diagrama de transferência de votos.", icon="ℹ️")

    tab = pd.DataFrame({"Território": v["NOME"], "UF": v["SG_UF"], "Aptos": v["QT_APTOS"],
                        "% 1º turno": v["PCT_1"], "% 2º turno": v["PCT_2"], "Variação p.p.": v["VAR_PP"],
                        "Votos 1º": v["VOTOS_1"], "Votos 2º": v["VOTOS_2"], "Variação votos": v["VAR_VOTOS"],
                        "Mais votado 1º": v["TERRITORIO"].map(l1["lider"]).map(rot),
                        "Mais votado 2º": v["TERRITORIO"].map(l2["lider"]).map(rot),
                        "Sem dado em um turno": v["SEM_UM_TURNO"]}).sort_values("Variação p.p.", ascending=False)
    if nivel_uf:
        tab = tab.drop(columns=["UF"])
    st.markdown(f"### Territórios · {rot[sq]}")
    st.dataframe(tab, hide_index=True, use_container_width=True, height=visuais.altura_tabela(len(tab), 360),
                 column_config={c: st.column_config.NumberColumn(format="%.1f%%") for c in ("% 1º turno", "% 2º turno")}
                 | {"Variação p.p.": st.column_config.NumberColumn(format="%+.1f")}
                 | {c: st.column_config.NumberColumn(format="localized")
                    for c in ("Aptos", "Votos 1º", "Votos 2º", "Variação votos")})
    visuais.botao_csv(tab, f"turnos_{s.cargo}_{ctx.sg_ue}")
    with st.expander("Resultado completo do 1º turno"):
        st.dataframe(c1[["NM_URNA_CANDIDATO", "SG_PARTIDO", "VOTOS", "PCT_VALIDOS", "SITUACAO_TURNO"]].rename(columns={
            "NM_URNA_CANDIDATO": "Candidato", "SG_PARTIDO": "Partido", "VOTOS": "Votos", "PCT_VALIDOS": "% válidos",
            "SITUACAO_TURNO": "Situação oficial"}), hide_index=True, use_container_width=True,
            column_config={"Votos": st.column_config.NumberColumn(format="localized"),
                           "% válidos": st.column_config.NumberColumn(format="%.2f%%")})
    visuais.contexto_fonte()
