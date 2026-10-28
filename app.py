"""Dashboard Eleições 2026 — ponto de entrada.

Executar (PowerShell, na raiz do projeto, venv ativo):
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Eleições 2026", page_icon="🗳️", layout="wide")

from paginas import comparacao, dados as pagina_dados, participacao, territorial, turnos, visao_geral  # noqa: E402
from src.componentes import dados_app, filtros, visuais  # noqa: E402

if not dados_app.pronto():
    st.error("Dados ainda não preparados.")
    st.markdown("Rode, na raiz do projeto, com o ambiente virtual ativo:")
    st.code("python -m scripts.preparar_dados baixar\n"
            "python -m scripts.preparar_dados auditar\n"
            "python -m scripts.preparar_dados geografia\n"
            "python -m scripts.preparar_dados modelar", language="powershell")
    st.stop()

visuais.estilos()
visuais.marca()
ctx = filtros.barra_lateral()

paginas = st.navigation([
    st.Page(lambda: visao_geral.render(ctx), title="Visão geral", icon="🗺️", url_path="visao-geral", default=True),
    st.Page(lambda: territorial.render(ctx), title="Análise territorial", icon="🧭", url_path="territorial"),
    st.Page(lambda: comparacao.render(ctx), title="Comparação A × B", icon="⚖️", url_path="comparacao"),
    st.Page(lambda: turnos.render(ctx), title="1º × 2º turno", icon="🔁", url_path="turnos"),
    st.Page(lambda: participacao.render(ctx), title="Participação", icon="🗳️", url_path="participacao"),
    st.Page(lambda: pagina_dados.render(ctx), title="Dados e metodologia", icon="📄", url_path="dados"),
])
paginas.run()
