"""Figuras de mapa (Plotly Choroplethmap / MapLibre, sem chave de API).

Camadas, de baixo para cima:
1. territórios sem dado / não aplicáveis (cinzas próprios, distintos do neutro);
2. dados (categórico por líder ou escala contínua);
3. contorno das UFs (mais forte que as bordas municipais), sem hover.

Todo hover é texto pronto (coluna HOVER), montado em `textos_hover`, para que
o conteúdo seja testável e não dependa só da cor.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from src.visualizacoes import cores
from src.visualizacoes.enquadramento import bbox_geojson, enquadrar

# Estilos vetoriais da CARTO embutidos no Plotly (gratuitos, sem chave). Não usar as
# variantes "*-nolabels" nem tiles raster da CARTO pedidos direto: no navegador ambos
# vieram com marca d'água "API KEY REQUIRED" (testado em 28/10/2026).
# Mapa de fundo completo (países, mar, cidades). Os polígonos são desenhados ACIMA de
# todas as camadas do fundo (below=""), então os rótulos do fundo ficam ocultos sob as
# cores — sem nomes "apagados" sobre o preenchimento — e continuam visíveis fora delas.
# Os nomes dos territórios do recorte vêm de Moldura.rotulos, por cima de tudo.
ESTILOS = {"claro": "carto-positron", "escuro": "carto-darkmatter"}
# Cores sólidas (translucidez desbotava as cores e deixava os nomes de fundo fracos);
# os nomes dos territórios do recorte são desenhados por cima (Moldura.rotulos).
OPACIDADE = 1.0
TEXTO_ROTULO = {"claro": "#14213d", "escuro": "#ffffff"}
# Bordas: municipais brancas e nítidas sobre preenchimentos saturados; estaduais marinho, grossas.
LINHA_MUN = {"claro": "rgba(255,255,255,0.95)", "escuro": "rgba(15,15,15,0.9)"}
LARGURA_MUN = 0.8
LINHA_UF = {"claro": "#14213d", "escuro": "#f0efec"}
LARGURA_UF = 2.0


@dataclass
class Moldura:
    """Geometria e enquadramento de um mapa."""
    geojson: dict
    idkey: str                 # ex.: "properties.CD_MUN"
    ids: list[str]             # todos os territórios desenhados
    contorno: dict | None      # GeoJSON de UFs para o traço de borda
    contorno_idkey: str = "properties.SIGLA_UF"
    altura: int = 620
    # Largura conservadora da coluna do mapa (3/5 da área útil em telas comuns);
    # errar para menos só deixa margem extra, errar para mais corta o território.
    # O Streamlit não informa a largura real; 600 px enquadra bem de ~1280 px de tela em
    # diante sem cortar (em telas muito largas sobra margem; use o zoom do mapa).
    largura_ref: int = 600
    # URLs das malhas servidas como estáticos. Se informadas, as figuras levam só a
    # URL (o navegador baixa e guarda em cache); o dict continua usado no servidor
    # para ids e enquadramento.
    url: str | None = None
    contorno_url: str | None = None
    # Espessura das bordas entre territórios: fina no Brasil por município (5.571 polígonos),
    # para as bordas não dominarem a cor; 0,8 px nos níveis com menos polígonos.
    largura_linha: float = LARGURA_MUN
    cor_linha: str | None = None   # None = LINHA_MUN do modo
    contorno_nome: str = "UF"
    # Linhas de referência finas e translúcidas por baixo do contorno forte
    # (ex.: divisas estaduais dentro do mapa por região).
    linhas_internas: dict | None = None
    linhas_internas_url: str | None = None
    linhas_internas_idkey: str = "properties.SIGLA_UF"
    # Nomes desenhados por cima dos polígonos: (lon, lat, texto).
    rotulos: list[tuple[float, float, str]] | None = None

    @property
    def fonte(self):
        return self.url or self.geojson

    @property
    def fonte_contorno(self):
        return self.contorno_url or self.contorno


def _camada_constante(m: Moldura, ids, cor, hover, linha, nome) -> go.Choroplethmap:
    return go.Choroplethmap(
        geojson=m.fonte, featureidkey=m.idkey, locations=list(ids), z=[0] * len(ids),
        colorscale=[[0, cor], [1, cor]], showscale=False, name=nome,
        marker_line_width=m.largura_linha, marker_line_color=linha,
        text=list(hover), hovertemplate="%{text}<extra></extra>",
    )


def _linhas(geojson, fonte, idkey: str, largura: float, cor: str, nome: str) -> go.Choroplethmap:
    ids = [f["properties"][idkey.split(".")[-1]] for f in geojson["features"]]
    return go.Choroplethmap(
        geojson=fonte, featureidkey=idkey, locations=ids, z=[0] * len(ids),
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
        marker_line_width=largura, marker_line_color=cor, hoverinfo="skip", name=nome,
    )


def _contorno(m: Moldura, modo: str) -> go.Choroplethmap | None:
    if not m.contorno:
        return None
    return _linhas(m.contorno, m.fonte_contorno, m.contorno_idkey, LARGURA_UF, LINHA_UF[modo], m.contorno_nome)


def _bordas(fig: go.Figure, m: Moldura, modo: str) -> None:
    """Linhas de referência (finas, translúcidas) e, por cima, o contorno forte."""
    if m.linhas_internas:
        cor = "rgba(20,33,61,0.28)" if modo == "claro" else "rgba(240,240,240,0.25)"
        fig.add_trace(_linhas(m.linhas_internas, m.linhas_internas_url or m.linhas_internas,
                              m.linhas_internas_idkey, 0.6, cor, "divisas internas"))
    if (c := _contorno(m, modo)) is not None:
        fig.add_trace(c)
    if m.rotulos:
        lon, lat, txt = zip(*m.rotulos)
        fig.add_trace(go.Scattermap(
            lon=lon, lat=lat, text=txt, mode="text", hoverinfo="skip", name="rótulos",
            textfont=dict(size=11, color=TEXTO_ROTULO[modo], weight="bold")))
    # below="": polígonos acima de todas as camadas do fundo (inclusive rótulos).
    fig.update_traces(marker_opacity=OPACIDADE, below="", selector=dict(type="choroplethmap"))


def _layout(fig: go.Figure, m: Moldura, modo: str, revisao: str) -> go.Figure:
    centro, zoom = enquadrar(bbox_geojson(m.geojson), m.largura_ref, m.altura)
    fig.update_layout(
        map_style=ESTILOS[modo], map_center=centro, map_zoom=zoom,
        margin=dict(l=0, r=0, t=0, b=0), height=m.altura, showlegend=False,
        clickmode="event+select", dragmode="pan",
        uirevision=revisao,  # muda com recorte ou "restaurar enquadramento"
        hoverlabel=dict(bgcolor="white" if modo == "claro" else "#1a1a19",
                        font_color="#0b0b0b" if modo == "claro" else "#f0efec", align="left"),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _sem_dados(fig, m, modo, ids_com_dado, hover_ausentes: dict[str, str], rotulo_ausente: str,
               nao_aplicaveis: dict[str, str] | None = None):
    """Camadas de ausência, distintas entre si e do ponto neutro das escalas:
    - não aplicável (disputa inexistente no recorte, ex.: UF sem 2º turno): cinza sólido;
    - sem dado (sem votos válidos / sem eleitorado / indisponível): branco vazado.
    """
    na = nao_aplicaveis or {}
    com_dado = set(ids_com_dado)  # construído uma vez (era recriado por território: O(n²))
    if na:
        ids_na = [i for i in m.ids if i in na and i not in com_dado]
        if ids_na:
            fig.add_trace(_camada_constante(m, ids_na, cores.NAO_APLICAVEL[modo], [na[i] for i in ids_na],
                                            "rgba(120,120,120,0.7)", "não aplicável"))
    faltam = [i for i in m.ids if i not in com_dado and i not in na]
    if faltam:
        hov = [hover_ausentes.get(i, rotulo_ausente) for i in faltam]
        fig.add_trace(_camada_constante(m, faltam, cores.SEM_DADO[modo], hov, "rgba(120,120,120,0.7)", "sem dado"))


def mapa_categorico(m: Moldura, dados: pd.DataFrame, modo: str, revisao: str,
                    hover_ausentes: dict[str, str] | None = None,
                    rotulo_ausente: str = "Sem dado",
                    nao_aplicaveis: dict[str, str] | None = None) -> go.Figure:
    """`dados`: TERRITORIO, COR, HOVER e, opcionalmente, INTENSIDADE (0–1).

    Uma camada por cor. Com INTENSIDADE, a cor vai do tom claro (misturado ao
    neutro) ao tom pleno, numa escala comum a todas as categorias.
    """
    fig = go.Figure()
    _sem_dados(fig, m, modo, dados["TERRITORIO"], hover_ausentes or {}, rotulo_ausente, nao_aplicaveis)
    usa_intensidade = "INTENSIDADE" in dados and dados["INTENSIDADE"].notna().any()
    for cor, g in dados.groupby("COR", sort=False):
        if usa_intensidade:
            escala = [[0, cores.misturar(cor, cores.NEUTRO[modo], 0.75)], [1, cor]]
            z = g["INTENSIDADE"].fillna(0).clip(0, 1)
        else:
            escala, z = [[0, cor], [1, cor]], [0] * len(g)
        fig.add_trace(go.Choroplethmap(
            geojson=m.fonte, featureidkey=m.idkey, locations=g["TERRITORIO"], z=z,
            zmin=0, zmax=1, colorscale=escala, showscale=False,
            marker_line_width=m.largura_linha, marker_line_color=m.cor_linha or LINHA_MUN[modo],
            text=g["HOVER"], hovertemplate="%{text}<extra></extra>",
        ))
    _bordas(fig, m, modo)
    return _layout(fig, m, modo, revisao)


def mapa_continuo(m: Moldura, dados: pd.DataFrame, modo: str, revisao: str, escala: list,
                  zmin: float, zmax: float, titulo_barra: str, zmid: float | None = None,
                  ticks: tuple[list, list] | None = None,
                  hover_ausentes: dict[str, str] | None = None, rotulo_ausente: str = "Sem dado",
                  nao_aplicaveis: dict[str, str] | None = None) -> go.Figure:
    """`dados`: TERRITORIO, Z (NaN = sem valor calculável), HOVER."""
    fig = go.Figure()
    com_valor = dados[dados["Z"].notna()]
    sem_valor = dados[dados["Z"].isna()]
    ausentes = dict(hover_ausentes or {})
    ausentes.update(dict(zip(sem_valor["TERRITORIO"], sem_valor["HOVER"])))
    _sem_dados(fig, m, modo, com_valor["TERRITORIO"], ausentes, rotulo_ausente, nao_aplicaveis)
    barra = dict(title=dict(text=titulo_barra, side="right"), thickness=12, len=0.8,
                 outlinewidth=0, tickfont=dict(color="#52514e" if modo == "claro" else "#c3c2b7"))
    if ticks:
        barra.update(tickvals=ticks[0], ticktext=ticks[1])
    fig.add_trace(go.Choroplethmap(
        geojson=m.fonte, featureidkey=m.idkey, locations=com_valor["TERRITORIO"], z=com_valor["Z"],
        zmin=zmin, zmax=zmax, zmid=zmid, colorscale=escala, colorbar=barra,
        marker_line_width=m.largura_linha, marker_line_color=m.cor_linha or LINHA_MUN[modo],
        text=com_valor["HOVER"], hovertemplate="%{text}<extra></extra>",
    ))
    _bordas(fig, m, modo)
    return _layout(fig, m, modo, revisao)


def mapa_mundi(dados: pd.DataFrame, modo: str, altura: int = 440) -> go.Figure:
    """Mapa-múndi por país (ISO-3), categórico: `dados` com TERRITORIO (ISO-3), COR, HOVER.

    Usa as fronteiras embutidas no Plotly (Natural Earth) — sem download nem chave.
    O Brasil aparece em cinza-escuro como referência (seus votos não são "exterior").
    """
    fig = go.Figure()
    for cor, g in dados.groupby("COR", sort=False):
        fig.add_trace(go.Choropleth(
            locations=g["TERRITORIO"], z=[0] * len(g), locationmode="ISO-3", colorscale=[[0, cor], [1, cor]],
            showscale=False, marker_line_color="white" if modo == "claro" else "#1a1a19", marker_line_width=0.6,
            text=g["HOVER"], hovertemplate="%{text}<extra></extra>"))
    fig.add_trace(go.Choropleth(
        locations=["BRA"], z=[0], locationmode="ISO-3", colorscale=[[0, "#14213d"], [1, "#14213d"]],
        showscale=False, hovertemplate="Brasil (votos no território nacional não entram aqui)<extra></extra>"))
    terra = "#e6e4dd" if modo == "claro" else "#2c2c2a"
    fig.update_geos(projection_type="natural earth", showcountries=True, countrycolor="#ffffff" if modo == "claro" else "#1a1a19",
                    showland=True, landcolor=terra, showocean=True, oceancolor="#eef1f5" if modo == "claro" else "#0d0d0d",
                    showlakes=False, showframe=False, lataxis_range=[-58, 85])
    fig.update_layout(height=altura, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, dragmode="pan",
                      hoverlabel=dict(bgcolor="white" if modo == "claro" else "#1a1a19", align="left"))
    return fig


def destacar(fig: go.Figure, m: Moldura, territorio: str | None, modo: str) -> go.Figure:
    """Contorno grosso no território selecionado (seleção visível sem depender da cor)."""
    if territorio and territorio in set(m.ids):
        fig.add_trace(go.Choroplethmap(
            geojson=m.fonte, featureidkey=m.idkey, locations=[territorio], z=[0],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
            marker_line_width=3.5, marker_line_color="#0b0b0b" if modo == "claro" else "#ffffff",
            hoverinfo="skip", name="selecionado", below=""))
    return fig


def territorio_selecionado(evento) -> str | None:
    """Extrai o território clicado do evento de seleção do st.plotly_chart."""
    try:
        pontos = evento["selection"]["points"]
    except (KeyError, TypeError):
        return None
    for p in pontos:
        if p.get("location"):
            return str(p["location"])
    return None
