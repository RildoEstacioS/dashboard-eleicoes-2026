# Relatório de qualidade do modelo

Gerado em 2026-10-28T03:08:46-03:00.

## Granularidade e chaves

| tabela | linhas | duplicadas na granularidade | nulos nas chaves | resultado |
|---|---|---|---|---|
| fato_apuracao | 37,521 | 0 | 0 | OK |
| fato_nominal | 6,748,427 | 0 | 0 | OK |
| fato_partido | 482,360 | 0 | 0 | OK |
| dim_eleicao | 4 | 0 | 0 | OK |
| dim_cargo | 6 | 0 | 0 | OK |
| dim_circunscricao | 109 | 0 | 0 | OK |
| dim_candidato | 18,842 | 0 | 0 | OK |
| dim_partido | 30 | 0 | 0 | OK |
| dim_federacao | 5 | 0 | 0 | OK |
| dim_uf | 27 | 0 | 0 | OK |
| dim_municipio | 5,757 | 0 | 0 | OK |
| disponibilidade | 218 | 0 | 0 | OK |
| apuracao_municipio | 34,267 | 0 | 0 | OK |
| apuracao_uf | 170 | 0 | 0 | OK |
| nominal_municipio | 5,976,001 | 0 | 0 | OK |
| nominal_uf | 19,234 | 0 | 0 | OK |
| partido_municipio | 436,957 | 0 | 0 | OK |
| partido_uf | 1,997 | 0 | 0 | OK |

## Casos especiais

| caso | quantidade | tratamento |
|---|---|---|
| Municípios × cargo × turno com zero votos válidos (estado 'sem votos', não empate) | 83 |  |
| Candidatos com votos só anulados sub judice (0 válidos) | 486 | Exibidos com votos válidos = 0; votos anulados aparecem à parte. |
| Linhas de votação com destinação 'Válido (legenda)' | 88 | Votos nominais convertidos em legenda por decisão judicial; contam nos válidos do partido. |
| Zonas com linhas de partido repetidas por SQ_COLIGACAO (federações) | 1,889 | Valores aditivos; agregados por partido somam as linhas (conferido contra o detalhe). |
| Zonas do exterior (SG_UF = ZZ) | 372 | Só presidente. |
| Candidatos (titulares) sem situação de totalização | 0 |  |
| Circunscrições sem vagas oficiais | 0 |  |
| Eleitos ≠ vagas (circunscrições) | 0 | Deve ser 0. |

## Disponibilidade das disputas

| cargo | turno | estado | circunscrições |
|---|---|---|---|
| Deputado Distrital | 1 | disponivel | 1 |
| Deputado Distrital | 2 | turno_nao_aplicavel | 1 |
| Deputado Estadual | 1 | disponivel | 26 |
| Deputado Estadual | 2 | turno_nao_aplicavel | 26 |
| Deputado Federal | 1 | disponivel | 27 |
| Deputado Federal | 2 | turno_nao_aplicavel | 27 |
| Governador | 1 | disponivel | 27 |
| Governador | 2 | disponivel | 6 |
| Governador | 2 | nao_houve_segundo_turno | 21 |
| Presidente | 1 | disponivel | 1 |
| Presidente | 2 | disponivel | 1 |
| Senador | 1 | disponivel | 27 |
| Senador | 2 | turno_nao_aplicavel | 27 |
