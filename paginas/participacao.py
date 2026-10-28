"""F. Participação — comparecimento, abstenção, brancos, nulos e válidos no mapa.

Indicadores são do eleitorado/votos do PRÓPRIO cargo, comparáveis entre territórios
mesmo em cargos estaduais (cada UF com sua disputa): não envolvem candidatos.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from paginas import comum
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.componentes.estado import NIVEL_MUNICIPIO, eh_municipal
from src.metricas import indicadores as m
from src.visualizacoes import cores, mapas, modos
from src.visualizacoes import formatos as f

ALTURA_MAPA = 460


def render(ctx) -> None:
    s = ctx.sel
    esc = comum.escopo(ctx)
    visuais.cabecalho(ctx, f"Participação · {s.cargo} · {s.turno}º turno", esc.rotulo)
    if comum.bloqueio_disputa(ctx):
        return
    visuais.kpis(visuais.kpis_participacao(comum.totais_escopo(ctx, esc), esc.rotulo))
    if esc.tipo == "exterior":
        st.info("O exterior não tem geometria no mapa; veja a participação por país e por cidade na Visão geral.",
                icon="🌍")
        return
    if st.session_state.get("f_nivel") == NIVEL_MUNICIPIO and not s.uf:
        st.info("Selecione uma UF (barra lateral) ou clique numa UF no mapa para ver os municípios.", icon="👆")

    c = st.columns([2, 1.4, 1], vertical_alignment="bottom")
    chave = c[0].segmented_control("Indicador", list(m.INDICADORES), key="par_ind", default="abstencao",
                                   format_func=lambda k: m.INDICADORES[k].rotulo) or "abstencao"
    minimo = c[1].number_input("Eleitorado mínimo (rankings)", min_value=0, step=1000, value=0, key="par_min")
    n = c[2].number_input("Itens", min_value=3, max_value=30, value=8, key="par_n")
    ind = m.INDICADORES[chave]
    st.caption(f"**{ind.rotulo}** = {ind.formula} ({ind.unidade}). Numerador e denominador somados no território "
               "antes de dividir." + (f" {ind.nota}" if ind.nota else ""))

    ap, _ = cmapa.dados_do_mapa(ctx)
    nivel_uf = not comum.mostrar_uf(ctx)
    d = modos.indicador(ap, chave, nivel_uf)

    col_mapa, col_lado = st.columns([2.1, 1], gap="medium")
    with col_mapa, st.container(border=True):
        moldura = cmapa.moldura(ctx, ap, altura=ALTURA_MAPA)
        validos = d["Z"].dropna()
        zmin, zmax = (float(validos.min()), float(validos.max())) if len(validos) else (0.0, 1.0)
        escala = cores.escala_sequencial()
        fig = mapas.mapa_continuo(moldura, d, ctx.fundo, cmapa.revisao(ctx, "par"), escala, zmin, zmax,
                                  f"{ind.rotulo} (%)", hover_ausentes=modos.ausentes_sem_votos(ap, nivel_uf),
                                  rotulo_ausente="Sem dado eleitoral")
        visuais.legenda([(escala[0][1], f"menor ({f.pct(zmin)})"), (escala[-1][1], f"maior ({f.pct(zmax)})"),
                         (cores.SEM_DADO[ctx.fundo], "Sem dado")])
        st.caption("Escala do menor ao maior valor do recorte (para realçar diferenças); "
                   "os valores exatos estão no tooltip e na tabela.")
        fig = mapas.destacar(fig, moldura, comum.destaque(ctx), ctx.fundo)
        cmapa.exibir(fig, ctx, "par")
        cmapa.barra_de_acoes(ctx, "par")

    with col_lado, st.container(border=True):
        base = d[d["DEN"] > 0]
        excl = int((base["QT_APTOS"] < minimo).sum())
        base = base[base["QT_APTOS"] >= minimo]
        nome = base["NOME"] + (" (" + base["SG_UF"] + ")" if eh_municipal(s.nivel) else "")
        t = pd.DataFrame({"Território": nome, ind.rotulo: base["Z"], "Aptos": base["QT_APTOS"]})
        cfg = {ind.rotulo: st.column_config.NumberColumn(format="%.1f%%"),
               "Aptos": st.column_config.NumberColumn(format="localized")}
        for titulo, df in ((f"Maior {ind.rotulo.lower()}", t.nlargest(n, ind.rotulo)),
                           (f"Menor {ind.rotulo.lower()}", t.nsmallest(n, ind.rotulo))):
            st.markdown(f"### {titulo}")
            st.dataframe(df, hide_index=True, use_container_width=True, column_config=cfg,
                         height=visuais.altura_tabela(len(df), 400))
        st.caption(f"{len(base)} territórios" + (f"; {excl} abaixo de {f.inteiro(minimo)} aptos ficaram de fora."
                                                if minimo else "."))

    st.markdown(f"### Comparação territorial · {len(d)} territórios")
    tab = pd.DataFrame({
        "Território": d["NOME"], "UF": d["SG_UF"], "Aptos": d["QT_APTOS"],
        "Comparecimento %": m.percentual(d["QT_COMPARECIMENTO"], d["QT_APTOS"]),
        "Abstenção %": m.percentual(d["QT_ABSTENCOES"], d["QT_APTOS"]),
        "Brancos %": m.percentual(d["QT_VOTOS_BRANCOS"], d["QT_VOTOS"]),
        "Nulos %": m.percentual(d["QT_TOTAL_VOTOS_NULOS"], d["QT_VOTOS"]),
        "Válidos %": m.percentual(d["QT_TOTAL_VOTOS_VALIDOS"], d["QT_VOTOS"]),
    }).sort_values("Aptos", ascending=False)
    if not eh_municipal(s.nivel):
        tab = tab.drop(columns=["UF"])
    st.dataframe(tab, hide_index=True, use_container_width=True, height=visuais.altura_tabela(len(tab), 320),
                 column_config={"Aptos": st.column_config.NumberColumn(format="localized")}
                 | {c: st.column_config.NumberColumn(format="%.1f%%") for c in tab.columns if "%" in c})
    visuais.botao_csv(tab, f"participacao_{s.cargo}_{s.turno}t")
    st.caption("Comparecimento e abstenção ÷ eleitorado apto do cargo; brancos, nulos e válidos ÷ total de votos do "
               "cargo" + (" (no Senado, 2 × comparecimento)." if s.cargo == "Senador" else "."))
    visuais.contexto_fonte()
