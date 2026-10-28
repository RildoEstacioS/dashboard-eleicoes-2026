"""Preparação das malhas do IBGE para navegação web.

Estratégia:
- Fonte: Malha Municipal 2025 (FTP do IBGE), SIRGAS 2000 (EPSG:4674).
- Reprojeta para EPSG:4326 (exigido pelos mapas web; diferença SIRGAS×WGS84
  é submétrica e irrelevante na escala do dashboard).
- Simplifica com `shapely.coverage_simplify`, que simplifica as fronteiras
  compartilhadas uma única vez e preserva a topologia (sem buracos/sobreposições
  entre vizinhos).
- UF e grandes regiões são obtidas por dissolução da malha municipal já
  simplificada, usando o prefixo oficial do código IBGE (2 dígitos = UF,
  1º dígito = região). Assim, as bordas dos três níveis coincidem exatamente.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from src.geografia.correspondencia import REGIOES_IBGE

CRS_WEB = "EPSG:4326"
# Tolerâncias em graus (≈ 111 km por grau). Calibradas na Etapa 1 medindo o
# tamanho da figura Plotly enviada ao navegador; ver docs/geografia.md.
TOLERANCIA_NACIONAL = 0.02   # ≈ 2,2 km — figura nacional ≈ 3,3 MB (0,01° dava 6,2 MB)
TOLERANCIA_UF = 0.004        # ≈ 450 m — zoom estadual
PRECISAO_COORD = 4           # casas decimais no GeoJSON (≈ 11 m, abaixo do erro da simplificação)


class ErroMalha(ValueError):
    pass


def ler_malha_municipal(zip_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{zip_path}", engine="pyogrio")
    if "CD_MUN" not in gdf.columns:
        raise ErroMalha(f"Coluna CD_MUN ausente; colunas: {list(gdf.columns)}")
    gdf["CD_MUN"] = gdf["CD_MUN"].astype("string").str.strip()
    return gdf


def validar_malha(gdf: gpd.GeoDataFrame) -> list[str]:
    problemas = []
    if not gdf["CD_MUN"].str.fullmatch(r"\d{7}").all():
        problemas.append("CD_MUN fora do padrão de 7 dígitos")
    if gdf["CD_MUN"].duplicated().any():
        problemas.append(f"CD_MUN duplicado: {gdf.loc[gdf['CD_MUN'].duplicated(), 'CD_MUN'].tolist()}")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        problemas.append("Geometrias nulas ou vazias")
    if gdf.crs is None:
        problemas.append("Malha sem CRS declarado")
    # A dissolução em UF/região usa o prefixo do código; confere com os atributos oficiais.
    if {"CD_UF", "CD_REGIAO"} <= set(gdf.columns):
        if (gdf["CD_MUN"].str[:2] != gdf["CD_UF"].astype("string")).any():
            problemas.append("Prefixo de CD_MUN diverge de CD_UF")
        if (gdf["CD_MUN"].str[0] != gdf["CD_REGIAO"].astype("string")).any():
            problemas.append("1º dígito de CD_MUN diverge de CD_REGIAO")
    return problemas


def preparar_base(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reprojeta, corrige geometrias inválidas e padroniza atributos."""
    g = gdf.to_crs(CRS_WEB)
    invalidas = ~g.geometry.is_valid
    if invalidas.any():
        g.loc[invalidas, "geometry"] = shapely.make_valid(g.loc[invalidas, "geometry"].values)
    g["CD_UF_IBGE"] = g["CD_MUN"].str[:2]
    g["CD_REGIAO"] = g["CD_MUN"].str[0]
    g["NM_REGIAO"] = g["CD_REGIAO"].map(REGIOES_IBGE).astype("string")
    if "SIGLA_UF" not in g.columns:
        raise ErroMalha("Coluna SIGLA_UF ausente na malha")
    return g[["CD_MUN", "NM_MUN", "SIGLA_UF", "CD_UF_IBGE", "CD_REGIAO", "NM_REGIAO", "AREA_KM2", "geometry"]]


def simplificar_cobertura(g: gpd.GeoDataFrame, tolerancia: float) -> gpd.GeoDataFrame:
    s = g.copy()
    s["geometry"] = shapely.coverage_simplify(g.geometry.values, tolerance=tolerancia)
    return s


def dissolver(g: gpd.GeoDataFrame, chave: str, atributos: list[str]) -> gpd.GeoDataFrame:
    d = g.dissolve(by=chave, aggfunc="first")[atributos + ["geometry"]].reset_index()
    d["geometry"] = [_so_poligonos(x) for x in shapely.make_valid(d.geometry.values)]
    return d


def _so_poligonos(geom):
    """make_valid pode gerar GeometryCollection com linhas/pontos residuais; mantém só áreas."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    partes = [p for p in shapely.get_parts(geom) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(partes) if partes else geom


class ErroGeometria(ValueError):
    pass


def salvar_geojson(g: gpd.GeoDataFrame, destino: Path, colunas: list[str]) -> int:
    """Grava GeoJSON só com Polygon/MultiPolygon, coordenadas na grade de PRECISAO_COORD.

    O arredondamento é feito ANTES da gravação (set_precision preserva a validade);
    arredondar só na escrita gerava GeometryCollection em algumas UFs, que o
    mapa não preenche. A gravação falha se sobrar qualquer outro tipo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    s = g[colunas + ["geometry"]].copy()
    grade = shapely.set_precision(s.geometry.values, grid_size=10 ** -PRECISAO_COORD)
    s["geometry"] = [_so_poligonos(x) for x in shapely.make_valid(grade)]
    tipos = set(s.geom_type)
    if not tipos <= {"Polygon", "MultiPolygon"}:
        raise ErroGeometria(f"{destino.name}: tipos inesperados {tipos}")
    s.to_file(destino, driver="GeoJSON", engine="pyogrio",
              layer_options={"COORDINATE_PRECISION": PRECISAO_COORD, "RFC7946": "YES"})
    return destino.stat().st_size


def tipos_no_arquivo(caminho: Path) -> set[str]:
    import json
    return {f["geometry"]["type"] for f in json.loads(caminho.read_text(encoding="utf-8"))["features"]}


def resumo_vertices(g: gpd.GeoDataFrame) -> int:
    return int(shapely.get_num_coordinates(g.geometry.values).sum())


def tabela_atributos(g: gpd.GeoDataFrame) -> pd.DataFrame:
    return pd.DataFrame(g.drop(columns="geometry"))
