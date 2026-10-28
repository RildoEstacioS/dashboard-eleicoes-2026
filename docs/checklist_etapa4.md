# Checklist de validação — Etapa 4

Roteiro manual com `streamlit run app.py`.

## Níveis de mapa
- [ ] **Brasil por região:** 5 regiões; hover com líder, votos, vantagem e denominador.
- [ ] Clicar numa região abre as UFs dela (filtro "Região" preenchido, chip "Região: …").
- [ ] Com região filtrada, KPIs e ranking mostram a região; "← Regiões" volta e limpa o filtro.
- [ ] **Brasil por UF** com região: só as UFs da região, enquadradas.
- [ ] **Municípios de uma UF**: sem UF, aviso para escolher; "← UFs" volta.
- [ ] **Brasil por município:** 5.571 municípios; divisas estaduais nítidas; cores sem
      "lavagem" pelas bordas; aparece em poucos segundos na primeira vez.
- [ ] No mapa nacional, clicar num município seleciona-o (contorno) e fixa a UF dele.
- [ ] Brasil por município + filtro de região: só os municípios da região.

## Totais
- [ ] Soma das regiões = Brasil sem exterior (1º turno: 118.969.906 válidos).
- [ ] KPIs do Brasil incluem o exterior (119.300.788); o rótulo diz "(inclui exterior)".

## Análise territorial
- [ ] Candidato e métrica (% válidos / votos) mudam mapa, rankings e tabela.
- [ ] Eleitorado mínimo altera só os rankings e informa quantos ficaram de fora.
- [ ] Clique numa linha da tabela: região → UFs; UF → municípios; município → seleção.
- [ ] "Baixar CSV" gera arquivo com `;` e vírgula decimal.
- [ ] Territórios sem votos válidos não entram nos rankings.

## Automático
- [ ] `python -m pytest` e `python -m pytest -m integracao` passam.
- [ ] `python -m scripts.medir_desempenho` registra os tempos dos quatro cenários.
