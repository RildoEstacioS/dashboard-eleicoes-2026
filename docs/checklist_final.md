# Checklist final de verificação

Rode `streamlit run app.py` na raiz do projeto. Os roteiros detalhados anteriores
estão em `checklist_etapa3.md` e `checklist_etapa4.md`.

## Cargos e turnos
- [ ] Presidente: 1º e 2º turnos; selo "Eleito (TSE): Lula (PT) · 2º turno".
- [ ] Governador sem UF: visão nacional por partido; "Eleitos (resultado final)" com o turno no tooltip.
- [ ] Governador 2º turno sem UF: só AC, AM, DF, ES, RN, TO coloridas; demais em cinza "Não houve 2º turno".
- [ ] Governador em PE + 2º turno: aviso com "Ver primeiro turno em PE" e "Ver UFs com segundo turno".
- [ ] Senador: só 1º turno; avisos de 2 vagas/2 votos; 2 eleitos por UF.
- [ ] Deputados: eleitos na cor do partido (tons), não eleitos em cinza-claro; abas Partidos e Eleitos;
      eleitos = vagas (ex.: SP federal 70).
- [ ] Deputado Estadual não oferece DF; Deputado Distrital só DF.

## Mapas
- [ ] Quatro níveis (região, UF, municípios da UF, Brasil por município); cliques navegam entre eles.
- [ ] Fundo cartográfico visível; sem marca d'água; nomes do painel legíveis por cima das cores.
- [ ] ES e PE enquadrados sem puxar para as ilhas oceânicas.
- [ ] Brasil por município aparece em poucos segundos.

## Páginas
- [ ] Análise territorial: mapa do candidato, maiores/menores, tabela vinculada, CSV.
- [ ] Comparação A × B: escala divergente, KPIs, tabela completa com CSV; exige UF em cargos estaduais.
- [ ] 1º × 2º turno: presidente e governador (ES); mapas na mesma escala, variação em p.p., aviso sobre
      comportamento individual, CSV.
- [ ] Participação: indicador escolhido no mapa com fórmula e denominador; tabela comparativa com CSV.
- [ ] Exterior (filtro UF): mapa-múndi por país, tabela por país e por cidade.
- [ ] Dados e metodologia: sete abas, relatórios de qualidade abrem, downloads funcionam.

## Automático
- [ ] `python -m pytest` (51) e `python -m pytest -m integracao` (21) passam.
- [ ] `python -m scripts.medir_desempenho` grava docs/relatorios/desempenho_etapa3.json.
