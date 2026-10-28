"""Manifesto de rastreabilidade dos arquivos baixados ou importados.

Cada entrada distingue:
- `baixado_em`: quando ESTE dashboard obteve o arquivo;
- `last_modified_servidor`: cabeçalho HTTP informado pela fonte;
- `dt_geracao_fonte`: data de geração gravada pela fonte dentro do arquivo
  (preenchida depois, na validação, a partir de DT_GERACAO/HH_GERACAO).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import ARQ_MANIFESTO


def sha256_arquivo(caminho: Path, bloco: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(bloco):
            h.update(chunk)
    return h.hexdigest()


def agora_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def carregar(caminho: Path = ARQ_MANIFESTO) -> dict[str, Any]:
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {"versao": 1, "recursos": {}}


def salvar(manifesto: dict[str, Any], caminho: Path = ARQ_MANIFESTO) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(caminho)


def registrar(chave: str, dados: dict[str, Any], caminho: Path = ARQ_MANIFESTO) -> None:
    m = carregar(caminho)
    anterior = m["recursos"].get(chave, {})
    m["recursos"][chave] = {**anterior, **dados}
    salvar(m, caminho)
