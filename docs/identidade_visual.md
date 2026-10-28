# Identidade visual e cores

## Marca do painel

| Papel | Cor | Uso |
|---|---|---|
| Marinho escuro | `#14213d` | barra lateral, faixa do cabeçalho, bordas estaduais |
| Marinho | `#1d3557` | cor primária dos controles, faixa dos KPIs, títulos de painel |
| Dourado | `#e0b84c` | acento: sublinhado do cabeçalho, aba ativa, selo do eleito |
| Fundo | `#eef1f5` | plano da página; painéis e KPIs em branco com sombra suave |

Configurada em `.streamlit/config.toml` (tema) e `src/componentes/visuais.py` (CSS).
As cores de marca não são usadas para dados.

## Cores dos dados (`src/visualizacoes/cores.py`)

Todas validadas com o validador de paletas, no critério "todos os pares" exigido
por mapas coropléticos: visão normal ΔE ≥ 15, protan/deutan ΔE ≥ 8.

- **Liderança:** até 3 cores por mapa. A cor segue o candidato (ordem do 1º turno
  da disputa), não a posição na tela. Do 4º em diante, "Outros" em cinza, com nome
  no tooltip e na tabela.
- **Cores de campanha por candidato** e **cores fixas por partido:** definidas pelo
  usuário em `config/cores_partidos.toml` (prioridade: candidato > partido > paleta;
  atualmente só PT = vermelho). O código não presume cores de campanha. Duas cores
  fixas indistinguíveis geram aviso no painel, e a segunda é trocada por uma da paleta. As demais cores são escolhidas automaticamente, com
  simulação de daltonismo, para ficarem distinguíveis da cor fixa. Resultado validado:
  - modo claro: azul `#2a78d6` + vermelho `#e34948` + ocre `#eda100`;
  - modo escuro: azul `#3987e5` + vermelho `#e66767` + verde `#008300`.
  O laranja padrão é excluído quando o vermelho está em uso (ΔE 7,1, indistinguível).
- **Modo Candidato:** escala de um só matiz com a cor do candidato no ranking
  (claro → cor → escurecida). O mínimo é tingido para não se confundir com "sem dado".
- **Comparação A × B:** por padrão, as cores dos próprios candidatos, se forem
  distinguíveis; senão, um dos pares validados (azul × laranja, azul × vermelho,
  violeta × verde-água). Centro neutro cinza.
- **Estados especiais:** sem dado = branco vazado com contorno cinza; empate =
  cinza-escuro; outros = cinza médio. Nenhum deles coincide com o centro neutro.

## Deputados (cargos proporcionais)

- Não eleitos (inclui suplentes): uma única cor neutra (`NAO_ELEITO`).
- Eleitos: cor do partido; eleitos do mesmo partido recebem tons diferentes
  (clareados/escurecidos da mesma cor). Partidos ordenados por nº de eleitos na UF.
- Paleta categórica completa (até 8 partidos); além disso, "outros partidos" em
  cinza-escuro, distinto do cinza-claro dos não eleitos. Contra cores fixas (PT
  vermelho) vale o critério de visão normal (ΔE ≥ 15), porque nome e partido estão
  sempre escritos nas barras e tabelas.

## Fundo e nomes no mapa

- Fundo `carto-positron` (claro) / `carto-darkmatter` (escuro), com países, mar e cidades.
  Os polígonos são inseridos acima de todas as camadas do fundo (`below=""`), então os
  rótulos do fundo ficam ocultos sob as cores e visíveis fora delas.
- Nomes desenhados pelo painel, em negrito marinho: regiões, siglas das UFs e os
  20 municípios de maior eleitorado da UF.
- Não usar estilos `*-nolabels` do Plotly nem tiles raster da CARTO pedidos direto:
  ambos vieram com marca d'água "API KEY REQUIRED".

## Bordas

Municipais em branco (0,8 px), visíveis sobre preenchimentos saturados; estaduais
em marinho (2 px) por cima, inclusive no mapa por UF; território selecionado com
contorno de 3,5 px.

## Ao mudar cores

1. Edite `config/cores_partidos.toml` (ou as paletas em `cores.py`).
2. Valide o conjunto resultante com o validador de paletas, modo `--pairs all`,
   claro e escuro.
3. Rode `python -m pytest`.
