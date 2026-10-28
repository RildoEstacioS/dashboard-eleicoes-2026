# Modelo de dados e regras de cálculo

Gerado por `python -m scripts.preparar_dados modelar` a partir da camada
Parquet bruta (`data/processed/bruto/`, fiel aos CSVs `_BRASIL` do TSE).

## Camadas

| Camada | Pasta | Conteúdo |
|---|---|---|
| Bruta | `data/raw/` | ZIPs oficiais, inalterados (hash no manifesto) |
| Bruta tabular | `data/processed/bruto/` | Parquet com as mesmas linhas e colunas do CSV, tudo como texto |
| Modelo | `data/processed/modelo/` | Dimensões e fatos tipados, chaves normalizadas |
| Agregados | `data/processed/agregados/` | Somas por município e UF usadas pela interface |

## Tabelas e granularidade

Granularidade = conjunto de colunas que identifica uma linha. É verificada a
cada execução (zero duplicatas e zero nulos; ver `docs/relatorios/qualidade_modelo.md`).

| Tabela | Uma linha por… | Observações |
|---|---|---|
| `fato_apuracao` | turno × cargo × UF × município × zona | Eleitorado, comparecimento, abstenção, válidos, brancos, nulos, anulados. **Única fonte de eleitorado e denominadores.** |
| `fato_nominal` | turno × cargo × UF × município × zona × candidato | `QT_VOTOS_NOMINAIS` (todos) e `QT_VOTOS_NOMINAIS_VALIDOS`; `NM_TIPO_DESTINACAO_VOTOS` e `VOTO_VALIDO` |
| `fato_partido` | turno × cargo × UF × município × zona × partido × `SQ_COLIGACAO` | Em federações, um partido pode ter duas linhas na mesma zona (uma zerada); os valores são aditivos |
| `dim_eleicao` | `CD_ELEICAO` | Um código por eleição e turno (federal/estadual × 1º/2º) |
| `dim_cargo` | `CD_CARGO` | `VOTOS_POR_ELEITOR` derivado de `QT_VOTOS ÷ QT_COMPARECIMENTO` (exige razão inteira); `SISTEMA` derivado da existência de "ELEITO POR QP/MÉDIA" |
| `dim_circunscricao` | cargo × `SG_UE` (BR ou UF) | `QT_VAGA` de `consulta_vagas` |
| `dim_candidato` | `SQ_CANDIDATO` | Situação oficial no 1º e 2º turno, `SITUACAO_FINAL`, `TURNO_ELEICAO`. Sem CPF, e-mail, título ou nascimento |
| `dim_partido` | `NR_PARTIDO` | |
| `dim_federacao` | `NR_FEDERACAO` | Rótulo pelo nome; `SG_FEDERACAO` tem grafias divergentes no TSE (todas guardadas) |
| `dim_uf` | `SG_UF` | 27 UFs; exterior (ZZ) não é UF |
| `dim_municipio` | UF × `CD_MUNICIPIO` (TSE) | Código IBGE, região e estado da junção (inclui exterior) |
| `disponibilidade` | cargo × circunscrição × turno | Estado da disputa (abaixo) |
| `apuracao_municipio` / `apuracao_uf` | turno × cargo × UF (× município) | Somas de `fato_apuracao` |
| `nominal_municipio` / `nominal_uf` | … × candidato | `VOTOS_VALIDOS`, `VOTOS_ANUL_SUBJUD`, `VOTOS_ANULADOS` |
| `partido_municipio` / `partido_uf` | … × partido | Somas sobre `SQ_COLIGACAO` |

Região e Brasil são obtidos somando UFs na consulta. O total de presidente no
Brasil inclui o exterior (ZZ); um mapa de regiões não inclui.

A conservação dos totais (zona → município → UF) é conferida a cada execução.

## Disponibilidade das disputas

Calculada para cada cargo × circunscrição × turno, só com os dados:

