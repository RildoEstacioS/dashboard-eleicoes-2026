# Geografia: malhas, junção e prova da biblioteca de mapas

## Edição territorial

**Malha Municipal 2025 do IBGE**, obtida no FTP oficial
(`geoftp.ibge.gov.br/.../municipio_2025/Brasil/BR_Municipios_2025.zip`,
Last-Modified 26/02/2026), SIRGAS 2000 (EPSG:4674), 5.573 polígonos: os
municípios e 2 áreas operacionais de lagoas no RS. Nenhuma contagem é fixada
no código; os números acima são resultado da execução.

Motivo de não usar a API de Malhas v3: o padrão da API não contém Boa Esperança
do Norte/MT, que tem votação em 2026, e o parâmetro `periodo` retornou HTTP 500
para 2023–2025 (testado em 28/10/2026).

## Processamento (`python -m scripts.preparar_dados geografia`)

1. Leitura e validação: `CD_MUN` com 7 dígitos e único; prefixo coerente com
   `CD_UF` e `CD_REGIAO`; CRS declarado; sem geometrias vazias.
2. Reprojeção para EPSG:4326 (exigido pelos mapas web; a diferença
   SIRGAS 2000 × WGS 84 é submétrica).
3. **Versão detalhada preservada**: `data/geo/municipios_detalhada.parquet`
   (20 milhões de vértices), para zoom local e expansões.
4. Simplificação topológica com `shapely.coverage_simplify` (GEOS 3.14).
   Fronteiras compartilhadas são simplificadas uma única vez, sem buracos nem
   sobreposições entre vizinhos.
   - Nacional: tolerância 0,02° (≈2,2 km) → 136 mil vértices,
     `municipios_brasil.geojson` 3,9 MB.
   - Por UF: tolerância 0,004° (≈450 m) → `uf/municipios_<UF>.geojson`
     (maior: MG, 2,1 MB).
5. UF e grandes regiões por **dissolução da malha municipal simplificada**
   (prefixo oficial do código IBGE). As bordas dos níveis coincidem
   exatamente. `ufs.geojson` 0,38 MB; `regioes.geojson` 0,24 MB.
6. GeoJSON com 4 casas decimais (≈11 m, abaixo do erro da simplificação) e só
   o identificador como propriedade. Nomes e atributos vêm de
   `data/processed/dim_municipio.parquet`.

### Calibração das tolerâncias (medida)

| Malha nacional | Arquivo | Figura Plotly (só id) | Serialização no servidor |
|---|---|---|---|
| 0,01°, 5 casas | 7,7 MB | 6,2 MB | 2,1 s |
| **0,02°, 4 casas (adotada)** | 4,4 MB → 3,9 MB sem atributos | 3,3 MB | 1,3 s |
| 0,04°, 4 casas | 3,0 MB | 2,2 MB | 1,0 s |

0,04° deforma municípios pequenos do litoral e do Sudeste e economiza pouco
(o custo é dominado pelo número de polígonos). Por isso a escolha foi 0,02°.

## Junção TSE–IBGE

Regra: `CD_MUNICIPIO` (TSE, normalizado para 5 dígitos) → tabela oficial
`municipio_tse_ibge` → `CD_MUNICIPIO_IBGE` → `CD_MUN` da malha, conferindo
`SG_UF`. Sem junção por nome e sem correspondência aproximada.

Resultado (`docs/relatorios/juncao_tse_ibge.md`):

| Estado | Territórios |
|---|---|
| associado | 5.571 |
| exterior (ZZ) | 186 |
| geometria sem votação (lagoas) | 2 |
| sem correspondência / UF divergente / sem geometria | 0 |

45 municípios têm grafia diferente entre o nome no arquivo de votação e o nome
na tabela de correspondência. Isso é só informativo, porque a junção é por código.

Estados de um território no mapa (para não confundir conceitos):

- **associado com votos** — valor numérico, inclusive zero votos para um candidato;
- **sem dado** — polígono sem eleitorado (lagoas), em cinza;
- **não aplicável** — disputa inexistente no recorte (ex.: UF sem 2º turno de
  governador), em cinza com legenda própria;
- **erro de associação** — hoje vazio; aparece no relatório de qualidade se surgir.

## Prova técnica da biblioteca de mapas

Protótipo: `prototipos/prova_mapa.py` (dado real: abstenção para presidente
por município, somando numeradores e denominadores das zonas).

| Requisito | Resultado |
|---|---|
| Renderização nacional (5.573 polígonos) | OK. Com a malha antiga de 6,9 MB, ≈3,2 s para desenhar no navegador (medido com o painel em segundo plano; pode ser menor em primeiro plano) |
| Hover | OK, com nome, UF, percentual, numerador e denominador |
| Seleção por clique | OK: `st.plotly_chart(on_select="rerun")` + `clickmode="event+select"` devolve `location` = código IBGE |
| Integração com filtros | OK: troca de turno e de UF recalcula via DuckDB (0,15–0,4 s com cache) |
| Bordas | Municipais finas e translúcidas; estaduais em traço escuro por cima, sem hover |
| Restaurar enquadramento | OK: centro/zoom calculados do bbox (`src/visualizacoes/enquadramento.py`) e `uirevision` renovado |
| Fundo claro/escuro | OK (`carto-positron` / `carto-darkmatter`, sem chave de API) |

**Limitação real.** O `st.plotly_chart` reenvia a figura inteira, com o
GeoJSON, a cada rerun que redesenha o mapa. Mitigações na Etapa 3:
`st.fragment` para isolar o mapa dos demais componentes, malha nacional enxuta
e níveis UF/região mais leves. Plotly continua viável e não há motivo para
trocar a biblioteca. `streamlit-folium` fica como alternativa documentada caso
o desempenho real se mostre insuficiente.

Ambiente da medição: Windows 11 Pro, 12 núcleos lógicos, Python 3.11.5,
Streamlit 1.66.1, Plotly 7.1.0 (plotly.js embutido no Streamlit 4.1.2),
navegador embutido do app Claude.
