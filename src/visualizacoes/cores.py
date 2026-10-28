"""Paletas do dashboard, validadas com o validador de paletas (dataviz).

Validação (28/10/2026, `--pairs all`, adequado a mapas coropléticos):
- Liderança padrão, 3 cores: passa CVD (ΔE 9,2 claro / 9,4 escuro) e visão normal
  (24,0 / 20,9). Verde-água claro tem contraste 2,74:1 → exige rótulos/tooltip/tabela.
- Liderança Okabe-Ito, 3 cores (claro): passa CVD (9,6) e visão normal (21,1);
  laranja e rosa abaixo de 3:1 → mesma exigência. No escuro reprova a faixa
  de luminosidade, então o mapa escuro sempre usa a paleta padrão.
- Pares divergentes A × B: azul↔laranja, azul↔vermelho e violeta↔verde-água
  passam CVD e visão normal nos dois modos.

Regras: cor segue a entidade (não o ranking da tela), no máximo 3 cores
categóricas no mapa (o 4º em diante vira "Outros"), sequencial em um só matiz,
divergente com ponto médio cinza. Nenhuma cor partidária é presumida.
"""
from __future__ import annotations

from dataclasses import dataclass

LIDERANCA = {
    "padrao": {"claro": ["#2a78d6", "#eb6834", "#1baf7a"], "escuro": ["#3987e5", "#d95926", "#199e70"]},
    "daltonismo": {"claro": ["#0072b2", "#e69f00", "#cc79a7"], "escuro": ["#3987e5", "#d95926", "#199e70"]},
}
ROTULO_PALETA = {"padrao": "Padrão", "daltonismo": "Alternativa (Okabe-Ito)"}

# Estados especiais: distintos entre si e do ponto neutro (#f0efec / #383835).
OUTROS = {"claro": "#a3a19a", "escuro": "#6b6a64"}
EMPATE = {"claro": "#52514e", "escuro": "#c3c2b7"}
SEM_DADO = {"claro": "#ffffff", "escuro": "#0d0d0d"}          # vazado, com contorno
NAO_APLICAVEL = {"claro": "#d6d4cc", "escuro": "#2c2c2a"}
NEUTRO = {"claro": "#f0efec", "escuro": "#383835"}

SEQUENCIAL_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


@dataclass(frozen=True)
class ParDivergente:
    chave: str
    rotulo: str
    claro: tuple[str, str]
    escuro: tuple[str, str]


PARES_DIVERGENTES = {
    p.chave: p for p in (
        ParDivergente("azul_laranja", "Azul × laranja", ("#2a78d6", "#eb6834"), ("#3987e5", "#d95926")),
        ParDivergente("azul_vermelho", "Azul × vermelho", ("#2a78d6", "#e34948"), ("#3987e5", "#e66767")),
        ParDivergente("violeta_verde", "Violeta × verde-água", ("#6250d6", "#1baf7a"), ("#9085e9", "#199e70")),
    )
}


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def misturar(cor: str, com: str, t: float) -> str:
    """Interpola em RGB: t=0 → `cor`, t=1 → `com`."""
    a, b = _hex_rgb(cor), _hex_rgb(com)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def escala_divergente(cor_a: str, cor_b: str, neutro: str, passos: int = 4) -> list[list]:
    """Escala Plotly: A (0) → neutro (0,5) → B (1), simétrica e contínua."""
    escala = []
    for i in range(passos + 1):  # braço A
        escala.append([0.5 * i / passos, misturar(cor_a, neutro, i / passos)])
    for i in range(1, passos + 1):  # braço B
        escala.append([0.5 + 0.5 * i / passos, misturar(neutro, cor_b, i / passos)])
    return escala


def escala_do_candidato(cor: str, modo: str = "claro") -> list[list]:
    """Sequencial de um só matiz com a cor do candidato (a mesma do ranking).

    Claro (quase o fundo) → cor do candidato (meio) → versão escurecida (máximo).
    """
    fundo = "#ffffff" if modo == "claro" else "#1a1a19"
    # Mínimo tingido (0,80, não branco puro) para não se confundir com "sem dado" (branco vazado).
    return [[0.0, misturar(cor, fundo, 0.80)], [0.5, cor], [1.0, misturar(cor, "#000000", 0.45)]]


def escala_sequencial() -> list[list]:
    n = len(SEQUENCIAL_AZUL) - 1
    return [[i / n, c] for i, c in enumerate(SEQUENCIAL_AZUL)]


