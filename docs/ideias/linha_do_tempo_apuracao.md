# Ideia futura: linha do tempo da apuração

Estudo de viabilidade feito em 28/10/2026. Nada foi implementado no painel.

## Objetivo

Mostrar como a contagem avançou na noite da eleição: % de seções apuradas e % de
cada candidato ao longo do tempo, por cargo, turno e UF.

## Fonte encontrada

Pacote CKAN do TSE **`resultados-2026-boletim-de-urna`** ("Resultados - 2026 -
Boletim de Urna"), com um ZIP por UF e turno, além do hash SHA-512. Exemplo:

    https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_AC_051020261403.zip

O nome do arquivo traz data e hora de geração. Por isso as URLs devem ser lidas do
catálogo (`package_show`) e nunca montadas por padrão.

O CSV (`;`, latin-1, 45 colunas) traz uma linha por seção × cargo × votável. A
coluna que viabiliza a ideia é:

- **`DT_BU_RECEBIDO`**: data e hora em que o boletim da seção foi recebido pela
  Justiça Eleitoral.

Também há `DT_EMISSAO_BU`, `DT_ABERTURA`, `DT_ENCERRAMENTO`, `NR_ZONA`,
`NR_SECAO`, `CD_CARGO_PERGUNTA`, `NR_VOTAVEL` e `QT_VOTOS`.

## Verificação (AC, 1º turno)

| Checagem | Resultado |
|---|---|
| Linhas / seções | 258.052 linhas, 2.270 seções |
| `DT_BU_RECEBIDO` vazio | 0 |
| Horários distintos por seção | sempre 1 |
| Faixa de horários | 04/10 17:08:44 → 20:53:12 |
| Seções acumuladas | 35,0% até 18h · 91,5% até 19h · 98,2% até 20h · 100% até 21h |
| Soma dos votos de governador (BU × painel) | idêntica para os 6 candidatos (diferença 0) |

Conclusão: **é viável.** O horário vem sempre preenchido e a soma dos boletins
fecha com o resultado oficial que o painel já usa.

## Limitações a explicar na tela

- A curva é uma **reconstrução** pelo horário de recebimento de cada boletim, não
  uma cópia das telas oficiais de divulgação. A hora de recebimento é próxima da
  hora de totalização, mas não é a mesma.
- Seções que precisaram de apuração especial (urna substituída, voto em cédula)
  podem chegar depois. É preciso verificar os valores de `DS_TIPO_URNA` nas outras
  UFs, já que no AC todas as seções eram "Apurada".

## Custo

- ZIPs: cerca de **5,1 GB no 1º turno** (SP sozinho tem 1,4 GB) e 144 MB no 2º turno.
- O painel não precisa guardar isso tudo. Basta reduzir na preparação para
  "votos por cargo × votável × UF × minuto de recebimento", o que deve ocupar
  poucos MB em Parquet.
- Vale fazer como etapa **opcional** do `preparar_dados`, porque o download é grande.

## Pendência encontrada no catálogo

O recurso "RR - Boletim de Urna - Segundo turno" no CKAN aponta para o arquivo
`.zip.sha512`, e não para o `.zip`. É preciso tratar esse caso (ou avisar) quando
for implementar.

## Esboço da página

- Gráfico de linhas: % de cada candidato (sobre os válidos apurados até o momento) × horário.
- Linha ou faixa com o % de seções apuradas.
- Filtros: cargo, turno, UF. Para presidente, também Brasil.
- Marcadores de "virada" (quando o líder muda), se houver.
