"""Blocos visuais do dashboard: cabeçalho compacto, faixa de KPIs, legenda, contexto."""
from __future__ import annotations

import html

import streamlit as st

from src.aquisicao.fontes import EDICAO_MALHA
from src.componentes import dados_app as dados
from src.componentes.estado import filtros_ativos
from src.visualizacoes import formatos as f

CSS = """
<style>
/* Layout de painel: menos respiro vertical, largura total */
.block-container {padding-top: 2.6rem; padding-bottom: 0.6rem; padding-left: 1.4rem; padding-right: 1.4rem;
                  max-width: 100%;}
[data-testid="stSidebar"] .block-container, section[data-testid="stSidebar"] > div {padding-top: 1rem;}
h1 {font-size: 1.35rem !important; padding: 0 !important; margin: 0 !important;}
h2, h3 {font-size: 1.0rem !important; padding: 0.1rem 0 0.2rem !important; margin: 0 !important;}
[data-testid="stVerticalBlock"] {gap: 0.45rem;}
[data-testid="stCaptionContainer"] p {font-size: 0.75rem;}
div[data-testid="stRadio"] > label, div[data-testid="stSelectbox"] > label {font-size: 0.75rem;}

/* ---- Identidade: marinho #14213d / #1d3557, acento dourado #e0b84c ---- */
.cab {display:flex; align-items:center; gap:14px; flex-wrap:wrap; background:#14213d; color:#fff;
      padding:10px 16px; border-radius:10px; border-bottom:3px solid #e0b84c;
      box-shadow:0 2px 6px rgba(20,33,61,.18)}
.cab .t {font-size:1.2rem; font-weight:700; letter-spacing:.01em}
.cab .s {font-size:0.85rem; color:#c9d3e0}
.chip {display:inline-block; padding:1px 9px; margin:0 4px 0 0; border-radius:10px; font-size:0.72rem;
       color:#e8edf3; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.22)}

.kpis {display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin:4px 0 6px}
.kpi {background:#ffffff; border-radius:10px; padding:9px 14px 8px; border-top:4px solid #1d3557;
      box-shadow:0 1px 3px rgba(20,33,61,.10), 0 1px 1px rgba(20,33,61,.06)}
.kpi .r {font-size:0.7rem; color:#4a5a73; text-transform:uppercase; letter-spacing:.06em; font-weight:600}
.kpi .v {font-size:1.45rem; font-weight:700; color:#14213d; white-space:nowrap; line-height:1.25}
.kpi .d {font-size:0.72rem; color:#7a8699; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}

/* Painéis (st.container(border=True)) como cartões brancos */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
    background:#ffffff; border-color:rgba(20,33,61,.08) !important;
    box-shadow:0 1px 3px rgba(20,33,61,.10), 0 1px 1px rgba(20,33,61,.06)}
[data-testid="stMain"] h3 {color:#1d3557; text-transform:uppercase; letter-spacing:.05em; font-size:0.85rem !important}
/* Abas com acento */
[data-baseweb="tab-highlight"] {background-color:#e0b84c !important}
[data-baseweb="tab"] p {font-weight:600}
/* Marca na barra lateral */
.marca {font-weight:800; font-size:1.05rem; color:#ffffff; letter-spacing:.02em; line-height:1.15;
        padding:2px 0 8px; border-bottom:2px solid #e0b84c; margin-bottom:6px}
.marca span {display:block; font-weight:500; font-size:0.72rem; color:#c9d3e0; letter-spacing:.06em;
             text-transform:uppercase}

.leg {display:flex; flex-wrap:wrap; gap:4px 14px; align-items:center; font-size:0.78rem; margin:0}
.leg span.sw {display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:5px;
              vertical-align:-1px; border:1px solid rgba(128,128,128,.45)}
.ctx {font-size:0.7rem; color:#898781; line-height:1.3}
.eleito {font-size:0.82rem; padding:6px 10px; border-radius:6px; background:#fbf6e6;
         border-left:4px solid #e0b84c; color:#14213d}
</style>
"""


def botao_csv(df, nome: str, rotulo: str = "⬇ Baixar CSV desta tabela") -> None:
    """Exporta a tabela exibida (recorte e filtros atuais): `;` e vírgula decimal (Excel pt-BR)."""
    import re
    arquivo = re.sub(r"[^A-Za-z0-9_]+", "_", nome).strip("_").lower() + ".csv"
    st.download_button(rotulo, df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=arquivo, mime="text/csv", key=f"csv_{arquivo}")


