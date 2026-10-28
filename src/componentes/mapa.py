"""Mapa interativo compartilhado pelas páginas, nos quatro níveis.

Navegação por clique:
- Brasil por região → clicar numa região abre as UFs dela;
- Brasil por UF     → clicar numa UF abre os municípios dela;
- Municípios de UF  → clicar num município o seleciona;
- Brasil por município → clicar num município o seleciona (e fixa a UF dele).
Botões: enquadrar, limpar seleção, subir um nível.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.componentes import dados_app as dados
from src.componentes.estado import (NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR, NIVEL_REGIAO, NIVEL_UF,
                                    nivel_consulta)
from src.componentes.filtros import TODAS, agendar
from src.visualizacoes import mapas


def dados_do_mapa(ctx) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(apuração, votos) dos territórios do mapa atual, respeitando o filtro de região."""
    s = ctx.sel
    nivel, uf = nivel_consulta(s.nivel, s.uf)
    regiao = None if s.nivel == NIVEL_REGIAO else s.regiao
    return (dados.apuracao_territorios(ctx.cd_cargo, s.turno, nivel, uf, regiao),
            dados.votos_territorios(ctx.cd_cargo, s.turno, nivel, uf, regiao))


def _filtrar(gj: dict, prop: str, ids: set[str]) -> dict:
    return {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"][prop] in ids]}


MAX_ROTULOS_MUNICIPIO = 20


def moldura(ctx, ap: pd.DataFrame, altura: int = 600) -> mapas.Moldura:
    """Geometria do nível atual, com os nomes a desenhar por cima dos polígonos."""
    m = _moldura(ctx, ap, altura)
    m.rotulos = _rotulos(ctx, m, ap)
    return m


def _rotulos(ctx, m: mapas.Moldura, ap: pd.DataFrame) -> list[tuple[float, float, str]]:
    """Regiões e UFs: todos os nomes/siglas. Municípios de uma UF: os maiores eleitorados.
    Brasil por município: siglas das UFs (nomes de 5.571 municípios seriam ilegíveis)."""
    s = ctx.sel
    if s.nivel == NIVEL_REGIAO:
        c = dados.centroides("regioes", "NM_REGIAO")
        return [(*c[i], i) for i in m.ids if i in c]
    if s.nivel in (NIVEL_UF, NIVEL_MUNICIPIO_BR):
        c = dados.centroides("ufs", "SIGLA_UF")
        ufs = m.ids if s.nivel == NIVEL_UF else [f["properties"]["SIGLA_UF"] for f in (m.contorno or {"features": []})["features"]]
        return [(*c[u], u) for u in ufs if u in c]
    c = dados.centroides(f"uf/municipios_{s.uf}", "CD_MUN")
    maiores = ap.nlargest(MAX_ROTULOS_MUNICIPIO, "QT_APTOS")
    return [(*c[t], n) for t, n in zip(maiores.TERRITORIO, maiores.NOME) if t in c]


def _moldura(ctx, ap: pd.DataFrame, altura: int) -> mapas.Moldura:
    """Geometria do nível atual. Com região selecionada, só os territórios dela.

    `ap`: territórios com dado (define o recorte quando há filtro de região).
    """
    s = ctx.sel
    url_ufs = dados.url_geojson("ufs")
    ufs = dados.geojson("ufs")
    if s.nivel == NIVEL_REGIAO:
        gj = dados.geojson("regioes")
        url_reg = dados.url_geojson("regioes")
        ids = [f["properties"]["NM_REGIAO"] for f in gj["features"]]
        # Divisas de região fortes; divisas entre estados finas e translúcidas, só como referência.
        return mapas.Moldura(gj, "properties.NM_REGIAO", ids, contorno=gj, contorno_idkey="properties.NM_REGIAO",
                             contorno_nome="Região", altura=altura, url=url_reg, contorno_url=url_reg,
                             linhas_internas=ufs, linhas_internas_url=url_ufs)
    if s.nivel == NIVEL_UF:
        gj = _filtrar(ufs, "SIGLA_UF", set(ap.TERRITORIO)) if s.regiao else ufs
        ids = [f["properties"]["SIGLA_UF"] for f in gj["features"]]
        return mapas.Moldura(gj, "properties.SIGLA_UF", ids, contorno=gj, altura=altura,
                             url=url_ufs, contorno_url=url_ufs)
    if s.nivel == NIVEL_MUNICIPIO_BR:
        gj = dados.geojson("municipios_brasil")
        contorno = ufs
        if s.regiao:
            gj = _filtrar(gj, "CD_MUN", set(ap.TERRITORIO))
            contorno = _filtrar(ufs, "SIGLA_UF", set(ap.SG_UF))
        ids = [f["properties"]["CD_MUN"] for f in gj["features"]]
        return mapas.Moldura(gj, "properties.CD_MUN", ids, contorno=contorno, altura=altura,
                             url=dados.url_geojson("municipios_brasil"), contorno_url=url_ufs,
                             largura_linha=0.15 if not s.regiao else 0.35,
                             # Bordas translúcidas: com 5.571 polígonos, o branco opaco “lava” as cores.
                             cor_linha="rgba(255,255,255,0.35)" if ctx.fundo == "claro" else "rgba(0,0,0,0.35)")
    nome = f"uf/municipios_{s.uf}"
    gj = dados.geojson(nome)
    ids = [f["properties"]["CD_MUN"] for f in gj["features"]]
    return mapas.Moldura(gj, "properties.CD_MUN", ids, contorno=dados.contorno_uf(s.uf), altura=altura,
                         url=dados.url_geojson(nome), contorno_url=url_ufs)


def revisao(ctx, pagina: str) -> str:
    n = st.session_state.get(f"mapa_reset_{pagina}", 0)
    return f"{pagina}-{ctx.sel.nivel}-{ctx.sel.regiao}-{ctx.sel.uf}-{n}"


def barra_de_acoes(ctx, pagina: str) -> None:
    s = ctx.sel
    c = st.columns(3)
    if c[0].button("⟲ Enquadrar", key=f"btn_reset_{pagina}", use_container_width=True,
                   help="Restaurar o enquadramento inicial do mapa"):
        st.session_state[f"mapa_reset_{pagina}"] = st.session_state.get(f"mapa_reset_{pagina}", 0) + 1
        st.rerun()
    if s.municipio and c[1].button("✕ Limpar seleção", key=f"btn_limpar_{pagina}", use_container_width=True):
        agendar(**{f"f_municipio_{s.uf}": None})
    if s.nivel == NIVEL_MUNICIPIO and c[2].button("← UFs", key=f"btn_voltar_{pagina}", use_container_width=True,
                                                  help="Voltar ao mapa por UF"):
        agendar(f_nivel=NIVEL_UF)
    elif s.nivel == NIVEL_UF and s.regiao and c[2].button("← Regiões", key=f"btn_voltar_{pagina}",
                                                         use_container_width=True, help="Voltar ao mapa por região"):
        agendar(f_nivel=NIVEL_REGIAO, f_regiao=TODAS, f_uf=None)


def _uf_do_municipio(cd_ibge: str) -> str | None:
    u = dados.ufs()
    r = u.loc[u.CD_UF_IBGE == cd_ibge[:2], "SG_UF"]
    return r.iloc[0] if len(r) else None


def exibir(fig, ctx, pagina: str) -> None:
    """Desenha o mapa e trata o clique conforme o nível."""
    s = ctx.sel
    # Chave inclui recorte e seleção: depois de tratado, o gráfico é recriado sem
    # seleção pendente (o evento não se repete em loop).
    chave = f"mapa_{pagina}_{s.nivel}_{s.regiao}_{s.uf}_{s.municipio}"
    evento = st.plotly_chart(fig, on_select="rerun", selection_mode=("points",), key=chave,
                             use_container_width=True,
                             config={"scrollZoom": True, "displaylogo": False,
                                     "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    alvo = mapas.territorio_selecionado(evento)
    if not alvo:
        return
    if s.nivel == NIVEL_REGIAO:
        agendar(f_nivel=NIVEL_UF, f_regiao=alvo, f_uf=None)
    elif s.nivel == NIVEL_UF:
        agendar(f_nivel=NIVEL_MUNICIPIO, f_uf=alvo)
    elif s.nivel == NIVEL_MUNICIPIO and alvo != s.municipio:
        agendar(**{f"f_municipio_{s.uf}": alvo})
    elif s.nivel == NIVEL_MUNICIPIO_BR and alvo != s.municipio:
        uf = _uf_do_municipio(alvo)
        if uf:
            agendar(f_uf=uf, **{f"f_municipio_{uf}": alvo})
