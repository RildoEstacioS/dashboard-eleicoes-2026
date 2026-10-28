"""G. Dados e metodologia — fontes, dicionário, regras, malhas, qualidade, limitações e download."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from paginas import comum
from src.aquisicao.fontes import EDICAO_MALHA
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.config import DIR_PROCESSED, DIR_RELATORIOS
from src.geografia import malhas
from src.metricas.indicadores import INDICADORES
from src.modelagem.dicionario import CAMPOS


def _md(nome: str) -> str:
    p = DIR_RELATORIOS / nome
    return p.read_text(encoding="utf-8") if p.exists() else f"_Relatório {nome} ainda não gerado._"


def render(ctx) -> None:
    st.markdown('<div class="cab"><span class="t">Dados e metodologia</span>'
                '<span class="s">fontes, regras de cálculo, qualidade e limitações</span></div>', unsafe_allow_html=True)
    abas = st.tabs(["Fontes", "Dicionário", "Regras de cálculo", "Malhas e junção", "Qualidade", "Limitações",
                    "Baixar dados"])

    with abas[0]:
        st.markdown(f"Dados oficiais do **TSE** (Portal de Dados Abertos) e malhas do **IBGE** ({EDICAO_MALHA}). "
                    "Os arquivos são baixados manualmente pelo script de preparação; o painel não consulta a internet "
                    "para dados e **não se atualiza em tempo real**.")
        m = dados.metadados()
        linhas = [{"Recurso": r.get("descricao", k), "Fonte": r.get("fonte"),
                   "Gerado pela fonte": r.get("dt_geracao_fonte", "—"),
                   "Last-Modified do servidor": r.get("last_modified_servidor", "—"),
                   "Baixado pelo painel": str(r.get("baixado_em", "—"))[:19].replace("T", " "),
                   "SHA-256": str(r.get("sha256", ""))[:16] + "…", "URL": r.get("url")} for k, r in m.items()]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True,
                     column_config={"URL": st.column_config.LinkColumn()})
        st.caption("Três datas distintas: geração informada pela fonte (dentro do arquivo), Last-Modified do servidor "
                   "e data em que este painel baixou o arquivo.")

    with abas[1]:
        st.dataframe(pd.DataFrame(CAMPOS, columns=["Campo", "Tabela", "Descrição", "Origem"]), hide_index=True,
                     use_container_width=True, height=visuais.altura_tabela(len(CAMPOS), 560))
        st.caption("Identificadores (códigos de município, SQ_CANDIDATO) são mantidos como texto. Marcadores do TSE "
                   "#NULO/#NE viram ausentes. Detalhes: docs/modelo_dados.md.")

    with abas[2]:
        st.markdown("""
- **% do candidato** = votos nominais válidos ÷ votos válidos do cargo no território. O denominador vem da apuração
  oficial e **não muda** ao filtrar candidatos ou partidos.
- **Agregações** (município → UF → região → Brasil): numeradores e denominadores são somados antes do percentual.
  Nunca média de percentuais.
- **Margem A × B** = 100 × (A − B) ÷ válidos do cargo. **Participação no par** = A ÷ (A + B) — exclui os demais.
- **Denominador zero** → sem percentual ("sem votos válidos"), nunca empate nem 0 %.
- **Mais votado no território** ≠ **eleito**: o eleito vem da situação oficial do TSE na circunscrição.
- **Deputados**: votos do partido = nominais + legenda; eleitos por quociente partidário (QP) e média, conforme a
  situação oficial; o painel **não recalcula cadeiras**.
- **Senado 2026**: duas vagas por UF e dois votos por eleitor; percentuais são de votos, não de eleitores.
- **Eleitorado depende do cargo**: presidente inclui o exterior e eleitores que só votam para presidente.
- **% oficial do TSE** nos relatórios de totalização usa votos concorrentes (válidos + anulados sub judice); difere do
  % sobre válidos só quando há votos sub judice.
- **1º × 2º turno**: comparação de agregados; não identifica comportamento individual (nenhuma transferência inferida).
""")
        st.markdown("**Indicadores de participação**")
        st.dataframe(pd.DataFrame([{"Indicador": i.rotulo, "Fórmula": i.formula, "Numerador": i.numerador,
                                    "Denominador": i.denominador, "Unidade": i.unidade, "Observação": i.nota}
                                   for i in INDICADORES.values()]), hide_index=True, use_container_width=True)

    with abas[3]:
        med_arq = DIR_RELATORIOS / "geografia_medicoes.json"
        med = json.loads(med_arq.read_text(encoding="utf-8")) if med_arq.exists() else {}
        from src.visualizacoes import formatos as fm
        st.markdown(f"""
