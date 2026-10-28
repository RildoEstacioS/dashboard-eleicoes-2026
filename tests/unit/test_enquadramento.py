"""Testes do enquadramento. Geometrias sintéticas (quadrados fictícios)."""
import math

from src.visualizacoes.enquadramento import TAMANHO_TILE, _lat_para_y, bbox_geojson, enquadrar


def _quadrado(x0, y0, x1, y1):
    return {"type": "Feature", "properties": {}, "geometry": {
        "type": "MultiPolygon", "coordinates": [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]]}}


def test_bbox_multipolygon():
    gj = {"features": [_quadrado(-50, -20, -45, -15), _quadrado(-44, -30, -40, -25)]}
    assert bbox_geojson(gj) == (-50, -30, -40, -15)


def test_bbox_cabe_no_mapa_com_margem():
    bbox = (-51.0, -23.0, -39.0, -14.0)
    largura, altura = 900, 650
    centro, zoom = enquadrar(bbox, largura, altura, margem=0.05)
    escala = TAMANHO_TILE * 2 ** zoom
    larg_px = (bbox[2] - bbox[0]) / 360 * escala
    alt_px = abs(_lat_para_y(bbox[1]) - _lat_para_y(bbox[3])) * escala
    assert larg_px <= largura * 0.9 + 1e-6 and alt_px <= altura * 0.9 + 1e-6
    # Uma das dimensões deve estar justa (não sobra zoom).
    assert math.isclose(larg_px, largura * 0.9, rel_tol=1e-6) or math.isclose(alt_px, altura * 0.9, rel_tol=1e-6)
    assert bbox[0] < centro["lon"] < bbox[2] and bbox[1] < centro["lat"] < bbox[3]


def test_ilha_minuscula_distante_nao_define_enquadramento():
    # Território grande + ilhota a 10° de distância (como Trindade/ES): a ilhota é ignorada.
    gj = {"features": [_quadrado(-42, -21, -40, -18), _quadrado(-29.4, -20.6, -29.3, -20.5)]}
    assert bbox_geojson(gj) == (-42, -21, -40, -18)


def test_territorio_minusculo_respeita_zoom_maximo():
    _, zoom = enquadrar((-47.9, -15.8, -47.8999, -15.7999), 800, 600, zoom_max=11)
    assert zoom == 11
