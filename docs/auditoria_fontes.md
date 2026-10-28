# Auditoria de fontes — Etapa 1

Auditoria realizada em 28/10/2026 consultando diretamente a API CKAN do TSE
(`package_show`, `package_search`), os arquivos da CDN do TSE, a API de Malhas
v3 do IBGE e o FTP de geociências do IBGE. Relatórios gerados automaticamente:

- `docs/relatorios/auditoria_layout.md` — colunas, contagens e perfil de cada arquivo.
- `docs/relatorios/consistencia.md` — identidades contábeis entre arquivos.
- `docs/relatorios/juncao_tse_ibge.md` — junção territorial.
- `docs/relatorios/geografia_medicoes.json` — medições das malhas.

## Matriz fonte → recurso → granularidade → campos → finalidade

| Fonte | Recurso (chave no projeto) | Granularidade (uma linha por…) | Campos usados | Finalidade |
|---|---|---|---|---|
| TSE · resultados-2026 | `detalhe_munzona` | turno × cargo × UF × município × zona | `QT_APTOS`, `QT_COMPARECIMENTO`, `QT_ABSTENCOES`, `QT_ELEITORES_SECOES_NAO_INSTALADAS`, `QT_VOTOS`, `QT_VOTOS_CONCORRENTES`, `QT_TOTAL_VOTOS_VALIDOS`, `QT_VOTOS_NOMINAIS_VALIDOS`, `QT_TOTAL_VOTOS_LEG_VALIDOS`, `QT_VOTOS_BRANCOS`, `QT_TOTAL_VOTOS_NULOS`, `QT_VOTOS_NULOS`, `QT_VOTOS_NULOS_TECNICOS`, `QT_TOTAL_VOTOS_ANULADOS`, `QT_TOTAL_VOTOS_ANUL_SUBJUD`, `QT_VOTOS_ANULADOS_APU_SEP`, `DT_ULTIMA_TOTALIZACAO` | Participação, denominadores, brancos/nulos, validação |
| TSE · resultados-2026 | `votacao_candidato_munzona` | turno × cargo × UF × município × zona × candidato (`SQ_CANDIDATO`) | `SQ_CANDIDATO`, `NR_CANDIDATO`, `NM_URNA_CANDIDATO`, `NR_PARTIDO`, `SG_PARTIDO`, `NR_FEDERACAO`, `SQ_COLIGACAO`, `QT_VOTOS_NOMINAIS`, `QT_VOTOS_NOMINAIS_VALIDOS`, `NM_TIPO_DESTINACAO_VOTOS`, `DS_SITUACAO_JULGAMENTO`, `DS_SIT_TOT_TURNO` | Votação nominal e situação oficial |
| TSE · resultados-2026 | `votacao_partido_munzona` | turno × cargo × UF × município × zona × partido | `NR_PARTIDO`, `SG_PARTIDO`, `NR_FEDERACAO`, `QT_VOTOS_LEGENDA_VALIDOS`, `QT_VOTOS_NOM_CONVR_LEG_VALIDOS`, `QT_TOTAL_VOTOS_LEG_VALIDOS`, `QT_VOTOS_NOMINAIS_VALIDOS` | Votos de legenda; resumo por partido/federação |
| TSE · candidatos-2026 | `consulta_cand` | candidatura × turno | `SQ_CANDIDATO`, `NM_URNA_CANDIDATO`, `NR_PARTIDO`, `NR_FEDERACAO`, `DS_SIT_TOT_TURNO` | Dimensão candidato (inclui candidatos sem votos e vices/suplentes) |
| TSE · candidatos-2026 | `consulta_vagas` | cargo × UF | `QT_VAGA` | Vagas oficiais (2 por UF no Senado em 2026) |
| TSE · candidatos-2026 | `consulta_coligacao` | coligação/federação × cargo × UF | composição | Rótulos de coligações |
| TSE · códigos oficiais | `municipio_tse_ibge` | município | `CD_MUNICIPIO_TSE`, `CD_MUNICIPIO_IBGE`, `SG_UF`, `CD_UF_IBGE` | Junção TSE → IBGE |
| IBGE · Malha Municipal 2025 (FTP) | `malha_municipios_2025` | polígono municipal (inclui 2 áreas operacionais de lagoas) | `CD_MUN`, `NM_MUN`, `SIGLA_UF`, `CD_UF`, `CD_REGIAO` | Mapas municipais; UF e regiões por dissolução |

