# Desempenho

Medido com dados oficiais reais, sem cache do Streamlit, por
`python -m scripts.medir_desempenho` (resultado bruto em
`docs/relatorios/desempenho_etapa3.json`, regravado a cada execução).

**Ambiente:** Windows 11 Pro (10.0.26200), AMD64 Family 25 (12 núcleos lógicos),
Python 3.11.5, DuckDB 2.0.0, Plotly 7.1.0, Streamlit 1.66.1. Disco D: local.

## Servidor (mediana, 28/10/2026)

| Tela (mais votado, 1º turno) | Consultas DuckDB | Dados + figura | Figura enviada |
|---|---|---|---|
| Brasil por UF (27) | 0,02 s | 0,03 s | 0,02 MB |
| Municípios de SP (645) | 0,03 s | 0,06 s | 0,29 MB |
| Municípios de MG (853) | 0,03 s | 0,07 s | 0,39 MB |
| Brasil por município (5.571), tooltip completo | 0,06 s | 0,24 s | 2,49 MB |
| Brasil por município (5.571), tooltip compacto (usado no app) | 0,06 s | 0,20 s | 1,47 MB |

Malhas baixadas uma vez pelo navegador (cache HTTP): `ufs` 0,36 MB, `regioes`
0,24 MB, `municipios_brasil` 3,9 MB, municípios por UF até 2,1 MB (MG).

## Navegador

- Brasil por município, primeira abertura (inclui baixar a malha de 3,9 MB e
  desenhar 5.571 polígonos): mapa visível em ≈ 5 s, medido no navegador embutido
  do app Claude. Aberturas seguintes reaproveitam a malha em cache.
- Medições de renderização em segundo plano não são confiáveis (o navegador
  reduz a prioridade de abas ocultas); por isso não há mais números de cliente.

## Otimizações e histórico

| Mudança | Efeito medido |
|---|---|
| Malhas por URL estática em vez de embutidas em cada camada da figura | Figura de MG 4,35 MB → 0,39 MB |
| Camada "sem dado": conjunto de ids construído uma vez (era O(n²)) | MG 0,65 s → 0,07 s; Brasil por município > 26 s → 0,23 s |
| Simplificação topológica da malha (0,02° nacional, 0,004° por UF) | 20 milhões → 136 mil vértices no mapa nacional |
| Tooltip compacto no mapa nacional por município (sem 2º colocado e participação, que seguem nas tabelas) | Figura 2,49 MB → 1,47 MB |

## Otimizações possíveis

- Migrar os tooltips para `customdata` + `hovertemplate` (números em vez de texto pronto).
- `st.fragment` no mapa, para trocas de controles fora do mapa não o redesenharem.
