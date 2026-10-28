"""C. Comparação A × B — painel: controles, KPIs, mapa divergente e painel lateral."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from paginas import comum
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.componentes.estado import NIVEL_MUNICIPIO
from src.metricas import indicadores as m
from src.visualizacoes import cores, graficos, mapas, modos
from src.visualizacoes import formatos as f

ALTURA_MAPA = 480


def render(ctx) -> None:
    s = ctx.sel
    rotulo = comum.escopo(ctx).rotulo
    visuais.cabecalho(ctx, f"Comparação A × B · {s.cargo} · {s.turno}º turno", rotulo)
    if comum.bloqueio_disputa(ctx):
        return
    ctx = comum.contexto_da_disputa(ctx, "A comparação A × B")
    if ctx is None:
        return
    s = ctx.sel
    if s.cargo == "Senador":
        st.caption("Senado 2026: duas vagas por UF e dois votos por eleitor. Comparar dois candidatos não representa "
                   "toda a disputa pelas duas vagas; percentuais são de votos, não de eleitores.")
    cands = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, s.turno)
    if len(cands) < 2:
        st.warning("Esta disputa tem menos de dois candidatos com votos neste turno.")
        return
    opcoes = cands.SQ_CANDIDATO.tolist()
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO + " (" + cands.SG_PARTIDO + ")"))

    if "_troca" in st.session_state:  # inversão pedida no rerun anterior (antes dos widgets)
        st.session_state.cmp_a, st.session_state.cmp_b = st.session_state.pop("_troca")
    # Seleção inválida para a disputa/turno é refeita com os dois mais votados.
    if st.session_state.get("cmp_a") not in opcoes or st.session_state.get("cmp_b") not in opcoes \
            or st.session_state.get("cmp_a") == st.session_state.get("cmp_b"):
        st.session_state.cmp_a, st.session_state.cmp_b = opcoes[0], opcoes[1]

    c = st.columns([2, 0.35, 2, 1.4, 1.7], vertical_alignment="bottom")
    a = c[0].selectbox("Candidato A", [o for o in opcoes if o != st.session_state.cmp_b], key="cmp_a",
                       format_func=rot.get, help="Só candidatos desta disputa (mesmo cargo, circunscrição e turno).")
    if c[1].button("⇄", help="Inverter A e B", use_container_width=True):
        st.session_state["_troca"] = (st.session_state.cmp_b, a)
        st.rerun()
    b = c[2].selectbox("Candidato B", [o for o in opcoes if o != a], key="cmp_b", format_func=rot.get)
    par_key = c[3].selectbox("Cores", ["candidatos", *cores.PARES_DIVERGENTES], key="cmp_cores",
                             format_func=lambda k: "Cores dos candidatos" if k == "candidatos"
                             else cores.PARES_DIVERGENTES[k].rotulo)
    metrica = c[4].segmented_control("Métrica", ["margem", "par"], key="cmp_metrica", default="margem",
                                     format_func={"margem": "Margem p.p.", "par": "Part. no par"}.get) or "margem"
    cmap, cor_outros = comum.mapa_cores(ctx)
    cor_a, cor_b = cmap.get(a), cmap.get(b)
    # "Cores dos candidatos" só vale se forem duas cores próprias e distinguíveis (inclusive para daltonismo).
    if par_key != "candidatos" or cor_outros in (cor_a, cor_b) or not cores.distintas(cor_a, cor_b):
        if par_key == "candidatos":
            st.caption("A e B não têm duas cores próprias distinguíveis; usando o par azul × laranja.")
        par = cores.PARES_DIVERGENTES["azul_laranja" if par_key == "candidatos" else par_key]
        cor_a, cor_b = par.claro if ctx.fundo == "claro" else par.escuro

    if st.session_state.get("f_nivel") == NIVEL_MUNICIPIO and not s.uf:
        st.info("Selecione uma UF (barra lateral) ou clique numa UF no mapa para ver os municípios.", icon="👆")

    nivel_uf = not comum.mostrar_uf(ctx)   # True = hover sem sufixo de UF
    ap, vt = cmapa.dados_do_mapa(ctx)
    d = modos.comparacao(ap, vt, cands, a, b, metrica, nivel_uf, compacto=s.nivel == "municipio_br")

    r = comum.ranking_escopo(ctx, cands).set_index("SQ_CANDIDATO")
    va, vb = float(r.loc[a, "VOTOS"]), float(r.loc[b, "VOTOS"])
    den = float(r["VALIDOS_CIRCUNSCRICAO"].dropna().iloc[0])
    cont = d["LIDERA"].value_counts()
    unid = {"região": "regiões", "UF": "UFs"}.get(comum.unidade(ctx), "municípios")
    visuais.kpis([
        ("A · votos", f.compacto(va), f"{f.pct(m.percentual([va], [den])[0])} dos válidos", rot[a]),
        ("B · votos", f.compacto(vb), f"{f.pct(m.percentual([vb], [den])[0])} dos válidos", rot[b]),
        ("Margem A − B", f.pp(m.margem_pp([va], [vb], [den])[0]), f"{f.inteiro(va - vb)} votos",
         f"100 × (A − B) ÷ {f.inteiro(den)} válidos do recorte"),
        ("A no par", f.pct(m.participacao_no_par([va], [vb])[0]), "A ÷ (A + B)", "Exclui os demais candidatos"),
        (f"{unid} · A lidera", str(int(cont.get("A", 0))), f"B lidera: {int(cont.get('B', 0))}",
         "Contagem de territórios — não é contagem de votos"),
        ("Empates · sem votos", f"{int(cont.get('empate', 0))} · {int(cont.get('sem_votos', 0))}",
         "sem votos ≠ empate", "Sem votos = denominador zero"),
    ])

    col_mapa, col_lado = st.columns([2.3, 1], gap="medium")
    with col_mapa, st.container(border=True):
        moldura = cmapa.moldura(ctx, ap, altura=ALTURA_MAPA)
        neutro = cores.NEUTRO[ctx.fundo]
        escala = cores.escala_divergente(cor_b, cor_a, neutro)  # z baixo = B à frente; z alto = A à frente
        centro = 0 if metrica == "margem" else 50
        lim = modos.limite_simetrico(d["Z"], centro)
        if metrica == "margem":
            ticks = ([-lim, 0, lim], [f"B +{f.decimal(lim, 0)} p.p.", "empate", f"A +{f.decimal(lim, 0)} p.p."])
        else:
            ticks = ([50 - lim, 50, 50 + lim], [f"B {f.decimal(50 + lim, 0)}%", "50%", f"A {f.decimal(50 + lim, 0)}%"])
        fig = mapas.mapa_continuo(moldura, d, ctx.fundo, cmapa.revisao(ctx, "cmp"), escala, centro - lim, centro + lim,
                                  "", zmid=centro, ticks=ticks, hover_ausentes=modos.ausentes_sem_votos(ap, nivel_uf),
                                  rotulo_ausente="Sem dado eleitoral")
        visuais.legenda([(cor_a, f"A à frente · {rot[a]}"), (neutro, "≈ empate"),
                         (cor_b, f"B à frente · {rot[b]}"), (cores.SEM_DADO[ctx.fundo], "Sem dado")])
        st.caption("Margem = 100 × (A − B) ÷ válidos do cargo no território." if metrica == "margem" else
                   "Participação no par = A ÷ (A + B); exclui os demais candidatos, não é % dos válidos.")
        fig = mapas.destacar(fig, moldura, comum.destaque(ctx), ctx.fundo)
        cmapa.exibir(fig, ctx, "cmp")
        cmapa.barra_de_acoes(ctx, "cmp")

    with col_lado, st.container(border=True):
        st.markdown(f"### Votos · {rotulo}")
        st.plotly_chart(graficos.barras_par(["A", "B"], [va, vb], [cor_a, cor_b], ctx.fundo),
                        use_container_width=True, config={"displayModeBar": False}, key="cmp_barras")
        st.caption("Liderar em mais territórios não significa vencer: territórios têm eleitorados "
                   "diferentes. Vale o resultado oficial da circunscrição.")
        votos_em = d.groupby("LIDERA")[["A", "B"]].sum()
        linhas = [(lado, votos_em.loc[lado, "A"], votos_em.loc[lado, "B"]) for lado in ("A", "B") if lado in votos_em.index]
        if linhas:
            st.markdown("**Votos nos territórios em que cada um lidera**")
            st.dataframe({"Onde lidera": [l[0] for l in linhas], "Votos A": [l[1] for l in linhas],
                          "Votos B": [l[2] for l in linhas]}, hide_index=True, use_container_width=True,
                         column_config={"Votos A": st.column_config.NumberColumn(format="localized"),
                                        "Votos B": st.column_config.NumberColumn(format="localized")})
        tab = d[d.LIDERA != "sem_votos"][["NOME", "MARGEM_PP", "QT_APTOS"]].sort_values("MARGEM_PP")
        st.markdown(f"**Maiores margens ({unid})**")
        topo = tab.tail(4).iloc[::-1].assign(Lado="A")
        base = tab.head(4).assign(Lado="B")
        st.dataframe(
            pd.concat([topo, base]).rename(columns={"NOME": "Território", "MARGEM_PP": "Margem p.p.", "QT_APTOS": "Aptos"}),
            hide_index=True, use_container_width=True, height=visuais.altura_tabela(len(topo) + len(base), 320),
            column_config={"Margem p.p.": st.column_config.NumberColumn(format="%+.1f"),
                           "Aptos": st.column_config.NumberColumn(format="localized")})
    completa = pd.DataFrame({"Território": d["NOME"], "UF": d["SG_UF"], "Aptos": d["QT_APTOS"],
                             f"Votos A · {rot[a]}": d["A"], f"Votos B · {rot[b]}": d["B"],
                             "% A": d["PCT_A"], "% B": d["PCT_B"], "Margem p.p.": d["MARGEM_PP"],
                             "A no par %": d["PAR_A"], "Lidera": d["LIDERA"],
                             "Válidos (denominador)": d["QT_TOTAL_VOTOS_VALIDOS"]})
    with st.expander(f"Tabela completa A × B · {len(completa)} territórios"):
        st.dataframe(completa.sort_values("Margem p.p.", ascending=False), hide_index=True, use_container_width=True,
                     height=visuais.altura_tabela(len(completa), 360))
        visuais.botao_csv(completa, f"comparacao_{s.cargo}_{s.turno}t")
    visuais.contexto_fonte()
