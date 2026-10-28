"""Extração segura de ZIPs (proteção contra path traversal e zip bombs)."""
from __future__ import annotations

import zipfile
from pathlib import Path

# Limite de razão de compressão por membro; CSVs do TSE ficam bem abaixo disso.
RAZAO_MAXIMA = 200
TAMANHO_MAXIMO_MEMBRO = 20 * 1024**3  # 20 GiB


class ErroExtracao(RuntimeError):
    pass


def membros_seguros(zf: zipfile.ZipFile, destino: Path) -> list[zipfile.ZipInfo]:
    destino = destino.resolve()
    membros = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        alvo = (destino / info.filename).resolve()
        if not alvo.is_relative_to(destino):
            raise ErroExtracao(f"Caminho inseguro no ZIP: {info.filename}")
        if info.file_size > TAMANHO_MAXIMO_MEMBRO:
            raise ErroExtracao(f"Membro grande demais: {info.filename}")
        if info.compress_size and info.file_size / info.compress_size > RAZAO_MAXIMA:
            raise ErroExtracao(f"Razão de compressão suspeita: {info.filename}")
        membros.append(info)
    return membros


def extrair(zip_path: Path, destino: Path, padrao: str | None = None) -> list[Path]:
    """Extrai membros (opcionalmente filtrados por `padrao` no nome).

    Reaproveita membros já extraídos com o mesmo tamanho.
    """
    destino.mkdir(parents=True, exist_ok=True)
    extraidos = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in membros_seguros(zf, destino):
            if padrao and padrao not in info.filename:
                continue
            alvo = destino / info.filename
            if not (alvo.exists() and alvo.stat().st_size == info.file_size):
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(alvo, "wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
            extraidos.append(alvo)
    return extraidos
