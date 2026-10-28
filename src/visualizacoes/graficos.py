"""Gráficos de barras (Plotly), com marcas finas, rótulo direto e sem eixo duplo."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.visualizacoes import formatos as f

TINTA = {"claro": ("#0b0b0b", "#52514e", "#e1e0d9"), "escuro": ("#f0efec", "#c3c2b7", "#2c2c2a")}


def _layout(fig, modo, altura):
    prim, sec, grade = TINTA[modo]
    fig.update_layout(
        height=altura, margin=dict(l=8, r=60, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color=sec), showlegend=False, bargap=0.35,
        hoverlabel=dict(align="left"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=grade, zeroline=True, zerolinecolor=grade, tickfont=dict(color=sec))
    fig.update_yaxes(showgrid=False, tickfont=dict(color=prim))
    return fig


def ranking(cands: pd.DataFrame, mapa_cores: dict[str, str], cor_outros: str, modo: str,
            metrica: str = "PCT_VALIDOS") -> go.Figure:
    """Barras horizontais por candidato; rótulo com valor; situação oficial no hover."""
    d = cands.sort_values("VOTOS", ascending=True)
    rot = d["NM_URNA_CANDIDATO"] + " (" + d["SG_PARTIDO"] + ")"
    txt = [f"{f.pct(p)} · {f.compacto(v)}" for p, v in zip(d["PCT_VALIDOS"], d["VOTOS"])]
    hov = [f"<b>{r}</b><br>Votos: {f.inteiro(v)}<br>% dos válidos: {f.pct(p)}<br>Situação oficial no turno: {s or '—'}"
           for r, v, p, s in zip(rot, d["VOTOS"], d["PCT_VALIDOS"], d["SITUACAO_TURNO"])]
    fig = go.Figure(go.Bar(
        x=d[metrica], y=rot, orientation="h", text=txt, textposition="outside", cliponaxis=False,
        marker_color=[mapa_cores.get(s, cor_outros) for s in d["SQ_CANDIDATO"]],
        marker_line_width=0, hovertext=hov, hoverinfo="text",
    ))
    fig = _layout(fig, modo, max(160, 30 * len(d) + 20))
    # Rótulo direto em cada barra: eixo x dispensável; margem para o texto externo.
    # Folga para o rótulo externo "xx,x% · y mi" caber na coluna estreita.
    fig.update_xaxes(visible=False, range=[0, float(d[metrica].max()) * 2.4 if len(d) else 1])
    fig.update_traces(textfont_size=11)
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4))
    return fig


def barras_partido(df: pd.DataFrame, rotulo: str, valor: str, modo: str, cor: str) -> go.Figure:
    d = df.sort_values(valor, ascending=True)
    fig = go.Figure(go.Bar(x=d[valor], y=d[rotulo], orientation="h", marker_color=cor, marker_line_width=0,
                           text=[f.pct(v) for v in d[valor]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
    fig = _layout(fig, modo, max(140, 28 * len(d) + 20))
    fig.update_xaxes(visible=False, range=[0, float(d[valor].max()) * 1.3 if len(d) else 1])
    return fig


def barras_contagem(df: pd.DataFrame, rotulo: str, valor: str, mapa_cores: dict[str, str], cor_outros: str,
                    modo: str) -> go.Figure:
    """Barras horizontais de contagem (ex.: eleitos por partido), na cor do partido."""
    d = df.sort_values(valor, ascending=True)
    fig = go.Figure(go.Bar(x=d[valor], y=d[rotulo], orientation="h", marker_line_width=0,
                           marker_color=[mapa_cores.get(p, cor_outros) for p in d[rotulo]],
                           text=[str(int(v)) for v in d[valor]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x}<extra></extra>"))
    fig = _layout(fig, modo, max(140, 26 * len(d) + 20))
    fig.update_xaxes(visible=False, range=[0, float(d[valor].max()) * 1.25 if len(d) else 1])
    return fig


def barras_par(rotulos: list[str], valores: list[float], cores_ab: list[str], modo: str,
               sufixo: str = "", formato=f.inteiro) -> go.Figure:
    """Duas barras lado a lado (A e B) com rótulo direto."""
    fig = go.Figure(go.Bar(x=valores, y=rotulos, orientation="h", marker_color=cores_ab, marker_line_width=0,
                           text=[formato(v) for v in valores], textposition="outside", cliponaxis=False,
                           hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed")
    fig = _layout(fig, modo, 120)
    fig.update_xaxes(visible=False, range=[0, max(valores) * 1.35 if valores else 1])
    return fig