def altura_tabela(linhas: int, maximo: int = 400) -> int:
    """Altura exata do st.dataframe (35 px por linha + cabeçalho), limitada a `maximo`."""
    return min(35 * (max(linhas, 1) + 1) + 3, maximo)


def estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def cabecalho(ctx, titulo: str, recorte: str) -> None:
    """Uma linha: título do painel, recorte e filtros ativos."""
    chips = "".join(f'<span class="chip">{html.escape(i)}</span>' for i in filtros_ativos(ctx.sel, ctx.rotulo_municipio))
    st.markdown(f'<div class="cab"><span class="t">{html.escape(titulo)}</span>'
                f'<span class="s">{html.escape(recorte)}</span><span>{chips}</span></div>', unsafe_allow_html=True)


def kpis(itens: list[tuple[str, str, str, str]]) -> None:
    """Faixa de indicadores. itens: (rótulo, valor, detalhe visível, dica com fórmula)."""
    corpo = "".join(
        f'<div class="kpi" title="{html.escape(dica)}"><div class="r">{html.escape(r)}</div>'
        f'<div class="v">{html.escape(v)}</div><div class="d">{html.escape(d)}</div></div>'
        for r, v, d, dica in itens)
    st.markdown(f'<div class="kpis">{corpo}</div>', unsafe_allow_html=True)


def kpis_participacao(t: dict, rotulo_escopo: str) -> list[tuple[str, str, str, str]]:
    from src.metricas.indicadores import percentual as p
    return [
        ("Eleitorado apto", f.compacto(t["aptos"]), f.inteiro(t["aptos"]), f"Eleitores aptos do cargo — {rotulo_escopo}"),
        ("Comparecimento", f.pct(p(t["comparecimento"], t["aptos"])), f.inteiro(t["comparecimento"]),
         f"{f.inteiro(t['comparecimento'])} ÷ {f.inteiro(t['aptos'])} aptos"),
        ("Abstenção", f.pct(p(t["abstencoes"], t["aptos"])), f.inteiro(t["abstencoes"]),
         f"{f.inteiro(t['abstencoes'])} ÷ {f.inteiro(t['aptos'])} aptos"),
        ("Votos válidos", f.compacto(t["validos"]), f"{f.pct(p(t['validos'], t['votos']))} dos votos",
         f"{f.inteiro(t['validos'])} ÷ {f.inteiro(t['votos'])} votos do cargo"),
        ("Brancos", f.pct(p(t["brancos"], t["votos"])), f.inteiro(t["brancos"]),
         f"{f.inteiro(t['brancos'])} ÷ {f.inteiro(t['votos'])} votos do cargo"),
        ("Nulos", f.pct(p(t["nulos"], t["votos"])), f.inteiro(t["nulos"]),
         f"{f.inteiro(t['nulos'])} ÷ {f.inteiro(t['votos'])} votos do cargo (inclui nulos técnicos)"),
    ]


def contexto_fonte(chaves=("detalhe_munzona", "votacao_candidato_munzona"), ultima_totalizacao=None) -> None:
    """Rodapé: fonte, geração na fonte, download e malha."""
    m = dados.metadados()
    gerado = m.get(chaves[0], {}).get("dt_geracao_fonte", "—")
    baixado = str(m.get(chaves[0], {}).get("baixado_em", "—"))[:16].replace("T", " ")
    tot = f" · última totalização {ultima_totalizacao:%d/%m/%Y %H:%M}" if ultima_totalizacao is not None else ""
    st.markdown(f'<div class="ctx">Fonte: TSE (dados abertos) · arquivos gerados pela fonte em {gerado}'
                f" · baixados pelo painel em {baixado}{tot} · geometrias {EDICAO_MALHA} · "
                "dados estáticos, sem tempo real · detalhes em Dados e metodologia</div>", unsafe_allow_html=True)


def legenda(itens: list[tuple[str, str]]) -> None:
    """Legenda sempre visível, com texto (nunca só cor)."""
    corpo = "".join(f'<span><span class="sw" style="background:{c}"></span>{html.escape(t)}</span>' for c, t in itens)
    st.markdown(f'<div class="leg">{corpo}</div>', unsafe_allow_html=True)


def selo_eleito(texto: str) -> None:
    st.markdown(f'<div class="eleito">★ {html.escape(texto)}</div>', unsafe_allow_html=True)


def marca() -> None:
    st.sidebar.markdown('<div class="marca">Eleições 2026<span>Painel de resultados · TSE</span></div>',
                        unsafe_allow_html=True)
