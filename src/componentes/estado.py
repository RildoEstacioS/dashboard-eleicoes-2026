"""Regras de dependência entre filtros (sem Streamlit, testável).

`sanear` recebe uma seleção e as opções válidas e devolve a seleção corrigida
mais avisos legíveis. Seleções inválidas são LIMPAS, nunca trocadas por outra
escolha silenciosa (ex.: nunca troca a UF ou o turno escolhidos pelo usuário).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

NIVEL_REGIAO = "regiao"
NIVEL_UF = "uf"
NIVEL_MUNICIPIO = "municipio"          # municípios de uma UF
NIVEL_MUNICIPIO_BR = "municipio_br"    # todos os municípios do Brasil
NIVEIS = (NIVEL_REGIAO, NIVEL_UF, NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR)
ROTULO_NIVEL = {NIVEL_REGIAO: "Brasil por região", NIVEL_UF: "Brasil por UF",
                NIVEL_MUNICIPIO: "Municípios de uma UF", NIVEL_MUNICIPIO_BR: "Brasil por município"}


def nivel_consulta(nivel: str, uf: str | None) -> tuple[str, str | None]:
    """(nível da consulta, UF) para um nível de tela."""
    if nivel == NIVEL_MUNICIPIO_BR:
        return NIVEL_MUNICIPIO, None
    if nivel == NIVEL_MUNICIPIO:
        return NIVEL_MUNICIPIO, uf
    return nivel, None


def eh_municipal(nivel: str) -> bool:
    return nivel in (NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR)


@dataclass(frozen=True)
class Selecao:
    cargo: str = "Presidente"
    turno: int = 1
    nivel: str = NIVEL_UF
    regiao: str | None = None
    uf: str | None = None
    municipio: str | None = None          # código IBGE
    candidato: str | None = None          # SQ_CANDIDATO (modo candidato)
    cand_a: str | None = None
    cand_b: str | None = None
    partidos: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Opcoes:
    turnos: tuple[int, ...]               # turnos disponíveis para o cargo no recorte
    ufs: tuple[str, ...]                  # UFs válidas para o cargo/turno
    municipios_da_uf: frozenset[str]      # códigos IBGE da UF escolhida
    candidatos: tuple[str, ...]           # SQ_CANDIDATO da disputa no turno
    partidos: tuple[str, ...]


def sanear(s: Selecao, o: Opcoes) -> tuple[Selecao, list[str]]:
    avisos: list[str] = []
    if s.turno not in o.turnos:
        avisos.append(f"O {s.turno}º turno não está disponível para {s.cargo} neste recorte.")
    if s.uf is not None and s.uf not in o.ufs:
        avisos.append(f"{s.uf} não tem esta disputa; UF desmarcada.")
        s = replace(s, uf=None, municipio=None)
    if s.nivel == NIVEL_MUNICIPIO and s.uf is None:
        s = replace(s, nivel=NIVEL_UF)
    if s.municipio is not None and s.municipio not in o.municipios_da_uf:
        # Nunca manter município de outra UF
        s = replace(s, municipio=None)
    if s.candidato is not None and s.candidato not in o.candidatos:
        s = replace(s, candidato=None)
        avisos.append("O candidato selecionado não participa desta disputa/turno; seleção limpa.")
    if s.cand_a not in o.candidatos or s.cand_b not in o.candidatos or s.cand_a == s.cand_b:
        if s.cand_a is not None or s.cand_b is not None:
            if s.cand_a not in o.candidatos or s.cand_b not in o.candidatos:
                avisos.append("A comparação A × B foi refeita: um dos candidatos não participa deste turno.")
        s = replace(s, cand_a=None, cand_b=None)
    partidos = tuple(p for p in s.partidos if p in o.partidos)
    if partidos != s.partidos:
        s = replace(s, partidos=partidos)
    return s, avisos


def filtros_ativos(s: Selecao, rotulos: dict[str, str]) -> list[str]:
    """Rótulos dos filtros ativos, para exibição."""
    out = [f"Cargo: {s.cargo}", f"{s.turno}º turno"]
    out.append(f"Municípios de {s.uf}" if s.nivel == NIVEL_MUNICIPIO else ROTULO_NIVEL[s.nivel])
    if s.regiao:
        out.append(f"Região: {s.regiao}")
    if s.uf and s.nivel != NIVEL_MUNICIPIO:
        out.append(f"UF: {s.uf}")
    if s.municipio:
        out.append(f"Município: {rotulos.get(s.municipio, s.municipio)}")
    if s.partidos:
        out.append("Partidos: " + ", ".join(s.partidos))
    return out
