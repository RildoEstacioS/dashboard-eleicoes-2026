"""Caminhos e parâmetros gerais do projeto.

Nada aqui contém informação eleitoral (candidatos, vencedores, UFs com 2º turno):
tudo isso é descoberto nos dados oficiais.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DIR_DATA = RAIZ / "data"
DIR_RAW = DIR_DATA / "raw"
DIR_EXTRAIDO = DIR_DATA / "raw" / "extraido"
DIR_PROCESSED = DIR_DATA / "processed"
DIR_BRUTO = DIR_PROCESSED / "bruto"      # Parquet fiel ao CSV, tudo texto
DIR_MODELO = DIR_PROCESSED / "modelo"    # dimensões e fatos tipados
DIR_AGREGADOS = DIR_PROCESSED / "agregados"
DIR_GEO = DIR_DATA / "geo"
DIR_GEO_WEB = RAIZ / "static" / "geo"       # cópia servida pelo Streamlit em /app/static/geo
URL_GEO_WEB = "/app/static/geo"
DIR_RELATORIOS = RAIZ / "docs" / "relatorios"
ARQ_MANIFESTO = DIR_DATA / "manifesto.json"

ANO_ELEICAO = 2026

# Parâmetros de rede
TIMEOUT_CONEXAO_S = 30
TIMEOUT_LEITURA_S = 120
MAX_TENTATIVAS = 4
TAMANHO_BLOCO = 1024 * 1024  # 1 MiB

# Layout dos CSV do TSE (verificado na auditoria; ver docs/auditoria_fontes.md)
TSE_ENCODING = "latin-1"
TSE_DELIMITADOR = ";"


def garantir_diretorios() -> None:
    for d in (DIR_RAW, DIR_EXTRAIDO, DIR_PROCESSED, DIR_GEO, DIR_RELATORIOS):
        d.mkdir(parents=True, exist_ok=True)
