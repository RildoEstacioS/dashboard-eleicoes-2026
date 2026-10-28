"""Cálculo de centro e zoom (Web Mercator) para enquadrar um território.

O Plotly `map` não tem "fit bounds" automático; o enquadramento é calculado
a partir do retângulo envolvente da geometria e do tamanho do mapa em pixels.
"""
from __future__ import annotations

import math
from typing import Iterable

TAMANHO_TILE = 512  # MapLibre usa tiles de 512 px no zoom 0


def _lat_para_y(lat: float) -> float:
    s = math.sin(math.radians(max(min(lat, 85.0), -85.0)))
    return 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


def bbox_geojson(geojson: dict) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) de uma FeatureCollection, para enquadrar.

    Ignora partes minúsculas (área < FRACAO_MINIMA da maior parte), como as ilhas
    oceânicas de Trindade e Martim Vaz (Vitória/ES) e Fernando de Noronha (PE):
    elas continuam desenhadas, mas não puxam o zoom para o oceano.
    """
    partes: list[list] = []  # anéis externos de cada polígono

    def poligonos(g: dict) -> None:
        if g is None:
            return
        t = g["type"]
        if t == "GeometryCollection":
            for sub in g["geometries"]:
                poligonos(sub)
        elif t == "Polygon":
            partes.append(g["coordinates"][0])
        elif t == "MultiPolygon":
            partes.extend(p[0] for p in g["coordinates"])

    for f in geojson["features"]:
        poligonos(f["geometry"])
    if not partes:
        raise ValueError("GeoJSON sem coordenadas")
    areas = [_area(anel) for anel in partes]
    limite = max(areas) * FRACAO_MINIMA
    usadas = [anel for anel, a in zip(partes, areas) if a >= limite]
    xs = [c[0] for anel in usadas for c in anel]
    ys = [c[1] for anel in usadas for c in anel]
    return min(xs), min(ys), max(xs), max(ys)


FRACAO_MINIMA = 0.01


def _area(anel) -> float:
    """Área plana (graus²) pela fórmula do laço; suficiente para comparar partes."""
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(anel, anel[1:]))) / 2


def enquadrar(
    bbox: tuple[float, float, float, float],
    largura_px: int,
    altura_px: int,
    margem: float = 0.08,
    zoom_max: float = 12.0,
) -> tuple[dict[str, float], float]:
    """Retorna (center, zoom) que fazem o bbox caber no mapa com `margem` relativa."""
    lon_min, lat_min, lon_max, lat_max = bbox
    y_medio = (_lat_para_y(lat_min) + _lat_para_y(lat_max)) / 2  # centro em Mercator, não em graus
    centro = {"lon": (lon_min + lon_max) / 2,
              "lat": math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y_medio))))}
    dx = max((lon_max - lon_min) / 360.0, 1e-9)
    dy = max(abs(_lat_para_y(lat_min) - _lat_para_y(lat_max)), 1e-9)
    uteis_x = largura_px * (1 - 2 * margem)
    uteis_y = altura_px * (1 - 2 * margem)
    zoom = min(math.log2(uteis_x / (TAMANHO_TILE * dx)), math.log2(uteis_y / (TAMANHO_TILE * dy)))
    return centro, max(0.0, min(zoom, zoom_max))
