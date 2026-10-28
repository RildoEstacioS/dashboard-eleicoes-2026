"""Mede o custo de servidor das telas do MVP com dados reais (sem cache do Streamlit).

Uso: python -m scripts.medir_desempenho
Mede consultas DuckDB, montagem dos dados do modo e tamanho/serialização da
figura Plotly (o que é enviado ao navegador a cada redesenho do mapa).
"""
from __future__ import annotations

import json
import platform
import statistics
import time

from src.config import DIR_GEO, DIR_RELATORIOS
from src.consultas import eleicao as q
from src.visualizacoes import cores, mapas, modos


def _gj(nome):
    return json.loads((DIR_GEO / f"{nome}.geojson").read_text(encoding="utf-8"))


def medir(rotulo, nivel, uf, n=5):
    con = q.conectar()
    tempos_q, tempos_f, tamanho = [], [], 0
    cands = q.candidatos(con, 1, "BR", 1)
    cmap = cores.atribuir_lideranca(cands.SQ_CANDIDATO.tolist(), "padrao", "claro")
    nome = "ufs" if nivel == "uf" else f"uf/municipios_{uf}"
    gj = _gj(nome)
    chave = "SIGLA_UF" if nivel == "uf" else "CD_MUN"
    ufs = _gj("ufs")
    contorno = ufs if nivel == "uf" else {"type": "FeatureCollection", "features": [
        f for f in ufs["features"] if f["properties"]["SIGLA_UF"] == uf]}
    # Como no app: malhas por URL estática (/app/static/geo), não embutidas na figura.
    m = mapas.Moldura(gj, f"properties.{chave}", [f["properties"][chave] for f in gj["features"]],
                      contorno=contorno, url=f"/app/static/geo/{nome}.geojson",
                      contorno_url="/app/static/geo/ufs.geojson")
    for _ in range(n):
        t = time.perf_counter()
        ap = q.apuracao_territorios(con, 1, 1, nivel, uf)
        vt = q.votos_territorios(con, 1, 1, nivel, uf)
        tempos_q.append(time.perf_counter() - t)
        t = time.perf_counter()
        d, _ = modos.lideranca(ap, vt, cands, cmap, "claro", nivel == "uf")
        fig = mapas.mapa_categorico(m, d, "claro", "x")
        tamanho = len(fig.to_json())
        tempos_f.append(time.perf_counter() - t)
    return {"tela": rotulo, "consultas_s": round(statistics.median(tempos_q), 3),
            "dados+figura_s": round(statistics.median(tempos_f), 3), "figura_MB": round(tamanho / 1e6, 2)}


def medir_nacional(n=3, compacto=True):
    """Brasil por município (5.571 territórios), malha nacional por URL."""
    con = q.conectar()
    cands = q.candidatos(con, 1, "BR", 1)
    cmap = cores.atribuir_lideranca(cands.SQ_CANDIDATO.tolist(), "padrao", "claro")
    gj, ufs = _gj("municipios_brasil"), _gj("ufs")
    m = mapas.Moldura(gj, "properties.CD_MUN", [f["properties"]["CD_MUN"] for f in gj["features"]],
                      contorno=ufs, url="/app/static/geo/municipios_brasil.geojson",
                      contorno_url="/app/static/geo/ufs.geojson")
    tq, tf, tam = [], [], 0
    for _ in range(n):
        t = time.perf_counter()
        ap = q.apuracao_territorios(con, 1, 1, "municipio", None)
        vt = q.votos_territorios(con, 1, 1, "municipio", None)
        tq.append(time.perf_counter() - t)
        t = time.perf_counter()
        d, _ = modos.lideranca(ap, vt, cands, cmap, "claro", False, compacto=compacto)
        fig = mapas.mapa_categorico(m, d, "claro", "x")
        tam = len(fig.to_json())
        tf.append(time.perf_counter() - t)
    rotulo = "Brasil por município (5.571)" + (" · tooltip compacto" if compacto else " · tooltip completo")
    return {"tela": rotulo, "consultas_s": round(statistics.median(tq), 3),
            "dados+figura_s": round(statistics.median(tf), 3), "figura_MB": round(tam / 1e6, 2)}


def main():
    res = [medir("Brasil por UF", "uf", None), medir("Municípios de SP", "municipio", "SP"),
           medir("Municípios de MG (maior UF)", "municipio", "MG"), medir_nacional(compacto=False),
           medir_nacional(compacto=True)]
    amb = {"python": platform.python_version(), "so": platform.platform(), "processador": platform.processor()}
    for r in res:
        print(r)
    print(amb)
    (DIR_RELATORIOS / "desempenho_etapa3.json").write_text(
        json.dumps({"ambiente": amb, "resultados": res}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
