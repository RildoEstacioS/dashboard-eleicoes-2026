# Relatório de junção TSE–IBGE

Gerado em 2026-10-28T04:11:55-03:00 por `python -m scripts.preparar_dados geografia`.

## Insumos

- Tabela de correspondência: `municipio_tse_ibge` (geração na fonte: 25/10/2026; baixada em 2026-10-28T02:23:40-03:00) — 5571 linhas.
- Municípios com votação: `detalhe_votacao_munzona_2026_BRASIL.csv` (geração na fonte: 27/10/2026 19:32:04).
- Malha: Malha Municipal 2025 (IBGE) — 5573 polígonos.

## Regra

Junção por `CD_MUNICIPIO` (TSE) → `CD_MUNICIPIO_TSE` da tabela oficial, com conferência de `SG_UF`; depois `CD_MUNICIPIO_IBGE` → `CD_MUN` da malha. Sem junção por nome e sem correspondência aproximada.

## Resultado

| estado | territórios |
|---|---|
| associado | 5571 |
| exterior | 186 |
| geometria_sem_votacao | 2 |

Problemas na tabela de correspondência: nenhum

## Territórios não associados ao mapa

| UF | cód. TSE | nome TSE | cód. IBGE | nome na malha | estado |
|---|---|---|---|---|---|
| — | — | — | 4300001 | Área Operacional "Lagoa Mirim" | geometria_sem_votacao |
| — | — | — | 4300002 | Área Operacional "Lagoa dos Patos" | geometria_sem_votacao |

Localidades no exterior (SG_UF = ZZ): 186. Não recebem geometria; entram nos totais nacionais de presidente e são exibidas em painel próprio.

## Nomes com grafia diferente (apenas informativo)

45 municípios associados por código têm nome TSE diferente do nome na tabela (maiúsculas/minúsculas já desconsideradas). Ver CSV completo de territórios em data/processed/dim_municipio.parquet.
