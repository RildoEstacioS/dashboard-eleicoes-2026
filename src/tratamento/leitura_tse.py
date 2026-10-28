"""Leitura dos CSV do TSE com DuckDB.

Os ZIPs de resultados trazem, para o mesmo conteúdo, recortes sobrepostos:
- `*_BR.csv`      : cargos de abrangência federal (presidente), todas as UFs + ZZ;
- `*_<UF>.csv`    : cargos de abrangência estadual daquela UF;
- `*_BRASIL.csv`  : união dos anteriores.
Para evitar dupla contagem, o pipeline lê SOMENTE o arquivo `_BRASIL` quando
ele existe. Isso é verificado em `validacao.auditoria.verificar_sobreposicao`.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb

from src.aquisicao.extracao import extrair
from src.config import DIR_EXTRAIDO, TSE_DELIMITADOR


def membros_csv(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        return [n for n in zf.namelist() if n.lower().endswith(".csv")]


def escolher_membro_consolidado(zip_path: Path) -> str:
    """Retorna o CSV `_BRASIL` do ZIP; se não houver e só existir um CSV, retorna-o."""
    csvs = membros_csv(zip_path)
    brasil = [n for n in csvs if n.upper().endswith("_BRASIL.CSV")]
    if len(brasil) == 1:
        return brasil[0]
    if len(csvs) == 1:
        return csvs[0]
    raise ValueError(f"{zip_path.name}: não há arquivo _BRASIL único entre {csvs}")


def extrair_consolidado(zip_path: Path) -> Path:
    membro = escolher_membro_consolidado(zip_path)
    destino = DIR_EXTRAIDO / zip_path.stem
    [caminho] = extrair(zip_path, destino, padrao=membro)
    return caminho


def relacao_csv(con: duckdb.DuckDBPyConnection, csv_path: Path) -> duckdb.DuckDBPyRelation:
    """Relação DuckDB com todas as colunas como texto (preserva zeros à esquerda).

    A conversão de tipos é feita explicitamente no tratamento, coluna a coluna.
    """
    return con.sql(f"SELECT * FROM {_read_csv(csv_path)}")


def _sql_caminho(p: Path) -> str:
    return "'" + str(p).replace("\\", "/").replace("'", "''") + "'"


def _read_csv(csv_path: Path) -> str:
    return (f"""read_csv({_sql_caminho(csv_path)}, delim='{TSE_DELIMITADOR}', quote='"',
                header=true, all_varchar=true, encoding='latin-1')""")


def csv_para_parquet_texto(csv_path: Path, destino: Path, forcar: bool = False) -> Path:
    """Camada 'bruta' em Parquet: mesmas linhas e colunas do CSV, tudo como texto.

    Serve de base para auditoria e tratamento sem reler o CSV a cada consulta.
    Reaproveitada se for mais nova que o CSV de origem.
    """
    if destino.exists() and not forcar and destino.stat().st_mtime >= csv_path.stat().st_mtime:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp.parquet")
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM {_read_csv(csv_path)}) TO {_sql_caminho(tmp)} "
        "(FORMAT parquet, COMPRESSION zstd)"
    )
    con.close()
    tmp.replace(destino)
    return destino
