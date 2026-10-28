"""B. Análise territorial — mapa do candidato, extremos e tabela vinculada ao mapa."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from paginas import comum
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.componentes.estado import NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR, NIVEL_REGIAO, NIVEL_UF, eh_municipal
from src.componentes.filtros import agendar
from src.metricas import indicadores as m
from src.visualizacoes import cores, mapas, modos
from src.visualizacoes import formatos as f

ALTURA_MAPA = 460


def render(ctx) -> None:
    s = ctx.sel
    esc = comum.escopo(ctx)
    visuais.cabecalho(ctx, f"Análise territorial · {s.cargo} · {s.turno}º turno", esc.rotulo)
    if comum.bloqueio_disputa(ctx):
        return
    ctx = comum.contexto_da_disputa(ctx, "A análise territorial por candidato")
    if ctx is None:
        return
    s = ctx.sel
    cands = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, s.turno)
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO + " (" + cands.SG_PARTIDO + ")"))
    opcoes = cands.SQ_CANDIDATO.tolist()
    if st.session_state.get("ter_cand") not in opcoes:
        st.session_state["ter_cand"] = opcoes[0]

    c = st.columns([2.2, 1.3, 1.4, 1.1], vertical_alignment="bottom")
    sq = c[0].selectbox("Candidato", opcoes, key="ter_cand", format_func=rot.get)
    metrica = c[1].segmented_control("Métrica", ["pct", "abs"], key="ter_metrica", default="pct",
                                     format_func={"pct": "% válidos", "abs": "Votos"}.get) or "pct"
    minimo = c[2].number_input("Eleitorado mínimo (rankings)", min_value=0, step=1000, value=0, key="ter_min",
                               help="Contextualiza os rankings de maiores/menores: exclui territórios com "
                                    "menos eleitores aptos. Não altera o mapa nem a tabela completa.")
    n = c[3].number_input("Itens", min_value=3, max_value=30, value=10, key="ter_n")

    if st.session_state.get("f_nivel") == NIVEL_MUNICIPIO and not s.uf:
        st.info("Selecione uma UF (barra lateral) ou clique numa UF no mapa para ver os municípios.", icon="👆")

    ap, vt = cmapa.dados_do_mapa(ctx)
    nivel_uf = not comum.mostrar_uf(ctx)
    d = modos.candidato(ap, vt, cands, sq, metrica, nivel_uf).merge(
        ap[["TERRITORIO", "NM_REGIAO", "QT_COMPARECIMENTO"]], on="TERRITORIO", how="left")
    d["PCT_COMP"] = m.percentual(d["QT_COMPARECIMENTO"], d["QT_APTOS"])
    cmap, cor_outros = comum.mapa_cores(ctx)

    col_mapa, col_lado = st.columns([2.1, 1], gap="medium")
    with col_mapa, st.container(border=True):
        moldura = cmapa.moldura(ctx, ap, altura=ALTURA_MAPA)
        escala = cores.escala_do_candidato(cmap.get(sq, cor_outros), ctx.fundo)
        zmax = float(d["Z"].max()) if d["Z"].notna().any() else 1.0
        fig = mapas.mapa_continuo(moldura, d, ctx.fundo, cmapa.revisao(ctx, "ter"), escala, 0, zmax,
                                  "% válidos" if metrica == "pct" else "votos",
                                  hover_ausentes=modos.ausentes_sem_votos(ap, nivel_uf),
                                  rotulo_ausente="Sem dado eleitoral")
        visuais.legenda([(escala[0][1], "menor"), (escala[-1][1], f"maior · {rot[sq]}"),
                         (cores.SEM_DADO[ctx.fundo], "Sem dado")])
        st.caption(f"{_rotulo_nivel(ctx)} · " + ("% sobre os válidos do cargo em cada território."
                   if metrica == "pct" else "⚠ Votos absolutos destacam territórios com mais eleitores."))
        fig = mapas.destacar(fig, moldura, comum.destaque(ctx), ctx.fundo)
        cmapa.exibir(fig, ctx, "ter")
        cmapa.barra_de_acoes(ctx, "ter")

    with col_lado, st.container(border=True):
        _extremos(d, int(minimo), int(n), metrica, ctx)

    _tabela(ctx, d, rot[sq], metrica)
    visuais.contexto_fonte()


def _rotulo_nivel(ctx) -> str:
    s = ctx.sel
    base = {NIVEL_REGIAO: "Regiões", NIVEL_UF: "UFs", NIVEL_MUNICIPIO: f"Municípios de {s.uf}",
            NIVEL_MUNICIPIO_BR: "Municípios do Brasil"}[s.nivel]
    return base + (f" da região {s.regiao}" if s.regiao and s.nivel != NIVEL_REGIAO else "")


def _extremos(d: pd.DataFrame, minimo: int, n: int, metrica: str, ctx) -> None:
    col = "PCT" if metrica == "pct" else "VOTOS"
    base = d[d["QT_TOTAL_VOTOS_VALIDOS"] > 0]
    excluidos = int((base["QT_APTOS"] < minimo).sum())
    base = base[base["QT_APTOS"] >= minimo]
    rot_col = "% válidos" if metrica == "pct" else "Votos"
    cfg = {rot_col: st.column_config.NumberColumn(format="%.1f%%" if metrica == "pct" else "localized"),
           "Aptos": st.column_config.NumberColumn(format="localized")}

    def tabela(df):
        out = pd.DataFrame({"Território": df["NOME"] + (" (" + df["SG_UF"] + ")" if eh_municipal(ctx.sel.nivel) else ""),
                            rot_col: df[col], "Aptos": df["QT_APTOS"]})
        # Altura exata (35 px por linha + cabeçalho): sem linha vazia sobrando nem rolagem.
        st.dataframe(out, hide_index=True, use_container_width=True, column_config=cfg,
                     height=35 * (len(out) + 1) + 3)

    st.markdown(f"### Maiores {rot_col.lower()}")
    tabela(base.nlargest(n, col))
    st.markdown(f"### Menores {rot_col.lower()}")
    tabela(base.nsmallest(n, col))
    nota = f"{len(base)} territórios considerados"
    if minimo:
        nota += f"; {excluidos} com menos de {f.inteiro(minimo)} aptos ficaram de fora"
    st.caption(nota + ". Territórios sem votos válidos não entram nos rankings.")


def _tabela(ctx, d: pd.DataFrame, nome_cand: str, metrica: str) -> None:
    municipal = eh_municipal(ctx.sel.nivel)
    t = pd.DataFrame({
        "TERRITORIO": d["TERRITORIO"], "Território": d["NOME"], "UF": d["SG_UF"], "Região": d["NM_REGIAO"],
        "Aptos": d["QT_APTOS"], "Comparecimento %": d["PCT_COMP"], "Válidos": d["QT_TOTAL_VOTOS_VALIDOS"],
        f"Votos · {nome_cand}": d["VOTOS"], "% válidos": d["PCT"],
    }).sort_values("% válidos", ascending=False, na_position="last")
    if not municipal:
        t = t.drop(columns=["UF"])
    if ctx.sel.nivel == NIVEL_REGIAO:
        t = t.drop(columns=["Região"])
    st.markdown(f"### Tabela vinculada ao mapa · {len(t)} territórios")
    st.caption("Clique numa linha para selecionar o território no mapa (nos níveis municipais) ou abrir o nível "
               "seguinte (região → UFs → municípios). % sobre os válidos do cargo no território.")
    ev = st.dataframe(
        t.drop(columns=["TERRITORIO"]), hide_index=True, use_container_width=True, height=300,
        # Chave inclui a seleção atual: após tratar um clique, a tabela volta sem linha marcada
        # (evita que uma seleção antiga desfaça um clique posterior no mapa).
        on_select="rerun", selection_mode="single-row",
        key=f"ter_tab_{ctx.sel.nivel}_{ctx.sel.regiao}_{ctx.sel.uf}_{ctx.sel.municipio}",
        column_config={"Aptos": st.column_config.NumberColumn(format="localized"),
                       "Válidos": st.column_config.NumberColumn(format="localized"),
                       f"Votos · {nome_cand}": st.column_config.NumberColumn(format="localized"),
                       "Comparecimento %": st.column_config.NumberColumn(format="%.1f%%"),
                       "% válidos": st.column_config.NumberColumn(format="%.2f%%")})
    visuais.botao_csv(t.drop(columns=["TERRITORIO"]), f"analise_territorial_{ctx.sel.cargo}_{ctx.sel.turno}t")
    linhas = (ev or {}).get("selection", {}).get("rows", []) if ev else []
    if linhas:
        alvo = t.iloc[linhas[0]]
        _selecionar(ctx, alvo["TERRITORIO"], alvo.get("UF"))


def _selecionar(ctx, territorio: str, uf: str | None) -> None:
    s = ctx.sel
    if s.nivel == NIVEL_REGIAO:
        agendar(f_nivel=NIVEL_UF, f_regiao=territorio, f_uf=None)
    elif s.nivel == NIVEL_UF:
        agendar(f_nivel=NIVEL_MUNICIPIO, f_uf=territorio)
    elif territorio != s.municipio and uf:
        agendar(f_uf=uf, **{f"f_municipio_{uf}": territorio})
