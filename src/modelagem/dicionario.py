"""Dicionário dos campos usados pelo painel (origem TSE, descrição conforme o leiame)."""
from __future__ import annotations

# (campo, tabela do modelo, descrição, origem)
CAMPOS = [
    ("NR_TURNO", "fatos e agregados", "Turno da eleição (1 ou 2).", "TSE · todos os arquivos de resultado"),
    ("CD_CARGO / DS_CARGO", "fatos, dim_cargo", "Código e nome do cargo.", "TSE"),
    ("SG_UF", "fatos e agregados", "UF de ocorrência da votação; ZZ = exterior.", "TSE"),
    ("SG_UE", "dim_candidato, dim_circunscricao", "Circunscrição da disputa: BR (presidente) ou a UF.", "TSE"),
    ("CD_MUNICIPIO", "fatos", "Código TSE do município, normalizado para 5 dígitos.", "TSE (normalizado)"),
    ("CD_MUNICIPIO_IBGE", "dim_municipio", "Código IBGE (7 dígitos) via tabela oficial TSE–IBGE.", "TSE · municipio_tse_ibge"),
    ("NR_ZONA", "fatos", "Zona eleitoral (inteiro).", "TSE (normalizado)"),
    ("QT_APTOS", "fato_apuracao", "Eleitoras e eleitores aptos a votar para o cargo.", "TSE · detalhe da apuração"),
    ("QT_COMPARECIMENTO", "fato_apuracao", "Eleitores que compareceram.", "TSE · detalhe da apuração"),
    ("QT_ABSTENCOES", "fato_apuracao", "Aptos que não compareceram.", "TSE · detalhe da apuração"),
    ("QT_ELEITORES_SECOES_NAO_INSTALADAS", "fato_apuracao",
     "Eleitores de seções não instaladas (não entram em comparecimento nem abstenção).", "TSE · detalhe da apuração"),
    ("QT_VOTOS", "fato_apuracao", "Total de votos do cargo (no Senado 2026, 2 × comparecimento).", "TSE · detalhe da apuração"),
    ("QT_VOTOS_CONCORRENTES", "fato_apuracao", "Válidos + anulados + anulados sub judice (base do % oficial do TSE).",
     "TSE · detalhe da apuração"),
    ("QT_TOTAL_VOTOS_VALIDOS", "fato_apuracao", "Votos válidos (nominais + legenda) — denominador do % do painel.",
     "TSE · detalhe da apuração"),
    ("QT_VOTOS_NOMINAIS_VALIDOS", "fato_apuracao, fato_nominal", "Votos nominais válidos.", "TSE"),
    ("QT_TOTAL_VOTOS_LEG_VALIDOS", "fato_apuracao, fato_partido", "Votos de legenda válidos (inclui nominais "
     "convertidos em legenda).", "TSE"),
    ("QT_VOTOS_BRANCOS", "fato_apuracao", "Votos em branco.", "TSE · detalhe da apuração"),
    ("QT_TOTAL_VOTOS_NULOS", "fato_apuracao", "Votos nulos, incluindo nulos técnicos.", "TSE · detalhe da apuração"),
    ("QT_TOTAL_VOTOS_ANUL_SUBJUD", "fato_apuracao", "Votos anulados sub judice (recurso pendente).", "TSE"),
    ("SQ_CANDIDATO", "fato_nominal, dim_candidato", "Identificador interno da candidatura (texto).", "TSE"),
    ("NM_URNA_CANDIDATO", "dim_candidato", "Nome de urna.", "TSE"),
    ("NM_TIPO_DESTINACAO_VOTOS", "fato_nominal", "Válido, Válido (legenda), Anulado, Anulado sub judice.", "TSE"),
    ("DS_SIT_TOT_TURNO_1 / _2", "dim_candidato", "Situação oficial de totalização em cada turno (ELEITO, ELEITO POR "
     "QP, ELEITO POR MÉDIA, 2º TURNO, SUPLENTE, NÃO ELEITO).", "TSE"),
    ("SITUACAO_FINAL / TURNO_ELEICAO", "dim_candidato", "Situação no último turno disputado e turno em que se elegeu.",
     "Derivado da situação oficial"),
    ("NR_PARTIDO / SG_PARTIDO", "dim_partido", "Número e sigla do partido.", "TSE"),
    ("NR_FEDERACAO / NM_FEDERACAO", "dim_federacao", "Federação partidária (a sigla do TSE tem grafias divergentes; "
     "o painel usa o nome).", "TSE"),
    ("QT_VAGA", "dim_circunscricao", "Vagas oficiais do cargo na circunscrição.", "TSE · consulta_vagas"),
    ("VOTOS_POR_ELEITOR", "dim_cargo", "Votos por eleitor no cargo, derivado de QT_VOTOS ÷ QT_COMPARECIMENTO "
     "(Senado 2026 = 2).", "Derivado"),
    ("ESTADO (disponibilidade)", "disponibilidade", "disponível, não houve 2º turno, cargo sem 2º turno, dados "
     "indisponíveis, sem disputa na UF.", "Derivado dos dados"),
    ("ESTADO_JUNCAO", "dim_municipio", "associado, exterior, sem correspondência, sem geometria, UF divergente.",
     "Derivado (junção TSE–IBGE)"),
    ("PAIS / ISO3", "config/exterior_paises.csv", "País da cidade do exterior — classificação auxiliar revisável, "
     "não publicada pelo TSE.", "Tabela auxiliar do projeto"),
]