| Estado | Regra | Exemplo 2026 (resultado da execução) |
|---|---|---|
| `disponivel` | Há registros do cargo, da circunscrição e do turno com comparecimento > 0 | Presidente 1º e 2º turno; Governador 2º turno em AC, AM, DF, ES, RN, TO |
| `nao_houve_segundo_turno` | Cargo admite 2º turno e o 1º turno terminou com eleito | Governador 2º turno nas outras 21 UFs |
| `turno_nao_aplicavel` | Cargo sem 2º turno pela regra legal (leiame: majoritário exceto Senador) | Senado e deputados, 2º turno |
| `dados_indisponiveis` | 1º turno indicou "2º TURNO", mas faltam registros do 2º turno | Nenhum caso |
| `circunscricao_inexistente` | Cargo não disputado na UF | Deputado Estadual no DF |

A única regra fixa em código é a legal (quais cargos admitem 2º turno),
documentada em `src/modelagem/vocabulario.py`. UFs e candidatos nunca são fixados.

## Situação oficial

`DS_SIT_TOT_TURNO` é classificada em: `eleito` (ELEITO, ELEITO POR QP,
ELEITO POR MÉDIA), `segundo_turno`, `suplente`, `nao_eleito` e `sem_situacao`.
Se o TSE publicar um valor novo, a construção do modelo **falha**, em vez de
classificar em silêncio.

- "Eleito" vem sempre da situação oficial. Liderança territorial é "mais votado
  no território".
- Deputados: eleitos = QP + média, conferido contra as vagas de cada UF.
- Senado 2026: dois eleitos por UF, conferido contra `consulta_vagas`.

## Regras de cálculo

| Métrica | Fórmula | Denominador |
|---|---|---|
| % do candidato sobre válidos | votos nominais válidos ÷ `QT_TOTAL_VOTOS_VALIDOS` do cargo no território | Apuração oficial, **independente do filtro de candidatos** |
| % oficial do TSE (relatório) | votos computados ÷ `QT_VOTOS_CONCORRENTES` | Válidos + anulados sub judice. Igual ao anterior quando não há sub judice |
| Margem A × B (p.p.) | 100 × (A − B) ÷ válidos do cargo no território | Válidos do cargo |
| Participação no par | A ÷ (A + B) | Só os dois candidatos; não é % dos válidos |
| Comparecimento | `QT_COMPARECIMENTO ÷ QT_APTOS` | Eleitorado apto **do próprio cargo** |
| Abstenção | `QT_ABSTENCOES ÷ QT_APTOS` | Idem |
| Brancos | `QT_VOTOS_BRANCOS ÷ QT_VOTOS` | Total de votos do cargo (no Senado, 2 × comparecimento) |
| Nulos | `QT_TOTAL_VOTOS_NULOS ÷ QT_VOTOS` | Idem; inclui nulos técnicos |

Regras gerais (`src/metricas/indicadores.py`):

- **Agregar primeiro, dividir depois.** Nunca média de percentuais.
- **Denominador 0** → sem percentual, estado `sem_votos`. Não é empate nem 0 %.
  Em 2026, os 83 casos de município × cargo × turno com zero válidos são todos
  localidades do exterior com seção não instalada.
- **Território sem registro** → `sem_dado`.
- **Empate na liderança** → estado `empate`, sem líder atribuído.
- **Eleitorado depende do cargo**: presidente inclui eleitores que só votam
  para presidente; nunca somar eleitorado entre cargos.
- **Votos anulados** (`Anulado`, `Anulado sub judice`) não entram nos válidos.
  São mostrados à parte. 486 candidatos têm só votos anulados sub judice.

## Validação

| Verificação | Onde | Resultado (28/10/2026) |
|---|---|---|
| 11 identidades contábeis entre CSVs | `docs/relatorios/consistencia.md` | 0 violações |
| Granularidade e chaves de 18 tabelas | `docs/relatorios/qualidade_modelo.md` | 0 duplicatas, 0 nulos |
| Conservação de totais nas agregações | `agregados.construir()` | OK |
| Confronto com o Relatório de Totalização (PDF) do ES, todos os cargos e turnos | `docs/relatorios/validacao_totalizacao.md` | 541 candidatos: 0 divergências de votos, situação ou %; eleitorado, abstenção e válidos idênticos |
| Idem, Presidente Brasil, dois turnos | idem | 14 candidatos: 0 divergências |
