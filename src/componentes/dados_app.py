"""Acesso a dados para a interface, com cache do Streamlit.

- Conexão DuckDB única (cache_resource); cada consulta usa um cursor próprio,
  seguro entre sessões.
- Resultados pequenos em cache_data (chaveados pelos parâmetros).
- Nada aqui baixa ou relê arquivos brutos: só Parquet do modelo/agregados e
  GeoJSON simplificados.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.aquisicao import manifesto
from src.config import DIR_GEO, DIR_MODELO
from src.consultas import eleicao as q
from src.consultas import estaduais as qe


@st.cache_resource(show_spinner=False)
def _conexao():
    if not (DIR_MODELO / "disponibilidade.parquet").exists():
        return None
    return q.conectar()


def pronto() -> bool:
    return _conexao() is not None


def _cur():
    return _conexao().cursor()


@st.cache_data(show_spinner=False)
def cargos() -> pd.DataFrame:
    return q.cargos(_cur())


@st.cache_data(show_spinner=False)
def disponibilidade() -> pd.DataFrame:
    return q.disponibilidade(_cur())


@st.cache_data(show_spinner=False)
def ufs() -> pd.DataFrame:
    return q.ufs(_cur())


@st.cache_data(show_spinner=False)
def municipios(sg_uf: str) -> pd.DataFrame:
    return q.municipios(_cur(), sg_uf)


@st.cache_data(show_spinner="Consultando candidatos…")
def candidatos(cd_cargo: int, sg_ue: str, turno: int) -> pd.DataFrame:
    return q.candidatos(_cur(), cd_cargo, sg_ue, turno)


@st.cache_data(show_spinner=False)
def totais(cd_cargo: int, turno: int, sg_uf: str | None, incluir_exterior: bool = True,
           regiao: str | None = None) -> dict:
    return q.totais(_cur(), cd_cargo, turno, sg_uf, incluir_exterior, regiao)


@st.cache_data(show_spinner="Consultando territórios…")
def apuracao_territorios(cd_cargo: int, turno: int, nivel: str, sg_uf: str | None,
                         regiao: str | None = None) -> pd.DataFrame:
    """`nivel` de consulta: 'regiao', 'uf' ou 'municipio' (sg_uf None = Brasil)."""
    return q.apuracao_territorios(_cur(), cd_cargo, turno, nivel, sg_uf, regiao)


@st.cache_data(show_spinner="Consultando votos…")
def votos_territorios(cd_cargo: int, turno: int, nivel: str, sg_uf: str | None,
                      regiao: str | None = None) -> pd.DataFrame:
    return q.votos_territorios(_cur(), cd_cargo, turno, nivel, sg_uf, regiao)


@st.cache_data(show_spinner=False)
def exterior(cd_cargo: int, turno: int) -> pd.DataFrame:
    return q.exterior(_cur(), cd_cargo, turno)


@st.cache_data(show_spinner=False)
def tem_exterior(cd_cargo: int, turno: int) -> bool:
    return not q.exterior(_cur(), cd_cargo, turno).empty


@st.cache_data(show_spinner=False)
def exterior_localidades(cd_cargo: int, turno: int) -> pd.DataFrame:
    return q.exterior_localidades(_cur(), cd_cargo, turno)


@st.cache_data(show_spinner=False)
def circunscricoes() -> pd.DataFrame:
    return _cur().sql(f"SELECT * FROM '{(DIR_MODELO / 'dim_circunscricao.parquet').as_posix()}'").df()


@st.cache_data(show_spinner=False)
def ordem_partidos(cd_cargo: int) -> list[str]:
    return qe.ordem_partidos(_cur(), cd_cargo)


@st.cache_data(show_spinner="Consultando partidos…")
def partidos_territorios(cd_cargo: int, turno: int, nivel: str, sg_uf: str | None,
                         regiao: str | None = None) -> pd.DataFrame:
    return qe.partidos_territorios(_cur(), cd_cargo, turno, nivel, sg_uf, regiao)


@st.cache_data(show_spinner=False)
def eleitos(cd_cargo: int, sg_ue: str | None = None) -> pd.DataFrame:
    return qe.eleitos(_cur(), cd_cargo, sg_ue)


@st.cache_data(show_spinner="Consultando partidos…")
def resumo_partidos(cd_cargo: int, sg_uf: str, turno: int = 1) -> pd.DataFrame:
    return qe.resumo_partidos(_cur(), cd_cargo, sg_uf, turno)


@st.cache_data(show_spinner="Carregando malha…")
def geojson(nome: str) -> dict:
    """'ufs', 'regioes', 'municipios_brasil' ou 'uf/municipios_<UF>'."""
    return json.loads((DIR_GEO / f"{nome}.geojson").read_text(encoding="utf-8"))


def url_geojson(nome: str) -> str | None:
    """URL estática da malha, se publicada em static/geo; senão None (embute o dict)."""
    from src.config import DIR_GEO_WEB, URL_GEO_WEB
    return f"{URL_GEO_WEB}/{nome}.geojson" if (DIR_GEO_WEB / f"{nome}.geojson").exists() else None


@st.cache_data(show_spinner=False)
def centroides(nome: str, prop: str) -> dict[str, tuple[float, float]]:
    """Ponto interno (representative_point) de cada feição, para rótulos no mapa."""
    from shapely.geometry import shape
    out = {}
    for ft in geojson(nome)["features"]:
        p = shape(ft["geometry"]).representative_point()
        out[ft["properties"][prop]] = (round(p.x, 4), round(p.y, 4))
    return out


@st.cache_data(show_spinner=False)
def contorno_uf(sg_uf: str) -> dict:
    gj = geojson("ufs")
    return {"type": "FeatureCollection",
            "features": [f for f in gj["features"] if f["properties"]["SIGLA_UF"] == sg_uf]}


@st.cache_data(show_spinner=False, ttl=300)
def metadados() -> dict:
    """Datas de geração (fonte) e de download (dashboard) dos recursos usados."""
    return manifesto.carregar()["recursos"]
