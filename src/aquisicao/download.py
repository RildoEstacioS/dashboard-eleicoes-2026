"""Download com timeout, retentativas, progresso e reutilização de arquivos.

Regras:
- Nunca baixa nada automaticamente pela interface; só via scripts/preparar_dados.py.
- Se o arquivo local existir e o servidor informar o mesmo tamanho e
  Last-Modified registrados no manifesto, o download é pulado.
- O download é feito em arquivo `.parcial` e só substitui o anterior ao final,
  depois de conferido o tamanho declarado pelo servidor.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import requests
from tqdm import tqdm

from src.aquisicao import manifesto
from src.aquisicao.fontes import Recurso
from src.config import (
    DIR_RAW,
    MAX_TENTATIVAS,
    TAMANHO_BLOCO,
    TIMEOUT_CONEXAO_S,
    TIMEOUT_LEITURA_S,
)

CABECALHOS = {"User-Agent": "dashboard-eleicoes-2026/0.1 (uso analitico local)"}


class ErroDownload(RuntimeError):
    pass


def _head(url: str) -> dict[str, str | int | None]:
    r = requests.head(url, timeout=(TIMEOUT_CONEXAO_S, TIMEOUT_LEITURA_S),
                      headers=CABECALHOS, allow_redirects=True)
    r.raise_for_status()
    tamanho = r.headers.get("Content-Length")
    return {
        "tamanho": int(tamanho) if tamanho else None,
        "last_modified": r.headers.get("Last-Modified"),
        "etag": r.headers.get("ETag"),
    }


def _baixar_stream(url: str, destino: Path, tamanho_esperado: int | None) -> None:
    parcial = destino.with_name(destino.name + ".parcial")
    with requests.get(url, stream=True, timeout=(TIMEOUT_CONEXAO_S, TIMEOUT_LEITURA_S),
                      headers=CABECALHOS) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0) or tamanho_esperado
        with open(parcial, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024,
            desc=destino.name, leave=True,
        ) as barra:
            for chunk in r.iter_content(chunk_size=TAMANHO_BLOCO):
                f.write(chunk)
                barra.update(len(chunk))
    obtido = parcial.stat().st_size
    if tamanho_esperado and obtido != tamanho_esperado:
        parcial.unlink(missing_ok=True)
        raise ErroDownload(f"Tamanho divergente: esperado {tamanho_esperado}, obtido {obtido}")
    parcial.replace(destino)


def baixar(recurso: Recurso, forcar: bool = False, dir_destino: Path = DIR_RAW) -> Path:
    """Baixa `recurso` se necessário e registra no manifesto. Retorna o caminho local."""
    dir_destino.mkdir(parents=True, exist_ok=True)
    destino = dir_destino / recurso.arquivo
    registro = manifesto.carregar()["recursos"].get(recurso.chave, {})

    info = _head(recurso.url)
    if (
        not forcar
        and destino.exists()
        and registro.get("sha256")
        and registro.get("tamanho_bytes") == destino.stat().st_size
        and info["tamanho"] == registro.get("tamanho_bytes")
        and info["last_modified"] == registro.get("last_modified_servidor")
    ):
        print(f"[reutilizado] {recurso.arquivo} (sem alteração no servidor)")
        return destino

    ultimo_erro: Exception | None = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            _baixar_stream(recurso.url, destino, info["tamanho"])  # type: ignore[arg-type]
            break
        except (requests.RequestException, ErroDownload) as e:
            ultimo_erro = e
            espera = 2 ** tentativa
            print(f"[tentativa {tentativa}/{MAX_TENTATIVAS}] falhou: {e}. Nova tentativa em {espera}s")
            time.sleep(espera)
    else:
        raise ErroDownload(f"Falha ao baixar {recurso.url}: {ultimo_erro}")

    manifesto.registrar(recurso.chave, {
        "fonte": recurso.fonte,
        "pacote": recurso.pacote,
        "descricao": recurso.descricao,
        "url": recurso.url,
        "arquivo_local": str(destino.relative_to(dir_destino.parent.parent)),
        "origem": "download",
        "baixado_em": manifesto.agora_iso(),
        "last_modified_servidor": info["last_modified"],
        "etag_servidor": info["etag"],
        "tamanho_bytes": destino.stat().st_size,
        "sha256": manifesto.sha256_arquivo(destino),
    })
    return destino


def importar_local(recurso: Recurso, origem: Path, dir_destino: Path = DIR_RAW) -> Path:
    """Importa um arquivo oficial obtido manualmente (portal indisponível)."""
    if origem.name != recurso.arquivo:
        raise ValueError(
            f"Nome inesperado: '{origem.name}'. Para o recurso '{recurso.chave}' "
            f"o arquivo oficial chama-se '{recurso.arquivo}'."
        )
    dir_destino.mkdir(parents=True, exist_ok=True)
    destino = dir_destino / recurso.arquivo
    shutil.copy2(origem, destino)
    manifesto.registrar(recurso.chave, {
        "fonte": recurso.fonte,
        "pacote": recurso.pacote,
        "descricao": recurso.descricao,
        "url": recurso.url,
        "arquivo_local": str(destino.relative_to(dir_destino.parent.parent)),
        "origem": f"importacao_local:{origem}",
        "baixado_em": manifesto.agora_iso(),
        "last_modified_servidor": None,
        "tamanho_bytes": destino.stat().st_size,
        "sha256": manifesto.sha256_arquivo(destino),
    })
    return destino