Fora do MVP (expansões possíveis, já identificadas no portal): votação e detalhe
por seção (`votacao_secao_2026_<UF>.zip`, `detalhe_votacao_secao_2026.zip`),
perfil do eleitorado, comparecimento por perfil, prestação de contas, bens,
pesquisas eleitorais e relatórios de totalização em PDF (úteis para conferência
manual).

## Datas e estado de consolidação

| Recurso | Geração na fonte (`DT_GERACAO HH_GERACAO`) | Last-Modified (servidor) |
|---|---|---|
| detalhe_munzona | 27/10/2026 19:32:04 | 27/10/2026 22:46 GMT |
| votacao_candidato_munzona | 27/10/2026 19:32:16 | 27/10/2026 23:11 GMT |
| votacao_partido_munzona | 27/10/2026 19:32:16 | 27/10/2026 22:38 GMT |
| consulta_cand | 27/10/2026 19:30:36 | 27/10/2026 22:35 GMT |
| municipio_tse_ibge | 25/10/2026 09:00:09 | — |

O metadado do pacote CKAN `resultados-2026` diz 08/10/2026, mas os arquivos
foram regerados depois do 2º turno. Por isso o manifesto (`data/manifesto.json`)
guarda as três datas separadamente: download pelo dashboard, `Last-Modified` e
geração informada dentro do arquivo. A fonte não publica um campo explícito de
"estado de consolidação"; o leiame avisa que os arquivos "estão em constante
processo de atualização". O dashboard não anuncia atualização em tempo real.

## Layout (confirmado no leiame e nos dados)

- Encoding Latin-1, `;` como separador, todos os campos entre aspas.
- `#NULO` (texto) / `-1` (número) = em branco; `#NE` / `-3` = não registrado
  naquele ano; `-4` / `NÃO DIVULGÁVEL` = candidato não divulgável.
- `SG_UF` pode valer `ZZ` (exterior); `VT` (voto em trânsito) e `BR` estão
  previstos no leiame. Em 2026, `ST_VOTO_EM_TRANSITO` = `N` em todas as linhas.
- Em 2026, `DS_SITUACAO_CANDIDATURA` é `#NE` (o leiame diz que só se aplica até
  2022). A situação do registro aparece em `DS_SITUACAO_JULGAMENTO`, e o
  destino do voto em `NM_TIPO_DESTINACAO_VOTOS` (`Válido`, `Válido (legenda)`,
  `Anulado`, `Anulado sub judice`).
- Nenhum valor negativo (sentinela) nas colunas `QT_` do detalhe.

## Achados que mudam o desenho do pipeline

1. **Recortes sobrepostos nos ZIPs.** Cada ZIP de resultados traz `_BR`
   (presidente), `_<UF>` (cargos estaduais) e `_BRASIL`. A contagem de linhas
   prova que `_BRASIL` é exatamente a soma dos demais em todos os recursos. O
   pipeline lê **somente** `_BRASIL`.
2. **Chaves sem zeros à esquerda.** Na votação nominal, parte das linhas traz
   `CD_MUNICIPIO`/`NR_ZONA` com 2–4 dígitos. Juntar texto cru perdia 561 zonas
   (MA, PA, AM, RO, AC, AP, RR). As chaves são normalizadas em
   `src/tratamento/chaves.py`; depois disso, todas as identidades fecham.