# ---- Cargos proporcionais (deputados) ----
# Não eleitos (inclui suplentes): uma única cor neutra. Eleitos: cor do partido, com
# tons diferentes para eleitos do mesmo partido. Até 8 partidos com cor própria
# (paleta categórica completa, validada em pares adjacentes para barras); a partir do
# 9º, "outros partidos" em cinza-escuro — distinto do cinza-claro dos não eleitos.
NAO_ELEITO = {"claro": "#d3d1ca", "escuro": "#4a4944"}
OUTROS_PARTIDOS = {"claro": "#6f6d66", "escuro": "#a3a19a"}
TONS = [0.0, 0.35, -0.30, 0.55, -0.45, 0.70, -0.55]  # >0 clareia, <0 escurece


def tom(cor: str, t: float) -> str:
    return misturar(cor, "#ffffff", t) if t >= 0 else misturar(cor, "#000000", -t)


def cores_partidos_proporcional(ordem_partidos: list[str], modo: str, fixas: dict[str, str]) -> dict[str, str]:
    """Cor por partido (ordem estável), respeitando cores fixas do usuário.

    Aqui o critério contra as cores fixas é só visão normal (ΔE ≥ 15): nas barras e
    tabelas de deputados o nome e o partido estão sempre escritos (codificação
    secundária), e exigir também o critério de daltonismo deixava 5+ partidos cinza.
    """
    usadas = [fixas[p] for p in ordem_partidos if p in fixas]
    livres = [c for c in CATEGORICA_COMPLETA[modo] if c not in usadas and all(delta_e(c, u) >= 15 for u in usadas)]
    out, i = {}, 0
    for p in ordem_partidos:
        if p in fixas:
            out[p] = fixas[p]
        elif i < len(livres):
            out[p], i = livres[i], i + 1
        else:
            out[p] = OUTROS_PARTIDOS[modo]
    return out


def cores_eleitos(eleitos: list[tuple[str, str]], cores_partido: dict[str, str], modo: str) -> dict[str, str]:
    """`eleitos`: (SQ_CANDIDATO, SG_PARTIDO) em ordem de votos. Mesmo partido → tons distintos."""
    contagem: dict[str, int] = {}
    out = {}
    for sq, p in eleitos:
        k = contagem.get(p, 0)
        contagem[p] = k + 1
        out[sq] = tom(cores_partido.get(p, OUTROS_PARTIDOS[modo]), TONS[k % len(TONS)])
    return out


def _oklab(h: str) -> tuple[float, float, float]:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in _hex_rgb(h))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def delta_e(a: str, b: str) -> float:
    """Distância OKLab × 100 (mesma escala do validador de paletas)."""
    return 100 * sum((x - y) ** 2 for x, y in zip(_oklab(a), _oklab(b))) ** 0.5


# Simulação de daltonismo (Machado et al. 2009, severidade 1,0), em RGB linear.
_CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
}


def _simular(h: str, tipo: str) -> str:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def gam(c):
        c = min(max(c, 0.0), 1.0)
        return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    rgb = [lin(x) for x in _hex_rgb(h)]
    out = [sum(m * v for m, v in zip(linha, rgb)) for linha in _CVD[tipo]]
    return "#" + "".join(f"{round(gam(c) * 255):02x}" for c in out)


def distintas(a: str, b: str) -> bool:
    """Critérios do validador: visão normal ΔE ≥ 15 e protan/deutan ΔE ≥ 8."""
    return delta_e(a, b) >= 15 and all(delta_e(_simular(a, t), _simular(b, t)) >= 8 for t in _CVD)


# Paleta completa, em ordem, de onde saem cores quando há cores fixas de partido.
CATEGORICA_COMPLETA = {
    "claro": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "escuro": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}
MAX_CORES_MAPA = 3  # limite do teste "todos os pares" para mapas coropléticos


def _config_cores() -> dict:
    import tomllib
    from src.config import RAIZ
    arq = RAIZ / "config" / "cores_partidos.toml"
    return tomllib.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def cores_partidos(modo: str) -> dict[str, str]:
    """Cores fixas por partido definidas pelo usuário em config/cores_partidos.toml."""
    return {k: v for k, v in _config_cores().get(modo, {}).items() if isinstance(v, str)}


