"""Votos no exterior agrupados por país.

O TSE publica a votação por CIDADE do exterior (UF "ZZ"), sem campo de país (os
recursos de local de votação e de perfil do eleitorado também não trazem país ou
coordenadas utilizáveis — auditado em 28/10/2026). O agrupamento usa a tabela
auxiliar `config/exterior_paises.csv` (cidade TSE → país, ISO-3), uma classificação
geográfica revisável que NÃO é dado oficial do TSE. Os votos são os oficiais.
"""
from __future__ import annotations

import pandas as pd

from src.config import RAIZ

ARQ_PAISES = RAIZ / "config" / "exterior_paises.csv"


def tabela_paises() -> pd.DataFrame:
    t = pd.read_csv(ARQ_PAISES, sep=";", dtype=str, keep_default_na=False)
    t["CD_MUNICIPIO"] = t["CD_MUNICIPIO"].str.strip().str.zfill(5)
    return t


def por_pais(localidades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """(apuração por país, votos por país × candidato, cidades sem país na tabela).

    `localidades`: saída de consultas.eleicao.exterior_localidades (cidade × candidato).
    A apuração soma numeradores e denominadores das cidades de cada país.
    """
    t = tabela_paises()
    loc = localidades.assign(CD_MUNICIPIO=localidades["CD_MUNICIPIO"].astype(str).str.zfill(5))
    loc = loc.merge(t[["CD_MUNICIPIO", "PAIS", "ISO3"]], on="CD_MUNICIPIO", how="left")
    sem_pais = sorted(loc.loc[loc["PAIS"].isna(), "LOCALIDADE"].unique())
    loc = loc[loc["PAIS"].notna()]
    cidades = loc.drop_duplicates("CD_MUNICIPIO")
    ap = cidades.groupby(["ISO3", "PAIS"], as_index=False).agg(
        CIDADES=("CD_MUNICIPIO", "count"), QT_APTOS=("APTOS", "sum"), QT_COMPARECIMENTO=("COMPARECIMENTO", "sum"),
        QT_ABSTENCOES=("ABSTENCOES", "sum"), QT_TOTAL_VOTOS_VALIDOS=("VALIDOS", "sum"))
    ap = ap.rename(columns={"ISO3": "TERRITORIO", "PAIS": "NOME"}).assign(SG_UF="")
    votos = (loc.dropna(subset=["SQ_CANDIDATO"]).groupby(["ISO3", "SQ_CANDIDATO"], as_index=False)["VOTOS"].sum()
             .rename(columns={"ISO3": "TERRITORIO"}))
    return ap, votos, sem_pais