3. **Eleitorado depende do cargo.** Na mesma zona e turno, `QT_APTOS` difere
   entre cargos em 2.164 chaves no 1º turno. Presidente inclui eleitores
   habilitados a votar só para presidente fora do domicílio, e o exterior (ZZ)
   só vota para presidente. Exemplos no 1º turno: aptos de Presidente
   (exc. ZZ) = 157.828.968; Governador = 157.646.356. **Participação é sempre
   calculada com o eleitorado do próprio cargo**, nunca somando cargos.
4. **Senado: dois votos por eleitor.** `QT_VOTOS` = 2 × `QT_COMPARECIMENTO` em
   todas as linhas de Senador. Percentuais do Senado sobre votos válidos não
   são percentuais de eleitores.
5. **Abstenção no exterior.** `QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES +
   QT_ELEITORES_SECOES_NAO_INSTALADAS`. Em 80 linhas do exterior, com seção não
   instalada, a abstenção oficial é 0 e os eleitores ficam na última parcela.
6. **Federação com sigla inconsistente.** `SG_FEDERACAO` aparece com duas
   grafias para a mesma federação (ex.: `PT/PC do B/PV` e
   `13-PT/65-PC do B/43-PV`). A chave será `NR_FEDERACAO`.
7. **Malha da API do IBGE desatualizada.** A API v3 entrega por padrão uma malha
   sem Boa Esperança do Norte/MT (IBGE 5101837), e `periodo=2023…2025`
   retornou HTTP 500. Fonte adotada: Malha Municipal 2025 do FTP oficial.

## Identidades contábeis verificadas (todas com 0 violações)

Ver `docs/relatorios/consistencia.md`. Em resumo:

- Chaves únicas no detalhe e na votação nominal.
- `QT_VOTOS = válidos + brancos + total nulos + anulados + anulados sub judice + apurados em separado`.
- `QT_TOTAL_VOTOS_VALIDOS = nominais válidos + total de legenda válidos`.
- Σ nominais da votação nominal = nominais do detalhe (por zona, cargo e turno).
- Σ "Anulado sub judice" da votação nominal = sub judice do detalhe.
- Σ legenda da votação em partido = legenda do detalhe.
- Situação de totalização única por candidato e turno, idêntica entre
  votação nominal e cadastro de candidatos (18.856 pares).

## Exterior por país (tabela auxiliar)

O TSE publica a votação no exterior por **cidade** (UF "ZZ", 186 cidades), sem país.
Auditado em 28/10/2026: `perfil_eleitor_secao_2026_ZZ` não tem país;
`eleitorado_local_votacao_2026` tem latitude/longitude vazias (-1) e o campo de bairro
às vezes traz o país ("ESTADOS UNIDOS") e às vezes não ("CENTRO").

Por isso o agrupamento por país usa `config/exterior_paises.csv` (cidade TSE → país
em português + ISO-3, com observações nos casos ambíguos, como Rio Branco/Uruguai e
São José/Costa Rica). É uma **classificação geográfica auxiliar, revisável, não um dado
do TSE**. Os votos são os oficiais. Um teste garante que todas as cidades "ZZ" têm país
e que os totais por país fecham com o total do exterior.

## Unidades especiais e tratamento

| Unidade | Como aparece | Tratamento |
|---|---|---|
| Exterior | `SG_UF = ZZ`, 186 localidades (cidades no exterior com código TSE próprio), só Presidente | Sem geometria; entra no total nacional de presidente; painel próprio "Exterior" |
| Distrito Federal | 1 município TSE/IBGE (Brasília, 5300108), 19 zonas; cargo Deputado Distrital em vez de Estadual | Tratado como unidade única; não há malha "municipal" do DF além do próprio DF |
| Lagoa Mirim e Lagoa dos Patos | Polígonos 4300001 e 4300002 da malha ("Área Operacional") | Exibidos em cinza como "área sem eleitorado", nunca como zero votos |
| Voto em trânsito (`VT`) | Previsto no leiame, ausente em 2026 | Validação alerta se aparecer |