def cores_candidatos(modo: str) -> dict[str, str]:
    """Cores fixas por candidato: chave 'Cargo:numero[:UF]' → cor (definidas pelo usuário)."""
    return dict(_config_cores().get("candidatos", {}).get(modo, {}))


def chave_candidato(ds_cargo: str, nr_candidato: str, sg_ue: str) -> list[str]:
    """Chaves aceitas na configuração, da mais específica à mais geral."""
    return [f"{ds_cargo}:{nr_candidato}:{sg_ue}", f"{ds_cargo}:{nr_candidato}"]


def atribuir_com_fixas(ordem_candidatos: list[str], paleta: str, modo: str,
                       fixa_de: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Como `atribuir_lideranca`, mas com cor fixa já resolvida por candidato.

    `fixa_de`: SQ_CANDIDATO → cor escolhida pelo usuário (candidato ou partido).
    Uma cor fixa indistinguível de outra já aceita é descartada (o candidato
    volta para a paleta) e gera um aviso. Na paleta padrão, "indistinguível" é só
    visão normal (ΔE < 15): a escolha do usuário prevalece. Na paleta de
    daltonismo vale também o critério protan/deutan. Retorna (cores, avisos).
    """
    compativeis = distintas if paleta == "daltonismo" else (lambda a, b: delta_e(a, b) >= 15)
    aceitas: dict[str, str] = {}
    avisos = []
    for sq in ordem_candidatos:
        cor = fixa_de.get(sq)
        if cor is None:
            continue
        conflito = next((o for o, c in aceitas.items() if not compativeis(cor, c)), None)
        if conflito is None:
            aceitas[sq] = cor
        else:
            avisos.append((sq, conflito))
    if not aceitas:  # sem cores fixas: paleta validada, na ordem
        base = LIDERANCA[paleta][modo]
        return {sq: (base[i] if i < len(base) else OUTROS[modo]) for i, sq in enumerate(ordem_candidatos)}, avisos
    candidatas = list(dict.fromkeys(LIDERANCA[paleta][modo] + CATEGORICA_COMPLETA[modo]))
    out = dict(aceitas)
    for sq in ordem_candidatos:
        if sq in out:
            continue
        usadas = set(out.values())
        cor = None
        if len(usadas) < MAX_CORES_MAPA:
            cor = next((c for c in candidatas if c not in usadas and all(distintas(c, u) for u in usadas)), None)
        out[sq] = cor or OUTROS[modo]
    return {sq: out[sq] for sq in ordem_candidatos}, avisos


def atribuir_lideranca(ordem_candidatos: list[str], paleta: str, modo: str,
                       partido_de: dict[str, str] | None = None,
                       fixas: dict[str, str] | None = None) -> dict[str, str]:
    """Cor por candidato segundo uma ordem ESTÁVEL da disputa (não a da tela).

    `ordem_candidatos`: SQ_CANDIDATO ordenados por votos no 1º turno da disputa.
    `fixas`: sigla → cor escolhida pelo usuário (tem prioridade). Sem cores
    fixas, vale a paleta validada. Com cores fixas, os demais candidatos recebem,
    em ordem, cores da paleta (depois da paleta completa) que sejam `distintas`
    de TODAS as cores já em uso, até MAX_CORES_MAPA cores; o resto vira "Outros".
    """
    partido_de = partido_de or {}
    fixas = fixas or {}
    em_uso = [fixas[partido_de[sq]] for sq in ordem_candidatos[:MAX_CORES_MAPA] if partido_de.get(sq) in fixas]
    if not em_uso:
        base = LIDERANCA[paleta][modo]
        return {sq: (base[i] if i < len(base) else OUTROS[modo]) for i, sq in enumerate(ordem_candidatos)}

    candidatas = list(dict.fromkeys(LIDERANCA[paleta][modo] + CATEGORICA_COMPLETA[modo]))
    out = {}
    for sq in ordem_candidatos:
        if partido_de.get(sq) in fixas and fixas[partido_de[sq]] in em_uso:
            out[sq] = fixas[partido_de[sq]]
            continue
        cor = None
        if len(set(out.values()) | set(em_uso)) < MAX_CORES_MAPA:
            cor = next((c for c in candidatas if c not in em_uso and c not in out.values()
                        and all(distintas(c, u) for u in set(out.values()) | set(em_uso))), None)
        out[sq] = cor or OUTROS[modo]
    return out
