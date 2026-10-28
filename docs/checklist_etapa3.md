# Checklist de validação — Etapa 3

Roteiro manual com `streamlit run app.py`. Marque cada item.

## Visão geral
- [ ] Brasil por UF, 1º turno: 27 UFs preenchidas, nenhuma em branco.
- [ ] KPIs do Brasil: eleitorado apto 158.745.502; válidos 119.300.788 (1º turno).
- [ ] Selo do eleito: Lula (PT), 2º turno — vem da situação oficial, não do mapa.
- [ ] 2º turno: válidos 124.082.273; ranking com 2 candidatos.
- [ ] Hover numa UF: líder, votos, % dos válidos, 2º colocado, vantagem, denominador,
      comparecimento e abstenção.
- [ ] Clique numa UF abre os municípios; "← Brasil" volta.
- [ ] Clique num município: contorno grosso, KPIs/ranking do município; "Limpar seleção".
- [ ] Município pela busca na barra lateral produz o mesmo resultado.
- [ ] Trocar a UF descarta o município da UF anterior.
- [ ] Modo Candidato: escala na cor do candidato; "Votos" exibe o alerta de eleitorado.
- [ ] Intensidade opcional mostra o intervalo na legenda.
- [ ] Filtro de partido muda o ranking, mas não o "% sobre N válidos".
- [ ] Aba Exterior (nível Brasil): 186 localidades; votos incluídos no total do Brasil.
- [ ] "⟲ Enquadrar" volta ao enquadramento inicial após zoom/deslocamento.
- [ ] Bordas municipais brancas visíveis; bordas estaduais marinho por cima.

## Comparação A × B
- [ ] A e B só oferecem candidatos da disputa/turno; trocar de turno refaz a seleção.
- [ ] "⇄" inverte A e B.
- [ ] Cores dos candidatos (azul × vermelho) por padrão; pares alternativos funcionam.
- [ ] Margem p.p.: centro claro = empate; legenda "B +x / empate / A +x".
- [ ] Participação no par: aviso de que exclui os demais candidatos.
- [ ] KPIs separam contagem de territórios e votos; aviso "territórios ≠ votos".
- [ ] Território sem votos válidos aparece como "sem dado", não como empate.

## Dados e metodologia
- [ ] Tabela de recursos com datas de geração, download e SHA-256.
- [ ] Regras de cálculo e indicadores com fórmula e denominador.

## Automático
- [ ] `python -m pytest` e `python -m pytest -m integracao` passam.
- [ ] `python -m scripts.medir_desempenho` registra os tempos em `docs/relatorios/desempenho_etapa3.json`.
