"""Correspondência oficial entre códigos municipais do TSE e do IBGE.

Fonte: recurso `municipio_tse_ibge` do TSE ("Códigos oficiais de UF e
municípios segundo o TSE e o IBGE"). Regras:
- A junção usa SEMPRE (SG_UF, CD_MUNICIPIO_TSE) → CD_MUNICIPIO_IBGE.
- Nunca se junta por nome. Diferenças de grafia são apenas reportadas.
- Nenhuma correspondência aproximada é aplicada.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Codificação oficial do IBGE: 1º dígito do código de UF/município = grande região.
REGIOES_IBGE = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

# Estados possíveis de cada território na junção. "zero votos" NÃO é um estado
# de junção: é um valor válido de um território associado.
ASSOCIADO = "associado"
SEM_CORRESPONDENCIA = "sem_correspondencia_tse_ibge"
SEM_GEOMETRIA = "sem_geometria_na_malha"
GEOMETRIA_SEM_VOTACAO = "geometria_sem_votacao"
UF_DIVERGENTE = "uf_divergente"
EXTERIOR = "exterior"

SG_UF_EXTERIOR = "ZZ"


class ErroCorrespondencia(ValueError):
    pass


def normalizar_tabela(df: pd.DataFrame) -> pd.DataFrame:
    """Tipa a tabela oficial preservando os códigos como texto com zeros à esquerda."""
    t = df[["SG_UF", "CD_UF_TSE", "CD_UF_IBGE", "CD_MUNICIPIO_TSE", "NM_MUNICIPIO_TSE",
            "CD_MUNICIPIO_IBGE", "NM_MUNICIPIO_IBGE", "DT_GERACAO"]].astype("string")
    t["CD_MUNICIPIO_TSE"] = t["CD_MUNICIPIO_TSE"].str.strip().str.zfill(5)
    t["CD_MUNICIPIO_IBGE"] = t["CD_MUNICIPIO_IBGE"].str.strip().str.zfill(7)
    t["CD_UF_IBGE"] = t["CD_UF_IBGE"].str.strip().str.zfill(2)
    t["NM_REGIAO"] = t["CD_MUNICIPIO_IBGE"].str[0].map(REGIOES_IBGE).astype("string")
    return t


def validar_tabela(t: pd.DataFrame) -> list[str]:
    """Retorna a lista de problemas encontrados (vazia se a tabela estiver íntegra)."""
    problemas = []
    if t["CD_MUNICIPIO_TSE"].duplicated().any():
        problemas.append(f"CD_MUNICIPIO_TSE duplicado: {t.loc[t['CD_MUNICIPIO_TSE'].duplicated(), 'CD_MUNICIPIO_TSE'].tolist()}")
    if t["CD_MUNICIPIO_IBGE"].duplicated().any():
        problemas.append(f"CD_MUNICIPIO_IBGE duplicado: {t.loc[t['CD_MUNICIPIO_IBGE'].duplicated(), 'CD_MUNICIPIO_IBGE'].tolist()}")
    if not t["CD_MUNICIPIO_IBGE"].str.fullmatch(r"\d{7}").all():
        problemas.append("CD_MUNICIPIO_IBGE fora do padrão de 7 dígitos")
    inconsistentes = t[t["CD_MUNICIPIO_IBGE"].str[:2] != t["CD_UF_IBGE"]]
    if len(inconsistentes):
        problemas.append(f"Prefixo de UF do código IBGE diverge de CD_UF_IBGE: {inconsistentes['CD_MUNICIPIO_TSE'].tolist()}")
    if t["NM_REGIAO"].isna().any():
        problemas.append("Código IBGE com dígito de região desconhecido")
    uf_por_cod = t.groupby("CD_UF_IBGE")["SG_UF"].nunique()
    if (uf_por_cod > 1).any():
        problemas.append(f"CD_UF_IBGE associado a mais de uma SG_UF: {uf_por_cod[uf_por_cod > 1].index.tolist()}")
    return problemas


@dataclass
class ResultadoJuncao:
    territorios: pd.DataFrame  # uma linha por território com o estado da junção
    resumo: pd.Series


def classificar_juncao(
    votacao: pd.DataFrame,
    tabela: pd.DataFrame,
    codigos_geometria: set[str],
) -> ResultadoJuncao:
    """Classifica cada município com votação e cada geometria.

    `votacao`: municípios distintos com SG_UF, CD_MUNICIPIO (TSE), NM_MUNICIPIO.
    `tabela`: saída de `normalizar_tabela`.
    `codigos_geometria`: códigos IBGE de 7 dígitos presentes na malha.
    """
    v = votacao[["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates().astype("string")
    v["CD_MUNICIPIO"] = v["CD_MUNICIPIO"].str.strip().str.zfill(5)

    m = v.merge(
        tabela, how="left", left_on="CD_MUNICIPIO", right_on="CD_MUNICIPIO_TSE",
        suffixes=("", "_tab"), indicator=True,
    )
    estado = pd.Series(ASSOCIADO, index=m.index, dtype="string")
    estado[m["SG_UF"] == SG_UF_EXTERIOR] = EXTERIOR
    nao_ext = m["SG_UF"] != SG_UF_EXTERIOR
    estado[nao_ext & (m["_merge"] == "left_only")] = SEM_CORRESPONDENCIA
    estado[nao_ext & (m["_merge"] == "both") & (m["SG_UF"] != m["SG_UF_tab"])] = UF_DIVERGENTE
    estado[(estado == ASSOCIADO) & ~m["CD_MUNICIPIO_IBGE"].isin(codigos_geometria)] = SEM_GEOMETRIA
    m["ESTADO_JUNCAO"] = estado
    m["NOME_DIVERGE"] = (
        m["NM_MUNICIPIO_TSE"].notna()
        & (m["NM_MUNICIPIO"].str.upper().str.strip() != m["NM_MUNICIPIO_TSE"].str.upper().str.strip())
    )

    associados_ibge = set(m.loc[m["CD_MUNICIPIO_IBGE"].notna(), "CD_MUNICIPIO_IBGE"])
    sobras = sorted(codigos_geometria - associados_ibge)
    extra = pd.DataFrame({
        "CD_MUNICIPIO_IBGE": pd.Series(sobras, dtype="string"),
        "ESTADO_JUNCAO": pd.Series([GEOMETRIA_SEM_VOTACAO] * len(sobras), dtype="string"),
    })

    cols = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "CD_MUNICIPIO_IBGE", "NM_MUNICIPIO_IBGE",
            "NM_REGIAO", "ESTADO_JUNCAO", "NOME_DIVERGE"]
    territorios = pd.concat([m[cols], extra], ignore_index=True)
    return ResultadoJuncao(territorios, territorios["ESTADO_JUNCAO"].value_counts())
