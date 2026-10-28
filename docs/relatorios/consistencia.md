# Verificações contábeis entre arquivos oficiais

Gerado em 2026-10-28T02:31:22-03:00. Chaves territoriais normalizadas (`src/tratamento/chaves.py`).

| verificação | grupo | violações | linhas/chaves | resultado |
|---|---|---|---|---|
| chave_unica_detalhe | todos | 0 | 37521 | OK |
| chave_unica_candidato | todos | 0 | 6748427 | OK |
| aptos_comparecimento_abstencao | todos | 0 | 37521 | OK |
| votos_por_eleitor | Presidente | 0 | 12584 | OK |
| votos_por_eleitor | Senador | 0 | 6106 | OK |
| votos_por_eleitor | Governador | 0 | 6619 | OK |
| votos_por_eleitor | Deputado Federal | 0 | 6106 | OK |
| votos_por_eleitor | Deputado Estadual | 0 | 6087 | OK |
| votos_por_eleitor | Deputado Distrital | 0 | 19 | OK |
| composicao_votos | Presidente | 0 | 12584 | OK |
| composicao_votos | Senador | 0 | 6106 | OK |
| composicao_votos | Governador | 0 | 6619 | OK |
| composicao_votos | Deputado Federal | 0 | 6106 | OK |
| composicao_votos | Deputado Estadual | 0 | 6087 | OK |
| composicao_votos | Deputado Distrital | 0 | 19 | OK |
| validos_nominais_legenda | Presidente | 0 | 12584 | OK |
| validos_nominais_legenda | Senador | 0 | 6106 | OK |
| validos_nominais_legenda | Deputado Estadual | 0 | 6087 | OK |
| validos_nominais_legenda | Governador | 0 | 6619 | OK |
| validos_nominais_legenda | Deputado Federal | 0 | 6106 | OK |
| validos_nominais_legenda | Deputado Distrital | 0 | 19 | OK |
| nominais_candidato_vs_detalhe | Presidente T2 | 0 | 6292 | OK |
| nominais_candidato_vs_detalhe | Presidente T1 | 0 | 6292 | OK |
| nominais_candidato_vs_detalhe | Governador T1 | 0 | 6106 | OK |
| nominais_candidato_vs_detalhe | Senador T1 | 0 | 6106 | OK |
| nominais_candidato_vs_detalhe | Deputado Estadual T1 | 0 | 6087 | OK |
| nominais_candidato_vs_detalhe | Governador T2 | 0 | 513 | OK |
| nominais_candidato_vs_detalhe | Deputado Federal T1 | 0 | 6106 | OK |
| nominais_candidato_vs_detalhe | Deputado Distrital T1 | 0 | 19 | OK |
| subjudice_candidato_vs_detalhe | Presidente T1 | 0 | 6292 | OK |
| subjudice_candidato_vs_detalhe | Deputado Estadual T1 | 0 | 6087 | OK |
| subjudice_candidato_vs_detalhe | Governador T2 | 0 | 513 | OK |
| subjudice_candidato_vs_detalhe | Presidente T2 | 0 | 6292 | OK |
| subjudice_candidato_vs_detalhe | Deputado Federal T1 | 0 | 6106 | OK |
| subjudice_candidato_vs_detalhe | Deputado Distrital T1 | 0 | 19 | OK |
| subjudice_candidato_vs_detalhe | Senador T1 | 0 | 6106 | OK |
| subjudice_candidato_vs_detalhe | Governador T1 | 0 | 6106 | OK |
| legenda_partido_vs_detalhe | Deputado Federal T1 | 0 | 6106 | OK |
| legenda_partido_vs_detalhe | Deputado Estadual T1 | 0 | 6087 | OK |
| legenda_partido_vs_detalhe | Presidente T1 | 0 | 6292 | OK |
| legenda_partido_vs_detalhe | Presidente T2 | 0 | 6292 | OK |
| legenda_partido_vs_detalhe | Deputado Distrital T1 | 0 | 19 | OK |
| legenda_partido_vs_detalhe | Governador T2 | 0 | 513 | OK |
| legenda_partido_vs_detalhe | Senador T1 | 0 | 6106 | OK |
| legenda_partido_vs_detalhe | Governador T1 | 0 | 6106 | OK |
| nominais_partido_vs_detalhe | Presidente T1 | 0 | 6292 | OK |
| nominais_partido_vs_detalhe | Deputado Distrital T1 | 0 | 19 | OK |
| nominais_partido_vs_detalhe | Deputado Federal T1 | 0 | 6106 | OK |
| nominais_partido_vs_detalhe | Presidente T2 | 0 | 6292 | OK |
| nominais_partido_vs_detalhe | Deputado Estadual T1 | 0 | 6087 | OK |
| nominais_partido_vs_detalhe | Governador T2 | 0 | 513 | OK |
| nominais_partido_vs_detalhe | Senador T1 | 0 | 6106 | OK |
| nominais_partido_vs_detalhe | Governador T1 | 0 | 6106 | OK |
| situacao_constante | todos | 0 | 18856 | OK |

## Descrição das verificações

- **chave_unica_detalhe**: Detalhe: uma linha por turno × cargo × UF × município × zona
- **chave_unica_candidato**: Votação nominal: uma linha por chave territorial × SQ_CANDIDATO
- **aptos_comparecimento_abstencao**: QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES + QT_ELEITORES_SECOES_NAO_INSTALADAS
- **votos_por_eleitor**: QT_VOTOS = QT_COMPARECIMENTO × votos por eleitor (2 para Senador em 2026; 1 nos demais)
- **composicao_votos**: QT_VOTOS = válidos + brancos + total nulos + anulados + anulados sub judice + anulados apurados em separado
- **validos_nominais_legenda**: QT_TOTAL_VOTOS_VALIDOS = QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS
- **nominais_candidato_vs_detalhe**: Σ QT_VOTOS_NOMINAIS_VALIDOS (votação nominal) = QT_VOTOS_NOMINAIS_VALIDOS (detalhe), por chave
- **subjudice_candidato_vs_detalhe**: Σ QT_VOTOS_NOMINAIS com destinação 'Anulado sub judice' = QT_VOTOS_NOMINAIS_ANUL_SUBJUD (detalhe)
- **legenda_partido_vs_detalhe**: Σ QT_TOTAL_VOTOS_LEG_VALIDOS (votação em partido) = QT_TOTAL_VOTOS_LEG_VALIDOS (detalhe), por chave
- **nominais_partido_vs_detalhe**: Σ QT_VOTOS_NOMINAIS_VALIDOS (votação em partido) = QT_VOTOS_NOMINAIS_VALIDOS (detalhe), por chave
- **situacao_constante**: Cada candidato tem uma única DS_SIT_TOT_TURNO por turno
