"""Orquestra a preparação geográfica e o relatório de junção TSE–IBGE.

Saídas:
- data/geo/municipios_detalhada.parquet      (GeoParquet, sem simplificação)
- data/geo/municipios_brasil.geojson         (simplificação nacional)
- data/geo/uf/municipios_<UF>.geojson        (simplificação local, por UF)
- data/geo/ufs.geojson, data/geo/regioes.geojson
- data/processed/dim_municipio.parquet       (dimensão território municipal)
- docs/relatorios/juncao_tse_ibge.md / .csv
- docs/relatorios/geografia_medicoes.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from src.aquisicao import manifesto
from src.aquisicao.fontes import EDICAO_MALHA, RECURSOS_IBGE, RECURSOS_TSE
from src.config import DIR_GEO, DIR_PROCESSED, DIR_RAW, DIR_RELATORIOS
from src.geografia import correspondencia as corr
from src.geografia import malhas
from src.tratamento.leitura_tse import extrair_consolidado, relacao_csv


def _arquivo(rec) -> Path:
    p = DIR_RAW / rec.arquivo
    if not p.exists():
        raise FileNotFoundError(
            f"{p.name} não encontrado. Rode: python -m scripts.preparar_dados baixar --so {rec.chave}"
        )
    return p


def carregar_tabela_correspondencia(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    csv = extrair_consolidado(_arquivo(RECURSOS_TSE["municipio_tse_ibge"]))
    return corr.normalizar_tabela(relacao_csv(con, csv).df())


def municipios_com_votacao(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    csv = extrair_consolidado(_arquivo(RECURSOS_TSE["detalhe_munzona"]))
    con.register("d", relacao_csv(con, csv))
    df = con.sql("SELECT DISTINCT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO FROM d").df()
    con.unregister("d")
    return df


def preparar_geografia() -> dict:
    DIR_GEO.mkdir(parents=True, exist_ok=True)
    (DIR_GEO / "uf").mkdir(exist_ok=True)
    med: dict = {"edicao_malha": EDICAO_MALHA}
    con = duckdb.connect()

    t0 = time.perf_counter()
    bruta = malhas.ler_malha_municipal(_arquivo(RECURSOS_IBGE["malha_municipios_2025"]))
    med["leitura_s"] = round(time.perf_counter() - t0, 2)
    med["colunas_malha"] = list(bruta.columns)
    med["crs_original"] = str(bruta.crs)
    med["n_poligonos"] = len(bruta)
    problemas = malhas.validar_malha(bruta)
    if problemas:
        raise malhas.ErroMalha("; ".join(problemas))

    base = malhas.preparar_base(bruta)
    med["vertices_original"] = malhas.resumo_vertices(base)
    base.to_parquet(DIR_GEO / "municipios_detalhada.parquet")

    t0 = time.perf_counter()
    nac = malhas.simplificar_cobertura(base, malhas.TOLERANCIA_NACIONAL)
    med["simplificacao_nacional_s"] = round(time.perf_counter() - t0, 2)
    med["vertices_nacional"] = malhas.resumo_vertices(nac)
    # Só o identificador vai ao navegador; nomes e atributos vêm de dim_municipio.
    cols_mun = ["CD_MUN"]
    med["bytes_municipios_brasil"] = malhas.salvar_geojson(nac, DIR_GEO / "municipios_brasil.geojson", cols_mun)

    ufs = malhas.dissolver(nac, "SIGLA_UF", [])
    med["bytes_ufs"] = malhas.salvar_geojson(ufs, DIR_GEO / "ufs.geojson", ["SIGLA_UF"])
    reg = malhas.dissolver(nac, "NM_REGIAO", [])
    med["bytes_regioes"] = malhas.salvar_geojson(reg, DIR_GEO / "regioes.geojson", ["NM_REGIAO"])

    t0 = time.perf_counter()
    local = malhas.simplificar_cobertura(base, malhas.TOLERANCIA_UF)
    med["simplificacao_uf_s"] = round(time.perf_counter() - t0, 2)
    med["bytes_por_uf"] = {}
    for sg_uf, g in local.groupby("SIGLA_UF"):
        med["bytes_por_uf"][sg_uf] = malhas.salvar_geojson(g, DIR_GEO / "uf" / f"municipios_{sg_uf}.geojson", cols_mun)

    # Conferência dos arquivos gravados: o mapa só preenche Polygon/MultiPolygon.
    ruins = {p.name: t for p in DIR_GEO.rglob("*.geojson")
             if not (t := malhas.tipos_no_arquivo(p)) <= {"Polygon", "MultiPolygon"}}
    if ruins:
        raise malhas.ErroGeometria(f"GeoJSON com tipos não preenchíveis: {ruins}")
    med["geojson_tipos_ok"] = True
    publicar_web()

    # --- junção TSE–IBGE ---
    tabela = carregar_tabela_correspondencia(con)
    problemas_tab = corr.validar_tabela(tabela)
    votacao = municipios_com_votacao(con)
    r = corr.classificar_juncao(votacao, tabela, set(base["CD_MUN"]))

    # Nome do IBGE na malha só para conferência visual; a junção é por código.
    r.territorios = r.territorios.merge(
        base[["CD_MUN", "NM_MUN"]].rename(columns={"CD_MUN": "CD_MUNICIPIO_IBGE", "NM_MUN": "NM_MUN_MALHA"}),
        on="CD_MUNICIPIO_IBGE", how="left",
    )
    DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    nao_assoc = r.territorios[~r.territorios["ESTADO_JUNCAO"].isin([corr.ASSOCIADO])]
    nao_assoc.to_csv(DIR_RELATORIOS / "juncao_tse_ibge_nao_associados.csv", index=False, encoding="utf-8-sig")

    dim = r.territorios[r.territorios["CD_MUNICIPIO"].notna()].copy()
    dim.to_parquet(DIR_PROCESSED / "dim_municipio.parquet", index=False)

    _relatorio_juncao(r, nao_assoc, problemas_tab, tabela, len(base))
    med["juncao"] = r.resumo.to_dict()
    med["problemas_tabela_correspondencia"] = problemas_tab
    (DIR_RELATORIOS / "geografia_medicoes.json").write_text(
        json.dumps(med, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in med.items() if k != "bytes_por_uf"}, ensure_ascii=False, indent=1, default=str))
    return med


def publicar_web() -> int:
    """Copia os GeoJSON simplificados para static/geo (servidos pelo Streamlit)."""
    import shutil
    from src.config import DIR_GEO_WEB
    n = 0
    for p in DIR_GEO.rglob("*.geojson"):
        destino = DIR_GEO_WEB / p.relative_to(DIR_GEO)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, destino)
        n += 1
    return n


def _relatorio_juncao(r, nao_assoc, problemas_tab, tabela, n_poligonos) -> None:
    m = manifesto.carregar()["recursos"]
    divergentes = r.territorios[r.territorios["NOME_DIVERGE"].fillna(False).astype(bool)]
    linhas = [
        "# Relatório de junção TSE–IBGE\n",
        f"Gerado em {manifesto.agora_iso()} por `python -m scripts.preparar_dados geografia`.\n",
        "## Insumos\n",
        f"- Tabela de correspondência: `municipio_tse_ibge` "
        f"(geração na fonte: {tabela['DT_GERACAO'].iloc[0]}; baixada em "
        f"{m.get('municipio_tse_ibge', {}).get('baixado_em')}) — {len(tabela)} linhas.",
        f"- Municípios com votação: `detalhe_votacao_munzona_2026_BRASIL.csv` "
        f"(geração na fonte: {m.get('detalhe_munzona', {}).get('dt_geracao_fonte')}).",
        f"- Malha: {EDICAO_MALHA} — {n_poligonos} polígonos.\n",
        "## Regra\n",
        "Junção por `CD_MUNICIPIO` (TSE) → `CD_MUNICIPIO_TSE` da tabela oficial, com "
        "conferência de `SG_UF`; depois `CD_MUNICIPIO_IBGE` → `CD_MUN` da malha. "
        "Sem junção por nome e sem correspondência aproximada.\n",
        "## Resultado\n",
        "| estado | territórios |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in r.resumo.items()],
        "",
        f"Problemas na tabela de correspondência: {problemas_tab or 'nenhum'}\n",
        "## Territórios não associados ao mapa\n",
    ]
    exibir = nao_assoc[nao_assoc["ESTADO_JUNCAO"] != corr.EXTERIOR]
    if len(exibir):
        linhas += ["| UF | cód. TSE | nome TSE | cód. IBGE | nome na malha | estado |", "|---|---|---|---|---|---|"]
        linhas += [f"| {x.SG_UF} | {x.CD_MUNICIPIO} | {x.NM_MUNICIPIO} | {x.CD_MUNICIPIO_IBGE} | "
                   f"{x.NM_MUN_MALHA} | {x.ESTADO_JUNCAO} |" for x in exibir.astype("object").fillna("—").itertuples()]
    else:
        linhas.append("Nenhum (excluídas as localidades do exterior, tratadas à parte).")
    n_ext = int((nao_assoc["ESTADO_JUNCAO"] == corr.EXTERIOR).sum())
    linhas += [
        f"\nLocalidades no exterior (SG_UF = ZZ): {n_ext}. Não recebem geometria; "
        "entram nos totais nacionais de presidente e são exibidas em painel próprio.\n",
        "## Nomes com grafia diferente (apenas informativo)\n",
        f"{len(divergentes)} municípios associados por código têm nome TSE diferente do nome na tabela "
        "(maiúsculas/minúsculas já desconsideradas). Ver CSV completo de territórios em data/processed/dim_municipio.parquet.\n",
    ]
    (DIR_RELATORIOS / "juncao_tse_ibge.md").write_text("\n".join(linhas), encoding="utf-8")
