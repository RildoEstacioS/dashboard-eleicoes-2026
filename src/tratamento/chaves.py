"""Normalização das chaves territoriais dos arquivos do TSE.

Achado da auditoria (Etapa 1): em `votacao_candidato_munzona_2026_BRASIL.csv`
parte das linhas traz CD_MUNICIPIO e NR_ZONA sem zeros à esquerda
(ex.: '1473' em vez de '01473'), enquanto o detalhe da apuração usa 5 dígitos.
Juntar os textos crus perde zonas silenciosamente. Toda junção deve usar as
expressões abaixo.
"""
from __future__ import annotations

# Expressões SQL (DuckDB) para chaves canônicas.
SQL_CD_MUNICIPIO = "lpad(trim(CD_MUNICIPIO), 5, '0')"
SQL_NR_ZONA = "CAST(trim(NR_ZONA) AS INTEGER)"
SQL_NR_TURNO = "CAST(trim(NR_TURNO) AS TINYINT)"
SQL_CD_CARGO = "CAST(trim(CD_CARGO) AS SMALLINT)"


def sql_chaves_munzona() -> str:
    """Colunas canônicas da granularidade turno × cargo × UF × município × zona."""
    return (
        f"{SQL_NR_TURNO} AS NR_TURNO, {SQL_CD_CARGO} AS CD_CARGO, SG_UF, "
        f"{SQL_CD_MUNICIPIO} AS CD_MUNICIPIO, {SQL_NR_ZONA} AS NR_ZONA"
    )


def normalizar_cd_municipio(valor: str) -> str:
    return str(valor).strip().zfill(5)