**Edição da malha:** {EDICAO_MALHA} (FTP oficial do IBGE), SIRGAS 2000 reprojetado para WGS 84 para os mapas web.
{fm.inteiro(med.get('n_poligonos'))} polígonos (municípios + 2 áreas operacionais de lagoas no RS, mostradas como
"sem dado").

**Simplificação topológica** (`shapely.coverage_simplify`, fronteiras compartilhadas simplificadas uma vez):
nacional {fm.decimal(malhas.TOLERANCIA_NACIONAL, 3)}° (≈ 2 km) → {fm.inteiro(med.get('vertices_nacional'))} vértices;
por UF {fm.decimal(malhas.TOLERANCIA_UF, 3)}° (≈ 450 m). Versão detalhada preservada
({fm.inteiro(med.get('vertices_original'))} vértices). UFs e regiões vêm da dissolução da malha municipal (bordas
idênticas entre níveis). Coordenadas com {malhas.PRECISAO_COORD} casas decimais.

**Por que não a API de malhas do IBGE:** o padrão da API v3 não tinha Boa Esperança do Norte/MT (com votos em 2026)
e o parâmetro de período retornou erro para 2023–2025.
""")
        dim = pd.read_parquet(DIR_PROCESSED / "dim_municipio.parquet")
        st.markdown("**Correspondência TSE–IBGE** (por código, nunca por nome; sem correspondência aproximada)")
        st.dataframe(dim["ESTADO_JUNCAO"].value_counts().rename_axis("Estado").reset_index(name="Territórios"),
                     hide_index=True)
        st.caption("Exterior (ZZ): sem geometria municipal; agrupado por país com a tabela auxiliar "
                   "config/exterior_paises.csv.")
        with st.expander("Relatório completo da junção"):
            st.markdown(_md("juncao_tse_ibge.md"))

    with abas[4]:
        st.markdown("Relatórios gerados pelos scripts de preparação (`docs/relatorios/`).")
        for titulo, arq in (("Validação contra os relatórios oficiais de totalização (PDF)", "validacao_totalizacao.md"),
                            ("Identidades contábeis entre arquivos", "consistencia.md"),
                            ("Granularidade, chaves e casos especiais do modelo", "qualidade_modelo.md")):
            with st.expander(titulo):
                st.markdown(_md(arq))

    with abas[5]:
        st.markdown("""
- **Dados estáticos**: refletem os arquivos baixados (ver datas em Fontes); não há atualização em tempo real.
- **Exterior por país**: o TSE publica só a cidade; o país vem de uma tabela auxiliar do projeto, revisável.
- **Seções eleitorais**: o painel usa município/zona; detalhamento por seção não está incluído.
- **Mapa nacional por município**: só os 20 maiores municípios da UF (ou as siglas das UFs) têm nome escrito.
- **Cores**: até 3 candidatos com cor própria nos mapas (validação para daltonismo); deputados: até 8 partidos.
- **Enquadramento**: o Streamlit não informa a largura real da tela; em telas muito largas sobra margem no mapa.
- **Validação contra PDF oficial** executada para ES (todos os cargos) e Brasil (presidente); outras UFs podem ser
  validadas com `python -m scripts.preparar_dados validar <UF>`.
- **Candidatos sem nenhum voto registrado** (ex.: renúncia antes da urna) não aparecem nas listas.
""")

    with abas[6]:
        st.markdown("Dados do **recorte atual** (cargo, turno, nível e filtros da barra lateral).")
        if ctx.sel.uf == "ZZ":
            st.caption("Exterior: baixe as tabelas por país/cidade na Visão geral.")
        else:
            ap, _ = cmapa.dados_do_mapa(ctx)
            ap = ap.drop(columns=[c for c in ("CD_MUNICIPIO_TSE",) if c in ap.columns])
            st.dataframe(ap.head(50), hide_index=True, use_container_width=True)
            visuais.botao_csv(ap, f"apuracao_{ctx.sel.cargo}_{ctx.sel.turno}t_{ctx.sel.nivel}",
                              "⬇ Baixar apuração por território (CSV)")
        if ctx.sg_ue:
            cands = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, ctx.sel.turno)
            visuais.botao_csv(comum.ranking_escopo(ctx, cands).drop(columns=["ORDEM_ESTAVEL"], errors="ignore"),
                              f"candidatos_{ctx.sel.cargo}_{ctx.sel.turno}t", "⬇ Baixar candidatos do recorte (CSV)")
        st.caption("CSV com ponto e vírgula e vírgula decimal (abre direto no Excel em português).")
