"""Vocabulário oficial do TSE e regras legais usadas na modelagem.

Aqui ficam apenas classificações de valores publicados pelo TSE e regras da
legislação descritas no leiame — nunca resultados (candidatos, eleitos, UFs).
Valores desconhecidos não são classificados silenciosamente: a validação falha.
"""
from __future__ import annotations

# DS_SIT_TOT_TURNO → categoria analítica.
SITUACAO_TOTALIZACAO = {
    "ELEITO": "eleito",
    "ELEITO POR QP": "eleito",
    "ELEITO POR MÉDIA": "eleito",
    "2º TURNO": "segundo_turno",
    "SUPLENTE": "suplente",
    "NÃO ELEITO": "nao_eleito",
    "#NULO": "sem_situacao",
}

# NM_TIPO_DESTINACAO_VOTOS → o voto entra nos válidos?
DESTINACAO_VALIDA = {
    "Válido": True,
    "Válido (legenda)": True,   # nominal convertido em legenda por decisão judicial
    "Anulado": False,
    "Anulado sub judice": False,
}

# Regra legal (leiame do TSE, campo NR_TURNO): só há 2º turno no sistema
# majoritário, exceto Senador. Em eleições gerais: Presidente e Governador.
# Identificado pelo nome oficial do cargo (DS_CARGO), não por resultado.
CARGOS_SEGUNDO_TURNO_POSSIVEL = {"Presidente", "Governador"}

# Estados de uma combinação cargo × circunscrição × turno.
DISPONIVEL = "disponivel"
NAO_HOUVE_SEGUNDO_TURNO = "nao_houve_segundo_turno"
TURNO_NAO_APLICAVEL = "turno_nao_aplicavel"
DADOS_INDISPONIVEIS = "dados_indisponiveis"
CIRCUNSCRICAO_INEXISTENTE = "circunscricao_inexistente"

ROTULOS_ESTADO = {
    DISPONIVEL: "Dados disponíveis",
    NAO_HOUVE_SEGUNDO_TURNO: "Não houve segundo turno",
    TURNO_NAO_APLICAVEL: "Cargo sem segundo turno",
    DADOS_INDISPONIVEIS: "Dados indisponíveis",
    CIRCUNSCRICAO_INEXISTENTE: "Não há disputa deste cargo nesta UF",
}
