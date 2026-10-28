"""Prova técnica da biblioteca de mapas (Etapa 1).

Valida, com dados oficiais reais (abstenção para Presidente, por município,
somando zonas), os requisitos: renderização, hover, seleção de território,
integração com filtro e desempenho com a malha municipal nacional.

Executar:
    streamlit run prototipos/prova_mapa.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import duckdb  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import DIR_GEO, DIR_PROCESSED  # noqa: E402
from src.tratamento.chaves import SQL_CD_MUNICIPIO  # noqa: E402
from src.visualizacoes.enquadramento import bbox_geojson, enquadrar  # noqa: E402

st.set_page_config(page_title="Prova de mapa", layout="wide")


@st.cache_data(show_spinner="Carregando malha…")
def carregar_geojson(caminho: str) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


@st.cache_data(show_spinner="Consultando DuckDB…")
def abstencao_municipal(turno: str) -> "pd.DataFrame":
    con = duckdb.connect()
    bruto = str(DIR_PROCESSED / "bruto" / "detalhe_munzona.parquet").replace("\\", "/")
    con.sql(f"CREATE VIEW d AS SELECT {SQL_CD_MUNICIPIO} CD_MUN_TSE, * FROM '{bruto}'")
    con.register("dim", con.read_parquet(str(DIR_PROCESSED / "dim_municipio.parquet")))
    # Numeradores e denominadores somados por município ANTES do percentual.
    return con.sql(f"""
        SELECT dim.CD_MUNICIPIO_IBGE, d.SG_UF, any_value(d.NM_MUNICIPIO) NM_MUNICIPIO,
               sum(CAST(QT_APTOS AS BIGINT)) aptos,
               sum(CAST(QT_ABSTENCOES AS BIGINT)) abstencoes,
               100.0 * sum(CAST(QT_ABSTENCOES AS BIGINT)) / nullif(sum(CAST(QT_APTOS AS BIGINT)), 0) pct
        FROM d JOIN dim ON d.CD_MUN_TSE = dim.CD_MUNICIPIO AND d.SG_UF = dim.SG_UF
        WHERE d.DS_CARGO = 'Presidente' AND d.NR_TURNO = '{turno}'
          AND dim.ESTADO_JUNCAO = 'associado'
        GROUP BY ALL
    """).df()


st.title("Prova técnica — mapa municipal (Plotly Choroplethmap)")
st.caption("Dado real: abstenção (%) = abstenções ÷ eleitorado apto, Presidente, somando zonas do município. "
           "Fonte: TSE, detalhe da apuração por município e zona.")

c1, c2, c3 = st.columns(3)
turno = c1.radio("Turno", ["1", "2"], horizontal=True)
escopo = c2.selectbox("Escopo", ["Brasil (malha nacional)"] +
                      sorted(p.stem.split("_")[1] for p in (DIR_GEO / "uf").glob("municipios_*.geojson")))
estilo = c3.radio("Fundo", ["carto-positron", "carto-darkmatter", "white-bg"], horizontal=True)

t0 = time.perf_counter()
gj_ufs = carregar_geojson(str(DIR_GEO / "ufs.geojson"))
if escopo.startswith("Brasil"):
    gj = carregar_geojson(str(DIR_GEO / "municipios_brasil.geojson"))
else:
    gj = carregar_geojson(str(DIR_GEO / "uf" / f"municipios_{escopo}.geojson"))
df = abstencao_municipal(turno)
if not escopo.startswith("Brasil"):
    df = df[df["SG_UF"] == escopo]
t_dados = time.perf_counter() - t0

ids_gj = [f["properties"]["CD_MUN"] for f in gj["features"]]
sem_dado = sorted(set(ids_gj) - set(df["CD_MUNICIPIO_IBGE"]))
fig = go.Figure()
# Polígonos sem dado (ex.: lagoas) em cinza hachurado-claro, distinto da escala.
fig.add_trace(go.Choroplethmap(
    geojson=gj, featureidkey="properties.CD_MUN", locations=sem_dado, z=[0] * len(sem_dado),
    colorscale=[[0, "#d9d9d9"], [1, "#d9d9d9"]], showscale=False,
    marker_line_width=0.2, marker_line_color="rgba(80,80,80,0.5)",
    hovertemplate="%{location}<br>Sem dado eleitoral (área sem eleitorado)<extra></extra>",
))
fig.add_trace(go.Choroplethmap(
    geojson=gj, featureidkey="properties.CD_MUN",
    locations=df["CD_MUNICIPIO_IBGE"], z=df["pct"],
    colorscale="Blues", marker_line_width=0.2, marker_line_color="rgba(80,80,80,0.5)",
    colorbar_title="Abstenção (%)",
    customdata=df[["NM_MUNICIPIO", "SG_UF", "abstencoes", "aptos"]],
    hovertemplate="<b>%{customdata[0]}</b> — %{customdata[1]}<br>"
                  "Abstenção: %{z:.1f}%<br>%{customdata[2]:,} de %{customdata[3]:,} aptos<extra></extra>",
))
# Bordas estaduais por cima, mais visíveis, sem preenchimento nem hover.
ufs_ids = [f["properties"]["SIGLA_UF"] for f in gj_ufs["features"]]
fig.add_trace(go.Choroplethmap(
    geojson=gj_ufs, featureidkey="properties.SIGLA_UF", locations=ufs_ids, z=[0] * len(ufs_ids),
    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
    marker_line_width=1.2, marker_line_color="rgba(40,40,40,0.9)", hoverinfo="skip",
))
ALTURA = 650
if "reset" not in st.session_state:
    st.session_state.reset = 0
if st.button("Restaurar enquadramento"):
    st.session_state.reset += 1
centro, zoom = enquadrar(bbox_geojson(gj), largura_px=900, altura_px=ALTURA)
fig.update_layout(map_style=estilo, map_zoom=zoom, map_center=centro,
                  margin=dict(l=0, r=0, t=0, b=0), height=ALTURA,
                  # uirevision muda com escopo ou reset: o Plotly descarta o zoom/pan do usuário.
                  uirevision=f"{escopo}-{st.session_state.reset}", clickmode="event+select")
t1 = time.perf_counter()
evento = st.plotly_chart(fig, on_select="rerun", selection_mode=("points", "box", "lasso"),
                         key=f"mapa_{escopo}", use_container_width=True)
t_fig = time.perf_counter() - t1

st.write(f"Dados+malha no servidor: {t_dados:.2f}s · serialização da figura: {t_fig:.2f}s · "
         f"{len(df)} municípios · {len(gj['features'])} polígonos · "
         f"figura ≈ {len(fig.to_json()) / 1e6:.1f} MB")
st.subheader("Evento de seleção recebido pelo Streamlit")
st.json(evento.get("selection", {}) if evento else {})
